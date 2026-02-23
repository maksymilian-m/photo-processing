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


def get_image_fingerprint(image: Image.Image) -> str:
    """Generate a stable fingerprint for an image based on its pixels.

    This uses a simplified 'average hash' algorithm:
    1. Convert to grayscale.
    2. Resize to 8x8.
    3. Calculate average brightness.
    4. Generate a bit-string based on whether each pixel is above/below average.

    This fingerprint is robust against different image formats and JPEG
    compression levels, making it ideal for detecting duplicates.

    Returns:
        A 64-character string of '0's and '1's.
    """
    # Resize to 8x8 and convert to grayscale ('L')
    reduced = image.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
    pixels = list(reduced.getdata())
    avg = sum(pixels) / 64
    return "".join("1" if p > avg else "0" for p in pixels)


def build_output_filename(
    source_path: Path,
    image: Image.Image,
    capture_dt: Optional[datetime],
    target_dir: Path,
    existing_names: set[str],
) -> tuple[str, bool]:
    """Build a unique, filesystem-safe JPEG filename and check for duplicates.

    If a filename collision occurs, the 'fingerprint' of the source image is
    compared against the existing file. If they match, the image is considered
    a duplicate and is skipped.

    Args:
        source_path: Path of the source image.
        image: The open PIL Image object.
        capture_dt: Parsed capture datetime, or *None*.
        target_dir: The output directory.
        existing_names: Set of filenames already reserved in the target directory.

    Returns:
        A tuple of (filename, is_duplicate).
    """
    if capture_dt:
        base = capture_dt.strftime(_FILENAME_DATE_FORMAT)
    else:
        base = f"{_NO_DATE_PREFIX}_{source_path.stem}"

    candidate = f"{base}.jpg"
    
    # Check if a file with this name already exists and if it's the same photo
    fingerprint = None
    counter = 1
    
    while candidate in existing_names:
        existing_file = target_dir / candidate
        if existing_file.exists():
            if fingerprint is None:
                fingerprint = get_image_fingerprint(image)
            
            try:
                with Image.open(existing_file) as other:
                    if get_image_fingerprint(other) == fingerprint:
                        return candidate, True
            except Exception:
                logger.debug("Could not open existing file %s for comparison.", candidate)
        
        # If it's a different photo with the same timestamp, try a suffix
        candidate = f"{base}_{counter}.jpg"
        counter += 1

    return candidate, False



def convert_image(
    source_path: Path,
    target_dir: Path,
    existing_names: set[str],
    seen_fingerprints: set[str],
    quality: int = 95,
) -> Path | None:
    """Convert a single image file to JPEG with a chronological filename.

    Checks for duplicates both against the target directory and files
    processed during the current run.

    Returns:
        The Path of the written file, or None if skipped as a duplicate.
    """
    with Image.open(source_path) as img:
        capture_dt = extract_exif_datetime(img)
        
        output_name, is_duplicate = build_output_filename(
            source_path, img, capture_dt, target_dir, existing_names
        )
        
        if is_duplicate:
            logger.info("Skipping duplicate: %s (matches %s)", source_path.name, output_name)
            return None

        # Even if name is unique, check if we've seen this content in this run
        fingerprint = get_image_fingerprint(img)
        if fingerprint in seen_fingerprints:
            logger.info("Skipping duplicate content: %s", source_path.name)
            return None
            
        seen_fingerprints.add(fingerprint)
        existing_names.add(output_name)

        target_path = target_dir / output_name
        rgb_img = img.convert("RGB")
        
        exif_bytes: Optional[bytes] = img.info.get("exif")
        save_kwargs: dict = {"quality": quality, "optimize": True}
        if exif_bytes:
            save_kwargs["exif"] = exif_bytes

        rgb_img.save(target_path, "JPEG", **save_kwargs)

    return target_path


def process_directory(
    source_dir: Path,
    target_dir: Path,
    quality: int = 95,
) -> tuple[list[Path], list[tuple[Path, Exception]], int]:
    """Convert all supported images in *source_dir* and save them to *target_dir*.

    Returns:
        A three-element tuple of (successes, failures, skips).
    """
    _register_heif_opener()
    target_dir.mkdir(parents=True, exist_ok=True)

    source_files = sorted([
        f for f in source_dir.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
    ])

    logger.info("Found %d supported file(s) in '%s'.", len(source_files), source_dir)

    existing_names: set[str] = {
        f.name for f in target_dir.iterdir() if f.is_file()
    }
    seen_fingerprints: set[str] = set()

    successes: list[Path] = []
    failures: list[tuple[Path, Exception]] = []
    skips: int = 0

    for source_path in source_files:
        try:
            output_path = convert_image(
                source_path, target_dir, existing_names, seen_fingerprints, quality
            )
            if output_path:
                logger.info("Converted: %s  →  %s", source_path.name, output_path.name)
                successes.append(output_path)
            else:
                skips += 1
        except Exception as exc:
            logger.error("Failed to convert '%s': %s", source_path.name, exc)
            failures.append((source_path, exc))

    logger.info(
        "Done. %d converted, %d skipped, %d failed.", 
        len(successes), skips, len(failures)
    )
    return successes, failures, skips

