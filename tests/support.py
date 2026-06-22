"""Shared helpers for the hook tests.

Each hook runs as `python -m mps_pre_commit_hooks.check_*`; the tests invoke it
the same way against a throwaway git repo. The package is made importable through
PYTHONPATH rather than an install, so a checkout can be tested without one."""

import os
import subprocess
import sys

SRC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")


def run_module(module, repo, *args):
    """Run mps_pre_commit_hooks.<module> as `python -m` inside `repo`."""
    env = {**os.environ, "PYTHONPATH": SRC}
    return subprocess.run(
        [sys.executable, "-m", f"mps_pre_commit_hooks.{module}", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        env=env,
    )


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()
