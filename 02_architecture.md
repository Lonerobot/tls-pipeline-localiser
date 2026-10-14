# 02 — Architecture

## Design principle

Separate **release selection**, **release localisation**, and **host initialisation**. These are related but distinct responsibilities and may occur at different lifecycle stages.

## Logical components

### 1. Release selector / context resolver

Determines the single effective release for a DCC process. Inputs may include:

- DCC identity, and optionally DCC version/platform.
- Studio default configuration.
- An explicit launch-context override supplied by AYON.
- An explicit TD sandbox/test override.
- Last-known-good studio configuration for supported offline vanilla launches.

It should return a structured resolution result, not mutate host state. It should identify the selected release and why it was selected.

### 2. Localiser core

Host-independent Python module responsible for:

- Reading and validating configuration and manifests.
- Resolving release artifact locations from release IDs.
- Checking local cache state.
- Fetching/copying and verifying a release archive when missing.
- Safely extracting to a staging directory.
- Publishing a completed release atomically into the immutable local cache.
- Recording local state and returning the final release root.
- Providing an explicit forced-resync operation.

The core must not import Maya, Blender, Nuke, AYON, or pipeline bundle modules.

### 3. Host adapter

A host-specific adapter knows how the selected release is exposed and initialised in its DCC. It handles environment variables, path configuration, native startup hooks, add-on setup, and any post-start initialisation that cannot happen before process creation.

The adapter must not choose a different release independently. It receives the already-resolved release information.

### 4. Entry points

Different entry points can call the same core:

- **AYON pre-launch integration:** knows project context and can prepare the exact release before launching the DCC.
- **Vanilla host bootstrap:** runs from the host's native startup mechanism and uses the studio default or a deliberately supplied override.
- **Manual repair command:** allows a user/TD to force-resync a release or inspect local cache status.

These are entry points into the same localiser, not separate implementations of localisation logic.

### 5. Release publisher

The publishing workflow creates immutable release artifacts and manifests. It is conceptually separate from runtime localisation. Source control may be Git, but DCC clients should not need to perform Git operations just to launch the pipeline. The initial artifact transport can be an existing network share.

## Suggested logical flow

`Entry point → Identify host → Resolve effective release → Ensure local release → Host adapter configures/initialises host`

AYON can perform the first four stages before process creation. A vanilla host bootstrap may only be able to perform some stages after the process has started; this limitation must be documented per host.

## One effective release per host process

There is no layered “studio pipeline plus override pipeline.” An override replaces the default selection for that DCC. For example, Maya may resolve to `2.9.0` in a normal launch or `feature-a81c3d2` in an overridden launch, but it must not load both as competing pipeline roots.

Studio defaults are independent by DCC. Selecting a Maya override must not change Blender or Nuke selections.

## Suggested release result

A resolved release object should carry at least:

- `host`: e.g. `maya`, `blender`, `nuke`.
- `package_id`: e.g. `maya-tools`.
- `release_id`: immutable release/build identifier.
- `selection_source`: e.g. `studio`, `project`, `sandbox`, `last_known_config`.
- `root_path`: verified local release root.
- `manifest`: parsed, validated release metadata.

The exact implementation type can be a dataclass or a simple validated structure, depending on the repository's Python compatibility requirements.

## Suggested repository boundaries

Names below are conceptual, not mandatory until the repository is inspected:

- `localiser/`: shared core, config, cache, artifact and validation logic.
- `localiser/hosts/`: host adapters for Maya, Blender and Nuke.
- `bootstrap/`: tiny host-native entry points with minimal dependencies.
- `ayon_integration/`: AYON hooks/plugin integration for pre-launch preparation.
- `publisher/` or `tools/`: release packaging and manifest generation, if in scope.
- `tests/`: unit, integration, host-contract and failure-mode tests.

Do not force this exact layout if the existing repository has a clearer convention. Explain any proposed deviation.
