# Chronological HEIC-to-JPG Converter

## Overview

The `heic-to-jpg` tool converts photos in **HEIC/HEIF** format (as exported from iPhone/iOS) — as well as standard **JPEG** and **PNG** files — into JPEG images. The key feature is automatic **chronological renaming** and **smart deduplication**: each output file is named after the exact moment the photo was taken, and identical photos (even if stored in different formats) are automatically identified and skipped to ensure only unique images end up in your collection.

This makes it trivial to sort a large batch of photos by capture time, merge photos from multiple sources into a single timeline, and import them into any photo management software or album without worrying about duplicates.

---

## Naming Convention & Deduplication

Output filenames follow this pattern:

```
YYYY-MM-DD_HH-MM-SS.jpg
```

### Examples

| Source file | EXIF Date | Status | Output filename |
|---|---|---|---|
| `IMG_4821.HEIC` | `2024:07:14 10:30:00` | New | `2024-07-14_10-30-00.jpg` |
| `IMG_4821_copy.JPG`| `2024:07:14 10:30:00` | **Duplicate** | *(Skipped)* |
| `Burst_01.HEIC` | `2024:07:14 10:30:00` | Different photo | `2024-07-14_10-30-00_1.jpg` |
| `IMG_4823.PNG` | *(none)* | New | `NO-DATE_IMG_4823.jpg` |

### Smart Collision Handling

If two photos share the same capture second (burst photos, for example), the tool performs a **content fingerprinting** check:
1. It calculates an "average hash" (fingerprint) of the new image.
2. It compares it against the fingerprint of any existing file with that name in the target directory.
3. If the fingerprints match, the new photo is **skipped** as a duplicate.
4. If they differ, a numeric suffix is appended (`_1`, `_2`, …) to keep both photos.

This approach ensures your target folder remains clean and free of identical images, even if you re-run the processing multiple times or have overlapping source backups.

### No-Date Fallback

When no parseable EXIF date is found, the filename is prefixed with `NO-DATE_` followed by the original file stem. These files are easy to identify and handle manually.

---

## EXIF Data Handling

### Date Extraction Priority

The tool reads the following EXIF tags **in order of priority**:

| Priority | Tag ID | Tag Name | Meaning |
|---|---|---|---|
| 1st | `36867` | `DateTimeOriginal` | When the shutter was pressed |
| 2nd | `36868` | `DateTimeDigitized` | When the image was digitised |
| 3rd | `306` | `DateTime` | File modification/write time |

The first tag that contains a parseable value is used. This hierarchy ensures the most accurate timestamp is always preferred.

### Metadata Preservation

The original EXIF byte block is forwarded to the output JPEG unchanged. Camera model, GPS coordinates, aperture, ISO, and all other embedded metadata are preserved as-is.

---

## Usage

### Command Line

```bash
# Basic usage
uv run heic-to-jpg <source_dir> <target_dir>

# With custom JPEG quality (default: 95)
uv run heic-to-jpg ./from_iphone ./album --quality 85

# Verbose output (shows DEBUG logs)
uv run heic-to-jpg ./from_iphone ./album --verbose
```

### Programmatic (Library) Usage

The converter can also be imported directly into other Python scripts:

```python
from pathlib import Path
from photo_processing.heic_to_jpg.converter import process_directory

source = Path("/path/to/source")
target = Path("/path/to/output")

successes, failures = process_directory(source, target, quality=95)

print(f"Converted: {len(successes)}, Failed: {len(failures)}")
```

---

## Supported Input Formats

| Extension | Format |
|---|---|
| `.heic`, `.heif` | HEIC/HEIF (iPhone, Apple devices) |
| `.jpg`, `.jpeg` | JPEG |
| `.png` | PNG |

---

## Technical Notes

- All images are converted to the **RGB colour space** before saving. This is required because HEIC and PNG files may use RGBA or other colour spaces incompatible with JPEG.
- The tool scans only the **top level** of the source directory (non-recursive by default).
- Target directory is **created automatically** if it does not exist.
- Files already present in the target directory are accounted for in collision resolution — rerunning the tool on the same target is safe.
