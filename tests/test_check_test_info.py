"""Tests for the TestInfo ban.

Each builds a throwaway git repository: the check discovers models through
`git ls-files`, so the fixtures have to be real, tracked files."""

import os
import subprocess

import pytest

from support import run_module, write

TEST_LANGUAGE_ID = "8585453e-6bfb-4d80-98de-b16074f1d86c"
TEST_INFO_CONCEPT_ID = "5097124989038916362"


def language(lang_id, name, *concepts):
    entries = "\n".join(f"      {c}" for c in concepts)
    return f'    <language id="{lang_id}" name="{name}">\n{entries}\n    </language>'


def concept(concept_id, name):
    return f'<concept id="{concept_id}" name="{name}" flags="ng" index="xx" />'


TEST_INFO = concept(TEST_INFO_CONCEPT_ID, "jetbrains.mps.lang.test.structure.TestInfo")
NODES_TEST_CASE = concept("1216913645126", "jetbrains.mps.lang.test.structure.NodesTestCase")


def model(*languages):
    registry = "\n".join(languages)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model ref="r:59f5b892-a6eb-4a9b-9c81-ecffc10026ee(jetbrains.mps.example)">\n'
        '  <persistence version="9" />\n'
        "  <registry>\n"
        f"{registry}\n"
        "  </registry>\n"
        "</model>\n"
    )


def run_check(repo, *args):
    return run_module("check_test_info", repo, *args)


@pytest.fixture
def repo(tmp_path):
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def add(repo):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)


def test_test_info_concept_is_reported(repo):
    write(
        os.path.join(repo, "solution/models/example.mps"),
        model(language(TEST_LANGUAGE_ID, "jetbrains.mps.lang.test", TEST_INFO)),
    )
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert "solution/models/example.mps" in result.stdout


def test_test_language_without_test_info_passes(repo):
    write(
        os.path.join(repo, "solution/models/clean.mps"),
        model(language(TEST_LANGUAGE_ID, "jetbrains.mps.lang.test", NODES_TEST_CASE)),
    )
    add(repo)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_mpsr_file_is_checked(repo):
    write(
        os.path.join(repo, "solution/models/roots.mpsr"),
        model(language(TEST_LANGUAGE_ID, "jetbrains.mps.lang.test", TEST_INFO)),
    )
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert "solution/models/roots.mpsr" in result.stdout


def test_look_alike_name_with_different_id_passes(repo):
    # A concept merely named "...TestInfo" but with a different id is a
    # different concept; matching keys on the id, so this must not trip.
    look_alike = concept("9999999999999999999", "com.example.structure.TestInfo")
    write(
        os.path.join(repo, "solution/models/lookalike.mps"),
        model(language(TEST_LANGUAGE_ID, "jetbrains.mps.lang.test", look_alike)),
    )
    add(repo)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_passed_file_scopes_the_check(repo):
    write(
        os.path.join(repo, "clean/clean.mps"),
        model(language(TEST_LANGUAGE_ID, "jetbrains.mps.lang.test", NODES_TEST_CASE)),
    )
    write(
        os.path.join(repo, "dirty/dirty.mps"),
        model(language(TEST_LANGUAGE_ID, "jetbrains.mps.lang.test", TEST_INFO)),
    )
    add(repo)
    clean = run_check(repo, "clean/clean.mps")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    reported = run_check(repo, "dirty/dirty.mps")
    assert reported.returncode == 1
    assert "dirty/dirty.mps" in reported.stdout
