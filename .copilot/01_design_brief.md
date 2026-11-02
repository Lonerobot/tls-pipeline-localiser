# 01 — Design Brief: Pipeline Localiser

Supersedes the original eight-file brief (see git history, commit `13af442`). Scope was deliberately narrowed after discussion; AYON, project overrides and manifest signing are out of scope for v1.

## 1. Problem

Studio pipeline code for each DCC (Maya, Blender, Nuke) lives on a network share. Loading many small files over the network slows DCC startup. We want each DCC to load a **local copy** of a versioned pipeline release, with the Python path pointing at that local copy.

What is *inside* a pipeline release is out of scope. The localiser only moves a release from the share to local disk and makes the DCC see it.

## 2. Scope

### In scope (v1)
- A **release** is a single zip per DCC pipeline, published to the network share with a SHA-256.
- A small JSON on the share names the default release per DCC.
- A host-independent, stdlib-only Python core: resolve → check local → sync if missing.
- A thin per-DCC stub that calls the core and then exposes the local release to the host.
- A one-time local install script that places the core and stubs in a stable local location.
- A publisher script that builds a release zip and manifest from a source folder.
- A TD override (env var) that replaces the default release for one DCC.
- Offline use of the last successfully read studio config and already-cached releases.

### Out of scope (v1, deliberately deferred)
- AYON addon / pre-launch hook (longer-term goal; it must later call the same core, not reimplement it).
- Project-specific release selection.
- Manifest signing / full trust model (mitigated by write-protecting the share; see §9).
- Mutable working-tree "dev mode".
- Auto-updating a running DCC, parallel extraction, delta updates, cache cleanup policy.

## 3. Architectural invariants

1. **One effective release per DCC process.** An override replaces the default; two pipeline roots are never active.
2. **Independent per-DCC versioning.** Changing Maya's release never affects Blender or Nuke.
3. **Release IDs are immutable and opaque.** A fix means a new ID. No ordering is inferred.
4. **A release exists locally iff its `.complete` marker exists.** Written last, after validation and atomic publish.
5. **Install via staging, publish atomically.** Never expose a partial release; never modify a published release directory in place.
6. **Explicit overrides never fall back silently.** If the requested release is unavailable, fail clearly with host and release ID.
7. **Cheap fast path.** An already-localised launch does only small local reads: no network traversal, no hashing of installed files.
8. **The core imports no DCC modules and no pipeline modules.**
9. **Stub and core live outside any release.** Otherwise bootstrap is circular.
10. **Select, localise, expose are separate steps** (resolver, core, host adapter).

## 4. Components

| Component | Responsibility |
|---|---|
| **Core** (`localiser/`) | Config parsing/validation, resolution, cache query, copy + verify + extract + publish, locking, state, logging. No host imports. |
| **Host stubs** (`bootstrap/<dcc>/`) | Tiny, stdlib-only, idempotent. Call the core, then expose the local root to the host in the way that host requires. |
| **Install script** | One-time/idempotent local setup: create cache dirs, copy core + stubs to the stable local location, wire each DCC's discovery mechanism. |
| **Publisher** (`publisher/`) | Zip a source folder → compute SHA-256 → write manifest → place on share. Refuses to overwrite an existing release ID. |
| **Repair/status CLI** | `status` (cached releases + validity), `resync <host> [release]` (transactional reinstall). Small, may follow core. |

Layout is conceptual; adjust to repo conventions once code exists.

## 5. Data and layout

### Network share (write-protected)
```text
pipeline-repository/
  config/studio-pipelines.json
  releases/<package_id>/<release_id>/
    pipeline.zip
    manifest.json
```

### Studio config (`studio-pipelines.json`)
```json
{ "schema_version": 1,
  "pipelines": { "maya": "2.9.0", "blender": "1.14.0", "nuke": "3.2.4" } }
```
Unknown schema version or malformed content is an error — never guess. Version strings are illustrative.

### Manifest (`manifest.json`)
```json
{ "schema_version": 1, "package_id": "maya-tools", "release_id": "2.9.0",
  "artifact": "pipeline.zip", "sha256": "<64 hex>", "python_root": "." }
```
`python_root` is **optional, default `"."`**. It is the path inside the extracted release that the host stub adds. It exists to cover edge cases (e.g. a zip with a top-level folder, or Nuke's `core/` subfolder). Where the release root is enough, omit it: the pipeline code resolves its own further paths. Add fields only on evidence.

**Contract principle:** the localiser's job ends at "here is a verified local release root". It does not know about toolchains, templates or sub-paths. The pipeline inside the release derives everything else from its own location (`__file__`) or from the root the localiser exposes.

### Local cache (per-user app data; Windows: `%LOCALAPPDATA%/TheLine/Pipeline/`)
```text
bootstrap/                     # stable: core module + stubs (NOT inside a release)
releases/<package_id>/<release_id>/.complete   (+ extracted files)
state/<host>.json              # per-DCC cache of last resolution: release_id, root, installed_at
state/studio-pipelines.json    # last-known-good copy of studio config
staging/  locks/  logs/
```

### Where "complete" state lives
- **Source of truth:** the `.complete` marker inside the release directory.
- **`state/<host>.json` is a convenience cache**, one file per DCC to avoid cross-DCC write conflicts, written atomically under the lock. If it disagrees with the filesystem, the filesystem wins.
- **Not** a single shared `config.json`: concurrent DCCs/instances would race on read-modify-write.
- The last-known-good studio config and local install state are separate files with separate lifecycles.

## 6. Runtime flow

1. **Install script (once):** create the cache tree; copy core + stubs to `bootstrap/`; wire each DCC (§8). A stub that finds no local cache or core treats it as first run and reports clearly.
2. **DCC starts → stub runs** (idempotent: guard against double execution).
3. **Resolve release:** override env var (`STUDIO_PIPELINE_<DCC>`) if set, else studio config for that DCC (network, falling back to last-known-good with a stale-config warning).
4. **Check local:** `releases/<pkg>/<id>/.complete` present? If yes → step 6.
5. **Sync (under per-release lock):**
   1. Create unique staging dir on the same filesystem as `releases/`.
   2. Copy `pipeline.zip` + `manifest.json` from share; confirm manifest identity matches package and release ID.
   3. Verify SHA-256 of the zip.
   4. Validate every member path before extraction (reject absolute, `..`, drive letters; decide symlink policy).
   5. Extract to staging; confirm `python_root` exists.
   6. Write `.complete`, atomically rename staging → final dir, update `state/<host>.json`.
   7. Release lock; clean abandoned staging when safe.
   If another process holds the lock, wait briefly then re-check for `.complete`; otherwise return a controlled timeout error.
6. **Expose:** stub adds `<release root>/<python_root>` to the host (§8). Log host, release ID, selection source (`studio` | `override` | `last_known_config`), root, outcome, elapsed time.

### Failure / offline behaviour
| Situation | Behaviour |
|---|---|
| Share config unreachable, vanilla launch | Use last-known-good config + cached release; log stale config. |
| Share unreachable, release not cached | Fail with clear message; do not load anything else. |
| Override release missing/unavailable | Fail clearly; no fallback to studio default. |
| Checksum mismatch / bad manifest / unsafe zip | Abort; nothing published; existing releases untouched. |
| Interrupted install | Staging ignored; retried/cleaned later. |
| State says installed but directory/marker missing | Treat as not installed; reinstall under lock. |
| Concurrent install of same release | Wait for lock, reuse result; never write the final dir concurrently. |
| Localiser/stub missing or damaged | Documented per-DCC failure message; install script repairs. |

Forced resync reinstalls transactionally under the same ID **only to restore identical verified content**; it never changes content behind an ID and never touches a directory another process may be using (publish to a replacement path or only when safe — detail in design phase).

## 7. Override policy (v1)

- Precedence: **override env var → studio default** (per DCC).
- `STUDIO_PIPELINE_<DCC>=<release_id>` replaces the release for that DCC only. Override use is logged prominently.
- Changing `os.environ` inside a running DCC does not retroactively fix inherited environment or already-imported modules; overrides must be set before the DCC process starts.
- Project (AYON) selection will slot in later between these two; it is not designed here.

## 8. Host exposure (to be verified against the installed DCC versions — do not assume)

| DCC | Proposed mechanism | To verify |
|---|---|---|
| **Maya** | Core pipeline = one folder (`v1.1.0/`) whose root goes on the Python path (`python_root` = `.`). A small **stub `userSetup.py` in a stable local directory** (on `PYTHONPATH`, outside any release) localises, then does `sys.path.insert(0, root)` once (idempotent). AYON-supplied tools untouched. See §8.2. | Which `userSetup.py` Maya actually runs when several are on the path; how `MAYA_CORE` is consumed and when (§8.2); supported Maya/Python versions (reference says Maya 2026 / Py 3.11; `__pycache__` in the folder shows 3.7–3.11 history). |
| **Nuke** | `NUKE_PATH` points at a **stable local stub directory** whose `init.py` localises, then calls `nuke.pluginAddPath(<release root>/<python_root>)` (expected `core/` inside the bundle). The stub path never changes between releases; only the resolved root does. Everything the pipeline needs must be set up in `init.py` (application start); `menu.py` only runs when the UI loads, which is too late. The source of `NUKE_PATH` (AYON env injection, or a system env var outside AYON) doesn't affect the design. See §8.1. | Whether `pluginAddPath` called from the stub's `init.py` makes Nuke run the added directory's `init.py` (and later `menu.py`) in the right order; Nuke Python version(s). |
| **Blender** | **5.0+ only; vanilla launches in scope.** Use the documented studio-deployment route: `BLENDER_SYSTEM_SCRIPTS` points at a **stable local stub script directory** (the install script sets it as a user environment variable, same pattern as Nuke's `NUKE_PATH`). Its `startup/` stub runs at Blender start, localises, then exposes the release (a scripts directory with `addons/`, `presets/`). No `--python` argument and no preference writes required. How the stub exposes the release in-session is the key item to test. See §8.3. | Whether a script directory (or `sys.path` / add-on path) added at runtime by the stub is honoured **in the same session** for add-ons and presets (the 5.0 manual says script-directory preference changes need a restart); that AYON does not already set `BLENDER_SYSTEM_SCRIPTS`; Python 3.13 syntax. |

### 8.1 Nuke pipeline refactor (finding from `reference/nuke/init.py`)

The existing Nuke `init.py` was written for a globally shared, versioned core and couples itself to the **share layout**:

- It parses `NUKE_PATH` to find the core folder, then infers `TLA_COMP_PIPELINE_ROOT` as the parent of `core/` (`.../nuke/core/X.X.X` → `.../nuke`) and `TLA_COMP_TOOLCHAINS` as `<root>/toolchains`.
- It has heuristics for AYON's `;`-separated `NUKE_PATH` (picks the entry containing `PIPELINE` plus `core` or a digit).
- It derives the displayed version from the last folder name of `NUKE_PATH`.
- It has hardcoded `Y:/PIPELINE/config/nuke/...` fallbacks.

Every one of these breaks (or silently produces wrong roots) once the code runs from `.../releases/<package>/<release_id>/`. With bundles, `core` and `toolchains` ship together in one immutable release, so the versioned `core/X.X.X` folder is no longer needed. Proposed pipeline-side changes (separate from the localiser, owned by the Nuke pipeline):

1. Derive the root from `Path(__file__)` (init.py's own location), not from parsing `NUKE_PATH`. Bundle layout becomes `<release>/core/…` and `<release>/toolchains/…`; `TLA_COMP_PIPELINE_ROOT` = `<release>`, `TLA_COMP_TOOLCHAINS` = `<release>/toolchains`.
2. Remove the AYON `;`-list heuristic and the hardcoded `Y:/PIPELINE` fallbacks; fail with a clear message instead of guessing.
3. Take the displayed version from the release ID exposed by the localiser (or a version file in the bundle), not a folder name.
4. `config.json` (debug flag) is read from inside the immutable release. Needs a local/user override (env var or local file) if debug must be switchable without a new release.

Unchanged and fine: the filename filter (registered early), env var export, reporter/logger setup.

Questions this raises (resolved): the Nuke bundle is a copy of the current pipeline as it stands (`core/` + `toolchains/`); toolchain/build consolidation is out of scope.

### 8.2 Maya findings (from `reference/maya/`)

Confirmed from the reference:
- The release is a plain folder of scripts. `mayaScriptLibrary.py` sits at its root and is the only code the host must import; everything else runs through `run_script(section, module)`, which resolves paths from its own `__file__`. It is **location-independent**, so a local copy works unchanged with `python_root = "."`.
- `mayaScriptLibrary.generate_pype_menu()` writes `corescripts_template.json` (menu definition; commands are relative, no absolute paths) into the release root. This is a **publish-time step**: the publisher must run it before zipping. Nothing may write into a localised release at runtime. A search of the release found no other runtime writes into the release folder (`CreateTaskOverride` writes to `AYON_WORKDIR`).
- `userSetup.py` lives **outside** the release and is on the Python path alongside the core folder. It does very little: prints a banner and the `AYON_VERSION`, and registers deferred calls (e.g. `disable_evaluator('invisibility')`). It never imports `mayaScriptLibrary`.
- The existing `userSetup.py` already satisfies "stub lives outside the managed release". It is the natural home for the localiser call.

Implications:
1. Only `userSetup.py` (the stub) needs to be on `PYTHONPATH` at launch. The core folder entry is replaced by the localised root added by the stub.
2. The localised root must be on the path **before anything imports `mayaScriptLibrary`**. Menu commands import it lazily on click, so this is likely safe, but see the open question on `MAYA_CORE`.
3. Publisher should exclude `__pycache__/`, `*.pyc` and `Thumbs.db` (present in the reference folder).
4. Optional later refactor (not required): move the version-specific startup behaviour (evaluator disable, shot override) from `userSetup.py` into the release so it is versioned, leaving `userSetup.py` as a minimal stub that localises, then calls a startup function in the release. Needs a decision; otherwise `userSetup.py` stays as-is plus the localiser call.
5. Print the localiser's release ID in the startup banner alongside `AYON_VERSION`.

Stub constraints: the reference uses the walrus operator (Python 3.8+), so the Maya stub can use Python 3.8+ syntax if only current Maya versions are supported. Confirm supported versions.

### 8.3 Blender findings (from `reference/blender/` and the Blender 5.0 manual)

Decided: **Blender 5.0+ only** (no backward compatibility) and **vanilla launches are in scope**.

Current launch (stated by user): AYON runs Blender with `--python-use-system-env --python Y:/PIPELINE/config/blender/_core/2.0.0/startup.py`. The reference `startup.py` is WIP because 5.0 changed script-directory handling. A `--python` argument cannot serve as the bootstrap going forward: local files live in a user account (so shared AYON settings can't hardcode the path), and vanilla launches have no such argument.

Confirmed from the reference:
- `startup.py` itself lives on the share inside a **versioned** `_core/<version>/` folder, so today the bootstrap is part of what is versioned. Under the localiser the bootstrap must be a **stable local file outside any release**. Reading even one file from the share at every launch would keep the network dependency and break offline use.
- The pipeline is exposed by AYON setting `BLENDER_CORE_ADDONS`; `set_pipeline_location()` adds a script directory named `THELINE_PIPELINE` to the user preferences. The release is therefore a **Blender scripts directory** (`addons/`, `presets/`) rather than a `sys.path` root.
- **Stale-path hazard:** `set_pipeline_location()` only checks whether an entry with that name already exists; it never updates its `directory`. Once a release path changes (any versioned or localised path), the persisted preference keeps pointing at the old location. The localiser design must *update* the entry's directory on every launch (idempotently, without duplicating entries), or avoid persisting a changing path.
- `studio_environment_startup` is an add-on in the release (registers a `load_post` handler, shot override and asset library setup). Enabling it with `persistent=True` also stores state in user preferences; an enabled add-on whose script directory is stale or missing will fail to load at the next start. `enable_startup_addon()` is currently commented out in `startup.py`.
- `startup.py` also does **Blender-installation setup unrelated to the release**: sets `QT_API=pyside6` before AYON imports Qt, and pip-installs PySide6 into Blender's own `site-packages`, with a UAC elevation retry (Windows-only: `ctypes.windll`, `python.exe`). This is a first-run/environment concern, not release content. It should not move into the versioned release, and is a candidate for the install script or the stable stub. Decision needed; the localiser itself stays out of it.
- `__pycache__` folders in the reference are `cpython-313`, consistent with Blender 5.0 on Python 3.13 (inference from the bytecode tag, not a stated fact). The publisher must exclude them.

Confirmed from the Blender 5.0 manual (Deploying Blender in Production; Blender's Directory Layout; Preferences → File Paths):
- **`$BLENDER_SYSTEM_SCRIPTS` is the documented way to add a script directory without modifying preferences**, intended for studio deployment. It may contain `startup/`, `addons/`, `modules/`, `presets/`. `.py` files in `startup/` are imported at startup; the manual's own example is a startup script that enables add-ons for every user via `addon_utils.enable()`.
- **Script-directory preference changes need a Blender restart** to take effect ("You have to restart Blender for all changes to the users scripts to take effect"). This matches the "callbacks don't run until the next start" quirk noted in the reference `startup.py`. A stub that localises at startup and then adds the release as a script directory at runtime may therefore not get its `addons/`/`presets/` picked up in the same session, and a persisted entry would lag one launch behind a release change. This is the main risk to test.
- Add-on `modules/` folders are added to `sys.path`; extension repositories (`$BLENDER_SYSTEM_EXTENSIONS`, local repos) are the manual's recommended route for add-ons. Some reference add-ons already have `blender_manifest.toml`; others are legacy single files. Converting to extensions is a possible later pipeline refactor, not a v1 localiser requirement.
- Python is Blender's bundled interpreter unless `--python-use-system-env` is used; the interpreter version is tied to the Blender version.

Candidate design (mirrors Nuke's `NUKE_PATH`):
1. The install script sets `BLENDER_SYSTEM_SCRIPTS` (user environment variable) to a **stable local stub script directory**. A user-level variable is inherited by AYON-launched Blender, so no per-user path needs to go into shared AYON settings. If AYON already sets `BLENDER_SYSTEM_SCRIPTS`, that must be reconciled.
2. The stub directory's `startup/` script localises the release, then exposes it. Exposure options, to be tested in Blender 5.0 in this order: (i) add/refresh a named script-directory entry plus `sys.path` for `modules/`, then check that add-ons and presets are discovered in the same session; (ii) enable the release's add-ons explicitly with `addon_utils` from the stub; (iii) if neither works in-session, the release path must be known **before** process creation (launcher or wrapper sets `BLENDER_SYSTEM_SCRIPTS` to the release directly), which a vanilla launch cannot guarantee. Document the limit if so.
3. No `--python` argument is needed, so AYON launches and vanilla launches use the same mechanism.

Stale-path hazard (applies if any preference entry is persisted): `set_pipeline_location()` only checks whether an entry with that name exists; it never updates its `directory`. A persisted entry must be refreshed idempotently on every launch (no duplicates, other entries untouched), or no changing path may be persisted at all.

Implications:
1. Blender's "expose" step differs from Maya/Nuke: the release is a scripts directory, not a `sys.path` root.
2. Prefer the environment-variable mechanism over preference writes; it avoids user-preference side effects and duplicate entries.
3. The Blender in-session exposure test is the gating item before the Blender stub can be designed in detail.

Stubs: stdlib-only, syntax compatible with the oldest supported interpreter, no pipeline imports before the path is set, log enough to diagnose failure.

## 9. Trust (v1 position)

The SHA-256 lives in the manifest next to the zip on the same share, so it detects corruption/truncation, not tampering. v1 relies on the share's `config/` and `releases/` being write-protected to the publishing group. Signing or a separately held digest is a possible later hardening, recorded in open decisions.

## 10. Testing strategy

Tests precede core implementation, use temp dirs and synthetic zips (no share access required):

- Config parse/validate, unsupported schema, last-known-good fallback.
- Resolution: studio, override, offline/stale, override-missing-fails.
- Fast path: marker present → no network access, no hashing.
- Marker/dir missing despite state → reinstall.
- Checksum mismatch, manifest identity mismatch, bad `python_root`.
- Zip-slip / absolute path / symlink rejection.
- Interrupted extraction leaves no valid release.
- Concurrent installers of the same release (multiprocess).
- Per-DCC state files do not conflict.
- Stub idempotency (run twice → one path entry).
- Failure messaging when localiser missing / install fails.
- In-host smoke test per DCC version (manual checklist).

## 11. Phased plan

0. **Discovery (read-only):** current ways each DCC finds the pipeline; supported DCC/Python versions; OS scope; repo conventions. Output: short report + host matrix (§8).
1. **Design review:** confirm module/API layout, schemas, locking approach, open decisions.
2. **Test design:** write the test list above as failing/skipped tests.
3. **Core + publisher:** smallest testable core (config → resolve → state → verify → extract → publish) and the publisher script.
4. **Maya stub + install script**, validated in the real Maya.
5. **Nuke stub.**
6. **Blender stub.**
7. **Pilot:** small TD group; measure startup before/after; log cache hits/installs/failures; documented disable switch.
8. **Later:** AYON pre-launch hook calling the same core; project selection; optional signing/retention.

## 12. Working rules for the Copilot agent

- **Plan before implementing.** Do not write production code, install dependencies or change project settings until the plan is approved.
- Separate confirmed facts from assumptions; do not invent host lifecycle behaviour — verify against installed versions and official docs.
- Stdlib-only for the core and stubs; no new dependencies or abstraction layers without evidence.
- Follow repo conventions unless they conflict with the invariants in §3; explain deviations.
- Keep public APIs small; make operations idempotent; test failure paths.
- Never report success before publication completes; never swallow exceptions.
- Structured logs: host, package, release ID, selection source, outcome, elapsed time; no sensitive paths/credentials.
- Update [02_open_decisions.md](./02_open_decisions.md) when something is decided; don't silently invent answers.
