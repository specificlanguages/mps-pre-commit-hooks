#!/usr/bin/env python3
#
# .mpsr model-header check.
#
# A model kept in the per-root persistence format (each root in its own *.mpsr
# file) needs a .model header file alongside it describing the model. Without the
# header MPS cannot load the roots, so the model is effectively lost. This reports
# any tracked *.mpsr root whose directory has no .model header.

from __future__ import annotations

import sys

from ._common import AnchoredGlob, git_ls_files, repo_root


def main() -> int:
    root = repo_root()

    failed = False
    for r in git_ls_files(AnchoredGlob("**/*.mpsr")):
        if ".mps" in r.parts:
            continue
        if not (r.parent / ".model").is_file():
            print(f"{r.relative_to(root).as_posix()}: *.mpsr root in a directory without a .model header")
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
