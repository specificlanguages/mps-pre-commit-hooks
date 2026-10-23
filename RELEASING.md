# Releasing

Releases are Git tags named `vX.Y.Z`. Users pin the tag through `rev:` in their `.pre-commit-config.yaml`, so the tag
must point at a commit that already contains the version bump and the changelog entry.

1. Start from an up-to-date `main` (or a branch that will be merged into `main` before tagging).
2. Choose the new version following [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
3. Update `CHANGELOG.md`:
   - Rename the `[Unreleased]` entries into a new `## [X.Y.Z] - YYYY-MM-DD` section and leave an empty `## [Unreleased]`
     above it.
   - Update the link references at the bottom: `[Unreleased]` compares `vX.Y.Z...HEAD`, and add `[X.Y.Z]` comparing the
     previous tag with `vX.Y.Z`.
4. Set `version` in `pyproject.toml` to `X.Y.Z`.
5. Run `uv lock` so the `mps-pre-commit-hooks` entry in `uv.lock` gets the new version.
6. Update `rev:` in the usage example in `README.md` to `vX.Y.Z`.
7. Run the checks:

   ```bash
   uv run pytest
   ```

8. Commit as `Bump version to X.Y.Z`, push, and merge to `main`.
9. Tag the merge commit on `main` and push the tag:

   ```bash
   git tag -a vX.Y.Z -m "Release X.Y.Z"
   git push origin vX.Y.Z
   ```

Never move or delete a tag after pushing it, since users may already have it cached. If a tag was created too early,
release the next patch version instead and mention it in the changelog.
