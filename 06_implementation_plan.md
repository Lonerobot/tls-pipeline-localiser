# 06 — Discovery, Planning and Implementation Plan

## Phase 0: Repository and environment discovery (no code changes)

The first Copilot task is to inspect the current repository and runtime setup. Do not implement the localiser during this phase.

Record:

- Repository structure, language/runtime constraints and current conventions.
- Current locations and entry points for Maya, Blender and Nuke pipeline code.
- Existing environment variable names and configuration sources.
- Current AYON addon/template patterns and launcher integration points.
- Supported DCC and Python versions.
- Current source control and release/publishing practices.
- Network share paths or artifact sources, using placeholders in docs if paths are sensitive.
- Existing tests, linting, packaging and CI expectations.

Deliverable: a concise discovery report with file references and confirmed versus assumed facts.

## Phase 1: Lifecycle mapping

For each DCC and AYON launch route, map the order of operations:

1. Launcher/context resolution.
2. Process environment construction.
3. DCC process creation.
4. Native startup script discovery.
5. Python path/script path setup.
6. Pipeline imports.
7. Add-on/plugin registration.
8. UI/menu creation and callbacks.

Identify which operations must happen before process creation and which can safely happen inside the host. Verify claims for the actual supported DCC versions rather than generalising from one version.

Deliverable: host lifecycle matrix and sequence diagrams.

## Phase 2: Architecture proposal

Propose:

- Core modules and public API.
- Release selection rules and precedence.
- Configuration and manifest schemas.
- Local cache layout and locking strategy.
- AYON integration point(s).
- Host adapter contract and native bootstrap locations.
- Logging, errors and offline policy.
- Supported platform and Python-version scope.

Deliverable: an implementation design for review. No production code yet.

## Phase 3: Test design

Define tests before implementing core behaviour:

- Configuration parsing, schema validation and last-known-good cache.
- Release resolution for studio, project, sandbox and offline cases.
- Archive checksum mismatch and invalid manifest handling.
- ZIP path traversal rejection.
- Interrupted extraction and atomic publication.
- Concurrent attempts to install the same release.
- Already-installed fast path.
- Missing local root despite local state saying installed.
- Forced resync while another process may be using a release.
- Host adapter environment generation.
- Vanilla bootstrap failure reporting and idempotency.
- AYON pre-launch selection and no-launch-on-sync-failure behaviour.

Use temporary directories and synthetic release archives for core tests. Do not require studio network access for unit tests.

## Phase 4: Minimal core implementation

Only after approval, implement the smallest testable core:

1. Configuration parsing/validation.
2. Release resolution result model.
3. Local state/cache query.
4. Artifact retrieval and checksum verification.
5. Safe staged extraction and atomic publication.
6. Clear logging/errors.
7. Unit tests for success and failure paths.

Do not add host integration until the core's behaviour is covered by tests.

## Phase 5: Host adapters and vanilla bootstraps

Implement one host at a time, based on the lifecycle matrix. Start with the host whose existing startup path is best understood, not necessarily the easiest one to sketch. Validate the adapter inside each supported DCC version.

## Phase 6: AYON pre-launch integration

Add the thin AYON integration that resolves project context, invokes the localiser before host creation, and passes the effective release/environment to the DCC launcher. Keep synchronisation logic in the shared core.

## Phase 7: Rollout and observability

- Pilot with a small TD group.
- Measure startup time before and after.
- Log cache hits, installs, failures, release selection source and elapsed sync time.
- Test network unavailable, corrupted cache and rollback scenarios.
- Document forced resync and support diagnostics.
- Roll out gradually, retaining a straightforward way to disable the bootstrap if needed.

## Planning exit criteria

Do not begin implementation until:

- The existing repo and launch mechanisms have been inspected.
- The host lifecycle matrix is complete enough to identify bootstrap limits.
- Override precedence is agreed.
- The source and trust model for config/manifests is clear.
- Cache layout, failure behaviour and test strategy are reviewed.
- Proposed file layout and interfaces are accepted.
