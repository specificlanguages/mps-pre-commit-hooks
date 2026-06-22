"""Tests for the module naming-consistency check.

Each builds a throwaway git repository: the check discovers descriptors through
`git ls-files`, so the fixtures have to be real, tracked files."""

import os
import subprocess

import pytest

from support import run_module, write


def solution(name):
    return f'<solution name="{name}" uuid="11111111-1111-1111-1111-111111111111" />\n'


def run_check(repo, *args):
    return run_module("check_module_naming", repo, *args)


@pytest.fixture
def repo(tmp_path):
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def add(repo):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)


def test_consistent_module_passes(repo):
    write(
        os.path.join(repo, "com.example.foo/com.example.foo.msd"),
        solution("com.example.foo"),
    )
    add(repo)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_file_name_mismatch_is_reported(repo):
    write(os.path.join(repo, "com.example.foo/renamed.msd"), solution("com.example.foo"))
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert "does not match file name" in result.stdout


def test_directory_name_mismatch_is_reported(repo):
    write(os.path.join(repo, "wrongdir/com.example.foo.msd"), solution("com.example.foo"))
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert "does not match directory name" in result.stdout


def test_nested_role_submodule_folder_is_reported(repo):
    # We used to allow sandbox or runtime solutions inside "sandbox" folder under a language, but not anymore.
    write(
        os.path.join(repo, "com.example.foo/com.example.foo.msd"),
        solution("com.example.foo"),
    )
    write(
        os.path.join(repo, "com.example.foo/sandbox/com.example.foo.sandbox.msd"),
        solution("com.example.foo.sandbox"),
    )
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert "does not match directory name" in result.stdout


def test_inconsistent_module_reported_without_exclude(repo):
    # A generated preference module (fixed file name "module", _spreferences
    # folder) satisfies neither naming rule, so it is reported by default.
    write(
        os.path.join(repo, "_spreferences/module.msd"),
        solution("com.example.foo.__spreferences.whatever"),
    )
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1


def test_excluded_glob_is_skipped(repo):
    # A trailing '/' names a directory; the floating glob skips the whole subtree
    # without the user spelling out a '**/...**' pattern.
    write(
        os.path.join(repo, "_spreferences/module.msd"),
        solution("com.example.foo.__spreferences.whatever"),
    )
    add(repo)
    result = run_check(repo, "--exclude", "*_spreferences/")
    assert result.returncode == 0, result.stdout + result.stderr


def test_exclude_floats_to_any_depth(repo):
    # A floating glob (no leading '/') matches at any depth, so a module nested
    # under sub/ is excluded without a '**/' prefix.
    write(
        os.path.join(repo, "sub/_spreferences/module.msd"),
        solution("com.example.foo.__spreferences.whatever"),
    )
    add(repo)
    result = run_check(repo, "--exclude", "*_spreferences/")
    assert result.returncode == 0, result.stdout + result.stderr


def test_leading_slash_anchors_exclude(repo):
    # A leading '/' anchors the glob to the repo root, so it does not reach a
    # module nested deeper.
    write(
        os.path.join(repo, "sub/_spreferences/module.msd"),
        solution("com.example.foo.__spreferences.whatever"),
    )
    add(repo)
    anchored = run_check(repo, "--exclude", "/_spreferences/")
    assert anchored.returncode == 1, anchored.stdout + anchored.stderr
    floating = run_check(repo, "--exclude", "_spreferences/")
    assert floating.returncode == 0, floating.stdout + floating.stderr


def test_interior_separator_anchors_exclude(repo):
    # As in .gitignore, a separator anywhere but the end anchors the glob to the
    # repo root: the matching prefix excludes the module, a non-matching one
    # leaves it reported.
    write(
        os.path.join(repo, "sub/_spreferences/module.msd"),
        solution("com.example.foo.__spreferences.whatever"),
    )
    add(repo)
    matching = run_check(repo, "--exclude", "sub/_spreferences/")
    assert matching.returncode == 0, matching.stdout + matching.stderr
    nonmatching = run_check(repo, "--exclude", "other/_spreferences/")
    assert nonmatching.returncode == 1, nonmatching.stdout + nonmatching.stderr


def test_bare_directory_name_excludes_its_subtree(repo):
    # As in .gitignore, a bare directory name (no trailing '/') excludes
    # everything under it, not just an entry of that exact name.
    write(
        os.path.join(repo, "sub/_spreferences/module.msd"),
        solution("com.example.foo.__spreferences.whatever"),
    )
    add(repo)
    result = run_check(repo, "--exclude", "_spreferences")
    assert result.returncode == 0, result.stdout + result.stderr


def test_passed_file_scopes_the_check(repo):
    # A clean module and a misnamed one. Checking only the clean file passes;
    # the misnamed one is still caught when it is the file passed.
    write(
        os.path.join(repo, "com.example.foo/com.example.foo.msd"),
        solution("com.example.foo"),
    )
    write(os.path.join(repo, "wrongdir/com.example.foo.msd"), solution("com.example.foo"))
    add(repo)
    clean = run_check(repo, "com.example.foo/com.example.foo.msd")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    reported = run_check(repo, "wrongdir/com.example.foo.msd")
    assert reported.returncode == 1
    assert "does not match directory name" in reported.stdout
