#!/usr/bin/env python3
#
# Helpers shared by the MPS check hooks: locating the repository, listing tracked
# files, reading a module's name, and walking a path's ancestors. Each hook runs
# as `python -m mps_pre_commit_hooks.check_*`, so they import these from the
# package rather than each carrying its own copy.

from __future__ import annotations

import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path, PurePath, PurePosixPath
from typing import Container, NewType

# A root-anchored, pathname-aware glob, in the dialect PurePath.full_match reads:
# `*` stays within a single path segment and `**` spans segments, so a leading
# `**/` matches at any depth, the repo root included. The stdlib has no dedicated
# glob type -- pathlib, fnmatch and glob all take a bare str -- so name one here,
# distinct from arbitrary strings.
AnchoredGlob = NewType("AnchoredGlob", str)

# A glob that need not be anchored to the repo root, written the way a .gitignore
# pattern reads, so a user can write `*_spreferences/` instead of spelling out
# `**/*_spreferences/**`. See anchor() for the precise translation to an
# AnchoredGlob.
FloatingGlob = NewType("FloatingGlob", str)


def anchor(glob: FloatingGlob) -> AnchoredGlob:
    """Resolve a FloatingGlob to its root-anchored equivalent.

    Anchoring follows .gitignore: a separator at the start or middle of the glob
    ties it to the repo root, so a leading `/` is dropped and the rest used
    verbatim. A glob with no separator (or only a trailing one) floats, and a
    `**/` prefix lets it match at any depth. Either way a trailing `/` names a
    directory, so a `**` suffix is added to match everything beneath it."""
    anchored = "/" in glob.rstrip("/")
    core = glob[1:] if glob.startswith("/") else glob
    if not anchored:
        core = "**/" + core
    if glob.endswith("/"):
        core += "**"
    return AnchoredGlob(core)


def matches(path: str | os.PathLike[str], *patterns: AnchoredGlob, subtree: bool = False) -> bool:
    """Whether `path` (repo-relative, /-separated) matches any of the given root-anchored globs.

    With `subtree`, a glob also matches everything beneath it -- so a bare `foo`
    catches `foo/bar` too, the way a .gitignore entry naming a directory ignores
    its contents. The internal extension globs leave it off, keeping their match
    in step with the `git ls-files` pathspecs that select the same files."""
    candidate = PurePosixPath(path)
    for pattern in patterns:
        if candidate.full_match(pattern):
            return True
        if subtree and not pattern.endswith("/**") and candidate.full_match(pattern + "/**"):
            return True
    return False


# The MPS files the hooks act on, by extension. `**/` matches them at any depth.
MODULE_GLOBS = [AnchoredGlob(f"**/*{ext}") for ext in (".msd", ".mpl", ".devkit", ".mpst")]
MODEL_GLOBS = [AnchoredGlob(f"**/*{ext}") for ext in (".mps", ".mpsr", ".model")]

# A project's wiring lives in a .mps/ directory, usually nested but sometimes at
# the repository root (a single-project repo); the leading `**/` covers both.
MODULES_XML_GLOBS = [AnchoredGlob("**/.mps/modules.xml")]
LIBRARIES_XML_GLOBS = [AnchoredGlob("**/.mps/libraries.xml")]


def project_dir_of(mps_xml: Path) -> Path:
    """The directory $PROJECT_DIR$ stands for: the one that contains the .mps
    folder. For a .mps/ at the repository root this is the root itself."""
    return mps_xml.parent.parent


def repo_root() -> Path:
    out = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return Path(out)


def git_ls_files(*globs: AnchoredGlob) -> list[Path]:
    """Tracked files matching `globs`, as absolute, platform-native paths.

    Runs in the repository root so the result is independent of the caller's
    working directory."""
    root = repo_root()
    # git ls-files speaks pathspecs, so wrap each glob in :(glob) magic.
    pathspecs = [":(glob)" + g for g in globs]
    out = subprocess.run(
        ["git", "ls-files", "--", *pathspecs],
        check=True,
        capture_output=True,
        text=True,
        cwd=root,
    ).stdout
    # git reports tracked paths with '/' separators on every platform, Windows
    # included -- the listing is always POSIX -- so read each line as a
    # PurePosixPath, then anchor it to the absolute, platform-native repo root.
    # (The only transformation git applies to the output is core.quotePath
    # quoting of non-ASCII bytes; it never rewrites separators.)
    return [root / PurePosixPath(line) for line in out.splitlines() if line]


def selected_files(passed: list[str], *globs: AnchoredGlob) -> list[Path]:
    """The files a per-file hook should act on, as absolute paths.

    When pre-commit passes filenames (`passed`), restrict to those that match
    `globs`; otherwise fall back to every tracked file matching `globs`.
    This lets a hook act only on the files in the changeset during a normal
    commit, yet still scan the whole repo when run standalone or with
    `--all-files` (which makes pre-commit pass every matching file). The passed
    list is filtered in-process with matches(), which applies the same :(glob)
    semantics git uses, so both paths select the same files."""
    if passed:
        root = repo_root()
        return [root / PurePosixPath(p) for p in passed if matches(p, *globs)]
    return git_ls_files(*globs)


def module_name(descriptor_root: ET.Element) -> str:
    # Solutions and devkits carry "name"; languages carry "namespace".
    return descriptor_root.get("name") or descriptor_root.get("namespace") or ""


def nearest_ancestor_in(path: PurePath, directories: Container[PurePath]) -> PurePath | None:
    """The nearest ancestor directory of `path` that is in `directories`, or None.
    Walks upward from path's parent; `path` itself is never considered."""
    for directory in path.parents:
        if directory in directories:
            return directory
    return None
