"""Tests for the empty default-model-root check."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from support import SRC, run_module, write

if SRC not in sys.path:
    sys.path.insert(0, SRC)

from mps_pre_commit_hooks.check_empty_model_roots import ancestor_directories

SOLUTION_MSD = """\
<solution name="com.example.foo" uuid="11111111-1111-1111-1111-111111111111">
  <models>
    <modelRoot contentPath="${module}" type="default">
      <sourceRoot location="models" />
      <sourceRoot location="tests" />
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
    return run_module("check_empty_model_roots", repo, *args)


def test_ancestor_directories_indexes_each_model_path():
    models = [Path("/repo/one/model.mps"), Path("/repo/two/nested/.model")]

    assert ancestor_directories(models) == {
        Path("/repo/one"),
        Path("/repo/two/nested"),
        Path("/repo/two"),
        Path("/repo"),
        Path("/"),
    }


@pytest.fixture
def repo(tmp_path):
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    write(os.path.join(root, "com.example.foo/com.example.foo.msd"), SOLUTION_MSD)
    write(os.path.join(root, "com.example.foo/models/main.mps"), MODEL_MPS)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root


def test_model_in_any_source_root_makes_model_root_nonempty(repo):
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_empty_model_root_is_reported(repo):
    os.remove(os.path.join(repo, "com.example.foo/models/main.mps"))
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    result = run_check(repo)

    assert result.returncode == 1
    assert result.stdout == (
        "com.example.foo/com.example.foo.msd: default model root has no models under its source roots: "
        "com.example.foo/models, com.example.foo/tests\n"
    )


def test_each_default_model_root_is_checked_independently(repo):
    descriptor = SOLUTION_MSD.replace(
        "  </models>",
        """\
    <modelRoot contentPath="${module}" type="default">
      <sourceRoot location="unused" />
    </modelRoot>
  </models>""",
    )
    write(os.path.join(repo, "com.example.foo/com.example.foo.msd"), descriptor)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    result = run_check(repo)

    assert result.returncode == 1
    assert "com.example.foo/unused" in result.stdout
    assert "com.example.foo/models" not in result.stdout


def test_default_model_root_without_source_roots_is_reported(repo):
    descriptor = SOLUTION_MSD.replace(
        "  </models>",
        '    <modelRoot contentPath="${module}" type="default" />\n  </models>',
    )
    write(os.path.join(repo, "com.example.foo/com.example.foo.msd"), descriptor)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    result = run_check(repo)

    assert result.returncode == 1
    assert "default model root has no source roots and no models" in result.stdout


def test_non_default_model_root_is_ignored(repo):
    descriptor = SOLUTION_MSD.replace(
        "  </models>",
        '    <modelRoot type="java_classes" />\n  </models>',
    )
    write(os.path.join(repo, "com.example.foo/com.example.foo.msd"), descriptor)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    result = run_check(repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_excluded_module_descriptor_is_not_checked(repo):
    os.remove(os.path.join(repo, "com.example.foo/models/main.mps"))
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    result = run_check(repo, "--exclude", "com.example.foo.msd")

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_excluded_subtree_is_not_checked(repo):
    os.remove(os.path.join(repo, "com.example.foo/models/main.mps"))
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    result = run_check(repo, "--exclude", "com.example.foo/")

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""
