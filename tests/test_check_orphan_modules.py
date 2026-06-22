"""Tests for the module-registration check.

Each test builds a throwaway git repository on disk -- the check discovers files
through `git ls-files`, so the fixtures have to be real, tracked files -- and
runs the hook as `python -m` (it chdir's into the repo root, which we don't want
leaking between tests)."""

import os
import subprocess

import pytest

from support import run_module, write

SOLUTION_MSD = '<solution name="com.example.foo" uuid="11111111-1111-1111-1111-111111111111" />\n'

MODULES_XML = """\
<project version="4">
  <component name="MPSProject">
    <projects>
      <modulePath path="$PROJECT_DIR$/com.example.foo/com.example.foo.msd" folder="" />
    </projects>
  </component>
</project>
"""

# MPS keeps each project's wiring in its own `.mps/` directory, usually nested.
# The fixture nests the project one level down so $PROJECT_DIR$ resolves to a real
# path; a root-level .mps/ is covered by its own test.
PROJ = "proj"


def proj_path(repo, *parts):
    return os.path.join(repo, PROJ, *parts)


def run_check(repo, *args):
    return run_module("check_orphan_modules", repo, *args)


@pytest.fixture
def consistent_repo(tmp_path):
    """A small project whose one module is registered."""
    repo = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    write(proj_path(repo, "com.example.foo/com.example.foo.msd"), SOLUTION_MSD)
    write(proj_path(repo, ".mps/modules.xml"), MODULES_XML)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    return repo


def test_registered_module_passes(consistent_repo):
    result = run_check(consistent_repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_unregistered_module_is_reported(consistent_repo):
    # Drop the registration so the module is no longer wired in.
    write(
        proj_path(consistent_repo, ".mps/modules.xml"),
        MODULES_XML.replace(
            '<modulePath path="$PROJECT_DIR$/com.example.foo/com.example.foo.msd" folder="" />',
            "",
        ),
    )
    subprocess.run(["git", "add", "-A"], cwd=consistent_repo, check=True)
    result = run_check(consistent_repo)
    assert result.returncode == 1
    assert "not registered in any modules.xml" in result.stdout


def test_root_level_project_is_scanned(tmp_path):
    # A single-project repo: .mps/modules.xml sits at the repository root, so
    # $PROJECT_DIR$ is the repo root itself.
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    write(os.path.join(root, "com.example.foo/com.example.foo.msd"), SOLUTION_MSD)
    write(os.path.join(root, ".mps/modules.xml"), MODULES_XML)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    # Registered: the $PROJECT_DIR$ entry must resolve to a repo-relative path.
    ok = run_check(root)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    # Unregistered: proves the root-level modules.xml is actually scanned.
    write(
        os.path.join(root, ".mps/modules.xml"),
        MODULES_XML.replace(
            '<modulePath path="$PROJECT_DIR$/com.example.foo/com.example.foo.msd" folder="" />',
            "",
        ),
    )
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    reported = run_check(root)
    assert reported.returncode == 1
    assert "not registered in any modules.xml" in reported.stdout
