"""Tests for photo_processing.heic_to_jpg.converter."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from photo_processing.heic_to_jpg.converter import (
    _FILENAME_DATE_FORMAT,
    _NO_DATE_PREFIX,
    build_output_filename,
    extract_exif_datetime,
    process_directory,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_image_mock(exif_data: dict[int, str] | None = None) -> MagicMock:
    """Return a :class:`MagicMock` that mimics a :class:`PIL.Image.Image`."""
    img = MagicMock()
    if exif_data is not None:
        # getexif() should return a dict-like object
        img.getexif.return_value = exif_data
    else:
        img.getexif.return_value = {}
    img.info = {}
    return img


# ---------------------------------------------------------------------------
# extract_exif_datetime
# ---------------------------------------------------------------------------

class TestExtractExifDatetime:
    def test_returns_none_when_no_exif(self) -> None:
        img = _make_image_mock(exif_data={})
        assert extract_exif_datetime(img) is None

    def test_prefers_date_time_original(self) -> None:
        img = _make_image_mock(
            exif_data={
                36867: "2024:07:14 10:30:00",  # DateTimeOriginal
                36868: "2024:07:14 11:00:00",  # DateTimeDigitized
                306:   "2024:07:14 12:00:00",  # DateTime
            }
        )
        result = extract_exif_datetime(img)
        assert result == datetime(2024, 7, 14, 10, 30, 0)

    def test_falls_back_to_date_time_digitized(self) -> None:
        img = _make_image_mock(
            exif_data={
                36868: "2024:08:20 08:15:00",
                306:   "2024:08:20 09:00:00",
            }
        )
        result = extract_exif_datetime(img)
        assert result == datetime(2024, 8, 20, 8, 15, 0)

    def test_falls_back_to_date_time(self) -> None:
        img = _make_image_mock(exif_data={306: "2023:12:31 23:59:59"})
        result = extract_exif_datetime(img)
        assert result == datetime(2023, 12, 31, 23, 59, 59)

    def test_returns_none_on_invalid_date_string(self) -> None:
        img = _make_image_mock(exif_data={36867: "not-a-date"})
        assert extract_exif_datetime(img) is None

    def test_returns_none_when_getexif_raises(self) -> None:
        img = MagicMock()
        img.getexif.side_effect = Exception("No EXIF block")
        assert extract_exif_datetime(img) is None


# ---------------------------------------------------------------------------
# build_output_filename
# ---------------------------------------------------------------------------

class TestBuildOutputFilename:
    def test_uses_exif_date_when_available(self) -> None:
        dt = datetime(2024, 7, 14, 10, 30, 0)
        name = build_output_filename(Path("IMG_001.HEIC"), dt, set())
        assert name == "2024-07-14_10-30-00.jpg"

    def test_uses_no_date_prefix_when_no_exif(self) -> None:
        name = build_output_filename(Path("IMG_001.HEIC"), None, set())
        assert name.startswith(f"{_NO_DATE_PREFIX}_")
        assert "IMG_001" in name
        assert name.endswith(".jpg")

    def test_resolves_collision_with_counter(self) -> None:
        dt = datetime(2024, 7, 14, 10, 30, 0)
        existing = {"2024-07-14_10-30-00.jpg"}
        name = build_output_filename(Path("IMG_002.HEIC"), dt, existing)
        assert name == "2024-07-14_10-30-00_1.jpg"

    def test_resolves_multiple_collisions(self) -> None:
        dt = datetime(2024, 7, 14, 10, 30, 0)
        existing = {
            "2024-07-14_10-30-00.jpg",
            "2024-07-14_10-30-00_1.jpg",
            "2024-07-14_10-30-00_2.jpg",
        }
        name = build_output_filename(Path("IMG_003.HEIC"), dt, existing)
        assert name == "2024-07-14_10-30-00_3.jpg"

    def test_unique_name_not_in_existing(self) -> None:
        dt = datetime(2025, 1, 1, 0, 0, 0)
        existing: set[str] = set()
        name = build_output_filename(Path("shot.heic"), dt, existing)
        assert name not in existing  # existence check before mutation

    def test_no_date_collision_uses_counter(self) -> None:
        existing = {f"{_NO_DATE_PREFIX}_shot.jpg"}
        name = build_output_filename(Path("shot.heic"), None, existing)
        assert name == f"{_NO_DATE_PREFIX}_shot_1.jpg"


# ---------------------------------------------------------------------------
# process_directory (integration-style, filesystem mocked)
# ---------------------------------------------------------------------------

class TestProcessDirectory:
    def test_empty_source_directory(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "target"

        successes, failures = process_directory(source, target)

        assert successes == []
        assert failures == []
        assert target.is_dir()

    def test_target_directory_is_created(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "nested" / "target"

        process_directory(source, target)

        assert target.is_dir()

    def test_unsupported_files_are_skipped(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "document.pdf").write_bytes(b"fake-pdf")
        (source / "notes.txt").write_bytes(b"hello")
        target = tmp_path / "target"

        successes, failures = process_directory(source, target)

        assert successes == []
        assert failures == []

    def test_failed_conversion_reported(self, tmp_path: Path) -> None:
        """A corrupt image should land in the failures list, not raise."""
        source = tmp_path / "source"
        source.mkdir()
        bad_file = source / "corrupt.heic"
        bad_file.write_bytes(b"not-an-image")
        target = tmp_path / "target"

        with patch(
            "photo_processing.heic_to_jpg.converter._register_heif_opener"
        ):
            successes, failures = process_directory(source, target)

        assert successes == []
        assert len(failures) == 1
        assert failures[0][0] == bad_file
