"""Command-line interface for the HEIC-to-JPG converter."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from photo_processing.heic_to_jpg.converter import process_directory


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
        level=level,
        stream=sys.stdout,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="heic-to-jpg",
        description=(
            "Convert HEIC/HEIF (and other formats) to JPEG with chronological "
            "filenames derived from EXIF metadata."
        ),
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Source directory containing images to convert.",
    )
    parser.add_argument(
        "target",
        type=Path,
        help="Target directory where converted JPEGs will be saved.",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=95,
        metavar="1-95",
        help="JPEG quality (default: 95).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable debug-level logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ``heic-to-jpg`` CLI command.

    Args:
        argv: Argument list (defaults to :data:`sys.argv`).

    Returns:
        Exit code: ``0`` on full success, ``1`` if any conversions failed.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    _configure_logging(args.verbose)
    logger = logging.getLogger(__name__)

    source_dir: Path = args.source
    target_dir: Path = args.target

    if not source_dir.is_dir():
        logger.error("Source path '%s' is not a directory or does not exist.", source_dir)
        return 1

    successes, failures, skips = process_directory(source_dir, target_dir, quality=args.quality)

    if failures:
        logger.warning("%d file(s) could not be converted.", len(failures))
        return 1
    
    if skips:
        logger.info("%d file(s) were skipped as duplicates.", skips)


    return 0


if __name__ == "__main__":
    sys.exit(main())
