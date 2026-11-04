"""Saved-mode and last-moment command refusal checks, without GameCore."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp1_session_admission as admission
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.workers.network_worker import _execute_xp1
from test_session_configuration import configuration
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.captured_session_profile import select


def fixture(mode='LAN', phase='TURNPHASE_SIMULTANEOUS', phase_tag=2,core_sha256=XP1_CORE_SHA256):
    selected=select(core_sha256)
    saved = object.__new__(SavedLoadOwner)
    saved._check = Mock()
    saved.inputs = NS(configuration=configuration(mode, phase, phase_tag=phase_tag),
        profile=selected.candidate.profile)
    saved.view_result = dict(observation=dict(turn=1,width=selected.width,height=selected.height,player_id=0))
    saved.player_view = NS(result=saved.view_result)
    saved.continuation = NS(view=saved.player_view)
    saved.backend = NS(captured_bundle=NS(initial_turn=1,inputs=saved.inputs,
        reference=selected.candidate.reference,content_profile={'engine':{'gamecore_sha256':core_sha256}}),
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
