"""Tests for the model-root membership check.

Builds a throwaway git repository: the check discovers models and model roots
through `git ls-files`, so the fixtures have to be real, tracked files."""

import os
import subprocess

import pytest

from support import run_module, write

# A descriptor with a default model root at models/.
SOLUTION_MSD = """\
<solution name="com.example.foo" uuid="11111111-1111-1111-1111-111111111111">
  <models>
    <modelRoot contentPath="${module}" type="default">
      <sourceRoot location="models" />
    </modelRoot>
  </models>
</solution>
"""

MODEL_MPS = """\
<model ref="r:00000000-0000-0000-0000-000000000001(com.example.foo)">
  <persistence version="9" />
</model>
"""


def run_check(repo, *args):
    return run_module("check_orphan_models", repo, *args)


@pytest.fixture
def repo(tmp_path):
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    write(os.path.join(root, "com.example.foo/com.example.foo.msd"), SOLUTION_MSD)
    write(os.path.join(root, "com.example.foo/models/main.mps"), MODEL_MPS)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root


def test_model_inside_root_passes(repo):
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_model_outside_root_is_reported(repo):
    write(os.path.join(repo, "com.example.foo/stray.mps"), MODEL_MPS)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    result = run_check(repo)
    assert result.returncode == 1
    assert "outside any default model root's source roots" in result.stdout
    assert "stray.mps" in result.stdout
