#!/usr/bin/env python3
#
# Model-root membership check.
#
# Every MPS model file (*.mps / *.mpsr / .model) must live inside a directory
# declared as a default model root by some module descriptor. A model outside any
# model root is invisible to MPS -- present on disk but never loaded -- usually
# the result of a move that didn't update the owning module, or a stray copy.

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from ._common import (
    MODEL_GLOBS,
    MODULE_GLOBS,
    git_ls_files,
    nearest_ancestor_in,
    repo_root,
)


def model_roots(root: Path) -> set[Path]:
    """Directories declared as default model roots across all module files."""
    roots: set[Path] = set()
    for module in git_ls_files(*MODULE_GLOBS):
        module_dir = module.parent
        descriptor = ET.parse(module).getroot()
        for model_root in descriptor.iter("modelRoot"):
            if model_root.get("type") != "default":
                continue
            content_path = model_root.get("contentPath", "").replace("${module}", str(module_dir))
            for source_root in model_root.findall("sourceRoot"):
                # Two persistence formats: a "location" relative to contentPath,
                # or an older "path" that spells out the ${module} macro itself.
                location = source_root.get("location")
                path = source_root.get("path")
                if location is not None:
                    directory = Path(content_path, location)
                elif path is not None:
                    directory = Path(path.replace("${module}", str(module_dir)))
                else:
                    continue
                # A path without ${module} is taken relative to the repo root;
                # an absolute directory keeps itself. normpath collapses '..'
                # lexically so the entry matches the path git reports for a model.
                roots.add(Path(os.path.normpath(root / directory)))
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
