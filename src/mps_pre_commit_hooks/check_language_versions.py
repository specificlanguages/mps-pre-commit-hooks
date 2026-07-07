#!/usr/bin/env python3
#
# Negative language-version check.
#
# Reports model files (*.mps / .model) whose <languages> header uses a language
# with version="-1". MPS writes -1 when it saves a model while the used
# language's version is unknown -- typically because the language module was not
# on the path at save time. The model still loads, but the missing version is a
# latent inconsistency that resurfaces as spurious diffs or migration problems
# the next time the language is available, so it should not be committed.

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET

from ._common import (
    AnchoredGlob,
    repo_root,
    selected_files,
)

# Only .mps and .model models carry a <languages> header with versioned uses;
# .mpsr root files do not, so they are deliberately left out.
MODEL_GLOBS = [AnchoredGlob(f"**/*{ext}") for ext in (".mps", ".model")]


def unversioned_languages(model_root: ET.Element) -> list[str]:
    """Names of the languages used with version="-1" in the model's <languages>
    header, in document order."""
    names = []
    for use in model_root.findall("languages/use"):
        if use.get("version") == "-1":
            names.append(use.get("name") or use.get("id") or "?")
    return names


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mps-check-language-versions",
        description='Report MPS models that use a language with version="-1".',
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

    failed = False
    for model in selected_files(args.files, *MODEL_GLOBS):
        names = unversioned_languages(ET.parse(model).getroot())
        if not names:
            continue
        rel = model.relative_to(root).as_posix()
        print(f"{rel}: uses language with version -1: {', '.join(names)}")
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
