#!/usr/bin/env python3
#
# Module naming-consistency check.
#
# An MPS module's name must agree with how it is laid out on disk, or the
# project becomes confusing to navigate and some tooling stops finding it. This
# hook reports, for every tracked module descriptor (*.msd / *.mpl / *.devkit / *.mpst):
#
#   1. A descriptor file whose name differs from the module name. The file must
#      be named after the full module name -- com.example.foo -> com.example.foo.mpl.
#   2. A descriptor whose containing directory differs from the module name. The
#      directory must likewise be named after the full module name. With the
#      corresponding opt-in flag, a language module may contain a nested runtime
#      or sandbox module: foo.bar.runtime can be stored as
#      foo.bar/runtime/foo.bar.runtime.msd, and foo.bar.sandbox as
#      foo.bar/sandbox/foo.bar.sandbox.msd. The language directory is recognized
#      by the presence of a .mpl descriptor directly inside it.
#
# Generated modules whose layout is fixed and unrelated to the module name (e.g.
# MPS' per-project preference modules) won't satisfy either rule; exclude them
# with --exclude, passing a glob that matches their descriptor paths.

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._common import (
    MODULE_GLOBS,
    FloatingGlob,
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
        "--allow-nested-runtime",
        action="store_true",
        help="Allow foo.bar.runtime to be stored as foo.bar/runtime/foo.bar.runtime.msd when foo.bar is a language module.",
    )
    parser.add_argument(
        "--allow-nested-sandbox",
        action="store_true",
        help="Allow foo.bar.sandbox to be stored as foo.bar/sandbox/foo.bar.sandbox.msd when foo.bar is a language module.",
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

    def allowed_nested_role(module: Path, name: str) -> bool:
        roles = {
            "runtime": args.allow_nested_runtime,
            "sandbox": args.allow_nested_sandbox,
        }
        role = module.parent.name
        language_dir = module.parent.parent
        return (
            module.suffix == ".msd"
            and roles.get(role, False)
            and name == f"{language_dir.name}.{role}"
            and module.stem == name
            and any(language_dir.glob("*.mpl"))
        )

    failed = False
    for module in selected_files(args.files, *MODULE_GLOBS):
        rel = module.relative_to(root).as_posix()
        if matches(rel, *excludes, subtree=True):
            continue

        descriptor = parse_xml(module)
        if descriptor is None:
            continue
        name = module_name(descriptor)
        nested_role_allowed = allowed_nested_role(module, name)

        suggestions = []
        if module.parent.name != name and not nested_role_allowed:
            suggestions.append(f"in directory '{name}'")
        if module.stem != name and not nested_role_allowed:
            suggestions.append(f"named '{name}{module.suffix}'")

        if not suggestions:
            continue

        failed = True
        print(f"{rel}: should be {' and '.join(suggestions)}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
