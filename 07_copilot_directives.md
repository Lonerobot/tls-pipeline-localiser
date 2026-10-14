# 07 — Directives for the Copilot Agent

## Mission

Plan a lightweight pipeline localiser for THE LINE that caches immutable, independently versioned DCC pipeline releases locally and supports both AYON-launched and vanilla DCC workflows.

## Highest-priority instruction

**Planning before implementation.** For the first task, inspect and report. Do not create, edit, move, or delete production source files. Do not install dependencies or change project settings. Do not begin implementation until the user explicitly approves the plan.

## Required initial workflow

1. Inspect the repository and relevant files.
2. Identify existing startup scripts, environment configuration, AYON integration conventions and release sources.
3. Separate confirmed facts from assumptions.
4. Map load order for each supported DCC and AYON launch route.
5. Identify unresolved decisions, technical risks and version-specific constraints.
6. Propose the smallest coherent architecture and file layout.
7. Propose a test matrix and phased implementation plan.
8. Stop and present the plan for review.

## Architectural invariants

- One effective release per DCC process. An override replaces the default; it does not add a second pipeline root.
- Studio releases are independently versioned by DCC.
- AYON is a launch-context provider and pre-cache entry point, not the owner of core localisation logic.
- Vanilla DCC launches use a small native bootstrap that calls the same shared localiser core.
- The bootstrap must be independent of the managed release bundle.
- Release selection, local synchronisation and host initialisation are separate responsibilities.
- The core must not import DCC modules or pipeline bundle modules.
- Host-specific adapters own host-specific path setup, add-on/plugin enablement and post-start initialisation.
- The global studio configuration declares default release IDs; it is not the local cache inventory.
- Published release IDs are immutable.
- The normal startup path must be cheap and must not recursively hash the entire local release or traverse network trees.
- Install to staging, validate, then publish atomically. Never expose an incomplete release as valid.
- Explicit project/sandbox selections must fail clearly if unavailable; do not silently fall back to studio default.
- Never modify a release directory in place while a DCC might be using it.
- Avoid adding dependencies, abstraction layers or performance optimisations without evidence that they are needed.

## Required decisions to surface, not guess

- Whether TD sandbox override outranks project context, and how sandbox mode is explicitly enabled.
- Supported OSes, DCC versions and Python runtimes.
- Exact AYON pre-launch integration point.
- Whether studio defaults should all be pre-cached at AYON launch or cached on demand.
- Network configuration and release artifact locations.
- Trust model for manifests and checksums.
- Cache cleanup/retention policy.
- Logging destination and user-facing error mechanism.

## Deliverables for the planning pass

1. Repository discovery report.
2. Host lifecycle matrix.
3. Proposed module/file layout.
4. Proposed APIs and data schemas.
5. Release-resolution precedence diagram.
6. Failure/offline behaviour matrix.
7. Test plan.
8. Phased implementation plan with dependencies and risks.
9. A list of decisions requiring user input.

## Code quality expectations for later approved implementation

- Follow existing repository conventions unless they conflict with the architectural invariants; explain deviations.
- Prefer standard-library functionality where sufficient.
- Keep public APIs small and typed/documented where the project runtime allows.
- Make operations idempotent where practical.
- Use clear, structured logs that include host, package, release ID, selection source and operation result without leaking credentials or sensitive paths.
- Test failure paths, not only the happy path.
- Avoid swallowing exceptions or reporting success before publication is complete.
- Do not make up host lifecycle behaviour. Verify it against the installed versions and authoritative docs.
