"""Tests for the shared glob helpers in mps_pre_commit_hooks._common.

These import the package directly rather than running a hook as a subprocess, so
the module source is put on the path the same way support.py does for PYTHONPATH."""

import sys

from support import SRC

if SRC not in sys.path:
    sys.path.insert(0, SRC)

from mps_pre_commit_hooks._common import AnchoredGlob, matches


def test_double_star_within_a_segment_acts_like_single_star():
    # A '**' that is not a whole path component is not recursive; like in a
    # .gitignore, 'a**b' behaves exactly like 'a*b': it matches within one path
    # segment and does not span '/'.
    assert matches("axb", AnchoredGlob("a**b"))
    assert matches("ab", AnchoredGlob("a**b"))
    assert not matches("ax/yb", AnchoredGlob("a**b"))

    for path in ("axb", "ab", "ax/yb", "a/b"):
        assert matches(path, AnchoredGlob("a**b")) == matches(path, AnchoredGlob("a*b"))
