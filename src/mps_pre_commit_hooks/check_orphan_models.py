#
# Model-root membership check.
#
# Every model file (*.mps / *.mpsr / .model) must live under a source root of some
# default model root; one that does not is invisible to MPS -- present on disk but
# never loaded -- usually a move that didn't update the owning module, or a stray copy.
#
# Model files that are known to be orphans can be skipped with --exclude.

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ._common import (
    MODEL_GLOBS,
    MODULE_GLOBS,
    FloatingGlob,
    anchor,
    default_model_root_dirs,
    git_ls_files,
    matches,
    nearest_ancestor_in,
    parse_xml,
    repo_root,
)


def model_roots(root: Path) -> set[Path]:
    """The source-root directories of every default model root across all module files.

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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mps-check-orphan-models",
        description="Check that every MPS model file lives under a default model root.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        type=FloatingGlob,
        help="Glob matching model file paths (repo-relative) that are not "
        "checked. Written like a .gitignore pattern ('*' stays within a path "
        "segment, '**' spans directories, a trailing '/' excludes a subtree). "
        "Repeatable. E.g. --exclude='some.lang/generator/template/main@generator.mps'.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    root = repo_root()

    roots = model_roots(root)
    excludes = [anchor(g) for g in args.exclude]

    # .mps/ holds project configuration, not models; skip it as the other checks do.
    failed = False
    for model in git_ls_files(*MODEL_GLOBS):
        if ".mps" in model.parts:
            continue
        if matches(model.relative_to(root).as_posix(), *excludes, subtree=True):
            continue
        if nearest_ancestor_in(model, roots) is None:
            print(f"{model.relative_to(root).as_posix()}: model file outside any default model root's source roots")
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
