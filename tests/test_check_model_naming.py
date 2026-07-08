"""Tests for the model naming-consistency check.

Each builds a throwaway git repository: the check discovers models and model
roots through `git ls-files`, so the fixtures have to be real, tracked files."""

import os
import subprocess

import pytest

from support import run_module, write

# A solution `foo.bar` with a default model root at models/.
SOLUTION = """\
<solution name="foo.bar" uuid="11111111-1111-1111-1111-111111111111">
  <models>
    <modelRoot contentPath="${module}" type="default">
      <sourceRoot location="models" />
    </modelRoot>
  </models>
</solution>
"""

# A language `NewLanguage` with a model root at models/ and one embedded generator
# `NewLanguage.generator` whose own model root is generator/templates/.
LANGUAGE = """\
<language namespace="NewLanguage" uuid="22222222-2222-2222-2222-222222222222">
  <models>
    <modelRoot contentPath="${module}" type="default">
      <sourceRoot location="models" />
    </modelRoot>
  </models>
  <generators>
    <generator alias="main" namespace="NewLanguage.generator" uuid="33333333-3333-3333-3333-333333333333">
      <models>
        <modelRoot contentPath="${module}/generator" type="default">
          <sourceRoot location="templates" />
        </modelRoot>
      </models>
    </generator>
  </generators>
</language>
"""


def model(name):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<model ref="r:59f5b892-a6eb-4a9b-9c81-ecffc10026ee({name})">\n'
        '  <persistence version="9" />\n'
        "</model>\n"
    )


def run_check(repo, *args):
    return run_module("check_model_naming", repo, *args)


@pytest.fixture
def repo(tmp_path):
    root = str(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    return root


def add(repo):
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)


def solution(repo):
    write(os.path.join(repo, "foo.bar/foo.bar.msd"), SOLUTION)


def language(repo):
    write(os.path.join(repo, "NewLanguage/NewLanguage.mpl"), LANGUAGE)


# -- the four accepted layouts, for a model foo.bar.baz.quux in module foo.bar --


@pytest.mark.parametrize(
    "path",
    [
        "foo.bar/models/foo.bar.baz.quux.mps",  # full name, dotted
        "foo.bar/models/baz.quux.mps",  # module name truncated, dotted
        "foo.bar/models/foo/bar/baz/quux.mps",  # full name, directories
        "foo.bar/models/baz/quux.mps",  # truncated, directories
    ],
)
def test_accepted_layouts_pass(repo, path):
    solution(repo)
    write(os.path.join(repo, path), model("foo.bar.baz.quux"))
    add(repo)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize(
    "path",
    [
        "foo.bar/models/foo.bar.baz.quux/.model",  # full name, dotted directory
        "foo.bar/models/baz/quux/.model",  # truncated, directories
    ],
)
def test_accepted_layouts_pass_for_per_root_model(repo, path):
    solution(repo)
    write(os.path.join(repo, path), model("foo.bar.baz.quux"))
    add(repo)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


# -- rejected layouts --


def test_partial_module_truncation_is_reported(repo):
    # Dropping only part of the module name (foo. of foo.bar) is not allowed.
    solution(repo)
    write(os.path.join(repo, "foo.bar/models/bar.baz.quux.mps"), model("foo.bar.baz.quux"))
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert "foo.bar/models/bar.baz.quux.mps" in result.stdout
    assert "foo.bar.baz.quux" in result.stdout


def test_unrelated_file_name_is_reported(repo):
    solution(repo)
    write(os.path.join(repo, "foo.bar/models/somethingElse.mps"), model("foo.bar.baz.quux"))
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert "foo.bar/models/somethingElse.mps" in result.stdout


def test_misnamed_per_root_model_is_reported(repo):
    solution(repo)
    write(os.path.join(repo, "foo.bar/models/wrong/.model"), model("foo.bar.baz.quux"))
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert "foo.bar/models/wrong/.model" in result.stdout


# -- a language's own models are checked by file layout, like a solution's --


def test_language_model_matches_language_namespace(repo):
    language(repo)
    write(os.path.join(repo, "NewLanguage/models/structure.mps"), model("NewLanguage.structure"))
    add(repo)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


# -- embedded generator models are only checked to be under the language namespace,
#    not for their file layout (the generator/template folder makes it unpredictable) --


def test_generator_model_under_language_namespace_passes(repo):
    # The name is namespaced under NewLanguage; the truncated file name is not
    # checked, so main@generator.mps under generator/templates is accepted.
    language(repo)
    write(
        os.path.join(repo, "NewLanguage/generator/templates/main@generator.mps"),
        model("NewLanguage.generator.template.main@generator"),
    )
    add(repo)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_generator_model_named_exactly_after_language_passes(repo):
    # A model named `<language>@generator`, with no `.generator` infix, is the
    # language namespace itself plus a stereotype -- it is under the language.
    language(repo)
    write(
        os.path.join(repo, "NewLanguage/generator/templates/whatever.mps"),
        model("NewLanguage@generator"),
    )
    add(repo)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_generator_model_with_non_namespaced_name_is_reported(repo):
    # A bare, non-unique name like main@generator is not under the language.
    language(repo)
    write(os.path.join(repo, "NewLanguage/generator/templates/main@generator.mps"), model("main@generator"))
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert "NewLanguage/generator/templates/main@generator.mps" in result.stdout
    assert "NewLanguage" in result.stdout


def test_generator_model_from_another_language_is_reported(repo):
    # A template left over from another language, sitting in NewLanguage's generator.
    language(repo)
    write(
        os.path.join(repo, "NewLanguage/generator/templates/main@generator.mps"),
        model("OtherLang.generator.template.main@generator"),
    )
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert "OtherLang.generator.template.main@generator" in result.stdout


# -- interactions with the rest of the repository --


def test_model_outside_any_root_is_left_to_orphan_check(repo):
    # A model outside every declared model root is mps-check-orphan-models' job;
    # this check has no root to measure the name against, so it stays silent.
    solution(repo)
    write(os.path.join(repo, "foo.bar/stray.mps"), model("whatever.name"))
    add(repo)
    result = run_check(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout == ""


def test_malformed_file_is_skipped_not_crashed(repo):
    solution(repo)
    write(os.path.join(repo, "foo.bar/models/broken.mps"), "")
    write(os.path.join(repo, "foo.bar/models/somethingElse.mps"), model("foo.bar.baz.quux"))
    add(repo)
    result = run_check(repo)
    assert result.returncode == 1
    assert result.stderr == "", result.stderr
    assert "foo.bar/models/somethingElse.mps" in result.stdout


def test_passed_file_scopes_the_check(repo):
    solution(repo)
    write(os.path.join(repo, "foo.bar/models/baz.quux.mps"), model("foo.bar.baz.quux"))
    write(os.path.join(repo, "foo.bar/models/somethingElse.mps"), model("foo.bar.baz.quux"))
    add(repo)
    clean = run_check(repo, "foo.bar/models/baz.quux.mps")
    assert clean.returncode == 0, clean.stdout + clean.stderr
    reported = run_check(repo, "foo.bar/models/somethingElse.mps")
    assert reported.returncode == 1
    assert "foo.bar/models/somethingElse.mps" in reported.stdout
