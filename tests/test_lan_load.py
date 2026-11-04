import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from civ6_host.runtime import lan_load


class LanLoadTests(unittest.TestCase):
    def setUp(self):
        self.state = dict(
            player_id=0, turn=1, game_mode_u32=20463770,
            turn_phase_u32=2594944703, turn_timer_u32=2769907115,
            human_count=1,
            players=[dict(player_id=i, human=(i == 0)) for i in range(6)],
        )
        self.process = dict(pid=18404, creation_filetime=134376979317354116,
                            image_path='C:/game/CivilizationVI.exe')
        snapshot = dict(
            status='read_only_reference_captured', process=self.process,
            game_actions_issued=0, actor_input=False,
            simultaneous_execution_qualified=False, inbox_restored=True,
            reference=dict(state=self.state, observed_unchanged=True,
                           atomic_snapshot=False),
        )
        self.snapshots = {'before': snapshot, 'after': snapshot}
        self.invocation = dict(
            status='correlated_capture_unqualified', process=self.process,
            expected_player_id=0, expected_turn=1, network_state_unchanged=True,
            training_eligible=False,
            manifest=dict(path='C:/private/work/official-capture/lan/manifest.json',
                          sha256='a' * 64),
            network_before={'path': 'before.json', 'sha256': 'b' * 64},
            network_after={'path': 'after.json', 'sha256': 'c' * 64},
        )
        self.reference = ('work/official-capture/lan/manifest.json', 'a' * 64)
        self.bundle = SimpleNamespace(reference=self.reference, initial_turn=1)
        self.owner = SimpleNamespace(
            captured_bundle=self.bundle,
            inputs=SimpleNamespace(official_bundle=self.reference,
                                   checkpoint=None,
                                   profile=SimpleNamespace(mode_name='LAN')),
            host=SimpleNamespace(configured_local_player_id=0),
        )

    def _capture_refs(self):
        return patch.object(lan_load, '_capture_receipt', return_value=self.invocation), \
            patch.object(lan_load, '_load_json_reference',
                         side_effect=lambda ref, label: self.snapshots[
                             'before' if ref['sha256'] == 'b' * 64 else 'after'])

    def _validate(self, observed='1|80|52|0|1|2|3|4|5', values='0=1|1=0|2=0|3=0|4=0|5=0'):
        capture_patch, files_patch = self._capture_refs()
        with capture_patch, files_patch:
            return lan_load.validate_loaded_roster(self.owner, observed, values)

    def test_reference_state_rejects_a_different_capture(self):
        capture_patch, files_patch = self._capture_refs()
        with capture_patch, files_patch:
            self.bundle.reference = ('work/official-capture/other/manifest.json', 'd' * 64)
            with self.assertRaisesRegex(ValueError, 'exact captured manifest'):
                lan_load.reference_state(self.bundle)

    def test_reference_rejects_integer_impostor_for_human_boolean(self):
        capture_patch, files_patch = self._capture_refs()
        self.snapshots['before']['reference']['state']['players'][0]['human'] = 1
        self.snapshots['after']['reference']['state']['players'][0]['human'] = 1
        with capture_patch, files_patch:
            with self.assertRaisesRegex(ValueError, 'six-major capture'):
                lan_load.reference_state(self.bundle)

    def test_loaded_roster_mismatch_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'major roster'):
            self._validate(observed='1|80|52|0|1|2|3|4')

    def test_native_human_status_mismatch_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'human status'):
            self._validate(values='0=1|1=1|2=0|3=0|4=0|5=0')

    def test_exact_capture_reports_verified_humans_without_control_claim(self):
        result = self._validate()
        self.assertEqual(result['human_player_ids'], [0])
        self.assertIs(result['human_status_native_verified'], True)
        self.assertIs(result['control_of_all_players_proven'], False)
        self.assertIs(result['simultaneous_execution_qualified'], False)

    def test_readback_sources_are_bounded_and_separate(self):
        roster = lan_load.roster_readback_source()
        human = lan_load.human_status_readback_source((0, 1, 2, 3, 4, 5))
        self.assertIn(b'PlayerManager.GetAliveMajorIDs', roster)
        self.assertIn(b'p:IsHuman()', human)
        self.assertNotIn(b'GetAliveMajorIDs', human)

    def test_human_wire_accepts_the_full_roster_and_requires_exact_ids(self):
        ids = tuple(range(64))
        wire = '|'.join(f'{pid}={int(pid in (0, 63))}' for pid in ids)
        self.assertGreater(len(wire), 256)
        self.assertEqual(lan_load._parse_humans(wire, ids), (0, 63))
        with self.assertRaises(ValueError):
            lan_load._parse_humans(wire.replace('10=0', '01=0', 1), ids)


if __name__ == '__main__':
    unittest.main()
