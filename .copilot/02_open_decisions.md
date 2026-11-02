# 02 — Open Decisions and Risks

Working log for [01_design_brief.md](./01_design_brief.md). `[x]` = decided (by user); `[ ]` = open. Recommendations are marked as such, not as decisions.

## Decided
- [x] Releases are **zip bundles** (copy zip locally, then extract), not folder copies.
- [x] AYON integration, project overrides and signing are deferred; AYON will later call the same core.
- [x] Release contents are out of scope; the localiser only localises and sets the path.
- [x] Per-DCC local state; no single shared state file as source of truth.

- [x] `python_root` kept in the manifest as an **optional** field (default `"."`); the pipeline resolves further paths itself.
- [x] Nuke: versioned `core/X.X.X` is no longer needed under the bundle model; Nuke only needs `NUKE_PATH` to reach the core inside the localised release (needs pipeline refactor, brief §8.1).

- [x] Nuke toolchains: out of scope for the localiser. Resolving `NUKE_PATH` to the localised copy of the current pipeline, as it currently is, is enough. (Longer term the modular toolchains could be baked into a build instead of selected at runtime, but that is a pipeline concern, not this project's.)
- [x] Where `NUKE_PATH` comes from does not matter to the design: AYON injects it at app startup; outside AYON a system env var (or similar) points at the stable local stub directory.
- [x] Nuke ordering: `init.py` runs at application start and `menu.py` only when the UI loads, so anything important (path/env setup, localising) must happen in `init.py`; `menu.py` is too late.

## Nuke refactor (see brief §8.1)
- [ ] What the localiser exposes to the pipeline: resolved root and release ID via env vars? Names TBD; avoid clashing with existing `TLA_COMP_*` variables.
- [ ] Local override for `config.json` debug flag, since it will live in an immutable release.

- [x] Blender: **5.0+ only**, no backward compatibility. (The add-on `bl_info` still says 4.2; update when the add-ons are next touched.)
- [x] Blender: **vanilla (non-AYON) launches are in scope.** A `--python` argument can't be the bootstrap, since local files live in a user account and vanilla has no such argument.

## Blender (see brief §8.3)
- [ ] **Gating test:** in Blender 5.0, does a release exposed at runtime from a `startup/` stub (script-directory entry and/or `sys.path` and/or `addon_utils.enable`) get its `addons/` and `presets/` picked up in the same session? The manual says script-directory preference changes need a restart.
- [ ] Mechanism: `BLENDER_SYSTEM_SCRIPTS` (set as a user env var by the install script) pointing at a stable local stub directory with a `startup/` stub. Recommended over preference writes. Confirm it works for AYON launches too, and that AYON doesn't already set `BLENDER_SYSTEM_SCRIPTS`.
- [ ] If runtime exposure doesn't work in-session: what does vanilla Blender do (launcher/wrapper, accept a one-launch lag, or document the limit)?
- [ ] PySide6 install / `QT_API` setup in `startup.py`: stays in the stable stub, moves to the install script, or stays separate? (Out of scope for the localiser itself.)
- [ ] Windows-only? `startup.py` uses `ctypes.windll` and `python.exe`.
- [ ] Publisher: exclude `__pycache__` / `*.pyc` from the Blender release.
- [ ] Later: convert add-ons to extensions (manual's recommended route)? Pipeline concern, not v1.

## Maya (see brief §8.2)
- [ ] How is `MAYA_CORE` consumed, and by what and when? (e.g. AYON menu/environment settings reading `corescripts_template.json` or adding the folder to `PYTHONPATH`.) If something reads it **before** `userSetup.py` runs, the localised root must be known pre-launch; if after, the stub can set `MAYA_CORE` in-process to the local root.
- [ ] Where does the existing `userSetup.py` live and who puts its folder on `PYTHONPATH` (AYON env injection, system env)? Does an AYON-provided `userSetup.py` also exist (Maya only executes one found on the path; verify)?
- [ ] Keep `userSetup.py` as-is plus a localiser call, or move its startup behaviour into the release (stub calls it)?
- [ ] Where do `ShotOverride`/`PreRenderChecks` (imported in the OpenPype branch of `userSetup.py`) come from? Is that branch still used?
- [ ] Reference `userSetup.py` bug, only if the OpenPype branch is live: `post_load_overrides_script_job` uses `cmds` without importing it.
- [ ] Publisher: run `generate_pype_menu()` before zipping and exclude `__pycache__`, `*.pyc`, `Thumbs.db`.

## Release and config
- [ ] Release ID format: semver, build IDs, or both. *Recommend: opaque IDs.*
- [ ] Network paths for `studio-pipelines.json` and `releases/`, and who has write access.
- [ ] Zip layout: confirm `python_root` per DCC (top-level folder or not).
- [ ] Override mechanism: env var name (`STUDIO_PIPELINE_<DCC>` is a placeholder; check against existing studio variables) and how TDs set it deliberately.
- [ ] Same-ID repair: *Recommend: never change content behind an ID; resync restores identical verified content only.*
- [ ] Trust model beyond a write-protected share (signing / separately held digest).

## Platform and versions
- [ ] Supported OSes (brief assumes Windows; confirm).
- [ ] Supported Maya, Blender, Nuke versions and their Python versions (limits stub syntax).

## Host lifecycle (verify per version)
- [ ] Maya: stub location/discovery for vanilla and AYON launches.
- [ ] Nuke: how `NUKE_PATH` is set for vanilla launches; `init.py` vs `menu.py` ordering.
- [ ] Blender: script-directory configuration per version, first-launch persistence, add-on ordering, avoiding preference side effects.
- [ ] First-run in-host install UX (blocking + message vs pre-warm by install script).
- [ ] What happens if the localiser/stub is missing or damaged, per DCC.

## Cache and ops
- [ ] Portable locking strategy for the supported OSes.
- [ ] Retention/cleanup of old releases and staging leftovers.
- [ ] Log location, rotation, and user-facing error mechanism.
- [ ] Startup-time baseline and acceptance targets.
- [ ] How the install script is distributed and updated, and how stubs are updated independently of releases.
