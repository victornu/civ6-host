"""Saved-mode regression cases; no native engine or learner is launched."""
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from civ6_host.runtime.captured_session_profile import saved_geometry
from civ6_host.runtime.session_configuration import _multiplayer_candidate, read_saved_major_roster, read_saved_settings
from civ6_host.runtime.native.native_game_configuration import game_configuration_hash as h


def configuration(mode="HOTSEAT", phase=None, *, phase_tag=3, game_tag=10):
    fields = [(h("GAME_MODE"), 3, h(mode))]
    if phase is not None:
        fields.append((h("TURN_PHASE_TYPE"), phase_tag, h(phase)))
    contents = struct.pack("<I", len(fields)) + b"".join(
        struct.pack("<IHHIII", key, tag, 0, 0, 0, value) for key, tag, value in sorted(fields))
    return struct.pack("<IIHHII", 1, h("GAME_ROOT"), game_tag, 0, 0x05000000, 0) + contents


def slot_configuration(slots):
    providers = []
    for player_id, status, level, tag in slots:
        fields = [(h("PLAYER_ID"), 2, player_id), (h("SLOT_STATUS"), 2, status)]
        if level is not None:
            fields.append((h("CIVILIZATION_LEVEL_TYPE_ID"), tag, h(level)))
        provider_key = h(f"PLAYER_{player_id}")
        root = struct.pack("<IHHIII", provider_key, 10, 0, 0x05000000, 0, len(fields))
        providers.append((provider_key, root + b"".join(
            struct.pack("<IHHIII", key, kind, 0, 0, 0, value) for key, kind, value in sorted(fields))))
    return struct.pack("<I", len(providers)) + b"".join(raw for _, raw in sorted(providers))


class SavedSessionConfigurationTests(unittest.TestCase):
    def test_saved_geometry_preserves_declared_seats_and_filters_city_states(self):
        full = "CIVILIZATION_LEVEL_FULL_CIV"
        raw = slot_configuration([
            (8, 3, full, 3), (3, 3, full, 2), (9, 1, full, 2),
            (10, 1, "CIVILIZATION_LEVEL_CITY_STATE", 2), (11, 2, full, 2),
            (14, 5, "CIVILIZATION_LEVEL_CITY_STATE", 2),
        ])
        bundle = SimpleNamespace(inputs=SimpleNamespace(configuration=raw), initial_turn=17,
                                 expected_readback=dict(turn=17, width=52, height=36, player_id=8))
        self.assertEqual(saved_geometry(bundle), dict(turn=17, width=52, height=36, local_player_id=8,
                                                     major_player_ids=(3, 8, 9), taken_player_ids=(3, 8)))
        bundle.expected_readback["player_id"] = 10
        with self.assertRaisesRegex(ValueError, "local seat"):
            saved_geometry(bundle)

    def test_saved_major_roster_refuses_ambiguous_occupied_slot(self):
        for row in ((0, 1, None, 2), (0, 3, "CIVILIZATION_LEVEL_CITY_STATE", 2), (0, 5, None, 2),
                    (0, 5, "CIVILIZATION_LEVEL_FULL_CIV", 2)):
            with self.subTest(row=row), self.assertRaises(ValueError):
                read_saved_major_roster(slot_configuration([row]))

    def test_saved_multihuman_candidate_distinguishes_lan_internet_and_roster(self):
        phase = "TURNPHASE_SIMULTANEOUS"
        lan = read_saved_settings(configuration("LAN", phase))
        internet = read_saved_settings(configuration("INTERNET", phase))
        self.assertEqual(_multiplayer_candidate(lan, {"taken_slot_count": 2}), {
            "matches_lan_multihuman_settings": True, "settings_blockers": [],
            "live_roster_observed": False, "native_commands_qualified": False})
        self.assertEqual(_multiplayer_candidate(lan, {"taken_slot_count": 1})["settings_blockers"],
                         ["fewer_than_two_saved_taken_slots"])
        self.assertEqual(_multiplayer_candidate(internet, {"taken_slot_count": 2})["settings_blockers"],
                         ["saved_network_mode_is_not_lan"])

    def test_hotseat_without_phase_does_not_inherit_multiplayer_default(self):
        result = read_saved_settings(configuration())
        self.assertEqual(result["game_mode"]["name"], "HOTSEAT")
        self.assertFalse(result["turn_phase"]["present"])
        self.assertIsNone(result["turn_phase"]["value"])

    def test_phase_and_mode_are_independent_saved_values(self):
        result = read_saved_settings(configuration(phase="TURNPHASE_SIMULTANEOUS"))
        self.assertEqual(result["game_mode"]["name"], "HOTSEAT")
        self.assertEqual(result["turn_phase"]["value"], h("TURNPHASE_SIMULTANEOUS"))
        self.assertNotIn("active_players", result)

    def test_unknown_network_mode_is_retained_without_a_guess(self):
        result = read_saved_settings(configuration("UNQUALIFIED_NETWORK_MODE", "TURNPHASE_DYNAMIC"))
        self.assertFalse(result["game_mode"]["recognized"])
        self.assertIsNone(result["game_mode"]["name"])
        self.assertEqual(result["game_mode"]["value"], h("UNQUALIFIED_NETWORK_MODE"))

    def test_exact_network_tokens_are_separate_from_turn_phase(self):
        for token in ("NETWORKMULTIPLAYER", "INTERNET", "CROSSPLAY", "LAN"):
            with self.subTest(token=token):
                result = read_saved_settings(configuration(token))
                self.assertEqual(result["game_mode"]["name"], token)
                self.assertTrue(result["game_mode"]["network_mode_token"])
                self.assertFalse(result["turn_phase"]["present"])

    def test_trailing_bytes_and_wrong_phase_type_refused(self):
        with self.assertRaisesRegex(ValueError, "trailing"):
            read_saved_settings(configuration() + b"extra")
        with self.assertRaisesRegex(ValueError, "supported integer/hash"):
            read_saved_settings(configuration(phase="TURNPHASE_DYNAMIC", phase_tag=1))


if __name__ == "__main__":
    unittest.main()
