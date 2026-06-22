#!/usr/bin/env python3
#
# Zero-sized XML check.
#
# Reports tracked MPS XML files that are zero bytes: model files (*.mps / *.mpsr /
# .model), module descriptors (*.msd / *.mpl / *.devkit), and the per-project
# .mps/modules.xml and .mps/libraries.xml. A zero-byte file here is almost always
# the result of a botched save, merge, or checkout: MPS won't load it, and it
# silently drops whatever the file was meant to hold. Meant to run as a
# pre-commit hook (or on CI).

from __future__ import annotations

import argparse
import sys
from pathlib import Path, PurePosixPath

from ._common import (
    LIBRARIES_XML_GLOBS,
    MODEL_GLOBS,
    MODULE_GLOBS,
    MODULES_XML_GLOBS,
    git_ls_files,
    matches,
    repo_root,
)

# Per-project configuration files worth checking. The rest of .mps/ is transient
# state, so model and descriptor pathspecs deliberately skip anything under it.
CONFIG_GLOBS = MODULES_XML_GLOBS + LIBRARIES_XML_GLOBS


def is_candidate(rel: PurePosixPath) -> bool:
    """Whether `rel` (a repo-relative path) is one of the MPS XML files whose
    emptiness would break the project: a model or descriptor outside .mps/, or
    one of the two config files inside it (at any depth, including the repo
    root). The rest of .mps/ is transient and skipped."""
    if matches(rel, *CONFIG_GLOBS):
        return True
    if ".mps" in rel.parts:
        return False
    return matches(rel, *MODEL_GLOBS, *MODULE_GLOBS)


def candidates(passed: list[str], root: Path) -> list[Path]:
    """The files to check, as absolute paths: those pre-commit passed, restricted
    to candidates, or every tracked candidate when none were passed."""
    if passed:
        relatives = [PurePosixPath(p) for p in passed]
    else:
        relatives = [
            PurePosixPath(p.relative_to(root).as_posix())
            for p in git_ls_files(*MODEL_GLOBS, *MODULE_GLOBS, *CONFIG_GLOBS)
        ]
    chosen = [rel for rel in dict.fromkeys(relatives) if is_candidate(rel)]
    return [root / rel for rel in chosen]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mps-check-zero-sized-xmls",
        description="Report tracked MPS XML files that are zero bytes.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Files to check; defaults to every tracked MPS XML file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = repo_root()

    failed = False
    for path in candidates(args.files, root):
        if path.stat().st_size == 0:
            print(f"{path.relative_to(root).as_posix()}: zero-sized file")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
