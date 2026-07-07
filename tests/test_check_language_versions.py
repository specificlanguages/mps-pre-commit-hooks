"""Tests for the negative-language-version check.

Each builds a throwaway git repository: the check discovers models through
`git ls-files`, so the fixtures have to be real, tracked files."""

import os
import subprocess

import pytest

from support import run_module, write


def model(*uses):
    entries = "\n".join(f"    {u}" for u in uses)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model ref="r:59f5b892-a6eb-4a9b-9c81-ecffc10026ee(jetbrains.mps.example)">\n'
        '  <persistence version="9" />\n'
        "  <languages>\n"
        f"{entries}\n"
        "  </languages>\n"
        "</model>\n"
    )


BASE_LANGUAGE = '<use id="f3061a53-9226-4cc5-a443-f952ceaf5816" name="jetbrains.mps.baseLanguage" version="12" />'
FIND_USAGES_UNVERSIONED = (
    '<use id="64d34fcd-ad02-4e73-aff8-a581124c2e30" name="jetbrains.mps.lang.findUsages" version="-1" />'
)


def run_check(repo, *args):
    return run_module("check_language_versions", repo, *args)


@pytest.fixture
def repo(tmp_path):
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def add(repo):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)


def test_language_with_negative_version_is_reported(repo):
    write(
        os.path.join(repo, "solution/models/example.mps"),
        model(BASE_LANGUAGE, FIND_USAGES_UNVERSIONED),
    )
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert "solution/models/example.mps" in result.stdout
    assert "jetbrains.mps.lang.findUsages" in result.stdout


def test_model_with_only_versioned_languages_passes(repo):
    write(
        os.path.join(repo, "solution/models/clean.mps"),
        model(BASE_LANGUAGE),
    )
    add(repo)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_dot_model_file_is_checked(repo):
    write(
        os.path.join(repo, "solution/models/.model"),
        model(FIND_USAGES_UNVERSIONED),
    )
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert "solution/models/.model" in result.stdout


def test_mpsr_file_is_not_checked(repo):
    write(
        os.path.join(repo, "solution/models/roots.mpsr"),
        model(FIND_USAGES_UNVERSIONED),
    )
    add(repo)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_passed_file_scopes_the_check(repo):
    write(os.path.join(repo, "clean/clean.mps"), model(BASE_LANGUAGE))
    write(os.path.join(repo, "dirty/dirty.mps"), model(FIND_USAGES_UNVERSIONED))
    add(repo)
    clean = run_check(repo, "clean/clean.mps")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    reported = run_check(repo, "dirty/dirty.mps")
    assert reported.returncode == 1
    assert "dirty/dirty.mps" in reported.stdout
