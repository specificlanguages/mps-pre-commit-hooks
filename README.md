# mps-pre-commit-hooks

Reusable [pre-commit](https://pre-commit.com) / [prek](https://github.com/j178/prek) hooks for
[JetBrains MPS](https://www.jetbrains.com/mps/) projects.

MPS keeps a lot of its project structure in files that are easy to leave in an inconsistent state by hand or by a bad
merge: a module added on disk but never registered in `.mps/modules.xml`, a model dropped outside every model root, a
descriptor renamed but not its folder. MPS silently ignores most of these, so the mistake only surfaces much later.
These hooks catch them at commit time.

## Usage

Add the repo to your project's `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/specificlanguages/mps-pre-commit-hooks
    rev: v0.2.0
    hooks:
      - id: mps-check-orphan-modules
      - id: mps-check-unbuilt-modules
      - id: mps-check-missing-modules
      - id: mps-check-orphan-models
      - id: mps-check-orphan-mpsr-files
      - id: mps-check-well-formed-xml
      - id: mps-check-language-versions
      - id: mps-check-no-test-info
      - id: mps-check-banned-model-names
      - id: mps-check-module-naming
      - id: mps-check-path-variables
```

Then `pre-commit install` (or just `prek install`). The hooks work the same under both runners.

Each hook is independent — enable only the ones you want. They all scan the whole repository (not just the staged
files), since most of what they check are cross-file relationships. The structural checks (orphans, and missing/dangling
references) run on **every** commit, because the problem they catch is often introduced by a commit that only _deletes_
a file — which pre-commit would otherwise skip them for. The per-file content checks (well-formed-xml, naming, path
variables) run only when a relevant file is added or changed.

## Hooks

### `mps-check-orphan-modules`

Reports **orphan modules** — `*.msd` / `*.mpl` / `*.devkit` / `*.mpst` files present on disk but not registered in any
`.mps/modules.xml`. MPS opens a project from its `modules.xml`, so it silently ignores an unregistered module, and the
mistake otherwise surfaces only much later.

### `mps-check-unbuilt-modules`

Reports **unbuilt modules** — modules that are not mentioned in any MPS build script.

Exclude demo and sandbox modules with `--exclude`:

```yaml
- id: mps-check-unbuilt-modules
  args: [--exclude=/code/applications, --exclude=_spreferences, --exclude=*.sandbox.msd]
```

### `mps-check-missing-modules` / `mps-fix-missing-modules`

The reverse of the orphan-modules check: reports `.mps/modules.xml` entries whose `modulePath` points to a file that no
longer exists on disk (typically left behind when a module is moved or deleted). Entries addressed through a path
variable are ignored.

`mps-check-missing-modules` is read-only — it reports and fails. `mps-fix-missing-modules` removes the dangling
`<modulePath>` entries from their `modules.xml`; use it when you want the hook to repair them for you:

```yaml
- id: mps-fix-missing-modules
```

These are defined as separate hooks because the `check` hook may run in parallel with other read-only hooks whereas the
`fix` hook requires serial execution (`require_serial: true`).

### `mps-check-orphan-models`

Reports model files (`*.mps` / `*.mpsr` / `.model`) living outside every module's declared default model root. A model
outside any root is invisible to MPS — present on disk but never loaded — usually the result of a move that didn't
update the owning module, or a stray copy.

### `mps-check-orphan-mpsr-files`

Reports `*.mpsr` files whose directory has no `.model` header file alongside them. The header describes the model;
without it MPS cannot load the roots, so the model is effectively lost.

### `mps-check-well-formed-xml`

Reports MPS XML files that do not parse as well-formed XML — model files (`*.mps` / `*.mpsr` / `.model`), module
descriptors (`*.msd` / `*.mpl` / `*.devkit` / `*.mpst`), and the per-project `.mps/modules.xml` / `.mps/libraries.xml`.
Besides the zero-byte file left by a botched save, merge, or checkout, this catches a truncated file or one still
carrying Git conflict markers — none of which MPS can load.

This is a thin wrapper over the [`check-xml`](https://github.com/pre-commit/pre-commit-hooks) hook from
`pre-commit/pre-commit-hooks`, pre-pointed at MPS's XML file extensions so it needs no configuration. If you would
rather wire up `check-xml` yourself — or already depend on that repo — enable it directly instead and give it the same
file pattern:

```yaml
- repo: https://github.com/pre-commit/pre-commit-hooks
  rev: v6.0.0
  hooks:
    - id: check-xml
      files: '(\.(msd|mpl|devkit|mps|mpsr|model)$)|((^|/)\.mps/(modules|libraries)\.xml$)'
      types: [file] # override the hook's default types: [xml], which excludes MPS's extensions
```

### `mps-check-language-versions`

Reports model files (`*.mps` / `.model`) whose `<languages>` header uses a language with `version="-1"`. MPS writes `-1`
when it saves a model while the used language's version is unknown — typically because the language module was not on
the path at save time. The model still loads, but the missing version is a latent inconsistency that resurfaces as
spurious diffs or migration problems once the language is available again.

### `mps-check-no-test-info`

Reports model files (`*.mps` / `*.mpsr`) whose registry instantiates the `jetbrains.mps.lang.test` **TestInfo** concept.
The concept is matched by its language and concept id, not its name.

### `mps-check-banned-model-names`

Reports model files (`*.mps` / `.model`) whose qualified name is one you forbid with `--ban`, a repeatable exact match
against the full model name. The name is read from the model's `ref` header, so a model is reported through its `.mps`
or `.model` file regardless of persistence format.

The motivating case is a generator model left with MPS' default unqualified name, `main@generator`: banning it catches
that mistake while leaving a properly namespaced `foo.bar.main@generator` alone.

```yaml
- id: mps-check-banned-model-names
  args: [--ban=main@generator]
```

### `mps-check-module-naming`

Checks that every module descriptor (`*.msd` / `*.mpl` / `*.devkit` / `*.mpst`) agrees with its layout on disk. The
directory and the file must be named after the full module name: `com.example.foo` must be located in
`com.example.foo/com.example.foo.mpl` (likewise for other module types).

Modules can be excluded with `--exclude`, a repeatable glob written like a `.gitignore` pattern:

```yaml
- id: mps-check-module-naming
  args: [--exclude=_spreferences, --exclude=some.lang/sandbox]
```

### `mps-check-path-variables` / `mps-fix-path-variables`

Reports path variables in `.mps/libraries.xml` and `.mps/modules.xml`. Replacing these paths with project-relative paths
makes it easier to check out and open the project.

`mps-check-path-variables` is check-only, it fails if a path variable is found. `mps-fix-path-variables` rewrites the
offending paths in place; use it when you want the hook to repair them for you:

```yaml
- id: mps-fix-path-variables
```

These are defined as separate hooks because the `check` hook may run in parallel with other read-only hooks whereas the
`fix` hook requires serial execution (`require_serial: true`).

The fix **assumes the macro's value is the Git repository root** and re-expresses the whole path relative to
`$PROJECT_DIR$`:

```
${mbeddr.github.core.home}/code/platform/com.mbeddr.doc
→ $PROJECT_DIR$/../../platform/com.mbeddr.doc
```

> **Caveat.** This assumption holds for the common case where a variable points at the project's own checkout root. In
> other cases the rewritten path will be incorrect. Like other pre-commit fixers, the hook exits non-zero when it
> changes files, so you re-stage them deliberately.

## License

MIT. See [LICENSE](LICENSE).
