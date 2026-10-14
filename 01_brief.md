# 01 — Project Brief

## Problem

Pipeline code currently lives on shared network locations and is exposed to DCCs through host-specific startup mechanisms. Repeated filesystem access to many small files can slow DCC startup. The goal is to keep executable pipeline code on the user's local drive while preserving controlled studio, project, and TD-test release selection.

The localiser must also respect DCC load order. It cannot assume that a script running inside a host can perform every action that would ideally happen before the host process starts.

## Goals

- Reduce routine DCC startup dependency on network filesystem I/O.
- Cache immutable, versioned pipeline releases locally.
- Resolve one effective release per DCC process.
- Support studio defaults, AYON project overrides, and explicit TD sandbox/test overrides.
- Support vanilla DCC launches without AYON.
- Keep the shared localiser independent of DCC-specific configuration details.
- Use a small network-hosted JSON file as the studio's default release selection.
- Make first-run installation safe, validated, observable, and recoverable.
- Keep the common startup path cheap: local metadata checks rather than full-tree hashing or network traversal.
- Produce clear diagnostics when a requested release cannot be resolved or installed.

## Non-goals for the first version

- Building a general package registry or cloud distribution platform.
- Automatically updating a running DCC process or replacing files in use.
- Supporting arbitrary mutable working trees as if they were immutable production releases.
- Building a monolithic pipeline package shared by all DCCs.
- Implementing project-release policy inside the localiser itself. AYON or another launch-context provider supplies that selection.
- Silent fallback from a requested project or sandbox release to the studio default.
- Optimising archive extraction through concurrency before measuring real bottlenecks.

## Primary users and scenarios

1. **Normal studio use:** user launches AYON; required studio releases are pre-cached; DCC starts using local code.
2. **Project-specific pipeline:** AYON supplies a project-selected release; localiser ensures that exact release is cached before launch.
3. **TD sandbox/test:** an explicit override selects a separately published test build or other clearly identified development source.
4. **Vanilla DCC launch:** a small host-native bootstrap uses the studio default configuration and initialises the pipeline as early as the host permits.
5. **Offline launch:** if the network config cannot be reached, a vanilla launch may use the last successfully retrieved config and locally cached release. Explicit overrides must still resolve exactly or fail clearly.
6. **Repair:** a TD or support user can request a forced resync of the selected release without modifying files currently used by another process.

## Success criteria

- A routine launch of an already-cached release does not recursively scan the network release tree or hash every local file.
- A missing release is installed before DCC launch where the launcher supports pre-launch preparation.
- A host-native bootstrap does not import pipeline modules before the selected release has been resolved and made available.
- Studio, project, and sandbox selection produce exactly one effective release per DCC process.
- A failed install never becomes the active release and does not destroy a previously working release.
- Logs make it clear which host, release ID, source of selection, cache path, and outcome were used.
- A reviewed plan and test matrix exist before implementation starts.
