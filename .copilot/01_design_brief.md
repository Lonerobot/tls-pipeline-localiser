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
- A shared workstation cache, not a separate pipeline installation or release selection per user; see §5.1 for platform and permission assessment.
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
| **Install script** | One-time/idempotent workstation setup: provision paths and permissions, persist repository/cache locations, copy core + stubs, wire each DCC's discovery mechanism. See §5.1. |
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

### Local workstation layout (recommended; paths and permissions in §5.1)
```text
<install root>/
  install.json                 # protected machine configuration; NOT a release manifest
  bootstrap/                   # protected, stable core + stubs (NOT inside a release)
<data root>/
  releases/<package_id>/<release_id>/.complete   (+ extracted files)
  state/<host>.json             # per-DCC cache of last resolution: release_id, root, installed_at
  state/studio-pipelines.json   # last-known-good copy of studio config
  state/manifests/<package_id>/<release_id>.json # verified release manifest
  staging/  locks/  logs/
```
`<install root>` and `<data root>` are logical boundaries: they may share a parent on Windows/macOS, but must have different write permissions. A cached copy of each verified release manifest must also be retained outside the extracted payload, keyed by package/release, for status and repair.

### Where "complete" state lives
- **Source of truth:** the `.complete` marker inside the release directory.
- **`state/<host>.json` is a convenience cache**, one file per DCC to avoid cross-DCC write conflicts, written atomically under the lock. If it disagrees with the filesystem, the filesystem wins.
- **Not** a single shared `config.json`: concurrent DCCs/instances would race on read-modify-write.
- The last-known-good studio config and local install state are separate files with separate lifecycles.

### 5.1 R&D assessment: platform locations and lightweight installation

**Direction supplied for this planning pass:** pipelines are not deployed per user. Normal launches use the studio default in one workstation-local store; a TD can deliberately select another immutable bundle and trigger a pull. The earlier `%LOCALAPPDATA%`-only layout is superseded. The locations below are recommendations, not evidence that these OSes or host integrations have been tested.

#### User versus system locations

| Platform | User-level candidate | Shared workstation recommendation | Deployment implications |
|---|---|---|---|
| **Windows** | `%LOCALAPPDATA%\TheLine\Pipeline` is normally writable by that account and avoids roaming profiles, but duplicates bundles and state across users. `%APPDATA%` may roam and is unsuitable for large local bundles. | Resolve the Windows **ProgramData known folder**, typically `C:\ProgramData`; provision `TheLine\Pipeline` below it. Protected `bootstrap/` and `install.json`; writable `releases/`, `state/`, `staging/`, `locks/`, `logs/` for the approved runtime group. | Shared application data belongs here rather than `Program Files` or `C:\Users\Public`. ProgramData is **not a blanket guarantee of cross-user modify access**: elevated provisioning must set explicit inheritable ACLs on the mutable subtrees, including access to files created by another account. Do not hardcode the drive or rely on creator-owner defaults. |
| **macOS** | `~/Library/Application Support/TheLine/Pipeline` is account-specific. `~/Library/Caches` is disposable, so not suitable as the only offline copy. | `/Library/Application Support/TheLine/Pipeline`, with protected `bootstrap/` and `install.json` and separately writable data subtrees. | `/Library` is the local-machine domain, unlike the user's `~/Library`. Administrator/MDM provisioning creates the tree and runtime group permissions. `/Users/Shared` is an alternative shared container, not a permission or integrity policy; do not assume files created there are writable by other users. Avoid `/System` and application bundles. |
| **Linux** | `$XDG_DATA_HOME/theline/pipeline` (default `~/.local/share/theline/pipeline`) could hold persistent bundles; `$XDG_CONFIG_HOME` holds user config and `$XDG_CACHE_HOME` disposable data. All remain per-account. | Protected core/stubs in `/opt/theline/pipeline-localiser/bootstrap`, machine descriptor at `/etc/opt/theline/pipeline-localiser/install.json`, persistent data in `/var/opt/theline/pipeline-localiser/`. | This follows FHS's split for an add-on package. Root provisions ownership and a dedicated runtime group; use setgid directories plus default ACLs where supported so newly created files remain usable across accounts. Verify the effective umask/ACLs. `/var/cache` may be purged and `/tmp` is neither durable nor appropriate for trusted executable bundles. |

Use persistent application data, despite calling it a "cache": an offline workstation depends on retained bundles and last-known-good configuration. Avoid network-mounted/roaming homes, cloud-synchronised folders and temporary directories. The installer may accept a different **machine-wide local data root** (e.g. a larger local disk), but must validate permissions, available space and filesystem semantics. Staging and final releases must be on the same filesystem for atomic publication.

#### What "publicly writable" can safely mean

Shared across accounts does not mean safe for **Everyone/world write**. These directories contain Python that DCCs execute. An account able to replace a release, its `.complete` marker or cached selection metadata can cause another account to execute its code. A manifest hash does not prevent this if the same account can replace both files. A sticky bit alone does not solve this, and localiser processes must never execute user-writable pipeline code with elevated privileges.

**Recommended lightweight v1:** an administrator provisions the protected bootstrap/configuration and grants a named, managed studio runtime group read/traverse plus the create/modify/delete rights needed on the data subtrees. Keep their common parent protected too, so runtime writers cannot rename or replace bootstrap/configuration entries through parent-directory permissions. Every identity that may pull a bundle must belong to that group, including render/service accounts if those are later supported. All such writers are consequently in the same code-execution trust boundary; accept that explicitly before rollout. Do not grant unrelated local accounts write access, or use `chmod 777`/an unrestricted Everyone ACL. Validate child-file inheritance and cross-account lock/release access, not just whether the parent directory is writable.

If artists must only read releases and only TDs may publish locally, an ordinary artist DCC **cannot** perform a cold pull under its own identity. The deployment then needs a TD/IT pre-warm step or, later, a privileged installer/updater service that validates and publishes bundles while DCCs remain readers. This is stronger isolation but is not supplied by a lightweight copy script alone. A service is not proposed for v1; this trust/deployment choice remains open in the decisions log.

#### Installer and manifest discovery contract (proposed)

1. **Provision once per workstation.** Use a small idempotent installer, with elevation only for protected files, machine integration and permission setup. It takes the studio repository location, the local data root and enabled DCCs; it does not install a separate pipeline for the installing account. Runtime pulls run unelevated.
2. **Persist a machine descriptor.** Write a schema-versioned `install.json` atomically at the protected platform location above. Proposed fields are `schema_version`, `repository_root`, `data_root` and a host-to-`package_id` mapping (e.g. `maya` → `maya-tools`); exact schema/API needs review. This fills the mapping not present in the illustrative studio config. Roots are absolute and explicitly configured per OS; a Windows mapped drive such as `Y:` must not be assumed available to other users or services. Prefer an accessible UNC path on Windows and a managed mount on macOS/Linux.
3. **Discover without user profiles.** Installed stubs know the platform's descriptor location (or an installer-recorded absolute path for a managed custom installation). The descriptor locates the shared data and repository roots. Read `<repository_root>/config/studio-pipelines.json`, then `<repository_root>/releases/<package_id>/<release_id>/manifest.json` and its zip. `install.json` is installation configuration, `studio-pipelines.json` selects studio defaults, and `manifest.json` describes one release: do not conflate their lifecycles. Missing/malformed/inaccessible installation configuration is a repairable error, never a silent fallback to a new user cache or another repository.
4. **Wire discovery for every intended launch.** Configure the stable Maya/Nuke/Blender stub paths using managed machine/session launch integration, preserving existing path entries. Windows machine environment changes require a newly started launcher/session; an existing AYON process retains its old environment. macOS Finder/Dock launches do not generally inherit shell startup files, and Linux desktop launches may not read interactive shell profiles. A shell `export` alone is not machine deployment. Verify vanilla GUI, shell and future AYON launches separately; the exact macOS/Linux mechanism remains an implementation gate.
5. **Validate and optionally pre-warm.** Check repository access as the intended runtime identity, path writability, permission inheritance, lock creation and atomic publication. Optionally pull current studio bundles before the first DCC launch; report failure explicitly rather than claiming a usable offline install. Record installation status/version without conflating it with a release ID.
6. **Repair without disturbing sessions.** Re-running the installer preserves configuration unless explicitly changed and repairs permissions/stubs. Updating the protected bootstrap is separate from releasing pipeline bundles and must not replace files being imported by a running host. Cache-root migration is an explicit maintenance operation; no automatic split into old and new stores.

User-level installation avoids administrator rights but creates account-specific storage and host wiring. It is an assessed alternative for an unmanaged pilot, **not the target deployment or an automatic fallback**. Shared storage saves duplicate downloads and lets the same machine reuse bundles across logins, but requires elevated initial provisioning and genuinely cross-account locks, permissions and state updates. It does not by itself solve host startup ordering (especially Blender's in-session discovery gate).

#### TD override and forced pull on a shared store

Keep selection and storage scope separate. A pre-launch `STUDIO_PIPELINE_<DCC>=<release_id>` override selects that release for the TD's new DCC process, localising it into the **same shared store** if absent. It does not create a per-user pipeline, persist a user default, change the machine descriptor or alter another running DCC. Setting a machine-wide environment override would affect subsequent launches by other users and is not the recommended TD workflow.

A new release ID causes a pull on cache miss; selecting an already-cached ID reuses it. If "force pull" means repairing a cached ID, use an explicit `resync <host> <release>` operation, not a second meaning for the selection variable. It must fetch and verify identical content under the existing ID, coordinate with other users and never delete/replace a tree in use. The safe replacement/quiescence mechanism remains to be designed; do not promise live same-ID replacement.

Shared `state/<host>.json` is only last-resolution diagnostic state: a TD override must not turn it into the next user's default. Offline default selection still comes from `state/studio-pipelines.json`; an override failure must never rewrite that file or fall back to another release. Atomic writes also need a dedicated lock for concurrent refreshes of the shared studio-config snapshot; per-release locks alone do not serialize that file. Logs need unique per-process files or a coordinated writer, and multi-account tests must cover both.

#### Sources and verification boundary

Platform conventions to verify against deployment targets:
- [Microsoft: Known Folder IDs](https://learn.microsoft.com/en-us/windows/win32/shell/knownfolderid) — `FOLDERID_ProgramData`, `FOLDERID_LocalAppData` and `FOLDERID_RoamingAppData`.
- [Apple: File System Programming Guide — File System Overview](https://developer.apple.com/library/archive/documentation/FileManagement/Conceptual/FileSystemProgrammingGuide/FileSystemOverview/FileSystemOverview.html) — user/local domains and Application Support versus Caches.
- [freedesktop.org: XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/latest/) — user data/config/cache defaults; not a machine-wide deployment specification.
- [Filesystem Hierarchy Standard 3.0](https://refspecs.linuxfoundation.org/FHS_3.0/fhs/index.html) — `/opt`, `/etc/opt`, `/var/opt` and `/var/cache`.

These are reference links, not a claim of fresh source verification: external documentation retrieval failed due to DNS resolution during this planning pass. Directory/permission recommendations are based on established platform conventions; ACL behaviour, host discovery and supported OS/DCC combinations must be verified on actual managed workstations before implementation approval.

## 6. Runtime flow

1. **Install script (once per workstation):** provision protected bootstrap/config and shared data permissions; record repository/data roots in `install.json`; wire each DCC (§5.1, §8). A stub that finds no descriptor or core reports that installation/repair is required; it does not silently create a per-user install.
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
- Overrides are launch-scoped selections into the shared workstation store, not per-user installations or persistent studio defaults. A missing ID triggers a bundle pull; same-ID forced repair is a separate explicit operation (§5.1).
- Project (AYON) selection will slot in later between these two; it is not designed here.

## 8. Host exposure (to be verified against the installed DCC versions — do not assume)

| DCC | Proposed mechanism | To verify |
|---|---|---|
| **Maya** | Core pipeline = one folder (`v1.1.0/`) whose root goes on the Python path (`python_root` = `.`). A small **stub `userSetup.py` in a stable local directory** (on `PYTHONPATH`, outside any release) localises, then does `sys.path.insert(0, root)` once (idempotent). AYON-supplied tools untouched. See §8.2. | **Verified (Maya 2026, Windows, §8.4):** Maya can run more than one `userSetup.py` in one process (a `PYTHONPATH` stub and one in `Documents\maya\2026\scripts` both ran), and executes them via `execfile` (no `__file__`). Still open: coexistence with the real AYON/studio file and whether an exception in one stops the others; how `MAYA_CORE` is consumed and when (§8.2); supported Maya/Python versions (reference says Maya 2026 / Py 3.11; `__pycache__` in the folder shows 3.7–3.11 history). |
| **Nuke** | `NUKE_PATH` points at a **stable local stub directory** whose `init.py` localises, then calls `nuke.pluginAddPath(<release root>/<python_root>)` (expected `core/` inside the bundle). The stub path never changes between releases; only the resolved root does. Everything the pipeline needs must be set up in `init.py` (application start); `menu.py` only runs when the UI loads, which is too late. The source of `NUKE_PATH` (AYON env injection, or a system env var outside AYON) doesn't affect the design. See §8.1. | **Verified (Nuke 17.0v3, Windows, GUI, §8.4):** `pluginAddPath` from the stub's `init.py` makes Nuke run the added directory's `init.py` right after the stub's returns, and its `menu.py` once the UI loads. Still open: order against other `NUKE_PATH` entries (AYON), non-GUI Nuke. Nuke 17.0v3 embeds Python 3.11.11, which meets the 3.11 floor. |
| **Blender** | **5.0+ only; vanilla launches in scope.** Use the documented studio-deployment route: `BLENDER_SYSTEM_SCRIPTS` points at a **stable local stub script directory**, provisioned through managed machine/session integration (§5.1), like Nuke's `NUKE_PATH`. Its `startup/` stub runs at Blender start, localises, then exposes the release (a scripts directory with `addons/`, `presets/`). No `--python` argument and no preference writes required. How the stub exposes the release in-session is the key item to test. See §8.3. | **Verified (Blender 5.2, Windows, §8.4):** a script directory set from the stub's `register()` plus `bpy.utils.refresh_script_paths()` is honoured in the same session, provided it runs before saved add-ons load. AYON does not set `BLENDER_SYSTEM_SCRIPTS` (user-reported). Still open: Python 3.13 syntax, other Blender versions. |

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

Current launch (stated by user): AYON runs Blender with `--python-use-system-env --python Y:/PIPELINE/config/blender/_core/2.0.0/startup.py`. The reference `startup.py` is WIP because 5.0 changed script-directory handling. Earlier research rejected `--python` because of per-user local paths and vanilla launches having no such argument. The proposed shared workstation root (§5.1) removes the per-user-path issue, but vanilla launches still require a discoverable stable bootstrap rather than an AYON-only argument.

Confirmed from the reference:
- `startup.py` itself lives on the share inside a **versioned** `_core/<version>/` folder, so today the bootstrap is part of what is versioned. Under the localiser the bootstrap must be a **stable local file outside any release**. Reading even one file from the share at every launch would keep the network dependency and break offline use.
- The pipeline is exposed by AYON setting `BLENDER_CORE_ADDONS`; `set_pipeline_location()` adds a script directory named `THELINE_PIPELINE` to the user preferences. The release is therefore a **Blender scripts directory** (`addons/`, `presets/`) rather than a `sys.path` root.
- **Stale-path hazard:** `set_pipeline_location()` only checks whether an entry with that name already exists; it never updates its `directory`. Once a release path changes (any versioned or localised path), the persisted preference keeps pointing at the old location. The localiser design must *update* the entry's directory on every launch (idempotently, without duplicating entries), or avoid persisting a changing path.
- `studio_environment_startup` is an add-on in the release (registers a `load_post` handler, shot override and asset library setup). Enabling it with `persistent=True` also stores state in user preferences; an enabled add-on whose script directory is stale or missing will fail to load at the next start. `enable_startup_addon()` is currently commented out in `startup.py`.
- `startup.py` also does **Blender-installation setup unrelated to the release**: sets `QT_API=pyside6` before AYON imports Qt, and pip-installs PySide6 into Blender's own `site-packages`, with a UAC elevation retry (Windows-only: `ctypes.windll`, `python.exe`). This is a first-run/environment concern, not release content. It should not move into the versioned release, and is a candidate for the install script or the stable stub. Decision needed; the localiser itself stays out of it.
- `__pycache__` folders in the reference are `cpython-313`, consistent with Blender 5.0 on Python 3.13 (inference from the bytecode tag, not a stated fact). The publisher must exclude them.

Confirmed from the Blender 5.0 manual (Deploying Blender in Production; Blender's Directory Layout; Preferences → File Paths):
- **`$BLENDER_SYSTEM_SCRIPTS` is the documented way to add a script directory without modifying preferences**, intended for studio deployment. It may contain `startup/`, `addons/`, `modules/`, `presets/`. `.py` files in `startup/` are imported at startup; the manual's own example is a startup script that enables add-ons for every user via `addon_utils.enable()`.
- **Script-directory preference changes need a Blender restart** to take effect ("You have to restart Blender for all changes to the users scripts to take effect"). This matches the "callbacks don't run until the next start" quirk noted in the reference `startup.py`. A stub that localises at startup and then adds the release as a script directory at runtime may therefore not get its `addons/`/`presets/` picked up in the same session, and a persisted entry would lag one launch behind a release change. This is the main risk to test. **Superseded by §8.4:** tested on Blender 5.2, a startup `register()` that sets the entry and calls `bpy.utils.refresh_script_paths()` is picked up in the same session; the restart note applies to changes made after startup add-on loading.
- Add-on `modules/` folders are added to `sys.path`; extension repositories (`$BLENDER_SYSTEM_EXTENSIONS`, local repos) are the manual's recommended route for add-ons. Some reference add-ons already have `blender_manifest.toml`; others are legacy single files. Converting to extensions is a possible later pipeline refactor, not a v1 localiser requirement.
- Python is Blender's bundled interpreter unless `--python-use-system-env` is used; the interpreter version is tied to the Blender version.

Candidate design (mirrors Nuke's `NUKE_PATH`):
1. The install script provisions `BLENDER_SYSTEM_SCRIPTS` to point at a **stable shared local stub script directory**, using managed machine/session integration (§5.1), not an account-specific path. Newly started AYON and vanilla Blender must receive it. If AYON already set `BLENDER_SYSTEM_SCRIPTS`, that would have to be reconciled; **it does not** (user-reported), but append to any existing value rather than overwrite, and inheritance by AYON-launched Blender is still to be confirmed.
2. The stub directory's `startup/` script localises the release, then exposes it (**verified approach: option (i), §8.4**). Exposure options, tested in Blender 5.2 in this order: (i) add/refresh a named script-directory entry plus `sys.path` for `modules/`, then `bpy.utils.refresh_script_paths()`, during startup registration: works in-session; (ii) enable the release's add-ons explicitly with `addon_utils` from the stub (only after (i)'s path refresh); (iii) the release path known before process creation: not required. Document the limit if so.
3. No `--python` argument is needed, so AYON launches and vanilla launches use the same mechanism.

Stale-path hazard (applies if any preference entry is persisted): `set_pipeline_location()` only checks whether an entry with that name exists; it never updates its `directory`. A persisted entry must be refreshed idempotently on every launch (no duplicates, other entries untouched), or no changing path may be persisted at all.

Implications:
1. Blender's "expose" step differs from Maya/Nuke: the release is a scripts directory, not a `sys.path` root.
2. Prefer the environment-variable mechanism over preference writes; it avoids user-preference side effects and duplicate entries.
3. The Blender in-session exposure test was the gating item; it has passed (§8.4).

Stubs: stdlib-only, syntax compatible with the oldest supported interpreter, no pipeline imports before the path is set, log enough to diagnose failure.

### 8.4 Discovery results (2026-11-02; Windows only)

Full evidence is in `03_user_discovery.md` and `discovery-tests/*/README.md`.

- **Blender 5.2.3 LTS:** release exposure works in the same session when done in the startup stub's `register()`: update the named script-directory entry, call `bpy.utils.refresh_script_paths()`. `bpy.ops.preferences.addon_refresh()` alone does not update `sys.path`. Doing it from a timer is too late, because saved enabled add-ons have already loaded from the old persisted path (and re-enabling reuses the imported module). Blender continues launching after a startup `register()` error, so a failed localisation does not by itself stop stale saved add-ons loading; failure policy is open. AYON does not set `BLENDER_SYSTEM_SCRIPTS` (user-reported).
- **Maya 2026:** more than one `userSetup.py` can run in one process (in `sys.path` order in the one test). They run via `execfile`, so there is no `__file__`. The stub must not assume it runs first or alone. Never overwrite an existing `userSetup.py` during install.
- **Nuke 17.0v3:** the added directory's `init.py` runs right after the calling `init.py` returns (not inside the `pluginAddPath` call); `menu.py` runs when the UI loads. `__file__` is defined for `init.py`.
- **Registration route (undecided, see `02_open_decisions.md`):** environment variables per DCC (leaning default), default lookup locations as a never-overwrite fallback, or a launcher that resolves first.
- Use one environment variable per host; a variable shared between hosts leaked into the wrong test during R&D.
- Not yet tested: other DCC versions, macOS/Linux, real AYON launches, coexistence with AYON's own startup files.

## 9. Trust (v1 position)

The SHA-256 lives in the manifest next to the zip on the same share, so it detects corruption/truncation, not tampering. v1 relies on the share's `config/` and `releases/` being write-protected to the publishing group. A shared writable local cache also trusts every local runtime writer (§5.1); share permissions alone do not protect executable files after localisation. Protect the bootstrap and machine descriptor separately and approve the local writer group before rollout. Signing or a separately held digest is a possible later hardening, recorded in open decisions.

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
- Two different OS accounts can reuse a release, acquire locks and publish with the intended inherited permissions; unrelated accounts cannot modify bootstrap/configuration or cached code.
- Concurrent studio-config refreshes and logs remain intact; a TD override never becomes another account's default, including offline.
- Installation/repair is idempotent; descriptor discovery, custom local roots, inaccessible repositories and invalid permissions produce explicit outcomes without a per-user fallback.
- Vanilla GUI/shell launches receive the stable stub paths on each supported OS; restarted launchers receive machine/session environment changes.
- Offline launches retain usable bundles after logout/reboot; same-ID repair is refused or deferred while unsafe.
- Stub idempotency (run twice → one path entry).
- Failure messaging when localiser missing / install fails.
- In-host smoke test per DCC version (manual checklist).

## 11. Phased plan

0. **Discovery (read-only):** current ways each DCC finds the pipeline; supported DCC/Python versions; OS scope; repo conventions. Output: short report + host matrix (§8), and verify the directory/ACL/GUI-launch assessment (§5.1) on supported workstation images.
1. **Design review:** confirm module/API layout, schemas, locking approach, open decisions; approve runtime writer trust boundary, machine paths, descriptor discovery and TD force-pull semantics.
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
