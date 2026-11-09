"""Native retained v39 form through the real parent/worker request validator."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import unittest
from civ6_host.runtime.network_protocol import NetworkProtocol
from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256


class CongressNativeProtocolTests(unittest.TestCase):
    def fixture(self):
        path = Path(os.environ['CIV6_HOST_RESOURCE_ROOT']) / (
            'work/trade-common-client/congress-permissions-staging/native-active-response.json')
        raw = path.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
            'd4c6af3424fe1e7312feafaf898337ca38a2bdb253cc24df1d00a3b909982b7e')
        reply = json.loads(raw)
        protocol = NetworkProtocol(DiagnosticEpisodeIdentity(reply['episode_id'],
            reply['game_generation']), reply['nonce'], initial_turn=61,
            core_sha256=XP2_CORE_SHA256)
        protocol.accept_response(reply)
        d = reply['decisions']
        row = next(x for x in d['candidates'] if x['action']['kind'] == 'congress_confirm_ballot')
        parameters = dict(resolutions=[dict(resolution_hash=r['resolution_hash'],
            option=2, target_index=r['targets'][0]['index'], votes=1)
            for r in d['world_congress']['resolutions']], discussions=[])
        request = dict(schema=protocol.schema, nonce=reply['nonce'],
            episode_id=reply['episode_id'], game_generation=reply['game_generation'],
            sequence=reply['sequence'] + 1, operation='act', player_id=0,
            selection=dict(decision_id=d['decision_id'], candidate_id=row['candidate_id'],
                           parameters=parameters))
        return protocol, request, reply

    def test_actual_active_form_can_submit_through_real_protocol_with_stored_observation(self):
        protocol, request, reply = self.fixture()
        self.assertIsNone(reply['decisions']['world_input'])
        self.assertFalse(reply['decisions']['native_command_permissions']['allow_strategic'])
        self.assertEqual(protocol.validate(request), 'act')
        action = protocol.selected(request)
        self.assertEqual(action['kind'], 'congress_confirm_ballot')
        self.assertEqual(action['resolutions'], request['selection']['parameters']['resolutions'])
        self.assertEqual(len(action['resolutions']), 3)
        self.assertEqual(protocol.observations[0], reply['observation'])

    def test_missing_or_foreign_observation_still_refuses(self):
        for mode in ('missing', 'foreign'):
            with self.subTest(mode=mode):
                protocol, request, _ = self.fixture()
                if mode == 'missing': protocol.observations.clear()
                else: protocol.observations[0]['player_id'] = 1
                with self.assertRaises(ValueError): protocol.validate(request)

    def test_bad_ballot_remains_refused_before_transport(self):
        protocol, request, _ = self.fixture()
        changed = deepcopy(request)
        changed['selection']['parameters']['resolutions'][0]['target_index'] = 99
        with self.assertRaises(ValueError): protocol.validate(changed)
        self.assertEqual(protocol.sequence, 1)
