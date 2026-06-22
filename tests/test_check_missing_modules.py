"""Tests for the dangling module-registration check.

Builds a throwaway git repository: the check resolves each modulePath against
files on disk, so the fixtures have to be real, tracked files."""

import os
import subprocess

import pytest

from support import read, run_module, write

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

# One valid entry (com.example.foo exists in the fixture) and one dangling.
TWO_ENTRIES = """\
<project version="4">
  <component name="MPSProject">
    <projects>
      <modulePath path="$PROJECT_DIR$/com.example.foo/com.example.foo.msd" folder="" />
      <modulePath path="$PROJECT_DIR$/com.example.gone/com.example.gone.msd" folder="" />
    </projects>
  </component>
</project>
"""

# The .mps lives one level below the repo root so $PROJECT_DIR$ resolves.
PROJ = "proj"


def proj_path(repo, *parts):
    return os.path.join(repo, PROJ, *parts)


def run_check(repo, *args):
    return run_module("check_missing_modules", repo, *args)


@pytest.fixture
def repo(tmp_path):
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    write(proj_path(root, "com.example.foo/com.example.foo.msd"), SOLUTION_MSD)
    write(proj_path(root, ".mps/modules.xml"), MODULES_XML)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root


def test_resolvable_registration_passes(repo):
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_dangling_module_path_is_reported(repo):
    write(
        proj_path(repo, ".mps/modules.xml"),
        MODULES_XML.replace("com.example.foo.msd", "com.example.gone.msd"),
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    result = run_check(repo)
    assert result.returncode == 1
    assert "missing file" in result.stdout
    assert "com.example.gone.msd" in result.stdout


def test_unknown_path_variable_is_skipped(repo):
    # A modulePath addressed through an unresolvable ${...} variable is left to
    # the path-variable hook, not reported as dangling here.
    write(
        proj_path(repo, ".mps/modules.xml"),
        MODULES_XML.replace(
            "$PROJECT_DIR$/com.example.foo/com.example.foo.msd",
            "${my.var}/somewhere/com.example.foo.msd",
        ),
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_fix_removes_dangling_entry_and_keeps_valid(repo):
    write(proj_path(repo, ".mps/modules.xml"), TWO_ENTRIES)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    result = run_check(repo, "--fix")
    assert result.returncode == 1  # fixers exit non-zero when they change files
    content = read(proj_path(repo, ".mps/modules.xml"))
    assert "com.example.gone.msd" not in content
    assert "com.example.foo.msd" in content  # valid registration left intact


def test_fix_is_idempotent(repo):
    write(proj_path(repo, ".mps/modules.xml"), TWO_ENTRIES)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    run_check(repo, "--fix")
    second = run_check(repo, "--fix")
    assert second.returncode == 0
    assert second.stdout == ""


def test_root_level_modules_xml_resolves(tmp_path):
    # .mps/modules.xml at the repo root: $PROJECT_DIR$ entries must resolve there
    # rather than against an empty (absolute) path.
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    write(os.path.join(root, "com.example.foo/com.example.foo.msd"), SOLUTION_MSD)
    write(os.path.join(root, ".mps/modules.xml"), MODULES_XML)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    result = run_check(root)
    assert result.returncode == 0, result.stdout + result.stderr


def test_root_level_modules_xml_dangling_is_reported(tmp_path):
    # The descriptor is absent, so the root-level modules.xml entry is dangling --
    # which is only caught if that modules.xml is scanned at all.
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    write(os.path.join(root, ".mps/modules.xml"), MODULES_XML)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    result = run_check(root)
    assert result.returncode == 1
    assert "missing file" in result.stdout
