"""Tests for the zero-sized XML check.

Builds a throwaway git repository: the check discovers files through
`git ls-files`, so the fixtures have to be real, tracked files."""

import os
import subprocess

import pytest

from support import run_module, write

MODEL_MPS = """\
<model ref="r:00000000-0000-0000-0000-000000000001(com.example.foo)">
  <persistence version="9" />
</model>
"""

SOLUTION_MSD = '<solution name="com.example.foo" uuid="11111111-1111-1111-1111-111111111111" />\n'

MODULES_XML = """\
<project version="4">
  <component name="MPSProject" />
</project>
"""


def run_check(repo, *args):
    return run_module("check_zero_sized_xmls", repo, *args)


@pytest.fixture
def repo(tmp_path):
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    write(os.path.join(root, "com.example.foo/com.example.foo.msd"), SOLUTION_MSD)
    write(os.path.join(root, "com.example.foo/models/main.mps"), MODEL_MPS)
    write(os.path.join(root, "com.example.foo/.mps/modules.xml"), MODULES_XML)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root


def test_non_empty_files_pass(repo):
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_zero_sized_model_is_reported(repo):
    write(os.path.join(repo, "com.example.foo/models/empty.mps"), "")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    result = run_check(repo)
    assert result.returncode == 1
    assert "empty.mps: zero-sized file" in result.stdout


def test_zero_sized_descriptor_is_reported(repo):
    write(os.path.join(repo, "com.example.foo/com.example.foo.msd"), "")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    result = run_check(repo)
    assert result.returncode == 1
    assert "com.example.foo.msd" in result.stdout


def test_zero_sized_modules_xml_is_reported(repo):
    write(os.path.join(repo, "com.example.foo/.mps/modules.xml"), "")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    result = run_check(repo)
    assert result.returncode == 1
    assert ".mps/modules.xml" in result.stdout


def test_root_level_config_xml_zero_sized_is_reported(tmp_path):
    # A zero-byte .mps/modules.xml at the repo root must be caught.
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    write(os.path.join(root, ".mps/modules.xml"), "")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    result = run_check(root)
    assert result.returncode == 1
    assert ".mps/modules.xml" in result.stdout


def test_passed_file_scopes_the_check(repo):
    # An empty model elsewhere is not reported when only a good file is passed,
    # but is reported when it is the file passed.
    write(os.path.join(repo, "com.example.foo/models/empty.mps"), "")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    clean = run_check(repo, "com.example.foo/models/main.mps")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    reported = run_check(repo, "com.example.foo/models/empty.mps")
    assert reported.returncode == 1
    assert "empty.mps" in reported.stdout


def test_empty_non_config_file_under_dot_mps_is_ignored(repo):
    # Inside .mps/ only modules.xml and libraries.xml matter; other transient
    # files there (an empty .mps left by tooling) are out of scope.
    write(os.path.join(repo, "com.example.foo/.mps/something.mps"), "")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
