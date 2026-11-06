# Discovery test stubs

Throwaway, stdlib-only scripts to deploy into real Maya/Nuke/Blender installs to answer the
host-level questions in [`03_user_discovery.md`](../.copilot/03_user_discovery.md) — mainly the
§0 gating tests (G1–G3) plus a few directly related items (M1, M3, N3, B1, B2). They are **not**
part of the localiser design; they exist only to produce evidence. Delete or archive them once
the worksheet is filled in.

Each stub is deliberately self-contained (no shared imports between files) so that import/path
failures in the thing under test can't be masked by a shared helper module failing silently —
that's exactly the kind of ordering/discovery bug we're trying to catch.

## Shared logging convention

Every stub appends plain-text lines to a single log file, one event per line, so events from
different processes/stubs can be interleaved and sorted by timestamp:

```
[2026-11-02T16:20:01] HOST=maya STUB=A FILE=... PID=12345 EVENT=userSetup_start MAYA_CORE=<unset> sys_path_len=42
```

Default location: `<tempfile.gettempdir()>/tls_discovery.log` (e.g. `%TEMP%\tls_discovery.log`
on Windows). Override with the `TLS_DISCOVERY_LOG` environment variable (set it to a full file
path) if you want every host's log in one place, e.g. on a shared drive, or a fresh file per
test run.

Read results with any text search, e.g. (PowerShell):

```powershell
Get-Content $env:TEMP\tls_discovery.log | Select-String "HOST=blender"
Get-Content $env:TEMP\tls_discovery.log | Sort-Object   # chronological, since lines are ISO-ish timestamped
```

Clear the log between test runs (`Remove-Item $env:TEMP\tls_discovery.log`) so each run's
evidence is unambiguous.

## Map: worksheet item → stub

| Item | Host | Stub |
|---|---|---|
| G1 | Blender | [`blender/system_scripts/startup/tls_discovery_startup.py`](blender/system_scripts/startup/tls_discovery_startup.py) |
| G2 | Nuke | [`nuke/stub/init.py`](nuke/stub/init.py) + [`nuke/fake_release/`](nuke/fake_release) |
| G3 | Maya | [`maya/stub_a/userSetup.py`](maya/stub_a/userSetup.py) + [`maya/stub_b/userSetup.py`](maya/stub_b/userSetup.py) |
| M1, M3 | Maya | same Maya stubs (import-watch instrumentation in stub A) |
| N3 | Nuke | same Nuke stubs (`init.py` vs `menu.py` timestamps) |
| B1, B2 | Blender | same Blender stub (script-directory entry naming/staleness, env var collision) |

See each subfolder's `README.md` for exact deployment steps.
