# photo-processing

A local-first Python utility toolset for **photo manipulation and automation**.
Built with `uv`, clean code principles, and designed to be easily extended with new tools over time.

## Tools

| Tool | Description | Docs |
|---|---|---|
| `heic-to-jpg` | Converts HEIC/HEIF photos to JPEG with chronological renaming from EXIF data | [→ docs](docs/chronological_converter.md) |

## Quick Start

```bash
# Install dependencies
uv sync

# Run the HEIC-to-JPG converter
uv run heic-to-jpg <source_dir> <target_dir>

# Example
uv run heic-to-jpg ./photos_from_cloud ./photos_output

# With options
uv run heic-to-jpg ./photos_from_cloud ./photos_output --quality 90 --verbose
```

## Running Tests

```bash
uv run pytest
```

## Project Structure

```
photo-processing/
├── photo_processing/
│   └── heic_to_jpg/
│       ├── converter.py   # Core logic (importable as a library)
│       └── cli.py         # Command-line entry point
├── tests/
│   └── test_converter.py
├── docs/
│   └── chronological_converter.md
└── pyproject.toml
```

## Adding New Tools

Each new tool gets its own sub-package under `photo_processing/` (e.g. `photo_processing/resize/`),
with a matching entry point in `pyproject.toml` and documentation in `docs/`.

## Requirements

- Python ≥ 3.13
- [`uv`](https://docs.astral.sh/uv/) for dependency management
