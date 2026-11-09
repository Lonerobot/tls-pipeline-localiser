# 02 — Open Decisions and Risks

Working log for [01_design_brief.md](./01_design_brief.md). `[x]` = decided (by user); `[ ]` = open. Recommendations are marked as such, not as decisions.

## Decided
- [x] Releases are **zip bundles** (copy zip locally, then extract), not folder copies.
- [x] AYON integration, project overrides and signing are deferred; AYON will later call the same core.
- [x] Release contents are out of scope; the localiser only localises and sets the path.
- [x] Per-DCC local state; no single shared state file as source of truth.
- [x] Deployment direction: pipelines are not per user; target a shared workstation-local bundle store, with a deliberate TD override to pull/select a bundle. Exact paths, permissions and installer contract remain recommendations (brief §5.1).

- [x] `python_root` kept in the manifest as an **optional** field (default `"."`); the pipeline resolves further paths itself.
- [x] Nuke: versioned `core/X.X.X` is no longer needed under the bundle model; Nuke only needs `NUKE_PATH` to reach the core inside the localised release (needs pipeline refactor, brief §8.1).

- [x] Nuke toolchains: out of scope for the localiser. Resolving `NUKE_PATH` to the localised copy of the current pipeline, as it currently is, is enough. (Longer term the modular toolchains could be baked into a build instead of selected at runtime, but that is a pipeline concern, not this project's.)
- [x] Where `NUKE_PATH` comes from does not matter to the design: AYON injects it at app startup; outside AYON a system env var (or similar) points at the stable local stub directory.
- [x] Nuke ordering: `init.py` runs at application start and `menu.py` only when the UI loads, so anything important (path/env setup, localising) must happen in `init.py`; `menu.py` is too late.

## Decided 2026-11-06 (test workstation work)
- [x] **Publishing lives in the core** (`src/localiser/publisher.py`, `python -m localiser publish`), self-contained: it merges shared packages into each bundle, reads the entry point from host defaults (Blender `startup`/`modules`, others `.`) or an optional `bundle.json`, and writes the immutable zip and manifest. `structure/build_test_workstation.py` only calls it.
- [x] **Shared code is vendored into every bundle at publish time** (`structure/shared_sources/`, e.g. `tls_common`), so each release stays one self-contained, checksummed zip. A bundle can't ship a package with a shared package's name. Shared logging is `tls_common` (`tls.<host>.<tool>` loggers, `TLS_LOG_LEVEL`, `TLS_LOG_FILE`).
- [x] **Environment provisioning belongs to the installer**, which sets the defaults (`TLS_PIPELINE`, `NUKE_PATH`, `BLENDER_SYSTEM_SCRIPTS`, Maya `PYTHONPATH`). AYON may change them at application startup. Stubs and bundles append, never clobber: core Nuke code no longer overwrites `NUKE_PATH`.
- [x] **Installer plan decided 2026-11-06**: a **per-user install with no elevation** (bundles are now about 8 MB in total, so per-user copies are cheap and the shared-store ACL and trust problem goes away; a machine-wide mode can come later); a **tray app on PySide6** that configures hosts and locations and runs the update check; updates **auto-sync in the background and running sessions are notified, never force-restarted**; **default lookup locations first, environment variables only as overrides**. AYON only supplies the per-session pin and asks for a pull.
- [x] **Built (phases A and B, core only; no UI yet)**: the host registry (`hosts.py`, with installed-version detection and the icons folder); `hosts`, `check_enabled` and `sync_enabled` with per-entry states and a `state/status.json`; `check-all`, `sync-all`, `hosts` and `provision` commands; the `hosts`, `check_interval_minutes` and `auto_sync` local config keys; the stubs and CLI default to `%LOCALAPPDATA%\TheLine\Pipeline` when `TLS_PIPELINE` is unset; DCC versions not listed in `hosts` load nothing; and per-host entries (Maya `.mod`, a marked block in Nuke's `init.py`, a Blender startup forwarder), verified on Maya 2026, Nuke 17.0v3 and Blender 5.2 with no `TLS_PIPELINE`, `PYTHONPATH` or `BLENDER_SYSTEM_SCRIPTS`.
- [x] **Decided: no in-host update notices.** They were built and removed. A timer in each DCC was verified to fire in Blender and Nuke, but on Maya 2026 startup became unstable with it on and the cause couldn't be isolated. Updates are reported and applied by the tray app only; a running DCC is never interrupted, and a new selection applies at the next launch. `selection_changed` stays in the core for the tray app.
- [x] **Built (phase C, the tray app)**: `src/localiser_tray/` (PySide6, optional dependency `tray`; the core stays stdlib-only). Check at start and on `check_interval_minutes`, auto-install when `auto_sync`, status and settings window, first-run setup creating `config.json`, one instance, closing hides to the tray. The core gained `save_local_config` and `apply_hosts` (validated, non-clobbering config write plus enabling and removing per-application entries). Decisions live in Qt-free `model.py`; tested directly and through the real window offscreen. Looked at on Windows only.
- [ ] **Remaining for the installer**: putting `bootstrap/`, `localiser/` and the app into the pipeline root; packaging and login start-up; macOS and Linux install locations and detection (only Windows is verified); verifying Nuke's default `~/.nuke` lookup itself (verified through a plugin-path folder); a `maya.png` icon; and whether a studio-config `mandatory` flag should force an update.
- [x] **Release lifecycle is manual for now**: a TD edits the remote `config.json`, publishes, and rolls back by re-pointing it. A web front end backed by a database may hold the config later. Whether `+tag` variants are used is left open. Cleanup of old releases is deferred while the policy is tweaked.
- [x] **Store administration is TD-only.** Publishing, selecting, pre-warming and cleanup are done by one trusted person; no other users are expected to manage the store. Concrete ACLs are still set at installation.
- [x] **Runtime logs live outside releases** (`bundles/logs`, passed to bundles as `TLS_LOG_DIR`); releases are never written to.
- [x] **Nuke refactor done**: no version folders under the bundle (`core/`, `toolchains/<name>/`); the core derives its paths from its own location and exports `TLA_COMP_CORE`, `TLA_COMP_PIPELINE_ROOT` and `TLA_COMP_TOOLCHAINS`.
- [x] **One remote repository, over a folder or https** (2026-11-06, built): `remote_repository` in the local config may be an `https://` address as well as a folder; `config.json` and `hosts/<host>/<release>/...` live under it. Static HTTPS hosting (Firebase Hosting, a bucket, any web server) is enough. Read-only, loopback-only plain http, no credentials in the address, redirects must stay safe, 1 MB text limit, 15 s timeout; offline behaviour is unchanged (last-known-good config, installed releases). The studio config is publicly readable by design: it holds only host and series to version numbers.
- [ ] **Firebase Realtime Database as the config source**: not built. It can't be the whole repository (one JSON tree, not files) and its keys can't contain `.`, so it only fits with a separate `studio_config` location and an entries-list encoding. Revisit if a web front end needs to write the config.
- [ ] **Config as the integrity anchor** (later): carry each release's sha256 in the studio config, so a tampered zip on the repository is rejected even if its manifest is changed with it.
- [x] **Per-session bundle pin and pull-only** (the override), built 2026-11-06: `TLS_PIPELINE_<HOST>_BUNDLE` replaces the `STUDIO_PIPELINE_<HOST>` placeholder. At startup it pins an installed release for that session only (no download; the release must have been pulled); `sync` honours the same variable (or `sync --bundle`) to select it machine-wide. `localiser pull <host> <release>` installs without selecting. A project override is therefore: pull, then set the variable at launch (AYON hook later). The core stays unaware of projects.
- [x] **Dev mode**, built 2026-11-06: `TLS_PIPELINE_<HOST>_SOURCE` (plus `TLS_PIPELINE_SHARED_SOURCES`) lays an unpublished bundle source out like a release in `bundles/dev/<host>/` using the same planner as the publisher, with no zip, hash or remote. Precedence at startup: source, then pin, then the selected release; an unusable source or pin is an error, never a fallback. The pipeline entry prints a loud banner. See `structure/DATA.md`.
- [ ] Remaining Nuke content to resolve later: 20 hard-coded `Y:/.../TheLine/0.0.2/...` references in `.nk` and `.gizmo` files.

## Blueprint direction (2026-11-05; `structure/THE-LINE/pipeline/`, not yet implemented in `src/localiser/`)
- [x] Config files are strict JSON; explanations live in `_comment*` keys, never `//` comments. Parsers ignore top-level keys starting with `_`.
- [x] Config nests DCC versions under the host: `hosts[<host>][<dcc series>]`. `dcc_target` is gone; the series is the key. Series are `2026` (Maya), `5.2` (Blender), `17.0` (Nuke), not exact patch versions.
- [x] Bundle location is `<root>/hosts/<host>/<bundle_version>` locally and on the remote. Remote version folders hold `pipeline.zip` + `manifest.json`.
- [x] Bundle versions are plain numbers for standard builds (`1.0.0`); the host is already in the path. A `+tag` suffix marks a variant (`1.0.0+dev`). IDs stay opaque and selection is by exact pin, not ordering; `0.0.1+dev` replaces `0.0.1` by being named, not by being "greater" (semver build metadata has no precedence).
- [x] `deploy_target` is dropped. Whether `remote_repository` is a disc path or a web URL is inferred from the value (`http(s)://` is web; `file://`, UNC, drive and relative paths are disc; a one-letter scheme is a drive letter, not a URL). `http(s)` is rejected with a clear error until web repositories are built. The local `bundle_repository` is always a folder.
- [x] Environment variables: `TLS_PIPELINE` is the local pipeline root. The localiser then sets `TLS_PIPELINE_MAYA`, `TLS_PIPELINE_BLENDER` and `TLS_PIPELINE_NUKE` to the resolved bundle path for that host. This supersedes the `STUDIO_PIPELINE_<DCC>` placeholder, which was the TD release override.
- [x] The TD bundle override is `TLS_PIPELINE_<HOST>_BUNDLE` (decided 2026-11-06, replacing the deferred `STUDIO_PIPELINE_<HOST>` placeholder; `TLS_PIPELINE_<HOST>` keeps the resolved path). See the 2026-11-06 section.
- [x] `additional_paths`, `menu_label` and `documentation_url` are removed from the config. Extra Python paths and DCC UI setup are handled by the host-specific code inside the bundle, not by the localiser.
- [x] Core moved to the blueprint shape (2026-11-05): `localise(host, series, config)`, nested studio config, `TLS_PIPELINE` / `TLS_PIPELINE_<HOST>`, `hosts/<host>/<version>` layout. The split of local vs remote config is implemented as proposed: local `config.json` is machine setup only; the remote `config.json` carries `hosts[<host>][<series>]`.

## Blueprint: open items (proposals, not decisions)
- [x] **Override variable name:** `TLS_PIPELINE_<HOST>_BUNDLE` (2026-11-06).
- [ ] **Split local and remote config roles.** Local `config.json`: static machine config (`remote_repository`, bundles root), read-only at runtime. Remote `config.json`: per host/series `bundle_version`. The last copy of the remote config is cached in `state/`, written per host or atomically, never edited in place. `bundle_repository` is the same for every entry, so *recommend* one top-level key.
- [ ] **Series matching and misses.** Normalise the detected DCC version per host to a series. *Recommend* failing clearly with host and series when no entry matches, never a silent fallback.
- [ ] **Detection.** Stubs pass `(host, series)` to the core (Maya `cmds.about`, `bpy.app.version`, `nuke.NUKE_VERSION_STRING`); the core imports no DCC modules. `pipeline/__init__.py` gets an explicit `localise(host, series)`, not import-time work.
- [ ] **"New version available"** means the remote pin differs from the local one (allows rollback), not "greater than". Whether launch reads the remote config or only the local cache is the open item under Core implementation choices.
- [ ] **Permissions.** `pipeline/` (code and config) is protected; `bundles/`, state, staging and locks are group-writable. Staging stays on the same filesystem as `bundles/`.
- [ ] **Path rules.** Relative paths in config resolve against the config file's folder, not the working directory. `host`, series and `bundle_version` are validated as single path components before being joined.
- [ ] A bundle's `startup/` entry must live outside the release, or it is circular (invariant 9). Confirm what the Blender fake bundle's `startup/` is meant to be.

## Core implementation choices (2026-11-02; made while building `src/localiser/`, pending design review)
Implemented and tested; each is a **recommendation** open to change, not a decision.
- [x] **Package ID is the host** (2026-11-05): bundles live at `hosts/<host>/<version>`, so the old `install.json` `"packages"` override is gone. The manifest and marker still carry a `package_id` field (set to the host); renaming it to `host` is a possible later cleanup.
- [x] **Override variable:** now `TLS_PIPELINE_<HOST>_BUNDLE` (2026-11-06). Blank means unset; an invalid value is an error, never ignored. It applies to every DCC series of that host.
- [ ] **Studio config read on every launch:** the fast path skips hashing and the `hosts/` tree, but still reads the one small `<remote_repository>/config.json`, falling back to the last-known-good copy in `state/studio-config.json`. This is a tension with invariant 7 ("no network traversal"); decide whether a launch may read the remote config or must use only the local copy and refresh separately.
- [ ] **Marker ordering:** the install writes `.complete` inside staging and then renames staging → final (brief §6 step 5.6). Invariant 4 says the marker is written "after atomic publish"; the implemented order is stronger (marker and directory appear together). Align the invariant's wording.
- [ ] **Marker content:** `.complete` is JSON (package, release, `python_root`, sha256, time) so the fast path needs one small local read. A missing, corrupt or mismatched marker means "not installed": the directory is moved aside under the lock and reinstalled.
- [ ] **Locking:** OS byte-range lock on a per-release lock file (`msvcrt` / `fcntl`); released automatically if the holder dies, so there are no stale locks. Windows and POSIX only; not tested on a network filesystem (the local store isn't one).
- [ ] **Failure policy and zip bombs:** extraction rejects absolute/`..`/drive/colon/backslash names, symlinks, duplicates (case-insensitive) and validates all members before writing. There is no size limit; decide whether one is needed.
- [x] **Local config discovery** (2026-11-05): `TLS_PIPELINE` names the pipeline root, whose `config.json` holds `remote_repository` and `bundle_repository` (relative paths resolve against that file). This replaces `install.json`. How the variable gets set on a workstation is still the installer question in brief §5.1.
- [ ] **Not implemented yet:** repair/status CLI, `resync`, retention/cleanup of old releases and abandoned staging, file logging, permissions/ACL provisioning.

## Nuke refactor (see brief §8.1)
- [ ] What the localiser exposes to the pipeline: resolved root and release ID via env vars? Names TBD; avoid clashing with existing `TLA_COMP_*` variables.
- [ ] Local override for `config.json` debug flag, since it will live in an immutable release.

- [x] Blender: **5.0+ only**, no backward compatibility. (The add-on `bl_info` still says 4.2; update when the add-ons are next touched.)
- [x] Blender: **vanilla (non-AYON) launches are in scope.** An AYON-only `--python` argument cannot be the sole bootstrap. The earlier per-user-path objection is superseded by the shared workstation direction; vanilla discovery is still required.

## Blender (see brief §8.3)
- [x] **Gating test passed** (Windows, Blender 5.2.3 LTS, UI launch): a release exposed from a `startup/` stub's `register()` (named script-directory entry + `bpy.utils.refresh_script_paths()`) gets its `addons/`, `modules/` and presets picked up in the same session. Must run **during startup registration, before saved add-ons load**; a timer is too late. `addon_refresh()` alone is insufficient. See `discovery-tests/blender/README.md`. Other Blender versions/platforms not yet tested.
- [ ] Mechanism: `BLENDER_SYSTEM_SCRIPTS` pointing at a stable shared local stub directory with a `startup/` stub, provisioned through machine/session integration (brief §5.1). Recommended over preference writes. Confirm GUI/vanilla and future AYON launch inheritance. **AYON does not set `BLENDER_SYSTEM_SCRIPTS`** (user-reported 2026-11-02), so no reconciliation with an AYON value is needed; still append rather than overwrite any existing value.
- [ ] If runtime exposure doesn't work in-session: **resolved, it works** (see gating test). Remaining: failure policy when localisation fails. Blender catches startup `register()` errors and keeps launching, so saved stale add-ons could still load; define how to prevent that, and when a last-known-good release is allowed.
- [ ] PySide6 install / `QT_API` setup in `startup.py`: stays in the stable stub, moves to the install script, or stays separate? (Out of scope for the localiser itself.)
- [ ] Windows-only? `startup.py` uses `ctypes.windll` and `python.exe`.
- [ ] Publisher: exclude `__pycache__` / `*.pyc` from the Blender release.
- [ ] Later: convert add-ons to extensions (manual's recommended route)? Pipeline concern, not v1.

## Maya (see brief §8.2)
- [ ] How is `MAYA_CORE` consumed, and by what and when? (e.g. AYON menu/environment settings reading `corescripts_template.json` or adding the folder to `PYTHONPATH`.) If something reads it **before** `userSetup.py` runs, the localised root must be known pre-launch; if after, the stub can set `MAYA_CORE` in-process to the local root.
- [ ] Where does the existing `userSetup.py` live and who puts its folder on `PYTHONPATH` (AYON env injection, system env)? Does an AYON-provided `userSetup.py` also exist? **Finding (Maya 2026, Windows): Maya ran two `userSetup.py` files from different `sys.path` folders in one process, so more than one can run.** Still to verify: real AYON/studio file coexistence and whether an exception in one stops the others. A `userSetup.py` already exists in `Documents\maya\scripts` on the tested machine; never overwrite one.
- [ ] Keep `userSetup.py` as-is plus a localiser call, or move its startup behaviour into the release (stub calls it)?
- [ ] Where do `ShotOverride`/`PreRenderChecks` (imported in the OpenPype branch of `userSetup.py`) come from? Is that branch still used?
- [ ] Reference `userSetup.py` bug, only if the OpenPype branch is live: `post_load_overrides_script_job` uses `cmds` without importing it.
- [ ] Publisher: run `generate_pype_menu()` before zipping and exclude `__pycache__`, `*.pyc`, `Thumbs.db`.

## Release and config
- [ ] Release ID format: semver, build IDs, or both. *Recommend: opaque IDs.*
- [ ] Network path for the remote repository (`config.json` and `hosts/`), and who has write access.
- [ ] Zip layout: confirm `python_root` per DCC (top-level folder or not).
- [ ] Override mechanism: env var name (`STUDIO_PIPELINE_<DCC>` is a placeholder; check against existing studio variables) and how TDs set it deliberately.
- [ ] Confirm TD workflow: launch-scoped selection pulls a new ID only if missing; explicit `resync` repairs an already-cached ID. Neither persists a user default nor changes other running hosts (brief §5.1).
- [ ] Same-ID repair: *Recommend: never change content behind an ID; resync restores identical verified content only.*
- [ ] Trust model beyond a write-protected share (signing / separately held digest).

## Platform and versions
- [ ] Supported OSes: Windows, macOS and Linux assessed in brief §5.1; inclusion in the supported deployment matrix is not yet confirmed.
- [ ] Supported Maya, Blender, Nuke versions and their Python versions (limits stub syntax).

## Host lifecycle (verify per version)
- [ ] **Stub registration approach (discussed 2026-11-02, not yet decided).** The stub is the same in every case; options differ only in how the DCC finds it: (1) **environment variable** per DCC (`BLENDER_SYSTEM_SCRIPTS`, `PYTHONPATH` for Maya's `userSetup.py`, `NUKE_PATH`), appended to any existing value, no user files touched; *leaning default*. Cautions: a global `PYTHONPATH` leaks to other Python tools (Maya's `MAYA_MODULE_PATH`/`.mod` is an untested alternative), and AYON/launchers may reset variables. (2) **Default lookup locations** (file placement, per user and per version): fallback only, never overwrite existing files; safe in Blender (`startup/` allows distinct filenames), risky for Maya (`userSetup.py` name is fixed) and Nuke (`~/.nuke/init.py` is a single file, so one-line append at most). (3) **Launcher/AYON resolves first** and the variable points straight at the local release: works for launcher starts only. Note the release is not sandboxed: it shares the DCC interpreter and `sys.modules`. Nuke behaviour is untested.
- [ ] Maya: stub location/discovery for vanilla and AYON launches. Tested: a folder on `PYTHONPATH` and `Documents\maya\<version>\scripts` both run; see G3 in `03_user_discovery.md`.
- [ ] Nuke: how `NUKE_PATH` is set for vanilla launches; `init.py` vs `menu.py` ordering. **Tested (Nuke 17.0v3, GUI):** `pluginAddPath` from a `NUKE_PATH` stub's `init.py` runs the added directory's `init.py` right after the stub's returns, and its `menu.py` after the UI loads. Untested: coexistence/order with other `NUKE_PATH` entries (AYON), non-GUI Nuke, other versions.
- [ ] Blender: script-directory configuration per version, first-launch persistence, add-on ordering, avoiding preference side effects.
- [ ] First-run in-host install UX (blocking + message vs pre-warm by install script).
- [ ] What happens if the localiser/stub is missing or damaged, per DCC.

## Cache and ops
- [ ] Portable cross-account locking strategy for supported OSes, including a separate shared studio-config snapshot lock and safe concurrent logging.
- [ ] Retention/cleanup of old releases and staging leftovers.
- [ ] Log location, rotation, and user-facing error mechanism.
- [ ] Startup-time baseline and acceptance targets.
- [ ] How the install script is distributed and updated, and how stubs are updated independently of releases.

## Workstation installation and permissions (assessment in brief §5.1)
- [ ] Approve machine-wide roots: ProgramData on Windows; `/Library/Application Support` on macOS; `/opt` + `/etc/opt` + `/var/opt` on Linux. Confirm local disks, space, filesystem semantics and managed custom-root discovery.
- [ ] Approve local code-execution trust boundary: managed runtime group can pull/write and therefore influence every cache reader, versus read-only artists with TD/IT pre-warming (a privileged updater would be later scope). No unrestricted world/Everyone write.
- [ ] Define group membership and ACL/default-ACL inheritance across accounts, including any render/service identities; verify actual permissions after atomic publication.
- [ ] Confirm the protected local `config.json` schema; distinguish local config, studio defaults, release manifests and diagnostic state.
- [ ] Repository addressing per OS/account: UNC versus managed mounts, availability before launch, credentials/access for runtime identities; no dependency on the installer's drive mappings.
- [ ] Machine/session host-discovery deployment for macOS GUI and Linux desktop launches; Windows environment refresh and existing launcher behaviour. Do not rely solely on interactive shell profiles.
- [ ] Installer packaging/distribution, elevation boundary, optional pre-warm, idempotent repair, safe bootstrap updates and explicit cache-root migration.
- [ ] Design safe same-ID repair with active readers; immutable paths must not be replaced while running DCCs use them.
- [ ] Verify cited platform conventions against official sources and managed workstation images; external source retrieval was blocked by DNS during this assessment.
