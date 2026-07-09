#!/usr/bin/env python3
#
# Language-version checks for MPS models.
#
# Two problems are reported, both in a model's <languages> header:
#
# 1. Negative version. A <use> with version="-1" is a language whose version was
#    unknown when the model was saved -- typically because the language module was
#    not on the path at save time. The model still loads, but the missing version
#    is a latent inconsistency that resurfaces as spurious diffs or migration
#    problems the next time the language is available.
#
# 2. Model/module disagreement. A language may be used by a model with one version
#    while the module that owns the model records a different version for the same
#    language in its descriptor's <languageVersions>. MPS logs this at load time
#    ("Migration assistant detected inconsistency in language versions", see
#    ModuleDependencyVersions.checkModelVersionsAreValid). MPS only logs it; that
#    method makes no change, and MPS changes a model's language version only by
#    running the actual migration, which migrates the node content along with the
#    number. So the mismatch is reported here rather than patched by rewriting a
#    version, which would move the number without the content migration.

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from ._common import (
    MODULE_GLOBS,
    AnchoredGlob,
    default_model_root_dirs,
    git_ls_files,
    matches,
    module_name,
    nearest_ancestor_in,
    parse_xml,
    repo_root,
)

# Only .mps and .model models carry a <languages> header with versioned uses;
# .mpsr root files do not, so they are deliberately left out.
MODEL_GLOBS = [AnchoredGlob(f"**/*{ext}") for ext in (".mps", ".model")]


class Use(NamedTuple):
    """A language used by a model: its UUID, display name, and imported version
    (None when the <use> carries no version attribute)."""

    id: str
    name: str
    version: int | None


class Owner(NamedTuple):
    """The module (or embedded generator) a model belongs to. `versions` maps a
    language UUID to the version the module records for it in its descriptor's
    <languageVersions>; `name` and `descriptor` identify the module for reporting."""

    name: str
    descriptor: str
    versions: dict[str, int]


def used_languages(model_root: ET.Element) -> list[Use]:
    """The languages the model's <languages> header uses, in document order."""
    uses = []
    for use in model_root.findall("languages/use"):
        version = use.get("version")
        uses.append(
            Use(
                use.get("id") or "",
                use.get("name") or use.get("id") or "?",
                int(version) if version is not None else None,
            )
        )
    return uses


def declared_versions(element: ET.Element) -> dict[str, int]:
    """The language versions a descriptor or generator element records, mapping
    each language's UUID to its version. The <language> `slang` reads `l:<uuid>:<name>`,
    so the UUID is its middle, colon-separated field."""
    versions = {}
    for language in element.findall("languageVersions/language"):
        slang = language.get("slang", "")
        version = language.get("version")
        parts = slang.split(":")
        if len(parts) >= 2 and version is not None:
            versions[parts[1]] = int(version)
    return versions


def model_owners(root: Path) -> dict[Path, Owner]:
    """Map each default-model-root source directory to its owning module. A module's
    own model roots take the module's recorded versions; an embedded generator's
    roots take the generator's own <languageVersions>, since a generator is a
    separate module with its own imports."""
    owners: dict[Path, Owner] = {}
    for module in git_ls_files(*MODULE_GLOBS):
        descriptor = parse_xml(module)
        if descriptor is None:
            continue
        module_dir = module.parent
        rel = module.relative_to(root).as_posix()
        name = module_name(descriptor)
        module_owner = Owner(name, rel, declared_versions(descriptor))
        _record(owners, descriptor.findall("models/modelRoot"), module_owner, module_dir, root)
        for generator in descriptor.findall("generators/generator"):
            generator_owner = Owner(name, rel, declared_versions(generator))
            _record(owners, generator.findall("models/modelRoot"), generator_owner, module_dir, root)
    return owners


def _record(
    owners: dict[Path, Owner],
    model_roots: list[ET.Element],
    owner: Owner,
    module_dir: Path,
    root: Path,
) -> None:
    for model_root in model_roots:
        for directory in default_model_root_dirs(model_root, module_dir, root):
            owners[directory] = owner


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mps-check-language-versions",
        description="Report MPS models that use a language with version -1, or with a "
        "version that disagrees with the owning module's recorded version.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Model and module files to check; defaults to every tracked *.mps / .model "
        "file. A passed module file is expanded to the models it owns, so a version bump "
        "in a descriptor is checked against its models even when no model file changed.",
    )
    return parser.parse_args(argv)


def models_to_check(passed: list[str], root: Path, owners: dict[Path, Owner]) -> list[Path]:
    """The models a run should check, as absolute paths. With no files passed, every
    tracked model. Otherwise every passed model, plus every model owned by a passed
    module -- since the consistency check reads both sides, a changed descriptor has
    to re-check its models even when none of them changed."""
    if not passed:
        return git_ls_files(*MODEL_GLOBS)
    # dict rather than set to keep order stable and deterministic across runs.
    selected: dict[Path, None] = {}
    for path in passed:
        if matches(path, *MODEL_GLOBS):
            selected[root / PurePosixPath(path)] = None
    passed_modules = {path for path in passed if matches(path, *MODULE_GLOBS)}
    if passed_modules:
        for model in git_ls_files(*MODEL_GLOBS):
            source_root = nearest_ancestor_in(model, owners)
            if source_root is not None and owners[Path(source_root)].descriptor in passed_modules:
                selected[model] = None
    return list(selected)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])
    root = repo_root()
    owners = model_owners(root)

    failed = False
    for model in models_to_check(args.files, root, owners):
        root_el = parse_xml(model)
        if root_el is None:
            continue
        rel = model.relative_to(root).as_posix()
        uses = used_languages(root_el)

        unversioned = [use.name for use in uses if use.version == -1]
        if unversioned:
            print(f"{rel}: uses language with version -1: {', '.join(unversioned)}")
            failed = True

        source_root = nearest_ancestor_in(model, owners)
        if source_root is None:
            # A model outside every known source root has no owning module to
            # compare against; that a model is orphaned is another check's concern.
            continue
        owner = owners[Path(source_root)]
        for use in uses:
            # -1 is reported above; a version-less <use> has nothing to compare.
            if use.version is None or use.version == -1:
                continue
            module_version = owner.versions.get(use.id)
            # A language the module records no version for cannot disagree -- MPS
            # skips it the same way (currentVersion == null).
            if module_version is None or module_version == use.version:
                continue
            print(
                f"{rel}: uses language {use.name} with version {use.version}, "
                f"but module {owner.name} records version {module_version}"
            )
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
