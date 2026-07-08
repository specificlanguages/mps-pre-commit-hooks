#!/usr/bin/env python3
#
# Model-root membership check.
#
# Every MPS model file (*.mps / *.mpsr / .model) must live inside a directory
# declared as a default model root by some module descriptor. A model outside any
# model root is invisible to MPS -- present on disk but never loaded -- usually
# the result of a move that didn't update the owning module, or a stray copy.

from __future__ import annotations

import sys
from pathlib import Path

from ._common import (
    MODEL_GLOBS,
    MODULE_GLOBS,
    default_model_root_dirs,
    git_ls_files,
    nearest_ancestor_in,
    parse_xml,
    repo_root,
)


def model_roots(root: Path) -> set[Path]:
    """Directories declared as default model roots across all module files.

    `iter` reaches every modelRoot, including those a language's embedded
    generators declare -- membership is all this check needs, so it does not
    matter which module owns each root."""
    roots: set[Path] = set()
    for module in git_ls_files(*MODULE_GLOBS):
        descriptor = parse_xml(module)
        if descriptor is None:
            continue
        for model_root in descriptor.iter("modelRoot"):
            roots.update(default_model_root_dirs(model_root, module.parent, root))
    return roots


def main() -> int:
    root = repo_root()

    roots = model_roots(root)

    # .mps/ holds project configuration, not models; skip it as the other checks do.
    failed = False
    for model in git_ls_files(*MODEL_GLOBS):
        if ".mps" in model.parts:
            continue
        if nearest_ancestor_in(model, roots) is None:
            print(f"{model.relative_to(root).as_posix()}: model file outside any module's model root")
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
