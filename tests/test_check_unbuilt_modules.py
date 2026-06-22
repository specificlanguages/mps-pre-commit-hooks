"""Tests for the build-membership check.

The check reads jetbrains.mps.build.mps build models, resolving concept indices
through each model's <registry>, so the fixture includes a minimal but real build
model that packages one module."""

import os
import subprocess

import pytest

from support import run_module, write


def solution(name):
    return f'<solution name="{name}" uuid="11111111-1111-1111-1111-111111111111" />\n'


# A minimal build model written in jetbrains.mps.build.mps. Its <registry>
# declares the BuildMps_Solution concept and INamedConcept.name so the check can
# resolve their indices; the single node packages the module named below.
def build_model(packaged):
    return f"""\
<model ref="r:00000000-0000-0000-0000-000000000002(build)">
  <persistence version="9" />
  <registry>
    <language id="l1" name="jetbrains.mps.build.mps">
      <concept id="1" index="bm" name="jetbrains.mps.build.mps.structure.BuildMps_Solution" />
    </language>
    <language id="l2" name="jetbrains.mps.lang.core">
      <concept id="2" index="in" name="jetbrains.mps.lang.core.structure.INamedConcept">
        <property id="3" index="nm" name="name" />
      </concept>
    </language>
  </registry>
{packaged}
</model>
"""


def packaged_node(name):
    return f'  <node concept="bm">\n    <property role="nm" value="{name}" />\n  </node>'


def run_check(repo, *args):
    return run_module("check_unbuilt_modules", repo, *args)


def add(repo):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)


@pytest.fixture
def repo(tmp_path):
    """A build solution that packages com.example.foo, plus that module."""
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    write(os.path.join(root, "build/build.msd"), solution("build"))
    write(
        os.path.join(root, "build/models/build.mps"),
        build_model(packaged_node("com.example.foo")),
    )
    write(
        os.path.join(root, "com.example.foo/com.example.foo.msd"),
        solution("com.example.foo"),
    )
    add(root)
    return root


def test_packaged_module_passes(repo):
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_unpackaged_module_is_reported(repo):
    # Rewrite the build model to package nothing; com.example.foo is now unbuilt.
    write(os.path.join(repo, "build/models/build.mps"), build_model(""))
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert "not packaged by any build script" in result.stdout
    assert "com.example.foo" in result.stdout


def test_excluded_glob_is_skipped(repo):
    # A trailing '/' names the module's directory; the floating glob skips it
    # without the user spelling out a '**/...' pattern.
    write(os.path.join(repo, "build/models/build.mps"), build_model(""))
    add(repo)
    result = run_check(repo, "--exclude", "com.example.foo/")
    assert result.returncode == 0, result.stdout + result.stderr


def test_no_build_scripts_is_a_noop(tmp_path):
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    write(
        os.path.join(root, "com.example.foo/com.example.foo.msd"),
        solution("com.example.foo"),
    )
    add(root)
    result = run_check(root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""
