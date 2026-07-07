# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-07-07

### Added

- `mps-check-language-versions` — reports model files (`*.mps` / `.model`) whose `<languages>` header uses a language
  with `version="-1"`.
- `mps-check-no-test-info` — reports model files (`*.mps` / `*.mpsr`) whose registry instantiates the
  `jetbrains.mps.lang.test` TestInfo concept, matched by language and concept id.
- `mps-check-well-formed-xml` — reports MPS XML files that do not parse as well-formed XML, catching empty, truncated,
  and conflict-marked files. It is a zero-configuration wrapper over the
  [`check-xml`](https://github.com/pre-commit/pre-commit-hooks) hook from `pre-commit/pre-commit-hooks`, which is now a
  dependency.

### Changed

- Every XML-parsing hook now skips a file it cannot parse instead of failing the whole run; reporting malformed XML is
  `mps-check-well-formed-xml`'s job.

### Removed

- `mps-check-zero-sized-xmls`, superseded by `mps-check-well-formed-xml`. Configurations referencing the old id must
  switch to the new one.

## [0.1.0] - 2026-06-29

Initial release.

### Added

- `mps-check-orphan-modules`
- `mps-check-unbuilt-modules`
- `mps-check-missing-modules` / `mps-fix-missing-modules`
- `mps-check-orphan-models`
- `mps-check-orphan-mpsr-files`
- `mps-check-zero-sized-xmls`
- `mps-check-module-naming`
- `mps-check-path-variables` / `mps-fix-path-variables`

[0.2.0]: https://github.com/specificlanguages/mps-pre-commit-hooks/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/specificlanguages/mps-pre-commit-hooks/releases/tag/v0.1.0
