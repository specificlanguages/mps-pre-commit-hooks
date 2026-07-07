#!/usr/bin/env python3
#
# Build-membership check.
#
# Reports modules (*.msd / *.mpl / *.devkit) that ought to be packaged by a
# jetbrains.mps.build.mps build script but are not -- a module left out of the
# build ships nothing, so the omission is easy to miss until something downstream
# is empty.
#
# Only meaningful for projects that ship product modules through build scripts,
# so it is a no-op (passes) when the project has no such scripts. Modules that
# are deliberately not packaged -- sample applications, generated preference
# modules, the build scripts' own modules -- are exempted with --exclude.
#
# The companion mps-check-orphan-modules checks the other half of "is this module
# wired in": that it is registered in a .mps/modules.xml.

from __future__ import annotations

import argparse
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePath, PurePosixPath

from ._common import (
    FloatingGlob,
    MODULE_GLOBS,
    anchor,
    git_ls_files,
    matches,
    module_name,
    nearest_ancestor_in,
    parse_xml,
    repo_root,
)

# Build scripts are models written in this MPS language. Inside them, every
# packaged module is a node of one of the BuildMps_* concepts below, carrying
# the module name in the standard INamedConcept "name" property.
BUILD_LANGUAGE = "jetbrains.mps.build.mps"
NAMED_CONCEPT = "jetbrains.mps.lang.core.structure.INamedConcept"
BUILT_MODULE_CONCEPTS = (
    "jetbrains.mps.build.mps.structure.BuildMps_Solution",
    "jetbrains.mps.build.mps.structure.BuildMps_Language",
    "jetbrains.mps.build.mps.structure.BuildMps_DevKit",
)


def build_models(root: Path) -> list[Path]:
    """Tracked models written in the MPS build language, as absolute paths."""
    found = subprocess.run(
        ["git", "grep", "-l", BUILD_LANGUAGE, "--", "*.mps"],
        capture_output=True,
        text=True,
        cwd=root,
    ).stdout
    models = (PurePosixPath(line) for line in found.splitlines() if line)
    return [root / m for m in models if ".mps" not in m.parts]


def registry_index(root: ET.Element, concept: str, member: str | None = None) -> str | None:
    """Look the runtime index of a concept (or one of its members) up by name in
    a model's <registry>, rather than relying on a hard-coded index. MPS derives
    these indices deterministically, but resolving them through the registry is
    the correct way to read a model."""
    for declared in root.iter("concept"):
        if declared.get("name") != concept:
            continue
        if member is None:
            return declared.get("index")
        for child in declared:
            if child.get("name") == member:
                return child.get("index")
    return None


def built_module_names(models: list[Path]) -> set[str]:
    """Names of all modules packaged by any build script."""
    names: set[str] = set()
    for model in models:
        root = parse_xml(model)
        if root is None:
            continue
        name_role = registry_index(root, NAMED_CONCEPT, "name")
        module_concepts = {registry_index(root, c) for c in BUILT_MODULE_CONCEPTS}
        module_concepts.discard(None)
        if name_role is None or not module_concepts:
            continue
        for node in root.iter("node"):
            if node.get("concept") in module_concepts:
                for prop in node.findall("property"):
                    if prop.get("role") == name_role:
                        value = prop.get("value")
                        if value is not None:
                            names.add(value)
    return names


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mps-check-unbuilt-modules",
        description="Check that every shipped MPS module is packaged by a build script.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        type=FloatingGlob,
        help="Glob matching module paths (repo-relative) that are never expected "
        "to be packaged by a build script -- sample applications, generated "
        "preference modules, and the like. Written like a .gitignore pattern "
        "('*' stays within a path segment, '**' spans directories). "
        "Repeatable. E.g. "
        "--exclude='/code/applications/' --exclude='*_spreferences/'.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    root = repo_root()

    names: dict[Path, str] = {}
    for m in git_ls_files(*MODULE_GLOBS):
        descriptor = parse_xml(m)
        if descriptor is not None:
            names[m] = module_name(descriptor)
    module_homes: dict[PurePath, str] = {m.parent: name for m, name in names.items()}

    build_model_paths = build_models(root)
    if not build_model_paths:
        # No build scripts in this project; nothing to check.
        return 0

    built = built_module_names(build_model_paths)
    # A build script's own module is itself never packaged, so it is exempt.
    build_script_modules = {
        module_homes[home]
        for model in build_model_paths
        for home in [nearest_ancestor_in(model, module_homes)]
        if home is not None
    }

    excludes = [anchor(g) for g in args.exclude]

    def excluded(path: Path) -> bool:
        # --exclude globs float by default; anchor() resolves them, then match
        # against the repo-relative path. subtree=True lets a bare directory name
        # exclude everything under it, as a .gitignore entry would.
        return matches(path.relative_to(root).as_posix(), *excludes, subtree=True)

    failed = False
    for module, name in names.items():
        if excluded(module) or name in build_script_modules or name in built:
            continue
        rel = module.relative_to(root).as_posix()
        print(f"{rel}: module '{name}' not packaged by any build script")
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
