# 03 — Runtime Procedure and State Transitions

## A. Standard AYON launch

1. AYON determines the DCC and launch context.
2. Resolve the studio default for that DCC.
3. If the project context selects a release, replace the default selection with that release.
4. If a deliberate TD override is supplied, apply the documented override precedence. Do not merge releases.
5. Validate the selected release identifier and locate its manifest/artifact.
6. Check local cache metadata for that exact release.
7. If valid and present, reuse it.
8. If absent, retrieve the artifact, verify it, extract to staging, validate expected contents, then publish atomically.
9. Build the pre-launch environment through the appropriate host adapter.
10. Launch the DCC with the resolved environment.
11. Host-native initialisation loads only from the resolved local release root.

If any required stage fails, AYON should not launch the host as if the selected release were ready. Return a useful error containing the host and release ID.

## B. Vanilla DCC launch

1. The host invokes its small native bootstrap.
2. Bootstrap identifies the host and obtains the studio configuration from the configured network source, or the last-known-good cached config if network access fails.
3. Resolve the effective release. No project context should be invented if none is available.
4. Ensure the selected release is cached, subject to what can safely be done inside that host's startup lifecycle.
5. Configure paths and initialise the selected release using host-specific mechanisms.
6. Log the selected release and any limitations or failures.

**Important:** the vanilla path cannot be assumed to provide the same pre-launch control as AYON. Investigate each host's actual startup order. If a required action must happen before process creation, document that the in-host bootstrap cannot guarantee it and identify a viable alternative.

## C. Release resolution policy

Conceptual precedence:

1. Explicit, deliberately enabled TD sandbox/test override.
2. Project-specific release supplied by AYON launch context.
3. Studio default for that DCC.

The team must confirm whether sandbox should outrank project context or whether sandbox selection should only be allowed in an explicit TD launch mode. This policy must be explicit in code and tests.

An override is a replacement of the effective release. It is not a second pipeline root. Do not define separate “studio pipeline” and “override pipeline” paths that are both added to Python paths.

## D. Local cache states

For each package/release, model states conceptually as:

- `missing`
- `installing` (staging only; never considered usable)
- `installed_valid`
- `invalid` or `incomplete`
- `repair_required`

Only `installed_valid` may be returned as the resolved local release. A staging directory must never be mistaken for a completed release.

## E. Safe installation procedure

1. Acquire a per-package/release lock or otherwise prevent concurrent installers from corrupting the same target.
2. Create a unique staging directory on the same filesystem as the final cache location where atomic rename is expected.
3. Retrieve/copy the archive and verify its SHA-256 against the trusted manifest/config metadata.
4. Validate archive member paths before extraction to prevent path traversal (zip-slip).
5. Extract into staging.
6. Validate required files, package identity and release ID.
7. Write local installation metadata.
8. Atomically rename/publish staging to the final immutable release directory.
9. Update local state only after successful publication.
10. Release the lock and clean up abandoned staging data when safe.

Never overwrite files inside a release directory that a running DCC may be using. A repair creates/replaces an installation transactionally; it does not partially mutate a live release.

## F. Failure and offline behaviour

- Network configuration unavailable: vanilla mode may use the last successfully retrieved configuration and cached release. Clearly log that it is using stale configuration.
- Requested explicit project/sandbox release unavailable: fail clearly; do not silently fall back to studio default.
- Artifact missing or checksum mismatch: do not publish the release; preserve existing valid releases.
- Interrupted install: staging is not valid; retry or clean up safely on a future run.
- Cache says installed but release root is missing: treat as invalid and repair, subject to locking.
- Another process is installing the same release: wait briefly, reuse the completed release, or return a controlled status. Do not race-write the final directory.

## G. Normal startup performance

The fast path should only need:

- Read a small configuration file or use an already available resolved launch selection.
- Compare requested release ID with local state.
- Confirm that the expected local release root exists and its local state says installation completed.

Do not recursively enumerate network directories or hash every installed file on every startup. Offer forced resync and optionally a separate integrity audit for repair scenarios.
