# 05 — Host Adapters and Load-Order Constraints

## Purpose

The shared localiser must not pretend that Maya, Blender and Nuke have identical startup lifecycles. Each host adapter translates a resolved release into the appropriate host configuration and initialisation steps.

The details below are investigation requirements, not final assertions about exact callback timing. Confirm against the installed host versions, current studio setup and official documentation before implementing.

## Shared adapter contract

Conceptual responsibilities:

1. Identify/validate the host.
2. Receive a resolved release object from the core.
3. Produce any pre-launch environment variables or path values required by the launcher.
4. Provide a minimal native bootstrap for vanilla launches.
5. Perform host-internal configuration only at a valid lifecycle stage.
6. Prevent loading more than one effective release.
7. Report initialisation failures clearly.

A possible interface could expose `build_launch_environment(resolved_release, base_environment)` and `initialise_in_host(resolved_release)`, but final method names and boundaries should follow repository conventions and lifecycle findings.

## Maya investigation

Determine:

- How the current studio code is exposed through Python paths, Maya module paths, `userSetup.py`, plug-ins or other mechanisms.
- Which setup must happen before Maya starts versus during Python initialisation.
- How a native bootstrap can import the localiser without first importing pipeline modules.
- Whether Maya Python version differences affect the bootstrap's syntax or standard-library use.
- How to avoid duplicate startup execution or repeated path insertion.
- How the existing pipeline's callbacks and plug-in loading order interact with the local release root.

Do not assume that changing environment variables from `userSetup.py` affects Maya's inherited process environment or already-initialised module search state.

## Blender investigation

Determine:

- The supported way the current Blender version discovers scripts and startup modules.
- Whether script directories should be configured pre-launch, in-host, or both.
- How add-ons are enabled and whether that must be persisted in user preferences or performed per launch.
- Whether enabling add-ons before the local release path is available creates an ordering issue.
- How to avoid unintended modification of user preferences or duplicate add-on registration.
- Whether startup behaviour differs materially across the studio's supported Blender versions.

Do not assume that adding a directory to a Python path alone is equivalent to configuring Blender script directories or enabling an add-on.

## Nuke investigation

Determine:

- How the current studio setup uses `NUKE_PATH`, `init.py`, `menu.py` or other startup files.
- Which code executes early enough to configure paths and which code must run later.
- How menu construction and pipeline imports depend on initialisation order.
- How to prevent duplicate menu commands, callbacks or path entries.
- Which Nuke versions and Python runtimes need support.

Do not assume `NUKE_PATH` can be safely repaired after the relevant startup scripts have already been discovered and executed.

## AYON integration investigation

Determine:

- Which AYON lifecycle hooks or launcher extension points can run before the DCC process is created.
- When project context and project-specific settings are available.
- How the selected release ID and resolved local root should be passed to the child process.
- How sync progress and errors should be surfaced to the user.
- Whether a DCC can be launched through multiple AYON paths that need consistent treatment.
- How sandbox overrides should be represented and protected from accidental use in ordinary production launches.

Prefer a pre-launch hook that calls the shared localiser. Do not duplicate the core sync logic in an AYON addon.

## Bootstrap constraints

The native bootstrap should be as small and stable as practical. It should:

- Use only dependencies guaranteed to be available in the relevant host runtime, ideally Python standard library only.
- Avoid importing the pipeline package before resolving the release.
- Locate and import the shared localiser from a stable bootstrap location.
- Log enough context to diagnose a failed launch.
- Be idempotent if the host runs startup hooks more than once.
- Have a documented failure strategy if the localiser cannot be found or a release cannot be installed.

If the bootstrap itself is stored only inside the release it needs to install, the design is circular. Its location and update strategy must be independent of the managed release bundle.

## Host compatibility matrix

Before implementation, create a matrix with at least:

- DCC and supported version(s).
- Native bootstrap location/mechanism.
- Earliest usable lifecycle stage.
- Pre-launch requirements.
- In-host requirements.
- Python version and syntax compatibility.
- AYON launch path.
- Vanilla launch path.
- Known constraints and evidence/source.
