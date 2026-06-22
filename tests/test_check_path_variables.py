"""Tests for the path-variable check and its --fix mode.

Like the structure-check tests, each builds a throwaway git repository: the
check discovers files through `git ls-files`, and the fix rewrites paths
relative to the repository root, both of which need a real repo on disk."""

import os
import subprocess

import pytest

from support import read, run_module, write

# The .mps lives two levels below the repo root, so $PROJECT_DIR$ resolves to
# proj/code/com.example.foo and a repo-root macro rewrites to "../../..".
PROJECT = "code/com.example.foo"

LIBRARIES_XML = """\
<application>
  <component name="libraries">
    <library>
      <option name="path" value="${my.repo.home}/code/platform/com.example.lib" />
    </library>
  </component>
</application>
"""

MODULES_XML = """\
<project version="4">
  <component name="MPSProject">
    <projects>
      <modulePath path="$PROJECT_DIR$/com.example.foo.msd" folder="" />
      <modulePath path="${my.repo.home}/tools/Debugger/Debugger.msd" folder="" />
    </projects>
  </component>
</project>
"""


def run_check(repo, *args):
    return run_module("check_path_variables", repo, *args)


@pytest.fixture
def repo(tmp_path):
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    write(os.path.join(root, PROJECT, ".mps/libraries.xml"), LIBRARIES_XML)
    write(os.path.join(root, PROJECT, ".mps/modules.xml"), MODULES_XML)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    return root


def libraries(repo):
    return os.path.join(repo, PROJECT, ".mps/libraries.xml")


def modules(repo):
    return os.path.join(repo, PROJECT, ".mps/modules.xml")


def test_clean_files_pass(repo):
    write(
        libraries(repo),
        LIBRARIES_XML.replace(
            "${my.repo.home}/code/platform/com.example.lib",
            "$PROJECT_DIR$/../platform/com.example.lib",
        ),
    )
    write(
        modules(repo),
        MODULES_XML.replace(
            "${my.repo.home}/tools/Debugger/Debugger.msd",
            "$PROJECT_DIR$/../../tools/Debugger/Debugger.msd",
        ),
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_variables_are_reported_in_both_files(repo):
    result = run_check(repo)
    assert result.returncode == 1
    assert ".mps/libraries.xml" in result.stdout
    assert ".mps/modules.xml" in result.stdout
    # $PROJECT_DIR$ on its own is fine and must not be reported.
    assert "$PROJECT_DIR$/com.example.foo.msd" not in result.stdout


def test_fix_rewrites_relative_to_project_dir(repo):
    result = run_check(repo, "--fix")
    assert result.returncode == 1  # fixers exit non-zero when they change files

    # macro == repo root, re-expressed relative to the project dir
    # code/com.example.foo: a sibling under code/ is one level up, a path at the
    # repo root is two.
    assert 'value="$PROJECT_DIR$/../platform/com.example.lib"' in read(libraries(repo))
    assert 'path="$PROJECT_DIR$/../../tools/Debugger/Debugger.msd"' in read(modules(repo))
    # An existing $PROJECT_DIR$ path is left untouched.
    assert 'path="$PROJECT_DIR$/com.example.foo.msd"' in read(modules(repo))
    assert "${" not in read(libraries(repo))
    assert "${" not in read(modules(repo))


def test_fix_is_idempotent(repo):
    run_check(repo, "--fix")
    second = run_check(repo, "--fix")
    assert second.returncode == 0
    assert second.stdout == ""


def test_root_level_libraries_xml_is_scanned(tmp_path):
    # .mps/libraries.xml at the repo root: a path variable there must be reported.
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    write(os.path.join(root, ".mps/libraries.xml"), LIBRARIES_XML)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    result = run_check(root)
    assert result.returncode == 1
    assert "libraries.xml" in result.stdout


def test_passed_file_scopes_the_check(repo):
    # Make modules.xml clean; libraries.xml still has a variable. Checking only
    # modules.xml passes; checking libraries.xml reports it.
    write(
        modules(repo),
        MODULES_XML.replace(
            "${my.repo.home}/tools/Debugger/Debugger.msd",
            "$PROJECT_DIR$/../../tools/Debugger/Debugger.msd",
        ),
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    clean = run_check(repo, os.path.join(PROJECT, ".mps/modules.xml"))
    assert clean.returncode == 0, clean.stdout + clean.stderr
    reported = run_check(repo, os.path.join(PROJECT, ".mps/libraries.xml"))
    assert reported.returncode == 1
    assert "libraries.xml" in reported.stdout
