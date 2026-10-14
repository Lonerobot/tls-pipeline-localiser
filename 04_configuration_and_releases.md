# 04 — Configuration, Release Format and Local Cache

## 1. Studio defaults

The authoritative studio configuration should be a small JSON file on an internal network share or internal service. Start with the existing network share unless discovery shows a compelling reason not to.

Example only:

```json
{
  "schema_version": 1,
  "pipelines": {
    "maya": "2.9.0",
    "blender": "1.14.0",
    "nuke": "3.2.4"
  }
}
```

These version strings are illustrative, not actual studio release commitments.

Requirements:

- Include a schema version so format changes can be handled deliberately.
- Validate required host keys and release ID types.
- Treat malformed or unsupported configuration as an error; do not guess.
- Cache the last successfully parsed configuration locally for offline vanilla launches.
- Write the cached config atomically only after validation.
- Log whether the active config came from the network or last-known-good cache.
- Avoid embedding project-specific policy in the studio defaults file unless a later design explicitly requires it.

## 2. Release identity

Each DCC package is versioned independently. A release ID must identify immutable content. Once a release ID is published, its artifact and manifest must not be silently changed. A fix requires a new release ID.

Human-readable semantic versions are useful, but unique build IDs are also valid, especially for test builds. The resolver treats release IDs as opaque identifiers after validation; it should not infer ordering unless a defined policy requires it.

## 3. Release repository layout

Illustrative layout:

```text
pipeline-repository/
  releases/
    maya-tools/
      2.9.0/
        pipeline.zip
        manifest.json
    blender-tools/
      1.14.0/
        pipeline.zip
        manifest.json
    nuke-tools/
      3.2.4/
        pipeline.zip
        manifest.json
  config/
    studio-pipelines.json
```

The actual transport can be a network share initially. Avoid making DCC clients perform Git operations during startup. Git may remain the source-control/publishing mechanism behind the release artifacts.

## 4. Release manifest

Illustrative schema, to be refined after repository discovery:

```json
{
  "schema_version": 1,
  "package_id": "maya-tools",
  "release_id": "2.9.0",
  "artifact": "pipeline.zip",
  "sha256": "<64-character-hex-digest>",
  "entrypoints": ["..."],
  "compatibility": {
    "hosts": ["maya"],
    "host_versions": []
  }
}
```

Requirements:

- Manifest identity must match the requested package and release ID.
- Verify artifact checksum before extraction.
- Validate required files/entry points after extraction.
- Consider whether compatibility metadata is required in v1; do not invent host-version policy without evidence.
- The manifest itself must be obtained from a trusted publication location or protected by a trusted configuration/signature mechanism. A checksum from an untrusted manifest does not establish trust on its own.

## 5. Local cache layout

Illustrative Windows location:

```text
%LOCALAPPDATA%/TheLine/Pipeline/
  releases/
    maya-tools/2.9.0/...
    blender-tools/1.14.0/...
  state/
    installed-releases.json
    studio-pipelines.json
  staging/
  locks/
  logs/
```

Use the platform's standard per-user application-data location rather than assuming Windows only, unless repository discovery confirms Windows-only support. Do not hardcode user names or workstation-specific paths.

The release directory is immutable after publication. Local state records successfully installed releases and enough metadata to detect a missing or incomplete installation without hashing every file on each launch.

## 6. Archive and extraction requirements

- Prefer one archive per release to reduce network overhead from many small files.
- Use Python standard library facilities where practical (`zipfile`, `hashlib`, `pathlib`, `shutil`, `os`).
- Validate archive paths before extraction; reject absolute paths, traversal segments and unsafe paths.
- Ensure staging and final paths are on a filesystem where the chosen publish/rename strategy is valid.
- Consider platform-specific file locking, permissions, symlinks, case sensitivity and antivirus scanning during implementation planning.
- Exclude generated caches such as `__pycache__` where appropriate, but do not delete source files or metadata needed by the host.
- Do not add parallel extraction or elaborate delta updates without benchmark evidence.

## 7. Local state and resync

Normal startup should compare the requested release ID to local state and confirm the expected root exists. Full integrity checks belong in install, forced resync or an optional audit command.

Provide conceptual operations equivalent to:

- `ensure_local_release(host, release_id)` — idempotently ensures a release is available.
- `force_resync(host, release_id)` — explicitly reinstalls the selected release transactionally.
- `get_cache_status(host)` — reports cached releases and validity status.

Exact API names are suggestions, not requirements.

## 8. Environment variable contract

Environment variables are a transport mechanism for selection, not the local cache itself. Keep names and meanings unambiguous. A single per-DCC variable may represent the effective release ID, for example:

- `STUDIO_PIPELINE_MAYA=2.9.0`
- `STUDIO_PIPELINE_BLENDER=1.14.0`
- `STUDIO_PIPELINE_NUKE=3.2.4`

When AYON selects a project or sandbox release, it replaces the value for that DCC in the child process environment. Do not use separate variables that imply two pipeline roots are simultaneously active. The final naming convention must be checked against existing studio variables before adoption.

Do not assume changing `os.environ` inside a running host retroactively changes the process environment inherited at launch or repairs already-imported modules and configured paths.
