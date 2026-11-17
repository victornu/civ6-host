from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.contracts import city_state_envoys, city_state_levies, dedications, information, network_turn
from civ6_host.runtime import xp1_dedications_source, xp1_session_view, xp2_dedications
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.xp1_saved_load import REFERENCE
import test_capability_combat_readiness as combat_readiness
from test_session_capabilities import seal


def expansion_catalogue():
    base = combat_readiness.CombatReadinessTests()
    base.setUp()
    observation = deepcopy(base.obs)
    player, turn = observation['player_id'], observation['turn']
    fields = dict(player_id=player, turn=turn)
    dimensions = {key: observation[key] for key in ('width', 'height')}
    value = network_turn.upgrade_captured_city_catalogue(
        base.current, dict(**fields, city=None, directives=[]), actions_closed=False)
    city_shots = [dict(city_id=city['id'], district_id=city['id'], x=city['x'], y=city['y'],
                       available=False, targets=[])
                  for city in sorted(observation['cities'], key=lambda city: city['id'])]
    value = network_turn.upgrade_xp1_city_shot_catalogue(
        value, dict(**fields, **dimensions, cities=city_shots))
    value = network_turn.upgrade_xp1_district_shot_catalogue(value, dict(**fields, **dimensions, districts=[]))
    value = network_turn.upgrade_xp1_governor_catalogue(value, dict(
        player_id=player, current_game_turn=turn, points_obtained=0, points_spent=0,
        can_appoint=False, titles_considered=False, governors=[]))
    value = network_turn.upgrade_xp1_city_state_envoys_catalogue(value, dict(
        **fields, schema=city_state_envoys.SCHEMA, city_states=[]))
    value['schema'] = network_turn.CAPABILITY_XP1_ENVOY_CHOICES_SCHEMA
    network_turn.add_envoy_choices(value, dict(player_id=player, current_game_turn=turn,
        tokens_to_give=0, can_give_influence=False, considered=False,
        giving_tokens_blocker_present=False, targets=[]), actions_closed=False)
    network_turn.add_xp1_city_state_levies(value, dict(
        **fields, schema=city_state_levies.SCHEMA, military_enabled=False, city_states=[]))
    network_turn.add_xp1_unit_levies(value, dict(**fields, schema=city_state_levies.UNIT_SCHEMA, units=[]))
    return observation, seal(value)


class RiseAndFallDedicationTests(unittest.TestCase):
    def test_current_offer_survives_public_validation_and_old_checkpoint_comparison(self):
        from civ6_host.runtime.network_checkpoint import _semantic_decisions

        observation, original = expansion_catalogue()
        player, turn = observation['player_id'], observation['turn']
        raw = f'{player}|{turn}|1|normal|1\nchoice|3|DEDICATION_TEST'.encode('ascii')
        state = xp2_dedications.parse_state(raw, player, turn)
        decisions = deepcopy(original)
        saved = object()
        with patch.object(xp2_dedications, 'catalogue', return_value=state) as catalogue:
            xp1_session_view._add_dedications(saved, observation, decisions, actions_closed=False,
                previous_schema=network_turn.CAPABILITY_XP1_UNIT_LEVIES_SCHEMA,
                target_schema=network_turn.CAPABILITY_XP1_DEDICATIONS_SCHEMA)
            catalogue.assert_called_once_with(saved, observation)
        del decisions['decision_id']
        decisions['decision_id'] = network_turn.digest(decisions)
        self.assertEqual(information.project('dedications', observation, decisions), state)
        self.assertEqual(information.project('unit_levies', observation, decisions),
                         information.project('unit_levies', observation, original))
        selection = dict(decision_id=decisions['decision_id'],
                         candidate_id=network_turn.digest(dedications.CANDIDATE),
                         parameters={'indices': [3]})
        self.assertEqual(network_turn.select_capability(decisions, selection),
                         dict(kind=dedications.KIND, indices=[3]))
        projected, transition = network_turn.checkpoint_catalogue(
            decisions, original, observation, core_sha256=XP1_CORE_SHA256)
        self.assertEqual(_semantic_decisions(projected, observation),
                         _semantic_decisions(original, observation))
        self.assertEqual(transition['added_action_families'], [dedications.KIND])
        self.assertEqual(transition['added_public_fields'], ['dedications'])
        self.assertEqual(network_turn.checkpoint_catalogue(
            decisions, decisions, observation, core_sha256=XP1_CORE_SHA256), (decisions, None))
        with self.assertRaises(ValueError):
            network_turn.checkpoint_catalogue(
                decisions, original, observation, core_sha256=XP2_CORE_SHA256)

    def test_xp1_source_and_permit_refuse_other_images_and_requests(self):
        source = xp1_dedications_source
        self.assertTrue(source.supports(REFERENCE, _XP1_PROFILE))
        self.assertFalse(source.supports(('foreign', 'other'), _XP1_PROFILE))
        self.assertFalse(source.supports(REFERENCE, None))
        self.assertIn(source.SOURCE[1], source.source_dependencies(_XP1_PROFILE).values())
        core = SimpleNamespace(_civ6_host_execution_image=_XP1_PROFILE)
        permit = xp2_dedications._Permit(xp2_dedications._SEAL, core, 32, 0, 3)
        parameters = {xp2_dedications.PARAMETER: 3}
        request = dict(core_sha256=XP1_CORE_SHA256, submit=True, allow_empty=False)
        operation = xp2_dedications.OPERATION
        self.assertEqual(xp2_dedications.authorize_request(
            permit, core, 32, 0, operation, parameters, **request), 'COMMEMORATE')
        for context, player, params in ((64, 0, parameters), (32, 1, parameters),
                                        (32, 0, {xp2_dedications.PARAMETER: 9})):
            with self.subTest(context=context, player=player, params=params), self.assertRaises(ValueError):
                xp2_dedications.authorize_request(permit, core, context, player, operation, params, **request)
        core._civ6_host_execution_image = None
        with self.assertRaises(ValueError):
            xp2_dedications.authorize_request(permit, core, 32, 0, operation, parameters, **request)

    def test_live_guard_checks_frozen_binding_spans(self):
        proof = xp1_dedications_source.source(_XP1_PROFILE)
        binding = proof['bindings']['GetEras']['callback']
        base = 0x1000
        callback = base + int(binding['rva'], 16)
        observed = dict(player_id=0, turn=31)
        checked = []

        def read(address, size):
            checked.append(address)
            return bytes(size)

        def verified_digest(raw):
            if checked[-1] == callback:
                return SimpleNamespace(hexdigest=lambda: 'invalid')
            for span in proof['paths'].values():
                if checked[-1] == base + int(span['rva'], 16):
                    return SimpleNamespace(hexdigest=lambda: span['sha256'])
            for span in proof['bindings']['GetEras'].values():
                if checked[-1] == base + int(span['rva'], 16):
                    return SimpleNamespace(hexdigest=lambda: span['sha256'])
            raise AssertionError('The fixture should stop at the corrupt callback')

        owner = SimpleNamespace(
            load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256),
            core=SimpleNamespace(_handle=base, _civ6_host_execution_image=_XP1_PROFILE),
            captured_bundle=SimpleNamespace(reference=REFERENCE),
            runtime=SimpleNamespace(read=read))
        saved = SimpleNamespace(xp1_dedications_enabled=True)
        continuation = SimpleNamespace(observation=observed)
        with (patch.object(xp2_dedications, '_owner', return_value=(owner, continuation, object(), object())),
              patch.object(xp2_dedications, 'sha256', side_effect=verified_digest)):
            with self.assertRaisesRegex(ValueError, binding['rva']):
                xp2_dedications._bound(saved, observed, active=False)
        self.assertIn(callback, checked)
