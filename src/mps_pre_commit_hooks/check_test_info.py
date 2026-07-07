#!/usr/bin/env python3
#
# TestInfo ban.
#
# Reports model files (*.mps / *.mpsr) whose <registry> instantiates the
# jetbrains.mps.lang.test TestInfo concept. Matching is by language and concept
# id, not name, since names are cosmetic.

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET

from ._common import (
    AnchoredGlob,
    repo_root,
    selected_files,
)

# Only .mps and .mpsr root files carry a <registry>; .model header files do not.
MODEL_GLOBS = [AnchoredGlob(f"**/*{ext}") for ext in (".mps", ".mpsr")]

# jetbrains.mps.lang.test / TestInfo, keyed by the ids MPS writes into the
# registry. Names alongside them are cosmetic and deliberately not matched.
TEST_LANGUAGE_ID = "8585453e-6bfb-4d80-98de-b16074f1d86c"
TEST_INFO_CONCEPT_ID = "5097124989038916362"


def has_test_info(model_root: ET.Element) -> bool:
    """Whether the model's <registry> declares the TestInfo concept -- which it
    does exactly when the model instantiates at least one TestInfo node."""
    for language in model_root.findall("registry/language"):
        if language.get("id") != TEST_LANGUAGE_ID:
            continue
        for concept in language.findall("concept"):
            if concept.get("id") == TEST_INFO_CONCEPT_ID:
                return True
    return False


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mps-check-no-test-info",
        description="Report MPS models that instantiate the TestInfo concept.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Model files to check; defaults to every tracked *.mps / *.mpsr file.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = repo_root()

    failed = False
    for model in selected_files(args.files, *MODEL_GLOBS):
        if not has_test_info(ET.parse(model).getroot()):
            continue
        rel = model.relative_to(root).as_posix()
        print(f"{rel}: contains a banned TestInfo node")
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
