# Pipeline Localiser: Planning Blueprint

This document set describes the intended design for a lightweight, host-aware pipeline localiser for THE LINE. It is a planning and implementation-directive package for a Copilot coding agent. **It is not an instruction to start implementing immediately.** The first task is to inspect the existing environment, identify lifecycle constraints, and produce a plan that can be reviewed before code changes.

## Documents

1. [`01_brief.md`](01_brief.md) — problem, goals, non-goals, and success criteria.
2. [`02_architecture.md`](02_architecture.md) — components, responsibilities, and boundaries.
3. [`03_runtime_procedure.md`](03_runtime_procedure.md) — resolution and startup flows.
4. [`04_configuration_and_releases.md`](04_configuration_and_releases.md) — configuration, release manifests, caching, and integrity.
5. [`05_host_adapters.md`](05_host_adapters.md) — host-specific integration requirements and load-order concerns.
6. [`06_implementation_plan.md`](06_implementation_plan.md) — staged discovery, planning, testing, and implementation sequence.
7. [`07_copilot_directives.md`](07_copilot_directives.md) — direct instructions for the coding agent.
8. [`08_open_decisions.md`](08_open_decisions.md) — unresolved questions that must not be silently guessed.

## Core design in one sentence

Resolve one effective pipeline release for a DCC, ensure that immutable release is available locally, then let a host-specific adapter configure and initialise the DCC at the correct lifecycle stage.

## Current assumptions

- The pipeline is modular by DCC. Maya, Blender, and Nuke releases are independently versioned.
- Studio defaults are selected by a small network-hosted JSON configuration.
- AYON can provide project launch context and can pre-cache required releases before starting a DCC.
- Vanilla DCC launches must also be supported through a small native-host bootstrap.
- The localiser should be reusable outside AYON.
- Release content is immutable once published. A changed build gets a new release ID.
- The first deliverable is a reviewed design and implementation plan, not production code.

## Agent operating rule

Do not make code changes during the initial planning pass. Inspect the repository and available runtime constraints, map the existing startup mechanisms, identify unknowns, then return a proposed file layout, lifecycle sequence, risk list, test plan, and phased implementation plan for approval.
