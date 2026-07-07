#!/usr/bin/env python3
#
# Module naming-consistency check.
#
# An MPS module's name must agree with how it is laid out on disk, or the
# project becomes confusing to navigate and some tooling stops finding it. This
# hook reports, for every tracked module descriptor (*.msd / *.mpl / *.devkit):
#
#   1. A descriptor file whose name differs from the module name. The file must
#      be named after the full module name -- com.example.foo -> com.example.foo.mpl.
#   2. A descriptor whose containing directory differs from the module name. The
#      directory must likewise be named after the full module name, except a
#      nested role sub-module (a runtime/ or sandbox/ folder inside another
#      module) may use the name's last segment as the role folder.
#
# Generated modules whose layout is fixed and unrelated to the module name (e.g.
# MPS' per-project preference modules) won't satisfy either rule; exclude them
# with --exclude, passing a glob that matches their descriptor paths.

from __future__ import annotations

import argparse
import sys

from ._common import (
    FloatingGlob,
    MODULE_GLOBS,
    anchor,
    matches,
    module_name,
    parse_xml,
    repo_root,
    selected_files,
)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mps-check-module-naming",
        description="Check that each MPS module's name agrees with its descriptor file name and containing directory.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        type=FloatingGlob,
        help="Glob matching descriptor file paths (repo-relative) to skip, written "
        "like a .gitignore pattern ('*' stays within a path segment, '**' "
        "spans directories). Repeatable. Use it to exempt generated modules "
        "whose layout is fixed, e.g. MPS preference modules: "
        "--exclude='*_spreferences/'.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Module descriptor files to check; defaults to every tracked one.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    root = repo_root()

    excludes = [anchor(g) for g in args.exclude]

    failed = False
    for module in selected_files(args.files, *MODULE_GLOBS):
        rel = module.relative_to(root).as_posix()
        if matches(rel, *excludes, subtree=True):
            continue

        descriptor = parse_xml(module)
        if descriptor is None:
            continue
        name = module_name(descriptor)

        suggestions = []
        if module.parent.name != name:
            suggestions.append(f"in directory '{name}'")
        if module.stem != name:
            suggestions.append(f"named '{name}{module.suffix}'")

        if not suggestions:
            continue

        failed = True
        print(f"{rel}: should be {' and '.join(suggestions)}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
