#!/usr/bin/env python3
#
# Module-registration check.
#
# Reports modules (*.msd / *.mpl / *.devkit) that are present on disk but not
# registered in any .mps/modules.xml, so MPS silently ignores them. MPS opens a
# project from its modules.xml, so an unregistered module is invisible -- the
# mistake otherwise surfaces only much later.
#
# Related checks live in their own hooks: whether a shipped module is packaged by
# a build script is mps-check-unbuilt-modules; the reverse direction (modules.xml
# entries pointing at a missing descriptor) is mps-check-missing-modules; models
# outside a model root, mps-check-orphan-models; *.mpsr without a .model header,
# mps-check-orphan-roots; zero-sized XML files, mps-check-zero-sized-xmls; module
# naming, mps-check-module-naming; path variables, mps-check-path-variables.

from __future__ import annotations

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from ._common import (
    MODULE_GLOBS,
    MODULES_XML_GLOBS,
    git_ls_files,
    module_name,
    repo_root,
)


def referenced_modules() -> set[Path]:
    """Module paths registered across all .mps/modules.xml files (absolute)."""
    referenced: set[Path] = set()
    for modules_xml in git_ls_files(*MODULES_XML_GLOBS):
        project_dir = modules_xml.parent.parent
        root = ET.parse(modules_xml).getroot()
        for module_path in root.iter("modulePath"):
            raw = module_path.get("path", "")
            # A modulePath is either $PROJECT_DIR$-relative, addressed through a
            # project-specific variable we can't resolve, or a plain relative path.
            if raw.startswith("$PROJECT_DIR$/"):
                directory = Path(project_dir, raw[len("$PROJECT_DIR$/") :])
            elif raw.startswith("${"):
                continue
            else:
                directory = Path(project_dir, raw)
            # normpath collapses '..' lexically so the entry matches the path git
            # reports for the descriptor on disk.
            referenced.add(Path(os.path.normpath(directory)))
    return referenced


def main() -> int:
    root = repo_root()

    referenced = referenced_modules()

    failed = False
    for module in git_ls_files(*MODULE_GLOBS):
        if module in referenced:
            continue
        name = module_name(ET.parse(module).getroot())
        rel = module.relative_to(root).as_posix()
        print(f"{rel}: module '{name}' not registered in any modules.xml")
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
