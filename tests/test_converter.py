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
    def test_uses_exif_date_when_available(self, tmp_path: Path) -> None:
        dt = datetime(2024, 7, 14, 10, 30, 0)
        img = _make_image_mock()
        name, is_dup = build_output_filename(Path("IMG_001.HEIC"), img, dt, tmp_path, set())
        assert name == "2024-07-14_10-30-00.jpg"
        assert is_dup is False

    def test_uses_no_date_prefix_when_no_exif(self, tmp_path: Path) -> None:
        img = _make_image_mock()
        name, is_dup = build_output_filename(Path("IMG_001.HEIC"), img, None, tmp_path, set())
        assert name.startswith(f"{_NO_DATE_PREFIX}_")
        assert "IMG_001" in name
        assert name.endswith(".jpg")
        assert is_dup is False

    def test_resolves_collision_with_counter(self, tmp_path: Path) -> None:
        dt = datetime(2024, 7, 14, 10, 30, 0)
        existing = {"2024-07-14_10-30-00.jpg"}
        img = _make_image_mock()
        # Mock fingerprinting to make them look different
        with patch("photo_processing.heic_to_jpg.converter.get_image_fingerprint", side_effect=["hash1", "hash2"]):
            name, is_dup = build_output_filename(Path("IMG_002.HEIC"), img, dt, tmp_path, existing)
            assert name == "2024-07-14_10-30-00_1.jpg"
            assert is_dup is False

    def test_resolves_multiple_collisions(self, tmp_path: Path) -> None:
        dt = datetime(2024, 7, 14, 10, 30, 0)
        existing = {
            "2024-07-14_10-30-00.jpg",
            "2024-07-14_10-30-00_1.jpg",
            "2024-07-14_10-30-00_2.jpg",
        }
        img = _make_image_mock()
        with patch("photo_processing.heic_to_jpg.converter.get_image_fingerprint", return_value="a-new-hash"):
             name, is_dup = build_output_filename(Path("IMG_003.HEIC"), img, dt, tmp_path, existing)
             assert name == "2024-07-14_10-30-00_3.jpg"
             assert is_dup is False

    def test_skips_identical_file_in_target(self, tmp_path: Path) -> None:
        dt = datetime(2024, 7, 14, 10, 30, 0)
        target_name = "2024-07-14_10-30-00.jpg"
        existing = {target_name}
        
        # Create a physical file in tmp_path to satisfy .exists()
        (tmp_path / target_name).write_bytes(b"dummy")
        
        img = _make_image_mock()
        with patch("PIL.Image.open") as mock_open:
            mock_open.return_value.__enter__.return_value = _make_image_mock()
            with patch("photo_processing.heic_to_jpg.converter.get_image_fingerprint", return_value="same-hash"):
                name, is_dup = build_output_filename(Path("source.heic"), img, dt, tmp_path, existing)
                assert name == target_name
                assert is_dup is True



# ---------------------------------------------------------------------------
# process_directory (integration-style, filesystem mocked)
# ---------------------------------------------------------------------------

class TestProcessDirectory:
    def test_empty_source_directory(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        target = tmp_path / "target"

        successes, failures, skips = process_directory(source, target)

        assert successes == []
        assert failures == []
        assert skips == 0
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

        successes, failures, skips = process_directory(source, target)

        assert successes == []
        assert failures == []
        assert skips == 0

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
            successes, failures, skips = process_directory(source, target)

        assert successes == []
        assert len(failures) == 1
        assert skips == 0
        assert failures[0][0] == bad_file

    def test_detects_and_skips_duplicates(self, tmp_path: Path) -> None:
        source = tmp_path / "source"
        source.mkdir()
        (source / "img1.jpg").write_bytes(b"dummy")
        (source / "img2.jpg").write_bytes(b"dummy")
        target = tmp_path / "target"
        
        # Mock Image.open and fingerprinting
        with patch("PIL.Image.open") as mock_open:
            img_mock = _make_image_mock()
            mock_open.return_value.__enter__.return_value = img_mock
            
            with patch("photo_processing.heic_to_jpg.converter.get_image_fingerprint", return_value="constant-hash"):
                successes, failures, skips = process_directory(source, target)
                
                # Should only convert 1, skip 1
                assert len(successes) == 1
                assert skips == 1

