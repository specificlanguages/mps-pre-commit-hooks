# MPS model IDs and model references

Reference notes for the hooks that read model files, distilled from MPS source
(`jetbrains.mps.persistence.PersistenceRegistry`, `jetbrains.mps.smodel.SModelId`,
`jetbrains.mps.smodel.SModelReference`, `jetbrains.mps.util.StringUtil`) and from scanning real projects (MPS,
MPS-extensions, mbeddr.core, iets3.opensource).

## Model IDs

A model ID serializes as `<designator>:<suffix>`. When parsing a standalone model ID,
`PersistenceRegistry.createModelId` splits on the **first** `:`, looks up an `SModelIdFactory` by the designator, and
hands it the suffix. Unknown designators throw.

`PersistenceRegistry.init()` registers four factories in the core; more can be registered by plugins (see `java` below,
and `ModelFactoryRegister` for others).

| Designator             | Class                                   | Suffix format                                                                                | Globally unique     | Notes                                                                                                                                                                                                                                              |
| ---------------------- | --------------------------------------- | -------------------------------------------------------------------------------------------- | ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `r`                    | `RegularSModelId`                       | a UUID, **or** a decimal `long` that becomes the UUID `00000000-0000-4000-XXXX-XXXXXXXXXXXX` | yes                 | The normal case. `toString` always re-emits canonical UUID form. Produced by `generate()`.                                                                                                                                                         |
| `f`                    | `ForeignSModelId`                       | arbitrary `[kind#]identity` string                                                           | claimed, unenforced | Legacy, explicitly discouraged in the source.                                                                                                                                                                                                      |
| `path`                 | `RelativePathSModelId`                  | a relative path (used verbatim as the model name too)                                        | inherits `true`     | Designator is the whole word `path`.                                                                                                                                                                                                               |
| `i`                    | `IntegerSModelId`                       | hex int, min width 4, zero-padded (`%04x`)                                                   | **no**              | Module-private; MPS reserves `0x0F000000..0xFFFFFFFF`.                                                                                                                                                                                             |
| `m`                    | `ModelNameSModelId`                     | the qualified model name                                                                     | yes                 | **Not a registered factory** — `createModelId("m:…")` throws. Only produced during _reference_ parsing when the id part has no `:`, and then serialized **without** the `m:` prefix. Treat it as a reference construct, not a standalone model ID. |
| `java`                 | `JavaPackageModelId` (`PackageModelId`) | Java package name                                                                            | **no**              | Registered by the java-stub plugin (type = `java`). Backs Java **stub** models generated on the fly from JARs/`.class` files.                                                                                                                      |
| `kotlin`, `kotlin_jvm` | `PackageModelId` variants               | package name                                                                                 | **no**              | Same idea as `java`, contributed by the Kotlin plugin via `ModelFactoryRegister`.                                                                                                                                                                  |

### What is actually used in real projects

Scanning every git-tracked `.mps` / `.model` / `.mpsr` file, splitting a model's **own** id (its `<model ref=…>` header)
from ids that only appear as `<import>` targets:

**As a model's own id (files you author or that MPS generates):**

- `r:` — the overwhelming majority in all four projects. This is _the_ format for hand-authored models. Includes the
  `r:00000000-0000-4000-…` decimal-derived form used by bootstrap/legacy languages.
- `i:` — MPS repo only, and only in **generated** checkpoint models under `source_gen/` (module `checkpoints`). Real
  persisted files, but artifacts, not hand-authored. Always carry a module-id prefix (not globally unique).
- `f:`, `path:`, `m:` — **not seen as an own id anywhere.**

**Only as import targets (never a persisted file's own id):**

- `java:` — very common (JDK, MPS runtime stubs).
- `kotlin:`, `kotlin_jvm:` — rare.

These stub ids (`java`/`kotlin`/`kotlin_jvm`, all `PackageModelId`, `isGloballyUnique() == false`) back package stubs of
compiled code. They are generated in memory from non-MPS sources and are never persisted as MPS model files — they only
appear as `<import>` references, always with a module-id prefix.

**Consequence for the hooks:** for hand-authored models the only own-id format to handle is `r:` (both UUID and
`r:00000000-0000-4000-…` forms). `i:` matters only if MPS-generated `source_gen` checkpoint models are in scope.
`java:`/`kotlin:` etc. are reference-only — tolerate them when walking imports, never expect them as a model's own id.

## Model references

A model id is only the middle of a **model reference**. `SModelReference.parseReferenceInternal` defines the grammar:

```
[ moduleID "/" ] modelID [ "(" [ moduleName "/" ] modelName ")" ]
```

producing four optional slots `[moduleId, modelId, moduleName, modelName]`.

### Parsing

1. Trim. If the string ends in `(…)`, the parenthesized text is the **presentation part**; strip it off. The remainder
   must then contain no parentheses.
2. In the remainder: if there is a `/`, the text before the first `/` is the **module id** and the rest is the **model
   id**. No `/` → no module id, the whole remainder is the model id.
3. Split the presentation part on its first `/`: `moduleName/modelName`, or just `modelName` when there is no `/`.

`PersistenceRegistry.createModelReference` then resolves the pieces:

- **module id** → `createModuleId` if non-blank.
- **model id** → if it contains `:`, dispatch to the factory for its designator; **if it has no `:`, it becomes a bare
  `ModelNameSModelId`** (the only way `m` arises, and it is written without an `m:` prefix).
- **model name** → if omitted/blank, fall back to `modelId.getModelName()`; if that is also null, error. So a reference
  to a bare `r:` id **must** carry a `(name)`, whereas a stub/name/path/integer id can derive its name from the id.

### Serialization (`toString`)

- With a module ref: `escape(moduleId) + "/"`.
- Model id: `ModelNameSModelId` → its bare name; anything else → `modelId.toString()` (`r:…`, `i:…`, `java:…`, …).
- The `(…)` is **omitted entirely** when there is no module ref _and_ the name equals `modelId.getModelName()`.
- Inside the parens: `moduleName/` only if the module ref has a name; the model name only if it differs from
  `modelId.getModelName()` (so a derivable name is not duplicated).

### Escaping (`StringUtil.escapeRefChars`)

Applied to each part independently. Only four characters are percent-escaped as `%XX` (uppercase hex of the char): **`%`
`(` `)` `/`**. Everything else — dots, `@` (stereotype), `#` (foreign kind), spaces — is literal. A `/` inside a model
name therefore becomes `%2f`, keeping it distinct from the structural separators.

### Structural rules worth remembering

- A **non-globally-unique** id (`i:`, `java:`, `kotlin:`) is invalid without a module id — the `SModelReference`
  constructor throws — which is why those always appear as `moduleId/modelId(...)`.
- A globally-unique `r:` reference always needs the `(name)`, because a UUID carries no derivable name.

### The presentation part, and the model _name_

The name a model file exposes is the `<presentation>` inside the parentheses of its header `ref`, which is
`([<moduleName>/]<modelName>)`. The `<moduleName>/` qualifier is present exactly when the reference is serialized with a
module part, which for a model's **own header** happens in two cases:

- **Generator template models** — the header carries the owning generator module, e.g.
  `…/r:db2cea87-…(com.mbeddr.mpsutil.framecell#8760592470372463296/com.mbeddr.mpsutil.framecell.generator.template.main@generator)`.
  Note a generator module's name itself contains `#<number>`.
- **Module-private ids** (not globally unique — e.g. checkpoint `i:` models), which _must_ carry a module reference,
  e.g. `…/i:fd8f593(checkpoints/jetbrains.…typesystem@descriptorclasses)`.

An ordinary globally-unique `r:` model has no module part, so its header is just `(<modelName>)`. To recover the model
name, strip anything before the last `/` in the presentation part; a bare name has none. This is unambiguous because a
`/` inside a name is percent-escaped (`%2f`), so the only literal `/` is the module/model separator.

### Worked examples (from real files)

| Reference                                                            | moduleId     | modelId          | moduleName    | modelName                          |
| -------------------------------------------------------------------- | ------------ | ---------------- | ------------- | ---------------------------------- |
| `r:9832fb5f-…(jetbrains.mps.ide.editor.actions)`                     | –            | `r:9832fb5f-…`   | –             | `jetbrains.mps.ide.editor.actions` |
| `6354ebe7-…/java:java.util(JDK/)`                                    | `6354ebe7-…` | `java:java.util` | `JDK`         | _(empty → derived `java.util`)_    |
| `00000000-…-5beb5f025beb/i:fd8f593(checkpoints/…@descriptorclasses)` | `0000…5beb`  | `i:fd8f593`      | `checkpoints` | `…typesystem@descriptorclasses`    |
