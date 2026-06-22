#!/usr/bin/env python3
#
# Path-variable check for MPS .mps/libraries.xml and .mps/modules.xml.
#
# MPS can address a library or a registered module through an IntelliJ path
# variable -- a ${...} macro whose value lives in the user's per-machine IDE
# settings. A checkout that doesn't have the variable configured then can't
# resolve the reference, so these paths should be written relative to
# $PROJECT_DIR$ (the directory that contains the .mps folder) instead.
#
# This hook reports any such macro and, with --fix, rewrites it. The fix assumes
# the macro's value is the repository root and re-expresses the whole path
# relative to $PROJECT_DIR$:
#
#     ${mbeddr.github.core.home}/code/platform/com.mbeddr.doc
#  -> $PROJECT_DIR$/../../platform/com.mbeddr.doc
#
# That assumption -- macro == repo root -- holds for the common case of a
# variable that just points at the project's own checkout, but NOT for a
# variable that points somewhere outside the repository. Review the result;
# see the README caveat.
#
# $PROJECT_DIR$ itself has no braces, so it is never reported.

from __future__ import annotations

import argparse
import posixpath
import re
import sys

from ._common import (
    LIBRARIES_XML_GLOBS,
    MODULES_XML_GLOBS,
    repo_root,
    selected_files,
)

PATH_VAR_FILES = LIBRARIES_XML_GLOBS + MODULES_XML_GLOBS

# A ${...} macro together with the path that immediately follows it, up to the
# enclosing quote/angle bracket. The captured suffix is the part the macro
# prefixes (usually starting with "/").
MACRO = re.compile(r"\$\{[^}]*\}([^\"'<>\s]*)")


def rewrite(line: str, project_dir: str) -> str:
    """Replace every path variable on `line` with a $PROJECT_DIR$-relative path,
    assuming the variable resolves to the repository root."""

    def replace(match: re.Match[str]) -> str:
        # The macro stands in for the repo root, so the path that follows it is
        # already repo-relative; re-express it relative to the project directory.
        target = match.group(1).lstrip("/") or "."
        relative = posixpath.relpath(target, project_dir)
        return "$PROJECT_DIR$" if relative == "." else "$PROJECT_DIR$/" + relative

    return MACRO.sub(replace, line)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mps-check-path-variables",
        description="Report (and optionally fix) path variables in MPS .mps/libraries.xml and .mps/modules.xml files.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Rewrite each path variable as a $PROJECT_DIR$-relative path, "
        "assuming the variable resolves to the repository root.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Files to check; defaults to every tracked libraries.xml / modules.xml.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = repo_root()

    failed = False
    for xml_file in selected_files(args.files, *PATH_VAR_FILES):
        rel = xml_file.relative_to(root).as_posix()
        # rewrite() works in repo-relative POSIX space, so express the project
        # directory relative to the repo root.
        project_dir = xml_file.parent.parent.relative_to(root).as_posix()
        with open(xml_file, encoding="utf-8") as handle:
            original = handle.readlines()
        updated = list(original)
        for index, line in enumerate(original):
            if "${" not in line:
                continue
            failed = True
            lineno = index + 1
            if args.fix:
                fixed = rewrite(line, project_dir)
                updated[index] = fixed
                print(f"{rel}:{lineno}: rewrote path variable: {line.strip()} -> {fixed.strip()}")
            else:
                print(f"{rel}:{lineno}: path variable (use $PROJECT_DIR$ instead): {line.strip()}")
        if args.fix and updated != original:
            with open(xml_file, "w", encoding="utf-8") as handle:
                handle.writelines(updated)

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
