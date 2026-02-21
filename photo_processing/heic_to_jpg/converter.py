"""
Core logic for converting HEIC/HEIF (and other image formats) to JPEG,
with chronological renaming based on EXIF metadata.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pillow_heif
from PIL import Image, ExifTags

logger = logging.getLogger(__name__)

# Supported source extensions (case-insensitive).
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".heic", ".heif", ".jpg", ".jpeg", ".png"}
)

# EXIF tag IDs used for date extraction, in priority order.
# 36867 = DateTimeOriginal (when the shutter was pressed)
# 36868 = DateTimeDigitized
# 306   = DateTime (file modification time – fallback)
_EXIF_DATE_TAG_IDS: tuple[int, ...] = (36867, 36868, 306)

# EXIF date format as specified by the EXIF standard.
_EXIF_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"

# Output filename date format – filesystem-safe.
_FILENAME_DATE_FORMAT = "%Y-%m-%d_%H-%M-%S"

_NO_DATE_PREFIX = "NO-DATE"


def _register_heif_opener() -> None:
    """Register the pillow-heif opener with Pillow (idempotent)."""
    pillow_heif.register_heif_opener()


def extract_exif_datetime(image: Image.Image) -> Optional[datetime]:
    """Return the best available capture datetime from EXIF data, or *None*.

    Priority:
    1. ``DateTimeOriginal`` (tag 36867)
    2. ``DateTimeDigitized`` (tag 36868)
    3. ``DateTime`` (tag 306)

    Args:
        image: An open :class:`PIL.Image.Image` instance.

    Returns:
        A :class:`datetime` object when a parseable date was found, else *None*.
    """
    try:
        exif = image.getexif()
        if not exif:
            return None

        for tag_id in _EXIF_DATE_TAG_IDS:
            raw = exif.get(tag_id)
            if raw:
                try:
                    return datetime.strptime(raw.strip(), _EXIF_DATE_FORMAT)
                except ValueError:
                    logger.debug("Could not parse EXIF date %r for tag %d.", raw, tag_id)

    except Exception:
        logger.debug("Failed to read EXIF data.", exc_info=True)

    return None


def build_output_filename(
    source_path: Path,
    capture_dt: Optional[datetime],
    existing_names: set[str],
) -> str:
    """Build a unique, filesystem-safe JPEG filename.

    When a capture datetime is available, the filename follows the pattern::

        YYYY-MM-DD_HH-MM-SS.jpg

    When no date is available the original stem is kept with a prefix::

        NO-DATE_<original-stem>.jpg

    If the candidate name already exists in *existing_names*, a numeric suffix
    is appended (``…_1.jpg``, ``…_2.jpg``, …) until a unique name is found.

    Args:
        source_path: Path of the source image (used as fallback stem).
        capture_dt: Parsed capture datetime, or *None*.
        existing_names: Set of filenames already reserved in the target directory.

    Returns:
        A unique filename string (including the ``.jpg`` extension).
    """
    if capture_dt:
        base = capture_dt.strftime(_FILENAME_DATE_FORMAT)
    else:
        base = f"{_NO_DATE_PREFIX}_{source_path.stem}"

    candidate = f"{base}.jpg"
    counter = 1
    while candidate in existing_names:
        candidate = f"{base}_{counter}.jpg"
        counter += 1

    return candidate


def convert_image(
    source_path: Path,
    target_dir: Path,
    existing_names: set[str],
    quality: int = 95,
) -> Path:
    """Convert a single image file to JPEG with a chronological filename.

    The converted file is saved into *target_dir*. EXIF metadata is preserved
    when available. The image is always converted to the ``RGB`` colour space
    before saving (required for HEIC and some PNG files).

    Args:
        source_path: Absolute path to the source image.
        target_dir: Absolute path to the output directory (must already exist).
        existing_names: Mutable set of filename strings already used in
            *target_dir*; updated in-place when a new file is written.
        quality: JPEG quality (1–95). Defaults to 95.

    Returns:
        The :class:`Path` of the newly created JPEG file.

    Raises:
        OSError: If the file cannot be opened or written.
    """
    with Image.open(source_path) as img:
        capture_dt = extract_exif_datetime(img)
        exif_bytes: Optional[bytes] = img.info.get("exif")

        output_name = build_output_filename(source_path, capture_dt, existing_names)
        existing_names.add(output_name)

        target_path = target_dir / output_name

        rgb_img = img.convert("RGB")
        save_kwargs: dict = {"quality": quality, "optimize": True}
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes

        rgb_img.save(target_path, "JPEG", **save_kwargs)

    return target_path


def process_directory(
    source_dir: Path,
    target_dir: Path,
    quality: int = 95,
) -> tuple[list[Path], list[tuple[Path, Exception]]]:
    """Convert all supported images in *source_dir* and save them to *target_dir*.

    Args:
        source_dir: Directory containing source images.
        target_dir: Output directory (created automatically if absent).
        quality: JPEG quality passed to each conversion. Defaults to 95.

    Returns:
        A two-element tuple of ``(successes, failures)`` where:

        - ``successes`` – list of :class:`Path` objects for written files.
        - ``failures``  – list of ``(source_path, exception)`` pairs.
    """
    _register_heif_opener()
    target_dir.mkdir(parents=True, exist_ok=True)

    source_files = [
        f for f in source_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    logger.info("Found %d supported file(s) in '%s'.", len(source_files), source_dir)

    # Pre-populate reserved names from files already present in target_dir.
    existing_names: set[str] = {
        f.name for f in target_dir.iterdir() if f.is_file()
    }

    successes: list[Path] = []
    failures: list[tuple[Path, Exception]] = []

    for source_path in source_files:
        try:
            output_path = convert_image(source_path, target_dir, existing_names, quality)
            logger.info("Converted: %s  →  %s", source_path.name, output_path.name)
            successes.append(output_path)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to convert '%s': %s", source_path.name, exc)
            failures.append((source_path, exc))

    logger.info(
        "Done. %d converted, %d failed.", len(successes), len(failures)
    )
    return successes, failures
