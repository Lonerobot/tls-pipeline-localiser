# Nuke discovery test — G2 / N3

Question: when the stub's `init.py` (loaded via `NUKE_PATH`) calls
`nuke.pluginAddPath(<release root>)`, does Nuke then run **that directory's** own `init.py`
(and later `menu.py` at UI load), in the right order — as if the directory had been on
`NUKE_PATH` from the start?

## What's here

- `stub/init.py` — the `NUKE_PATH` stub. Logs itself, then calls `nuke.pluginAddPath()` pointing
  at `fake_release/`.
- `fake_release/init.py`, `fake_release/menu.py` — log their own execution so you can see whether
  and when they ran, relative to the stub.

## Deploy

1. Set `NUKE_PATH` to the absolute path of `stub/` (not `fake_release/` — that's the point: only
   the stub is on `NUKE_PATH`, the "release" is reached only via `pluginAddPath`).
2. Optionally set `TLS_DISCOVERY_NUKE_FAKE_RELEASE` to an absolute path if you want
   `fake_release/` to live somewhere other than next to `stub/`. This is deliberately not the
   Blender test's `TLS_DISCOVERY_FAKE_RELEASE`: a leftover value from the Blender test pointed
   the Nuke stub at Blender's release, which has no `init.py`/`menu.py`, so nothing ran. Unset
   any old value, and check `EVENT=target_check` (`has_init=True`, `has_menu=True`) in the log.
3. Launch Nuke, open the UI (so `menu.py` has a chance to run), then inspect the log.

## Reading the result

- `EVENT=stub_init_start` / `plugin_add_path_call` / `stub_init_end` come from `stub/init.py`.
- `EVENT=fake_release_init_ran` coming from `fake_release/init.py` **between** `plugin_add_path_call`
  and `stub_init_end` (or shortly after) confirms `pluginAddPath` causes Nuke to run the added
  directory's `init.py` in the same startup pass — this answers G2's `init.py` half.
- `EVENT=fake_release_menu_ran` should only appear once the UI loads (later, a separate log
  timestamp) — confirms the `menu.py`-runs-too-late ordering assumption (N3), and that it still
  fires correctly for a path added via `pluginAddPath` rather than being on `NUKE_PATH` directly.
- If `fake_release_init_ran` never appears, `pluginAddPath` is not sourcing `init.py` from the
  added directory the way the design assumes — this blocks the stub design in brief §8.1/§8 and
  needs a fallback (e.g. the stub does the equivalent setup itself instead of delegating).
