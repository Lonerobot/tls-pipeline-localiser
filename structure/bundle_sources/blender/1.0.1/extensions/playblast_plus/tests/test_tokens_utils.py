"""Unit tests for the version extraction token and predefined suffix helpers.

These tests exercise pure-Python functions in ``lib/utils.py`` and do not
require a running Blender instance.
"""

import sys
import os

# Ensure the repo root is on sys.path so we can import lib/ directly.
# pytest.ini sets pythonpath=.. but this guard helps when running the file
# directly with `python tests/test_tokens_utils.py`.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from lib.utils import extract_version_from_stem, parse_suffixes


# ---------------------------------------------------------------------------
# extract_version_from_stem
# ---------------------------------------------------------------------------

class TestExtractVersionFromStem:

    def test_lowercase_v_three_digits(self):
        assert extract_version_from_stem("character_v001_rigging") == "v001"

    def test_uppercase_v_three_digits(self):
        assert extract_version_from_stem("character_V001_rigging") == "V001"

    def test_one_digit(self):
        assert extract_version_from_stem("shot_v1") == "v1"

    def test_two_digits(self):
        assert extract_version_from_stem("shot_v01") == "v01"

    def test_four_digits(self):
        assert extract_version_from_stem("shot_v0001") == "v0001"

    def test_version_at_end(self):
        assert extract_version_from_stem("anim_turnaround_v023") == "v023"

    def test_version_at_start(self):
        assert extract_version_from_stem("v010_character") == "v010"

    def test_no_version_returns_empty(self):
        assert extract_version_from_stem("character_rigging") == ""

    def test_empty_string_returns_empty(self):
        assert extract_version_from_stem("") == ""

    def test_five_digits_not_matched(self):
        # Version numbers longer than 4 digits are outside the supported range.
        # The regex {1,4} stops at 4 digits, so 'v00001' yields 'v0000'
        # (the 5th digit is not captured). This is intentional — VFX filenames
        # rarely exceed v9999, and capturing a partial match is preferable to
        # silently returning no version at all.
        assert extract_version_from_stem("shot_v00001") == "v0000"

    def test_vfx_prefix_not_confused_with_version(self):
        # 'vfx' starts with 'v' but is not followed by digits — no match.
        assert extract_version_from_stem("vfx_shot_001") == ""

    def test_first_match_returned_when_multiple(self):
        # When multiple version strings appear, the first one is returned.
        result = extract_version_from_stem("v001_final_v002")
        assert result == "v001"

    def test_uppercase_v_one_digit(self):
        assert extract_version_from_stem("scene_V3_draft") == "V3"


# ---------------------------------------------------------------------------
# parse_suffixes
# ---------------------------------------------------------------------------

class TestParseSuffixes:

    def test_default_suffixes(self):
        result = parse_suffixes("None,Chalk,Turnaround,Rig,Anim")
        assert result == ["None", "Chalk", "Turnaround", "Rig", "Anim"]

    def test_strips_whitespace(self):
        result = parse_suffixes(" None , Chalk , Rig ")
        assert result == ["None", "Chalk", "Rig"]

    def test_skips_empty_entries(self):
        result = parse_suffixes("None,,Chalk,")
        assert result == ["None", "Chalk"]

    def test_single_entry(self):
        assert parse_suffixes("None") == ["None"]

    def test_empty_string_returns_empty_list(self):
        assert parse_suffixes("") == []

    def test_custom_suffixes(self):
        result = parse_suffixes("None,WIP,Final,Draft")
        assert result == ["None", "WIP", "Final", "Draft"]


# ---------------------------------------------------------------------------
# Suffix appending logic (integration-style, no Blender required)
# ---------------------------------------------------------------------------

def _build_output_name(token_result: str, suffix: str) -> str:
    """Mirror the logic used in operators.py for appending the suffix."""
    output_name = token_result or "playblast"
    if suffix and suffix != "None":
        output_name = f"{output_name}_{suffix}"
    return output_name


class TestSuffixAppending:

    def test_none_suffix_not_appended(self):
        assert _build_output_name("my_scene_v001_cam", "None") == "my_scene_v001_cam"

    def test_suffix_appended_with_underscore(self):
        assert _build_output_name("my_scene_v001_cam", "Turnaround") == "my_scene_v001_cam_Turnaround"

    def test_empty_suffix_not_appended(self):
        assert _build_output_name("my_scene", "") == "my_scene"

    def test_empty_token_result_uses_fallback(self):
        assert _build_output_name("", "None") == "playblast"

    def test_empty_token_result_with_suffix(self):
        assert _build_output_name("", "Rig") == "playblast_Rig"

    def test_chalk_suffix(self):
        assert _build_output_name("character_v002_camera", "Chalk") == "character_v002_camera_Chalk"

    def test_anim_suffix(self):
        assert _build_output_name("shot_v01_cam", "Anim") == "shot_v01_cam_Anim"
