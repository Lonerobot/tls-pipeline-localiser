# Pipeline Localiser: Planning Blueprint

Planning and R&D for THE LINE's lightweight, host-aware pipeline localiser. Resolve one effective release for Maya, Blender or Nuke, copy and verify its immutable zip bundle locally, then expose it at the correct host startup stage.

**Status: planning, not implementation.** The original eight planning documents have been consolidated into:

| Document | Contents |
|---|---|
| [Design brief](.copilot/01_design_brief.md) | Scope, architecture, manifests, runtime flow, host research, trust model, testing strategy and phased implementation plan. |
| [Open decisions and risks](.copilot/02_open_decisions.md) | Confirmed decisions, unresolved questions and deployment/host validation gates. Recommendations are not decisions. |

The [platform and installer assessment](.copilot/01_design_brief.md#51-rd-assessment-platform-locations-and-lightweight-installation) compares Windows, macOS and Linux user/system directories and recommends a **shared workstation-local store**, not separate pipelines per user. A lightweight installer would provision protected bootstrap/configuration, writable data directories for an approved studio group, and stable host discovery. Unrestricted public write access is not recommended for executable pipeline code.

A TD's pre-launch override selects a bundle in that shared store and pulls it if missing; it does not change the studio default or other running sessions. Explicit repair of an already-cached bundle is separate. Exact permissions, installer details and supported OSes remain subject to review.

## Scope and research

V1 covers a stdlib-only core, publisher, lightweight installer, native-host stubs, per-DCC release selection and offline reuse of cached bundles. AYON integration, project overrides and manifest signing are deferred; future AYON integration must call the same core.

[`reference/`](reference/) contains existing pipeline code used for lifecycle research, not a localiser implementation. Key findings are in the design brief's host sections: Nuke needs location-independent root resolution, Maya's startup/discovery ordering needs confirmation, and Blender 5.0+ needs an in-session add-on/preset discovery test before its adapter can be designed.

Review the brief and open decisions before writing production code, installing dependencies or changing host settings. Verify platform permissions and host behaviour on the supported workstation images rather than assuming the proposed mechanisms work.
