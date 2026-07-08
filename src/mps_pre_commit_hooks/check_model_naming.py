#!/usr/bin/env python3
#
# Model naming-consistency check.
#
# A model's name and the module it belongs to should agree with how it is stored,
# or the project becomes confusing to navigate. This reports two kinds of mismatch,
# depending on where a tracked model file (*.mps / .model) lives:
#
# 1. A model stored in a source root of a solution's or language's own default model
#    root must have a file name that matches its name. Relative to that source root,
#    a model `foo.bar.baz.quux` in a module `foo.bar` may be stored as:
#
#      foo.bar.baz.quux.mps        the full name
#      baz.quux.mps                the full name with the module name truncated
#      foo/bar/baz/quux.mps        the full name, each segment its own directory
#      baz/quux.mps                truncated, each segment its own directory
#
#    and any mix of dot- and directory-separated segments. Truncation removes the
#    whole owning module name and nothing less. A per-root model is a directory of
#    the same name holding a `.model` header, so the rules apply to that directory.
#    A `@stereotype` suffix (e.g. `@tests`) is part of the name and so of the file
#    name: `foo` and `foo@tests` are different models, kept in different files.
#
# 2. A model in a language's embedded generator instead only has its name checked:
#    it must be namespaced under the owning language. This catches a template model
#    that is a leftover from another language, or one left with a non-unique name
#    like `main@generator`. The file layout of generator models is not checked --
#    the generator/template folder makes it unpredictable, and the generator's own
#    declared namespace is unreliable (legacy `#id` forms), so the language
#    namespace is what a generator model is measured against.

from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import NamedTuple

from ._common import (
    MODULE_GLOBS,
    AnchoredGlob,
    default_model_root_dirs,
    git_ls_files,
    model_name,
    module_name,
    nearest_ancestor_in,
    parse_xml,
    repo_root,
    selected_files,
)

# The model files to check: .mps and .model headers are named after the model,
# whereas a per-root .mpsr is named after a root, not the model, so it is left
# out. (MODULE_GLOBS, by contrast, selects the descriptors that declare the roots.)
MODEL_GLOBS = [AnchoredGlob(f"**/*{ext}") for ext in (".mps", ".model")]


class Owner(NamedTuple):
    """A source root's owner. `is_generator` marks a root of an embedded generator;
    `is_solution` marks one whose module is a solution (rather than a language or
    devkit). `namespace` is what a model under the root is measured against -- the
    module's own name for the module's roots, the owning language's namespace for a
    generator's roots."""

    is_generator: bool
    is_solution: bool
    namespace: str


def owned_model_roots(root: Path) -> dict[Path, Owner]:
    """Map each source-root directory of a default model root to its owner."""
    owners: dict[Path, Owner] = {}
    for module in git_ls_files(*MODULE_GLOBS):
        descriptor = parse_xml(module)
        if descriptor is None:
            continue
        module_dir = module.parent
        namespace = module_name(descriptor)
        is_solution = descriptor.tag == "solution"
        # The module's own models, named after the module. A language's embedded
        # generators each declare their own roots; a model there is measured
        # against the language namespace, so record them with the same one.
        _record(owners, descriptor.findall("models/modelRoot"), Owner(False, is_solution, namespace), module_dir, root)
        for generator in descriptor.findall("generators/generator"):
            _record(
                owners, generator.findall("models/modelRoot"), Owner(True, is_solution, namespace), module_dir, root
            )
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


def without_stereotype(name: str) -> str:
    """A model name without its `@stereotype` suffix, if any."""
    return name.split("@", 1)[0]


def under_namespace(name: str, namespace: str) -> bool:
    """Whether `name` is `namespace` or lies within it, at a segment boundary."""
    base = without_stereotype(name)
    return bool(namespace) and (base == namespace or base.startswith(namespace + "."))


def acceptable_names(name: str, namespace: str, allow_short: bool = True) -> list[str]:
    """The names a model may be stored under: its full name, and -- when short names
    are allowed and the name is inside the owning module's namespace -- the name with
    that whole namespace truncated away. A `@stereotype` is part of the name and so of
    the file name: `foo` and `foo@tests` are different models and belong in different
    files."""
    names = [name]
    if allow_short and namespace and name.startswith(namespace + "."):
        names.append(name[len(namespace) + 1 :])
    return names


def aligned(header: str, rows: list[tuple[str, str]]) -> str:
    """A header line followed by indented `label: value` rows whose values line up in a
    column, so the two paths to compare sit directly under one another."""
    width = max(len(label) for label, _ in rows)
    lines = [header]
    lines += [f"    {label + ':':<{width + 1}} {value}" for label, value in rows]
    return "\n".join(lines)


def preferred_name(acceptable: list[str], current_segments: int) -> str:
    """Of the names a model may be stored under, the one to suggest: whichever is
    closest in segment count to the current path, so the fix is the smallest change --
    the short name when the model already uses a short one, the full name otherwise.
    Ties go to the full name (the first entry)."""
    return min(acceptable, key=lambda name: abs(name.count(".") + 1 - current_segments))


def render_like(name: str, current: str, suffix: str) -> str:
    """Render the dot-separated `name` as a path shaped like `current` (the model's real
    path within its source root): reuse a directory boundary from `current` for each
    leading segment that still agrees, so keeping the existing folders and renaming only
    what differs is enough. Remaining segments are dot-joined."""
    body = current[: len(current) - len(suffix)] if suffix else current
    current_segments = re.split(r"[./]", body) if body else []
    separators = re.findall(r"[./]", body)
    segments = name.split(".")
    out = []
    for i, segment in enumerate(segments):
        out.append(segment)
        if i < len(segments) - 1:
            keeps_prefix = segments[: i + 1] == current_segments[: i + 1]
            out.append(separators[i] if keeps_prefix and i < len(separators) else ".")
    return "".join(out) + suffix


def stored_name(model: Path, source_root: Path) -> str:
    """The dot-separated name a model is stored under within its source root: the
    path below the source root with directory separators read as dots. For a per-root
    model this is the directory the `.model` header sits in, for any other its file
    name without the extension."""
    relative = model.parent if model.name == ".model" else model.with_suffix("")
    return relative.relative_to(source_root).as_posix().replace("/", ".")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mps-check-model-naming",
        description="Check that each MPS model's file name agrees with its name.",
    )
    parser.add_argument(
        "--no-short-names",
        dest="allow_short_names",
        action="store_false",
        help="For solution models, require the full name as the file name; "
        "reject the short form with the owning module's namespace truncated away "
        "(e.g. baz.quux.mps for model foo.bar.baz.quux in solution foo.bar). "
        "Language models keep the short form either way. Off by default, so the "
        "short form is accepted everywhere.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Model files to check; defaults to every tracked one.",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    root = repo_root()
    owners = owned_model_roots(root)

    failed = False
    for model in selected_files(args.files, *MODEL_GLOBS):
        # .mps/ holds project configuration, not models; skip it as the other checks do.
        if ".mps" in model.parts:
            continue
        source_root = nearest_ancestor_in(model, owners)
        # A model outside every source root is mps-check-orphan-models' concern.
        if source_root is None:
            continue
        header = parse_xml(model)
        if header is None:
            continue
        name = model_name(header)
        if name is None:
            continue

        owner = owners[Path(source_root)]
        rel = model.relative_to(root).as_posix()

        if owner.is_generator:
            if under_namespace(name, owner.namespace):
                continue
            failed = True
            print(
                aligned(
                    f"{rel}: generator model is not named under its language",
                    [("model name", name), ("language", owner.namespace)],
                )
            )
        else:
            # --no-short-names tightens solutions only; languages keep the short form.
            allow_short = args.allow_short_names or not owner.is_solution
            acceptable = acceptable_names(name, owner.namespace, allow_short)
            src = Path(source_root)
            stored = stored_name(model, src)
            if stored in acceptable:
                continue
            failed = True
            # A per-root model is stored as a directory holding a `.model` header, so
            # report it by that directory -- the trailing `/.model` is noise.
            if model.name == ".model":
                current, suffix = model.parent.relative_to(src).as_posix(), ""
            else:
                current, suffix = model.relative_to(src).as_posix(), ".mps"
            expected = render_like(preferred_name(acceptable, stored.count(".") + 1), current, suffix)
            print(
                aligned(
                    f"{rel}: path does not match model name {name}",
                    [("expected path", expected), ("current path", current)],
                )
            )

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
