#!/usr/bin/env python3
#
# Dangling module-registration check.
#
# Every <modulePath> entry in a .mps/modules.xml must point at a file that exists on disk. A dangling entry -- typically
# left behind when a module is moved or deleted -- makes MPS fail to open the project. This is the reverse of the
# registration check in mps-check-orphan-modules, which reports descriptors present on disk but absent from modules.xml.
#
# This hook reports any such entry and, with --fix, removes it from its modules.xml. The removal is line-based, so the
# rest of the file keeps its formatting, the same way mps-fix-path-variables rewrites in place.
#
# Entries addressed through a project-specific path variable other than $PROJECT_DIR$ are skipped, since their value is
# unknown here.

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from ._common import MODULES_XML_GLOBS, git_ls_files, repo_root

# A <modulePath> element with its path attribute captured. Used to drop the
# matching line on --fix; MPS writes one entry per line.
MODULE_PATH = re.compile(r'<modulePath\b[^>]*\bpath="([^"]*)"')


def dangling_paths(modules_xml: Path) -> list[str]:
    """Raw modulePath values in this file pointing to missing files."""
    project_dir = modules_xml.parent.parent
    root = ET.parse(modules_xml).getroot()
    dangling = []
    for module_path in root.iter("modulePath"):
        raw = module_path.get("path", "")
        if raw.startswith("$PROJECT_DIR$/"):
            relative = raw[len("$PROJECT_DIR$/") :]
            resolved = Path(project_dir, relative)
        elif raw.startswith("${"):
            # A project-specific path variable whose value is unknown here.
            continue
        else:
            resolved = Path(project_dir, raw)
        if not resolved.is_file():
            dangling.append(raw)
    return dangling


def remove_entries(modules_xml: Path, dangling: set[str]) -> bool:
    """Drop every <modulePath> line whose path is in `dangling`, in place.
    Returns whether the file changed."""
    with open(modules_xml, encoding="utf-8") as handle:
        original = handle.readlines()
    kept = []
    for line in original:
        match = MODULE_PATH.search(line)
        if match and match.group(1) in dangling:
            continue
        kept.append(line)
    if kept == original:
        return False
    with open(modules_xml, "w", encoding="utf-8") as handle:
        handle.writelines(kept)
    return True


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mps-check-missing-modules",
        description="Report (and optionally remove) .mps/modules.xml entries that point at a file that does not exist on disk.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Remove each dangling <modulePath> entry from its modules.xml.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = repo_root()

    failed = False
    for modules_xml in git_ls_files(*MODULES_XML_GLOBS):
        dangling = dangling_paths(modules_xml)
        if not dangling:
            continue
        failed = True
        rel = modules_xml.relative_to(root).as_posix()
        if args.fix:
            remove_entries(modules_xml, set(dangling))
            for raw in dangling:
                print(f"{rel}: removed dangling modulePath entry: {raw}")
        else:
            for raw in dangling:
                print(f"{rel}: modulePath entry points at a missing file: {raw}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
