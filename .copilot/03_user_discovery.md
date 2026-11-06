# 03 — User Discovery: Host-Level Verification Worksheet

Companion to [01_design_brief.md](./01_design_brief.md) and [02_open_decisions.md](./02_open_decisions.md). The brief and decisions log describe what still needs deciding; this document turns the items that can only be answered by **looking at a real host/workstation** into discrete tasks with a blank to fill in.

**How to use this:** work through each task, record what you found in the `Answer:` line (replace the `_____` placeholder), and note the DCC/OS/version you tested against where it matters. Once filled in, these answers feed back into updating `[x]`/`[ ]` status in 02_open_decisions.md. Leave a task blank if you can't test it yet rather than guessing.

**Test stubs:** the §0 gating tests and several per-host items below have ready-to-deploy, self-contained test scripts in [`discovery-tests/`](../discovery-tests) — see [`discovery-tests/README.md`](../discovery-tests/README.md) for the full map and shared logging convention. These are throwaway instrumentation, not localiser code.

---

## 0. Gating tests (highest priority — these block stub design)

### G1. Blender in-session script-directory pickup
In Blender 5.0+, if a `startup/` script (loaded via `BLENDER_SYSTEM_SCRIPTS`) adds/refreshes a script-directory entry and/or `sys.path` and/or calls `addon_utils.enable()` at startup, are that release's `addons/` and `presets/` picked up **in the same session** — or does it require a restart (as the 5.0 manual implies for preference-based changes)?
- Test: point `BLENDER_SYSTEM_SCRIPTS` at a stub, have its `startup/` script register a release path by each of the three methods, launch Blender 5.0+ vanilla, and check whether an add-on from that release is available without restarting.
- Test stub: [`discovery-tests/blender/`](../discovery-tests/blender)
- Answer: **Yes, in the same session, if done at the right time** (Windows, Blender 5.2.3 LTS, normal UI launch, 2026-11-02). A startup `register()` that sets the named script-directory entry and calls `bpy.utils.refresh_script_paths()` made the release's `addons/` and `modules/` importable and its add-on enableable with no restart; presets were confirmed in a background run. Two traps found: (1) `bpy.ops.preferences.addon_refresh()` alone does **not** update `sys.path`; (2) doing this from a timer is too late, because Blender has already auto-loaded saved enabled add-ons from the previously persisted path, and re-enabling reuses the already imported module. Details and a stub sketch: [`discovery-tests/blender/README.md`](../discovery-tests/blender/README.md). Not yet tested on other Blender versions or platforms.

### G2. Nuke `pluginAddPath` ordering
When the stub's `init.py` (loaded via `NUKE_PATH`) calls `nuke.pluginAddPath(<release root>/<python_root>)`, does Nuke then run **that directory's** `init.py` (and later `menu.py` at UI load) in the right order, same as if it had been on `NUKE_PATH` from the start?
- Test: set up a stub `init.py` that calls `pluginAddPath` pointing at a release folder containing its own `init.py`/`menu.py`; confirm both run and in the expected order.
- Test stub: [`discovery-tests/nuke/`](../discovery-tests/nuke)
- Answer: **Yes** (Nuke 17.0v3, Windows, GUI launch, 2026-11-02). With only `stub/` on `NUKE_PATH`, `nuke.pluginAddPath(<release>)` from the stub's `init.py` caused Nuke to run the release's `init.py` and then, once the UI loaded, its `menu.py`. Observed order: stub `init.py` start, `pluginAddPath` call, stub `init.py` end, **then** the release's `init.py`, then the release's `menu.py` about a second later. So the added directory's `init.py` runs right after the calling `init.py` returns, not inside the `pluginAddPath` call; the stub must not expect its effects to exist immediately after the call. Not tested: ordering against other `NUKE_PATH` entries (e.g. AYON's), non-GUI/terminal Nuke, or other Nuke versions. A stale `TLS_DISCOVERY_FAKE_RELEASE` from the Blender test initially misdirected the first run; the Nuke stub now uses its own variable.

### G3. Maya `userSetup.py` resolution when multiple are on the path
If more than one `userSetup.py` is reachable on `PYTHONPATH`/`sys.path` (e.g. an AYON-provided one and our stub), which one(s) does Maya actually execute? Confirm Maya only runs **one** `userSetup.py` per process (per Maya docs) or whether it can run several from different path entries.
- Test: place two differently-named-but-discoverable `userSetup.py` files (or one via AYON env injection, one via system `PYTHONPATH`) and confirm actual behaviour by logging from each.
- Test stub: [`discovery-tests/maya/`](../discovery-tests/maya)
- Answer: **Maya 2026 (Windows) ran more than one `userSetup.py` in the same process.** Stub B (folder on `PYTHONPATH`, `sys.path` index 1) and stub C (`Documents\maya\2026\scripts`, index 34) both executed, B first. The "only one runs" assumption is wrong. Order matched `sys.path` order (one observation). Maya executes `userSetup.py` via `execfile`, which defines no `__file__`; stubs must not use it. **Not shown:** whether Autodesk's MASH `userSetup.py` or a real `Documents\maya\scripts\userSetup.py` also ran (they don't log), whether an exception in an earlier file stops later ones, and behaviour with AYON's real file. Implication: a localiser stub can coexist with others but must not assume it runs first or alone.

---

## 1. Maya

### M1. `MAYA_CORE` consumption
What actually reads `MAYA_CORE`, and when relative to `userSetup.py`?
- Is it read by AYON menu/environment settings, `corescripts_template.json`, something added to `PYTHONPATH`, or something else?
- Does it get read **before** `userSetup.py` runs (meaning the localised root must be known pre-launch) or **after** (meaning the stub can set it in-process)?
- Test stub: [`discovery-tests/maya/`](../discovery-tests/maya) (stub A's import-watch instrumentation)
- Answer: _____

### M2. Existing `userSetup.py` location and path ownership
Where does the current `userSetup.py` live on disk, and what puts its containing folder on `PYTHONPATH` — AYON env injection, a system/user env var, or something else?
- Answer: Partial. On this machine a `userSetup.py` already exists in `Documents\maya\scripts`, which Maya 2026 puts on `sys.path` (with `Documents\maya\2026\scripts` and `2026\prefs\scripts`). Its owner/source is still to be established. Do not overwrite an existing `userSetup.py` when testing or deploying.

### M3. AYON-provided `userSetup.py`
Does AYON itself ship/inject a separate `userSetup.py`? If so, which one does Maya run — see G3 above — and does our stub need to merge with or replace it?
- Test stub: swap `discovery-tests/maya/stub_b/userSetup.py` for the real AYON-provided file and re-run the G3 test.
- Answer: _____

### M4. `ShotOverride` / `PreRenderChecks` origin
The OpenPype branch of the reference `userSetup.py` imports `ShotOverride` and `PreRenderChecks`. Where do these come from, and is that branch still live/used in current pipelines?
- Answer: _____

### M5. Supported Maya and Python versions
Which Maya versions must the stub and bundle support, and what Python version ships with each (constrains stub syntax — reference `__pycache__` shows a 3.7–3.11 history; docs say Maya 2026 → Python 3.11)?
- Answer: _____

---

## 2. Nuke

### N1. Source of `NUKE_PATH`
Confirmed as not design-relevant, but worth recording for deployment testing: in your environment, is `NUKE_PATH` set by AYON env injection, a system environment variable, or a launcher script — for both vanilla and AYON launches?
- Answer: potentially all of those

### N2. Nuke Python version(s)
Which Nuke versions are in use/supported, and which Python version(s) do they embed (constrains stub syntax)?
- Answer: print(sys.version)
print(sys.version_info[:3])
print(sys.executable)
# Result: 3.11.11 (remotes/origin/foundry/v3.11.11:42e60506bdd, Jul 23 2025, 10:51:14) [MSC v.1935 64 bit (AMD64)]
(3, 11, 11)
C:\Program Files\Nuke17.0v3\Nuke17.0.exe

### N3. `init.py` vs `menu.py` ordering in practice
Separate from G2: does anything in the current pipeline rely on `menu.py` running logic that should actually happen at `init.py` time (startup setup that's currently "too late")?
- Test stub: [`discovery-tests/nuke/`](../discovery-tests/nuke) (`fake_release_init_ran` vs `fake_release_menu_ran` timestamps confirm the ordering gap directly).
- Answer: Partial. The mechanical ordering is confirmed (Nuke 17.0v3 GUI): a release's `init.py` runs at startup, its `menu.py` only after the UI loads (about a second later in the test). Whether the *current pipeline* relies on `menu.py` for logic that should run earlier is a code-review question and is still open.

---

## 3. Blender

### B1. Does AYON already set `BLENDER_SYSTEM_SCRIPTS`?
If AYON's Blender integration sets this env var itself, our install script's value must be reconciled (merged/overridden) rather than silently clobbered or ignored.
- Test stub: [`discovery-tests/blender/`](../discovery-tests/blender) README, "B1" section.
- Answer: **No: AYON does not set `BLENDER_SYSTEM_SCRIPTS`** (reported by the user, 2026-11-02; not independently verified from an AYON launch log). The install script can therefore set it without reconciling with an AYON-provided value. Still to confirm: that a newly started AYON-launched Blender inherits the machine/user value (P2), and that nothing else on a workstation already sets it, so the install script should still append rather than overwrite.

### B2. Script-directory entry naming and staleness
Confirm whether `set_pipeline_location()` (or its replacement) is still used, and whether a persisted script-directory entry (named e.g. `THELINE_PIPELINE`) needs to be refreshed every launch to avoid pointing at a stale/old release path.
- Test stub: [`discovery-tests/blender/`](../discovery-tests/blender) README, "B2" section (`fake_release_v1` → `fake_release_v2` re-point test).
- Answer: **A persisted entry goes stale and must be refreshed every launch, before add-ons load.** Updating the same named entry in startup `register()` re-pointed it v2 → v1 without creating a duplicate, and both the module and the add-on loaded from the new release (UI launch; v1 → v2 confirmed in an isolated-preferences background run). Updating it later from a timer failed: the old release's add-on had already loaded. Whether `set_pipeline_location()` is still used remains unchecked.

### B3. PySide6 / `QT_API` setup ownership
`startup.py` currently sets `QT_API=pyside6` and pip-installs PySide6 into Blender's own `site-packages` (with UAC elevation retry on Windows) before AYON imports Qt. Decide where this now lives: stable local stub, install script, or something else entirely separate from the localiser.
- Answer: _____

### B4. Windows-only assumption
`startup.py` uses `ctypes.windll` and `python.exe` directly. Is Blender support required on macOS/Linux for v1, or is Windows-only acceptable (at least for the PySide6/elevation portion)?
- Answer: _____

### B5. Supported Blender and Python versions
Confirm Blender 5.0+ is really the full support floor (no 4.x fallback anywhere), and which Python version(s) ship with the supported Blender releases (manual/bytecode tag points to 3.13 for 5.0).
- Answer: _____

### B6. Add-on → extension conversion
Out of scope for v1, but worth a quick check: do any current add-ons already ship a `blender_manifest.toml` (extension format), or are they all legacy single-file add-ons? Useful context for a later pipeline refactor.
- Answer: _____

---

## 4. Platform, OS and workstation checks

These are less "open the DCC" and more "open a terminal / check with IT", but still need a real workstation or managed image rather than a guess.

### P1. Supported operating systems
Which OSes must v1 actually support: Windows only, or Windows + macOS + Linux? (Brief §5.1 assessed all three but this isn't confirmed.)
- Answer: _____

### P2. Machine-wide environment variable propagation (Windows)
After the install script sets a machine-wide env var (e.g. `NUKE_PATH`, `BLENDER_SYSTEM_SCRIPTS`), does a **newly started** launcher/session pick it up without a reboot? Does an already-running AYON process keep its old environment, as expected?
- Answer: _____

### P3. macOS / Linux launch environment inheritance
If macOS/Linux are in scope: do Finder/Dock launches (macOS) or desktop launchers (Linux) inherit the env vars set by machine/session integration, or only shell-launched sessions?
- Answer: _____

### P4. ProgramData / shared root permissions
On a real managed workstation: can the intended runtime/artist group actually read + write the proposed data subtrees (`releases/`, `state/`, `staging/`, `locks/`, `logs/`) under `C:\ProgramData\TheLine\Pipeline` (or OS equivalent), including files created by a different account? Confirm inheritance, not just parent-folder writability.
- Answer: _____

### P5. Repository share access
Is the network share path (`pipeline-repository/`) reachable via a path that doesn't depend on a per-user mapped drive (UNC path on Windows, managed mount on macOS/Linux), for every account/identity that needs to read it?
- Answer: _____

---

## 5. Release and ops details

### R1. Release ID format
Confirm: opaque IDs only (recommended), or semver / build-ID based?
- Answer: _____

### R2. Override env var naming
Does `STUDIO_PIPELINE_<DCC>` clash with any existing studio environment variable naming convention?
- Answer: _____

### R3. Zip layout per DCC
For each DCC bundle, confirm whether the zip has a top-level wrapping folder or not (affects `python_root` per package).
- Maya: _____
- Nuke: _____
- Blender: _____

---

## Notes
- Items here mirror the `[ ]` entries in [02_open_decisions.md](./02_open_decisions.md); once answered, update that log's checkboxes/status accordingly rather than duplicating the answer in two places long-term.
- If an answer reveals a new constraint or risk, add it back into 02_open_decisions.md rather than only recording it here.
