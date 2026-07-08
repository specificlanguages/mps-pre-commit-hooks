#!/usr/bin/env python3
#
# Banned model-name check.
#
# Reports model files (*.mps / .model) whose qualified name is one a project has
# chosen to forbid, passed with --ban. Matching is exact: banning `main@generator`
# catches a generator model left with MPS' default unqualified name but leaves a
# properly namespaced `foo.bar.main@generator` alone.

from __future__ import annotations

import argparse
import sys

from ._common import (
    AnchoredGlob,
    model_name,
    parse_xml,
    repo_root,
    selected_files,
)

# A model's name lives in the root <model> element's `ref`. .mps and .model headers
# carry it; a per-root .mpsr repeats its model's ref, so scanning it too would report
# the same model twice -- leave it out and every model is reported once, through its
# .mps or .model.
MODEL_GLOBS = [AnchoredGlob(f"**/*{ext}") for ext in (".mps", ".model")]


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mps-check-banned-model-names",
        description="Report MPS models whose name is one banned with --ban.",
    )
    parser.add_argument(
        "--ban",
        action="append",
        default=[],
        metavar="NAME",
        help="A model name to forbid, matched exactly against the full qualified "
        "name. Repeatable. E.g. --ban=main@generator catches a generator model "
        "left with MPS' default unqualified name.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Model files to check; defaults to every tracked *.mps / .model file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = repo_root()

    banned = set(args.ban)

    failed = False
    for model in selected_files(args.files, *MODEL_GLOBS):
        root_el = parse_xml(model)
        if root_el is None:
            continue
        name = model_name(root_el)
        if name is None or name not in banned:
            continue
        rel = model.relative_to(root).as_posix()
        print(f"{rel}: banned model name '{name}'")
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
