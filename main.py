"""
photo-processing – top-level entry point.

Each tool has its own CLI registered in pyproject.toml under [project.scripts].
This file is kept for direct `python main.py` invocation during development.

Usage:
    python main.py heic-to-jpg <source> <target> [options]
"""

from __future__ import annotations

import sys


def main() -> None:
    tools = {
        "heic-to-jpg": "photo_processing.heic_to_jpg.cli",
    }

    if len(sys.argv) < 2 or sys.argv[1] not in tools:
        print("Available tools:", ", ".join(tools))
        print("Usage: python main.py <tool> [args...]")
        sys.exit(1)

    tool_name = sys.argv.pop(1)
    module_path = tools[tool_name]

    import importlib
    module = importlib.import_module(module_path)
    sys.exit(module.main())


if __name__ == "__main__":
    main()
