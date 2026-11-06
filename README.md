# Pipeline Localiser: Planning Blueprint

Planning and R&D for THE LINE's lightweight, host-aware pipeline localiser. Resolve one effective release for Maya, Blender or Nuke, copy and verify its immutable zip bundle locally, then expose it at the correct host startup stage.

**Status: R&D complete for host exposure on Windows (Blender 5.2, Maya 2026, Nuke 17.0v3). The stdlib-only core and publisher are implemented and tested, and a test workstation in [`structure/`](structure) localises a bundle and runs its entry point in all three hosts (headless). Not yet built: the install script, real bundle exposure in the hosts (e.g. `pluginAddPath`, Blender script directories), the TD override and the pilot.** The original eight planning documents have been consolidated into:

| Document | Contents |
|---|---|
| [Design brief](.copilot/01_design_brief.md) | Scope, architecture, manifests, runtime flow, host research, trust model, testing strategy and phased implementation plan. |
| [Open decisions and risks](.copilot/02_open_decisions.md) | Confirmed decisions, unresolved questions and deployment/host validation gates. Recommendations are not decisions. |
| [User discovery worksheet](.copilot/03_user_discovery.md) | Host-level verification tasks with blanks to fill in once tested on real workstations/DCCs. |

[`discovery-tests/`](discovery-tests) contains throwaway, stdlib-only stubs to deploy into real Maya/Nuke/Blender installs to produce the evidence the worksheet asks for (not localiser code).

The [platform and installer assessment](.copilot/01_design_brief.md#51-rd-assessment-platform-locations-and-lightweight-installation) compares Windows, macOS and Linux user/system directories and recommends a **shared workstation-local store**, not separate pipelines per user. A lightweight installer would provision protected bootstrap/configuration, writable data directories for an approved studio group, and stable host discovery. Unrestricted public write access is not recommended for executable pipeline code.

A TD's pre-launch override selects a bundle in that shared store and pulls it if missing; it does not change the studio default or other running sessions. Explicit repair of an already-cached bundle is separate. Exact permissions, installer details and supported OSes remain subject to review.

## Code and tests

- [`src/localiser/`](src/localiser): the core (config/manifest parsing, resolution, staged verify-and-extract install, locking, publisher). Stdlib-only, no DCC imports. `localiser.localise(host, series, config)` returns the verified local bundle root for a host stub to expose, and `expose_environment` sets `TLS_PIPELINE_<HOST>` to it. `TLS_PIPELINE` names the pipeline root holding `config.json`. The blueprint it follows is in [`structure/`](structure) and the decisions log.
- [`tests/`](tests): unit tests using temp dirs and synthetic zips; no share access needed.

```powershell
python -m unittest discover -s tests -t .
```

Passes on Python 3.11 (Maya 2026's `mayapy`; Nuke 17.0v3's bundled `python.exe`, 3.11.11), 3.13 (Blender 5.2) and 3.14. The supported floor is 3.11.

## Test workstation

[`structure/`](structure) is a working prototype of the blueprint: a pipeline root (`THE-LINE/pipeline`) with a shared entry, per-host bootstrap stubs, a fake remote repository and fake bundle sources. Hosts find their stub through their own variable; the stub detects the DCC version, calls the localiser, and runs the bundle's `__init__.py`.

| Variable | Set by | Value |
|---|---|---|
| `TLS_PIPELINE` | you / installer | the pipeline root |
| `PYTHONPATH` (Maya), `NUKE_PATH`, `BLENDER_SYSTEM_SCRIPTS` | you / installer | `<root>/bootstrap/<host>` |
| `TLS_PIPELINE_MAYA` / `_NUKE` / `_BLENDER` | the localiser | the resolved bundle path |

```powershell
python structure\build_test_workstation.py   # copy the core in; publish fake bundles to the fake remote
python structure\run_host.py maya            # or nuke / blender; add --gui for the full application
```

`run_host.py` prints the variables it sets. Old discovery stubs left in a DCC's user folders or preferences will also run and add noise.

## Scope and research

V1 covers a stdlib-only core, publisher, lightweight installer, native-host stubs, per-DCC release selection and offline reuse of cached bundles. AYON integration, project overrides and manifest signing are deferred; future AYON integration must call the same core.

[`reference/`](reference/) contains existing pipeline code used for lifecycle research, not a localiser implementation. Key findings are in the design brief's host sections (see §8.4 for the discovery results): Nuke needs location-independent root resolution, Maya can run more than one `userSetup.py`, and Blender exposes a release in-session when set up during startup registration, before saved add-ons load.

Review the brief and open decisions before changing host settings or adding host stubs. Verify platform permissions and host behaviour on the supported workstation images rather than assuming the proposed mechanisms work.
