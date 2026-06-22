"""Tests for the .mpsr model-header check.

Builds a throwaway git repository: the check discovers *.mpsr roots through
`git ls-files` and looks for a sibling .model, so the fixtures have to be real,
tracked files."""

import os
import subprocess

import pytest

from support import run_module, write

MPSR_ROOT = """\
<node id="1">
  <property role="name" value="Root" />
</node>
"""

MODEL_HEADER = """\
<model ref="r:00000000-0000-0000-0000-000000000001(com.example.foo)">
  <persistence version="9" />
</model>
"""


def run_check(repo, *args):
    return run_module("check_orphan_mpsr_files", repo, *args)


@pytest.fixture
def repo(tmp_path):
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    write(os.path.join(root, "com.example.foo/models/root.mpsr"), MPSR_ROOT)
    return root


def test_mpsr_with_header_passes(repo):
    write(os.path.join(repo, "com.example.foo/models/.model"), MODEL_HEADER)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_mpsr_without_header_is_reported(repo):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    result = run_check(repo)
    assert result.returncode == 1
    assert "without a .model header" in result.stdout
    assert "root.mpsr" in result.stdout
