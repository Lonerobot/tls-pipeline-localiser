# 08 — Open Decisions and Risks

This is a working decision log. The Copilot agent should update it during discovery, distinguishing confirmed answers from recommendations and unanswered questions. Do not silently invent answers.

## Release selection

- [ ] Confirm precedence between explicit TD sandbox override and AYON project release.
- [ ] Define how sandbox mode is deliberately enabled so a test release cannot be selected accidentally in normal production work.
- [ ] Decide whether release IDs are semantic versions, unique build IDs, or both.
- [ ] Decide whether the selector supports only published immutable builds in v1 or also an explicit mutable working-tree development mode.

## Configuration and distribution

- [ ] Confirm the network source for `studio-pipelines.json`.
- [ ] Confirm the release artifact repository layout and access permissions.
- [ ] Decide how manifest authenticity is established. SHA-256 verifies artifact integrity against a known digest, but a checksum delivered alongside an untrusted artifact is not a complete trust model.
- [ ] Define offline policy for stale studio configuration and how staleness is reported.
- [ ] Decide whether configuration refresh happens only on launch, on AYON startup, or through another mechanism.

## Bootstrap and lifecycle

- [ ] Confirm exact supported Maya, Blender and Nuke versions.
- [ ] Confirm native bootstrap mechanisms and their ordering for each supported version.
- [ ] Identify operations that must happen before DCC process creation.
- [ ] Determine whether the vanilla bootstrap may synchronise during host startup, and how to prevent a poor or broken user experience if a large first-run install occurs.
- [ ] Decide what should happen if the localiser itself is missing or damaged.
- [ ] Confirm whether any host supports an appropriate early external launcher or wrapper for vanilla launches; do not assume it does.

## Cache and concurrency

- [ ] Confirm per-user cache location across supported operating systems.
- [ ] Choose a portable locking strategy appropriate to the supported platforms.
- [ ] Decide retention policy for old releases and staging leftovers.
- [ ] Decide whether a repair can publish a replacement under the same release ID or whether the immutable-release rule requires a new ID. Recommended default: never change content behind an existing release ID.
- [ ] Define cache-state schema and migration strategy.

## AYON integration

- [ ] Identify the correct pre-launch hook/extension point in the actual AYON version/template.
- [ ] Determine when project context and release settings are available.
- [ ] Decide how the resolved release is passed to the child process.
- [ ] Decide how progress/errors are surfaced and whether launch blocks until sync completes.
- [ ] Confirm all relevant AYON launch routes use the integration.

## Observability and support

- [ ] Choose log location and rotation/retention policy.
- [ ] Define user-facing messages for network unavailable, checksum failure, invalid release, permission errors and lock timeout.
- [ ] Decide what diagnostic command/menu action is exposed to TDs.
- [ ] Define startup performance measurements and acceptance targets.
