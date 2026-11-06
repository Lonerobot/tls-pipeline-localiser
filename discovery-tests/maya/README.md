# Maya discovery test — G3 / M1 / M3

Question: if more than one `userSetup.py` is reachable on `sys.path`, which one does Maya
actually run — and when (relative to this) does anything read `MAYA_CORE` or import the studio
pipeline?

## What's here

- `stub_a/userSetup.py` — represents **our** localiser stub.
- `stub_b/userSetup.py` — represents an **existing/AYON-provided** `userSetup.py`.
- `stub_c/userSetup.py` — logging stub for testing a copy placed in Maya's own user scripts
  folder (see "Reading the result").

Both log their own start/end, `MAYA_CORE`, and `sys.path` length. Stub A additionally installs a
temporary `builtins.__import__` watcher (removed at the end of its own execution) that logs the
first import of anything matching `mayaScriptLibrary` or `corescripts_template`, so you can see
*when* (if ever) those get imported relative to `userSetup.py` running — this is the evidence for
M1. This is only safe/acceptable because it's a throwaway discovery script; do not carry the
import watcher into production code.

## Deploy

1. Add **both** `stub_a/` and `stub_b/` directories to `PYTHONPATH` before launching Maya (order
   matters — put whichever one you want to test "winning" first). In a real deployment these
   would be two independently-sourced `userSetup.py` files (e.g. one from AYON env injection, one
   from a system `PYTHONPATH` entry) — reproduce that shape as closely as you can.
2. Optionally set `TLS_DISCOVERY_LOG` to a specific file path, and/or set `MAYA_CORE` to some
   test value so you can see it echoed back.
3. Launch Maya (vanilla and/or via AYON — test both if relevant) and let it fully start up,
   including opening the pipeline menu once (to see whether `mayaScriptLibrary` imports lazily).
4. Inspect the log (default `<tempfile.gettempdir()>/tls_discovery.log`).

## Reading the result

- If only `EVENT=userSetup_start STUB=A` (or only `STUB=B`) appears, Maya ran a single
  `userSetup.py`. **Observed instead (Maya 2026, Windows, B + C): more than one runs**, in
  `sys.path` order in that test. Treat G3's original single-winner assumption as wrong.
- Maya runs `userSetup.py` via `execfile`, which defines no `__file__`; the stubs log a
  placeholder `FILE`, and stub C also logs `userSetup_candidate` events listing which `sys.path`
  folders contain a `userSetup.py`.
- `stub_c/userSetup.py` is meant to be copied to `Documents\maya\<version>\scripts` (confirm with
  `cmds.internalVar(userScriptDir=True)`). Never overwrite an existing `userSetup.py` (the shared
  `Documents\maya\scripts` folder may hold a real one); back up first and remove the copy after.
  It logs `STUB=C`, the full `sys.path` and the candidate files.
- Not yet shown: whether Autodesk's or the studio's own `userSetup.py` also ran (they don't
  log), whether an exception in one stops the next, and behaviour with AYON's real file (M3).
- Swap the `PYTHONPATH` order and re-run to confirm precedence is controlled by path order, not
  some other Maya-specific mechanism.
- Compare the timestamp of any `EVENT=import_observed` line against `userSetup_start`/`userSetup_end`
  to answer M1 (whether `MAYA_CORE` consumers import before or after `userSetup.py` finishes).
- If you can identify a second, separately-sourced `userSetup.py` already in the environment
  (AYON's own), repeat the test with that real file in place of `stub_b` to answer M3 directly.
