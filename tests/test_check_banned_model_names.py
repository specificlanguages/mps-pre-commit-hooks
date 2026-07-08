"""Tests for the banned model-name check.

Each builds a throwaway git repository: the check discovers models through
`git ls-files`, so the fixtures have to be real, tracked files."""

import os
import subprocess

import pytest

from support import run_module, write


def model(name):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<model ref="r:59f5b892-a6eb-4a9b-9c81-ecffc10026ee({name})">\n'
        '  <persistence version="9" />\n'
        "</model>\n"
    )


def run_check(repo, *args):
    return run_module("check_banned_model_names", repo, *args)


@pytest.fixture
def repo(tmp_path):
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def add(repo):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)


def test_banned_name_is_reported(repo):
    write(os.path.join(repo, "generator/models/main.mps"), model("main@generator"))
    add(repo)
    result = run_check(repo, "--ban=main@generator")
    assert result.returncode == 1
    assert "generator/models/main.mps" in result.stdout
    assert "main@generator" in result.stdout


def test_qualified_name_with_same_suffix_passes(repo):
    write(os.path.join(repo, "generator/models/main.mps"), model("foo.bar.main@generator"))
    add(repo)
    result = run_check(repo, "--ban=main@generator")
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_no_ban_passes_everything(repo):
    write(os.path.join(repo, "generator/models/main.mps"), model("main@generator"))
    add(repo)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_dot_model_file_is_checked(repo):
    write(os.path.join(repo, "generator/models/.model"), model("main@generator"))
    add(repo)
    result = run_check(repo, "--ban=main@generator")
    assert result.returncode == 1
    assert "generator/models/.model" in result.stdout


def test_multiple_bans(repo):
    write(os.path.join(repo, "a/one.mps"), model("main@generator"))
    write(os.path.join(repo, "b/two.mps"), model("sandbox"))
    add(repo)
    result = run_check(repo, "--ban=main@generator", "--ban=sandbox")
    assert result.returncode == 1
    assert "a/one.mps" in result.stdout
    assert "b/two.mps" in result.stdout


def test_malformed_file_is_skipped_not_crashed(repo):
    # An unrelated malformed model elsewhere must not crash the run; the real
    # finding is still reported. (Malformed XML is mps-check-well-formed-xml's job.)
    write(os.path.join(repo, "broken/broken.mps"), "")
    write(os.path.join(repo, "dirty/dirty.mps"), model("main@generator"))
    add(repo)
    result = run_check(repo, "--ban=main@generator")
    assert result.returncode == 1
    assert result.stderr == "", result.stderr
    assert "dirty/dirty.mps" in result.stdout


def test_passed_file_scopes_the_check(repo):
    write(os.path.join(repo, "clean/clean.mps"), model("foo.bar.main@generator"))
    write(os.path.join(repo, "dirty/dirty.mps"), model("main@generator"))
    add(repo)
    clean = run_check(repo, "--ban=main@generator", "clean/clean.mps")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    reported = run_check(repo, "--ban=main@generator", "dirty/dirty.mps")
    assert reported.returncode == 1
    assert "dirty/dirty.mps" in reported.stdout
