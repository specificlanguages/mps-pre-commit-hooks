# MPS model roots and source roots

How a module descriptor tells MPS where to find its models. Full write-up with a diagram:
[model-roots-and-source-roots.html](model-roots-and-source-roots.html). Source links point at JetBrains MPS commit
[`c4689bd`](https://github.com/JetBrains/MPS/tree/c4689bddb9300043a71a0582b9d23d4de519f625) (post-2025.3 `master`).

## The terms

- **Module** — a solution, language, devkit, or generator. Its descriptor (`*.msd`, `*.mpl`, `*.devkit`, `*.mpst`) lists
  its models inside a `<models>` element.
- **Model root** — an entry under `<models>` describing one group of related models and where they come from. It has a
  `type` (e.g. `default`), an optional **content directory**, and a list of **source roots**.
- **Content directory** — a single base path, the `contentPath` attribute. Relative source roots resolve against it.
- **Source root** — a directory MPS reads models from. MPS walks each source root recursively and loads every model file
  it finds; one source root can hold many models.

In one line: a module's models live in directories called source roots; a model root groups source roots under a `type`
and an optional base directory (`contentPath`).

## How a source root gives its path

A source root's path is written in one of two ways:

- **Relative** — a `location` attribute, resolved against `contentPath`. `location="."` refers to the content directory
  itself.
- **Absolute** — a `path` attribute, taken as written after macros (`${module}`, `${mps_home}`) are expanded.

Each source root has a **kind**: `SOURCES` supplies models, `EXCLUDED` marks a subtree to leave out. Loading a `default`
model root reads the `SOURCES` source roots and collects the models under each — see
[`DefaultModelRoot.loadModels()`](https://github.com/JetBrains/MPS/blob/c4689bddb9300043a71a0582b9d23d4de519f625/core/kernel/source/jetbrains/mps/persistence/DefaultModelRoot.java#L140-L158).

## XML shape

From
[`FileBasedModelRoot.save()`](https://github.com/JetBrains/MPS/blob/c4689bddb9300043a71a0582b9d23d4de519f625/core/kernel/source/jetbrains/mps/extapi/persistence/FileBasedModelRoot.java#L196-L235):

```xml
<modelRoot contentPath="${module}" type="default">
  <sourceRoot location="models" />          <!-- SOURCES, relative: resolved against contentPath -->
  <sourceRoot path="${module}/gen" />       <!-- SOURCES, absolute: taken as written -->
  <excluded location="models/generated" />  <!-- EXCLUDED: a subtree to leave out -->
</modelRoot>
```

- `<modelRoot>` carries `type` and, when a content directory is set, `contentPath`.
- Each `SOURCES` source root is a `<sourceRoot>` child; each `EXCLUDED` one is an `<excluded>` child.
- A source root child carries `location` (relative) or `path` (absolute).

Relative source roots dominate in real projects (~1131 `location=` vs ~29 `path=` across MPS-extensions, mbeddr.core,
iets3.opensource).

## Model root types

| `type`                        | Class                                             | Models come from                                                             |
| ----------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------- |
| `default`                     | `DefaultModelRoot`                                | model files you author, under the source roots (`.mps` / `.mpsr` / `.model`) |
| `java_classes`                | `JavaClassStubsModelRoot`                         | compiled Java in `.jar` / `.class` files under the source roots              |
| `jdk`                         | `JDKStubsModelRoot`                               | the configured project JDK (uses no source roots)                            |
| `java_source_stubs`           | `JavaSourceStubModelRoot`                         | Java source files under the source roots                                     |
| `kotlin_jvm`, `kotlin_common` | Kotlin plugin roots                               | Kotlin artifacts under the source roots                                      |
| others                        | PSI Java stub, `property_files_stubs` (sample), … | plugin/sample-specific sources                                               |

A `default` model root holds the models you write and MPS saves to disk. The other types build their models in memory
from compiled code or source files each time the module loads; those generated models appear in other models as
`<import>` references. `jdk` takes its input from the project JDK setting and configures no source roots.

Type constants:
[`PersistenceRegistry`](https://github.com/JetBrains/MPS/blob/c4689bddb9300043a71a0582b9d23d4de519f625/core/kernel/source/jetbrains/mps/persistence/PersistenceRegistry.java#L68-L70).

## What this means for the hooks

- Tracked model files live in `default` model roots, so the hooks read `type="default"` model roots and collect the
  directories of their `SOURCES` source roots.
- To get those directories: resolve each `<sourceRoot location=…>` against `contentPath`, take each
  `<sourceRoot path=…>` as written, expanding `${module}` to the descriptor's directory. A `${mps_home}` path points at
  an MPS installation outside the repository, so the hooks leave it as written and it matches no tracked model.
- A model belongs to a module when it sits under one of the module's source roots. A model under no source root is what
  `mps-check-orphan-models` reports.
- `mps-check-model-naming` measures a model's file name against its qualified name relative to the source root the model
  sits under.

The directory-collection logic lives in `default_model_root_dirs()` in
[`_common.py`](../../src/mps_pre_commit_hooks/_common.py).
