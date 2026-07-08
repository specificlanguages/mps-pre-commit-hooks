#!/usr/bin/env python3
#
# Model naming-consistency check.
#
# A model's name and the module it belongs to should agree with how it is stored,
# or the project becomes confusing to navigate. This reports two kinds of mismatch,
# depending on where a tracked model file (*.mps / .model) lives:
#
# 1. A model in a solution's or language's own default model root must be stored
#    under a file name that matches its qualified name. Relative to that root, a
#    model `foo.bar.baz.quux` in a module `foo.bar` may be stored as:
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

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

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


# A model root's owner: whether it belongs to an embedded generator, and the
# namespace a model in it is measured against -- the module's own name for a
# module root, the owning language's namespace for a generator root.
Owner = tuple[bool, str]


def owned_model_roots(root: Path) -> dict[Path, Owner]:
    """Map each default model-root directory to its owner."""
    owners: dict[Path, Owner] = {}
    for module in git_ls_files(*MODULE_GLOBS):
        descriptor = parse_xml(module)
        if descriptor is None:
            continue
        module_dir = module.parent
        namespace = module_name(descriptor)
        # The module's own models, named after the module. A language's embedded
        # generators each declare their own roots; a model there is measured
        # against the language namespace, so record them with the same one.
        _record(owners, descriptor.findall("models/modelRoot"), (False, namespace), module_dir, root)
        for generator in descriptor.findall("generators/generator"):
            _record(owners, generator.findall("models/modelRoot"), (True, namespace), module_dir, root)
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


def acceptable_names(name: str, namespace: str) -> list[str]:
    """The names a model may be stored under: its full name, and -- when the name
    is inside the owning module's namespace -- the name with that whole namespace
    truncated away. A `@stereotype` is part of the name and so of the file name:
    `foo` and `foo@tests` are different models and belong in different files."""
    names = [name]
    if namespace and name.startswith(namespace + "."):
        names.append(name[len(namespace) + 1 :])
    return names


def stored_name(model: Path, model_root: Path) -> str:
    """The dot-separated name a model is stored under within its model root: the
    path below the root with directory separators read as dots. For a per-root
    model this is the directory the `.model` header sits in, for any other its file
    name without the extension."""
    relative = model.parent if model.name == ".model" else model.with_suffix("")
    return relative.relative_to(model_root).as_posix().replace("/", ".")


def main(argv: list[str]) -> int:
    root = repo_root()
    owners = owned_model_roots(root)

    failed = False
    for model in selected_files(argv, *MODEL_GLOBS):
        # .mps/ holds project configuration, not models; skip it as the other checks do.
        if ".mps" in model.parts:
            continue
        model_root = nearest_ancestor_in(model, owners)
        # A model outside every model root is mps-check-orphan-models' concern.
        if model_root is None:
            continue
        header = parse_xml(model)
        if header is None:
            continue
        name = model_name(header)
        if name is None:
            continue

        is_generator, namespace = owners[Path(model_root)]
        rel = model.relative_to(root).as_posix()

        if is_generator:
            if under_namespace(name, namespace):
                continue
            failed = True
            print(f"{rel}: generator model '{name}' is not named under its language '{namespace}'")
        else:
            acceptable = acceptable_names(name, namespace)
            if stored_name(model, Path(model_root)) in acceptable:
                continue
            failed = True
            suffix = "/.model" if model.name == ".model" else ".mps"
            expected = " or ".join(f"'{n}{suffix}'" for n in acceptable)
            print(
                f"{rel}: file name does not match model name '{name}'; "
                f"under its model root it should be {expected} "
                f"(a '.' may instead be a directory separator)"
            )

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
