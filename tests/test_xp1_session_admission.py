"""Saved-mode and last-moment command refusal checks, without GameCore."""
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp1_session_admission as admission
from civ6_host.runtime.native.native_official_bundle import PreparedBundle
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.workers.network_worker import _execute_xp1
from test_session_configuration import configuration, slot_configuration
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.captured_session_profile import select


def fixture(mode='LAN', phase='TURNPHASE_SIMULTANEOUS', phase_tag=2,
            core_sha256=XP1_CORE_SHA256, *, second_human=False):
    selected=select(core_sha256)
    saved = object.__new__(SavedLoadOwner)
    saved._check = Mock()
    raw = configuration(mode, phase, phase_tag=phase_tag)
    if core_sha256 == XP2_CORE_SHA256:
        full = 'CIVILIZATION_LEVEL_FULL_CIV'
        raw = slot_configuration([(0, 3, full, 2), (1, 3 if second_human else 1, full, 2)],
                                 game=raw)
    saved.inputs = NS(configuration=raw, profile=selected.candidate.profile)
    saved.view_result = dict(observation=dict(turn=1,width=selected.width,height=selected.height,player_id=0))
    saved.player_view = NS(result=saved.view_result)
    saved.continuation = NS(view=saved.player_view)
    bundle = PreparedBundle(reference=selected.candidate.reference, inputs=saved.inputs,
        initial_turn=1, engine_path=Path('fixture-core.dll'), fixture={}, dependencies={},
        content_profile={'engine': {'gamecore_sha256': core_sha256}},
        expected_readback=dict(saved.view_result['observation']))
    saved.backend = NS(captured_bundle=bundle,
        load_abi=NS(core_sha256=core_sha256),
        loaded_roster='|'.join(map(str,(1,selected.width,selected.height,*selected.major_ids))).encode('ascii'),
                       host=NS(configured_local_player_id=0))
    return saved


class AdmissionTests(unittest.TestCase):
    def test_xp2_identity_does_not_borrow_xp1_roster_or_reference(self):
        saved=fixture(core_sha256=XP2_CORE_SHA256)
        with patch('civ6_host.runtime.xp2_bundle_inputs.validate_candidate_inputs') as validate:
            ref=admission.bind(saved)
        validate.assert_called_once_with(saved.inputs,saved.backend.captured_bundle)
        self.assertEqual(ref['major_player_ids'],(0,1))
        self.assertEqual(ref['capture_manifest_sha256'],select(XP2_CORE_SHA256).candidate.reference[1])
        for wrong in ('roster','engine','dimensions'):
            saved=fixture(core_sha256=XP2_CORE_SHA256)
            if wrong=='roster':saved.backend.loaded_roster=b'1|44|26|0|1|2|3|4|5'
            elif wrong=='engine':saved.backend.load_abi.core_sha256=XP1_CORE_SHA256
            else:saved.view_result['observation']['width']=74
            with patch('civ6_host.runtime.xp2_bundle_inputs.validate_candidate_inputs'),self.assertRaises(ValueError):
                admission.bind(saved)
            self.assertFalse(hasattr(saved,'network_reference'))

    def test_second_saved_human_stays_declared_from_preload_through_session_binding(self):
        from civ6_host.runtime import captured_saved_load

        saved = fixture(core_sha256=XP2_CORE_SHA256, second_human=True)
        backend = saved.backend
        backend.inputs = saved.inputs
        closure = dict(input_profile='xp2-lan', raw_only_candidate=True,
                       post160_candidate=True, unit_commands_candidate=True,
                       publish_cache_candidate=True, observe_player_candidate=True,
                       close_loaded_candidate=True)
        # Only the exact capture validator is replaced by the fixture. The
        # saved provider, two native roster strings and reference join run.
        with (patch.object(captured_saved_load, 'validate_candidate_inputs'),
              patch('civ6_host.runtime.xp2_bundle_inputs.validate_candidate_inputs')):
            captured_saved_load.configure_requested(backend, closure)
            receipt = captured_saved_load.validate_loaded_roster(
                backend, backend.loaded_roster, b'0=1|1=1')
            self.assertEqual(receipt['human_player_ids'], [0, 1])
            self.assertIs(receipt['control_of_all_players_proven'], False)
            with self.assertRaisesRegex(ValueError, 'human/local identity differs'):
                captured_saved_load.validate_loaded_roster(
                    backend, backend.loaded_roster, b'0=1|1=0')
            ref = admission.bind(saved)
            self.assertEqual((ref['state']['player_id'], ref['human_player_ids']), (0, (0, 1)))

    def test_saved_mode_and_retained_view_joined_once_without_defaults(self):
        saved = fixture()
        with patch('civ6_host.runtime.xp1_saved_load.validate_candidate_inputs') as exact:
            ref = admission.bind(saved)
            exact.assert_called_once_with(saved.inputs, saved.backend.captured_bundle)
            self.assertEqual(ref['human_player_ids'], (0,))
            self.assertEqual(ref['major_player_ids'], tuple(range(6)))
            self.assertIs(saved.network_reference, ref)
            with self.assertRaisesRegex(ValueError, 'already bound'):
                admission.bind(saved)

    def test_unqualified_mode_phase_or_owner_refused_before_reference_exists(self):
        cases = [fixture('HOTSEAT'), fixture(phase=None),
                 fixture(phase='TURNPHASE_DYNAMIC'), fixture(phase_tag=3),fixture()]
        cases[-1].player_view.result = dict(cases[-1].view_result)
        for saved in cases:
            with self.subTest(saved=saved), patch(
                    'civ6_host.runtime.xp1_saved_load.validate_candidate_inputs'), self.assertRaises(ValueError):
                admission.bind(saved)
            self.assertFalse(hasattr(saved, 'network_reference'))

    def test_stale_legal_selection_is_refused_without_native_dispatch(self):
        saved = NS(execute=Mock(side_effect=AssertionError('must not dispatch')),
                   continuation=NS(observation=dict(width=74,height=46)))
        action = dict(kind='found_city',unit_id=65536,x=43,y=29)
        with patch('civ6_host.runtime.xp1_session_view.read',
                   return_value=({}, {}, {'candidates':[]})) as read:
            result = _execute_xp1(saved,action,0,5,'unused-private-closure.json')
        read.assert_called_once_with(saved,0,5)
        self.assertEqual(result,dict(status='refused',reason='native_action_no_longer_available',
                                     requested_action=action))
        saved.execute.assert_not_called()


if __name__ == '__main__': unittest.main()
