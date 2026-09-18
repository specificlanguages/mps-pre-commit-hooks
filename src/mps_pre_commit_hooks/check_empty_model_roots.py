"""Report default model roots that contain no tracked models."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterable
from pathlib import Path

from ._common import (
    MODEL_GLOBS,
    MODULE_GLOBS,
    FloatingGlob,
    anchor,
    default_model_root_dirs,
    git_ls_files,
    matches,
    parse_xml,
    repo_root,
)


def display_path(path: Path, root: Path) -> str:
    """Render repository paths relatively and external paths absolutely."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def ancestor_directories(paths: Iterable[Path]) -> set[Path]:
    """All directories containing at least one of the given paths."""
    return {directory for path in paths for directory in path.parents}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mps-check-empty-model-roots",
        description="Report default model roots that contain no tracked models.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        type=FloatingGlob,
        help="Glob matching module descriptor paths (repo-relative) whose model roots should be skipped, written "
        "like a .gitignore pattern ('*' stays within a path segment, '**' spans directories). Repeatable. "
        "E.g. --exclude='sandbox/'.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = repo_root()
    models = [model for model in git_ls_files(*MODEL_GLOBS) if ".mps" not in model.parts]
    directories_with_models = ancestor_directories(models)
    excludes = [anchor(glob) for glob in args.exclude]

    failed = False
    for module in git_ls_files(*MODULE_GLOBS):
        module_path = module.relative_to(root).as_posix()
        if matches(module_path, *excludes, subtree=True):
            continue
        descriptor = parse_xml(module)
        if descriptor is None:
            continue
        for model_root in descriptor.iter("modelRoot"):
            if model_root.get("type") != "default":
                continue
            directories = tuple(default_model_root_dirs(model_root, module.parent, root))
            if any(directory in directories_with_models for directory in directories):
                continue

            if directories:
                source_roots = ", ".join(display_path(directory, root) for directory in directories)
                print(f"{module_path}: default model root has no models under its source roots: {source_roots}")
            else:
                print(f"{module_path}: default model root has no source roots and no models")
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
