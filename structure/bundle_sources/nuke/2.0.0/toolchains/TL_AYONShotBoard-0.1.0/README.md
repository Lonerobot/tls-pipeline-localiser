# The Line — AYON Shot Board 0.1.0

Load published plates and reviews into the current Nuke script, using AYON's
installed Nuke loader plugins. Each shot gets a backdrop column. Each imported
product gets a sticky note showing its product name, type, version,
representation, publish status and author.

This is a first implementation for studio testing. It has been checked with
mock Nuke/AYON APIs, not a running studio Nuke session or your AYON server.

## Install

1. Copy the supplied TL_AYONShotBoard folder into:

   Y:/PIPELINE/config/nuke/toolchains/

   The resulting files are:

   Y:/PIPELINE/config/nuke/toolchains/TL_AYONShotBoard/0.1.0/menu.py
   Y:/PIPELINE/config/nuke/toolchains/TL_AYONShotBoard/0.1.0/tl_ayon_shot_board.py

2. Add the entry in toolchain-entry.json inside the existing "toolchains"
   object in your ACTIVE core toolchains.json. Do not replace the whole file.
   Your loader defaults to:

   Y:/PIPELINE/config/nuke/core/0.0.1/toolchains.json

   If your active NUKE_PATH points to a different core version, edit that
   version instead. Leave both build flags false: menu.py creates the menu.

3. Restart Nuke through AYON in the project you want to browse.

4. Open: The Line > AYON Shot Board > Build or Configure.

No text entries are added to the left-hand Nodes toolbar and no keyboard
shortcuts are assigned. Your Align Nodes tool is unaffected.

## First use

Start with a separate empty Nuke script. Set its start frame first.
For a small first test, use folder scope /shots/sh080, as in your screenshot.
Set Shot folder type to the actual AYON folder type used by your shots
(normally Shot). The match ignores case.

Choose Latest or All versions. Latest loads the newest regular version of
every plate/review product. All includes published version history. Hero
versions and inactive versions are excluded. Both plates and reviews are
enabled by default.

Use /shots to collect every shot below that folder, including sequences.
The scope must be an AYON folder path, not a filesystem path. Products in
shot subfolders are grouped under their nearest ancestor of type Shot.
Shots without matching published products do not create empty backdrops.

Press OK to scan and import. Save the script normally as an .nk file.
The tool stores its settings and grouping IDs inside the script.

## Update

Choose: The Line > AYON Shot Board > Update — Add Missing.

The tool scans the saved scope again and checks live AYON representation IDs
already loaded in this script. It adds missing clips and creates backdrops
for new shots. Existing nodes retain their positions and connections;
backdrops expand to include newly appended assets.

With Latest selected, if v001 was imported and v002 is published later,
Update adds v002 alongside v001. It does not replace v001. If v002 and v003
were published between scans, Latest adds v003 only. Choose All to load every
historical version, including those intermediate versions.

You can use AYON Scene Inventory to update or remove existing imports as
usual. The tool reads the live AYON container metadata, so an update there
does not leave stale representation IDs in its duplicate check.
Deleting an imported Read allows that representation to be loaded again.
Its old sticky note is not automatically deleted.

An identical representation already loaded manually is also skipped. Manual
imports are left in place and are not automatically moved into a shot backdrop.
Duplicate checking includes AYON containers inside Groups. New imports go
at the script root, even when you invoke the command while inside a Group.

## What is included

- AYON products with productBaseType, or legacy productType, plate or review.
  This matches the plate/review rows shown in your Loader screenshot.
- One compatible media representation per product version, not every encoding.
- Plate format preference: exr, dpx, tif, tiff, png, mov, mp4, jpg, jpeg.
- Review format preference: mov, mp4, jpg, jpeg, png, exr.
- The enabled compatible LoadClip loader is preferred, then LoadImage.
  Your AYON loader settings and representation restrictions are respected.

Change the format preference lists or allowed loader names in DEFAULTS for a
new board. Existing boards retain the configuration saved in their .nk file.

Review representations embedded in products of other types, such as render
or image, are not included by this version. Server-only web review uploads
without a published media representation are not downloaded. Media must
already be accessible to the normal AYON Nuke loader on your workstation.

## Timing and colour

The actual AYON loader sets file paths, container metadata, Read frame ranges,
colour spaces and optional published retime nodes. The tool does not guess
input colour spaces or change your OCIO configuration.

"Align clips to script start" is enabled by default for comparing different
shots in one script. Disable it to retain the loader's original clip timing.
"Load published retimes" is also enabled by default.
Different frame rates are not automatically converted into a common rate.
The script's start/end frames and fps are restored after importing.

The loader is requested to use ordinary Read nodes for this review board.
This is not a deep-image comp workflow.

## Failures, cancellation and undo

Each failed load is reported, and its newly created nodes are removed.
Other successful imports remain. Update retries clips that did not load.
Cancellation between assets keeps completed imports and stops further work.
Scan cancellation changes nothing. Calls already waiting on the server or
a loader must finish before cancellation takes effect.

The batch is wrapped in a Nuke undo group. AYON loaders may add their own
nested undo groups. The full summary is printed in the Script Editor.
Show Last Report also displays the last saved report.

Save the .nk after loading to retain settings and notes across sessions.
The tool reads the server; it does not publish, edit statuses, or write to
the AYON server. It does not save over your Nuke script automatically.

## Direct test without the JSON entry

After copying the folder, run in Nuke's Python Script Editor:

    import nuke
    nuke.pluginAddPath(
        "Y:/PIPELINE/config/nuke/toolchains/TL_AYONShotBoard/0.1.0"
    )
    import tl_ayon_shot_board
    tl_ayon_shot_board.configure()

## Verification

Offline tests cover first import, repeated runs, missing new versions,
deleted Read recovery, manual imports, changes via Scene Inventory,
scope boundaries, natural shot ordering, representation selection, all-version
mode, empty queries, cancelled scanning, project mismatch, failed loader
cleanup, failed layout rollback, unsupported media and root timing preservation.

Run them outside Nuke:

    python -m unittest discover -s tests -v

Before studio rollout, test one shot in your AYON-launched Nuke:

1. Build a board. Confirm expected review and plate Reads, notes and backdrop.
2. Check colour spaces, slate/timing, retime connections and frame ranges
   against loading the same media through the standard AYON Loader.
3. Run Update twice. Confirm it imports nothing twice.
4. Publish a new review, then Update. Confirm exactly one new clip appears.
5. Save and reopen the .nk, then Update again.
6. Test Undo and verify the items appear in AYON Scene Inventory.

The LoadClip options/container shape were inspected in ayon-nuke 0.4.15,
the addon version shown in your earlier publish log. The installed AYON Core
version was not available here; its documented load APIs were used. A version
mismatch will be shown in the Script Editor instead of silently creating
unmanaged Read nodes.

## Sources

AYON Core loader entry points and representation contexts:
https://docs.ayon.dev/ayon-core/latest/autoapi/client/ayon_core/pipeline/load/utils.html

AYON Python API entity queries:
https://docs.ayon.dev/ayon-python-api/ayon_api.html

AYON Nuke LoadClip, addon 0.4.15:
https://github.com/ynput/ayon-nuke/blob/0.4.15/client/ayon_nuke/plugins/load/load_clip.py

AYON Nuke container metadata and inventory:
https://github.com/ynput/ayon-nuke/blob/0.4.15/client/ayon_nuke/api/pipeline.py
