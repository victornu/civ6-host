"""Great People reader composition for the exact BBG checkpoint."""
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from lupa.lua51 import LuaRuntime
import pefile

from civ6_host.contracts import great_people, great_people_actions, information, network_turn
from civ6_host.runtime import xp1_great_people as reader, xp2_great_people_source as source
from civ6_host.runtime import xp1_great_people_commands as commands
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _PROFILE, known_path
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.xp1_continuation import SavedContinuation
from test_xp1_great_people import _ENV
from test_session_capabilities import seal


def fixture_reply(turn, *, congress=False, strategic=True):
    lua = (f"cfg.turn={turn}; cfg.strategic={str(strategic).lower()}; "
           "Game.GetWorldCongress=function() return {IsInSession=function() "
           f"return {str(congress).lower()} end}} end\n").encode('ascii')
    return LuaRuntime(encoding=None).execute(_ENV + lua + reader.query_source(0, turn, xp2=True))


def read_fixture(turn, *, congress=False, strategic=True):
    return reader.parse(fixture_reply(turn, congress=congress, strategic=strategic), 0, turn, xp2=True)


class XP2GreatPeopleTests(unittest.TestCase):
    def test_active_command_revalidates_through_its_already_bound_reader(self):
        runtime = Mock()
        runtime.evaluate_text.return_value = fixture_reply(8)
        prefix = SimpleNamespace(runtime=runtime, ui_child=object(), actions=Mock(),
                                 deferred_events=SimpleNamespace(pending=[]), emit=Mock())
        backend = SimpleNamespace(load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256),
                                  runtime=runtime, core=object(), context=64,
                                  captured_bundle=SimpleNamespace(reference=source.REFERENCE))
        panel = read_fixture(8)
        saved = SimpleNamespace(backend=backend, prefix=prefix, explicit_great_people_actions=panel)
        offer = next(a for a in great_people_actions.actions(panel) if a['kind'] == great_people_actions.PATRONIZE)
        before = {'turn': 8, 'player_id': 0}
        refusal = {'can_start': False, 'request_invoked': False}
        with patch.object(source, 'bind_actions') as bound, patch.object(source, 'bind') as idle, \
                patch.object(commands, '_effect'), \
                patch.object(commands, 'request_player_operation', return_value=refusal) as request:
            result = commands.apply(saved, offer, before)
        bound.assert_called_once_with(saved)
        idle.assert_not_called()
        runtime.evaluate_text.assert_called_once_with(prefix.ui_child, reader.query_source(0, 8, xp2=True),
            b'@xp2_public_great_people', capacity=reader._MAX_RESPONSE)
        operation, params = commands._operation(offer)
        request.assert_called_once_with(backend.core, backend.context, 0, operation, params,
            core_sha256=XP2_CORE_SHA256, read=runtime.read)
        self.assertEqual(result['status'], 'refused')
        self.assertEqual(result['source_sha256'], source.OPERATION_SOURCE[1])

    def test_continuation_routes_only_explicitly_enabled_commands(self):
        continuation = SavedContinuation.__new__(SavedContinuation)
        continuation.owner = SimpleNamespace(load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256))
        continuation.observation = {'player_id': 0}
        continuation.world_input_prompts = {}
        session = SimpleNamespace(xp2_great_people=True, xp2_great_people_actions=True)
        actions = great_people_actions.actions(read_fixture(8), include_reject=True)
        self.assertEqual({action['kind'] for action in actions}, set(great_people_actions.KINDS))
        with patch.object(continuation, '_transition') as execute:
            for action in actions:
                continuation.execute(action, session=session)
                execute.assert_called_with(action, session=session, pump=False)
            for flag in ('xp2_great_people', 'xp2_great_people_actions'):
                setattr(session, flag, False)
                execute.reset_mock()
                with self.assertRaisesRegex(ValueError, 'admitted expansion'):
                    continuation.execute(actions[0], session=session)
                execute.assert_not_called()
                setattr(session, flag, True)

    def test_read_only_congress_keeps_prices_native_flags_and_own_points(self):
        open_panel = read_fixture(8)
        self.assertTrue(open_panel['timeline'][1]['recruitment']['available'])
        for congress, strategic in ((True, True), (False, False)):
            with self.subTest(congress=congress, strategic=strategic):
                panel = read_fixture(8, congress=congress, strategic=strategic)
                self.assertTrue(panel['read_only'])
                self.assertEqual(panel['own_points'], open_panel['own_points'])
                self.assertEqual(panel['timeline'][0]['patronage']['YIELD_GOLD']['cost'], 550)
                self.assertIsNone(panel['timeline'][0]['claimant_player_id'])
                self.assertTrue(panel['timeline'][1]['recruitment']['native_can_recruit'])
                self.assertFalse(panel['timeline'][1]['recruitment']['available'])
                self.assertFalse(panel['timeline'][2]['rejection']['available'])
                great_people.validate(panel, 0, 8)
                panel['timeline'][1]['recruitment']['available'] = True
                with self.assertRaisesRegex(ValueError, 'Read-only'):
                    great_people.validate(panel, 0, 8)

    def test_t74_checkpoint_projection_preserves_every_prior_choice(self):
        root = resource_root()
        proof = json.loads((root/'evidence/host-xp2-bbg-holy-site-prayers-t74-native.json').read_bytes())
        ref = proof['checkpoint_out']
        raw = (root/ref['path']).read_bytes()
        self.assertEqual(sha256(raw).hexdigest(), ref['sha256'])
        saved = json.loads(raw)
        old, observation = saved['decisions'], saved['observation']
        current = deepcopy(old)
        panel = read_fixture(observation['turn'])
        network_turn.add_xp2_great_people(current, panel)
        seal(current)
        self.assertIn(current['schema'], network_turn.SUPPORTED_SCHEMAS)
        self.assertIn(current['schema'], network_turn.WORLD_CONGRESS_CAPABILITY_SCHEMAS)
        identity = SimpleNamespace(episode_id=current['episode_id'], game_generation=current['game_generation'])
        network_turn.validate_capability_catalogue(current, identity, current['sequence'],
            observation['turn'], player_id=observation['player_id'], observation=observation)
        self.assertEqual(information.project('great_people', observation, current), panel)
        self.assertEqual(current['candidates'], old['candidates'])
        projected, transition = network_turn.checkpoint_catalogue(current, old, observation,
                                                                 core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, old)
        self.assertEqual(transition['added_public_fields'], ['great_people'])
        self.assertEqual(transition['added_action_families'], [])
        with self.assertRaisesRegex(ValueError, 'Gathering Storm'):
            network_turn.checkpoint_catalogue(current, old, observation, core_sha256=XP1_CORE_SHA256)
        enabled = deepcopy(current)
        network_turn.add_xp2_great_people_actions(enabled)
        seal(enabled)
        self.assertIn(enabled['schema'], network_turn.SUPPORTED_SCHEMAS)
        self.assertIn(enabled['schema'], network_turn.WORLD_CONGRESS_CAPABILITY_SCHEMAS)
        self.assertEqual(information.project('great_people', observation, enabled), panel)
        network_turn.validate_capability_catalogue(enabled, identity, enabled['sequence'],
            observation['turn'], player_id=observation['player_id'], observation=observation)
        offered = [row['action'] for row in enabled['candidates'][len(old['candidates']):]]
        self.assertEqual(offered, great_people_actions.actions(panel, include_reject=True))
        self.assertEqual({a['kind'] for a in offered}, set(great_people_actions.KINDS))
        projected, transition = network_turn.checkpoint_catalogue(enabled, old, observation,
                                                                 core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, old)
        self.assertEqual(transition['added_public_fields'], ['great_people'])
        self.assertEqual(transition['added_action_families'], list(great_people_actions.KINDS))

    def test_reader_verifies_live_installed_image_and_rejects_foreign_capture(self):
        pe = pefile.PE(str(known_path(_PROFILE.id)), fast_load=True)
        self.addCleanup(pe.close)
        base = pe.OPTIONAL_HEADER.ImageBase
        source.verify_live(base, lambda addr, size: pe.get_data(addr-base, size),
                           image=_PROFILE, reference=source.REFERENCE)
        with self.assertRaisesRegex(ValueError, 'exact Boston'):
            source.require_source(_PROFILE, reference=None)
        changed = source.require_source(_PROFILE, reference=source.REFERENCE)['timeline_reifier'][0]['rva']

        def corrupt(addr, size):
            raw = pe.get_data(addr-base, size)
            return bytes([raw[0] ^ 1]) + raw[1:] if addr == base + changed else raw

        with self.assertRaisesRegex(ValueError, 'binding differs'):
            source.verify_live(base, corrupt, image=_PROFILE, reference=source.REFERENCE)
        source.verify_actions_live(base, lambda addr, size: pe.get_data(addr-base, size),
                                   image=_PROFILE, reference=source.REFERENCE)
        changed = source.require_actions(_PROFILE, reference=source.REFERENCE)['spans']['recruit_handler']['rva']
        with self.assertRaisesRegex(ValueError, 'binding differs'):
            source.verify_actions_live(base, corrupt, image=_PROFILE, reference=source.REFERENCE)

    def test_stock_rules_choose_distinct_dependencies_and_share_the_verified_engine(self):
        pe = pefile.PE(str(known_path(_PROFILE.id)), fast_load=True)
        self.addCleanup(pe.close)
        base = pe.OPTIONAL_HEADER.ImageBase
        read = lambda addr, size: pe.get_data(addr-base, size)
        stock = source.STOCK_REFERENCE
        shared = source.require_source(_PROFILE, reference=stock)
        stock_proof = source._stock_proof(shared)
        source.verify_live(base, read, image=_PROFILE, reference=stock)
        source.verify_actions_live(base, read, image=_PROFILE, reference=stock)
        before = source.source_dependencies(_PROFILE, reference=stock)
        after = source.source_dependencies(_PROFILE, reference=stock, include_actions=True)
        self.assertEqual(set(after.values())-set(before.values()),
                         {source.OPERATION_SOURCE[1], source.require_actions(_PROFILE, reference=stock)
                          ['player_operation_source']['sha256']})
        self.assertTrue({stock[1], source.STOCK_SOURCE[1], stock_proof['database']['sha256'],
                         stock_proof['configuration']['sha256']} <= set(before.values()))
        self.assertFalse({source.REFERENCE[1], shared['gameplay']['sha256'],
                          shared['ui_sources']['bbg_popup']['sha256']} & set(after.values()))
        patronage = next(a for a in great_people_actions.actions(read_fixture(8))
                         if a['kind'] == great_people_actions.PATRONIZE)
        self.assertEqual(commands.source_for(patronage, xp2=True, reference=stock), source.STOCK_SOURCE)
        self.assertEqual(commands.source_for(patronage, xp2=True, reference=source.REFERENCE), source.OPERATION_SOURCE)
        with self.assertRaisesRegex(ValueError, 'Unknown Gathering Storm'):
            commands.source_for(patronage, xp2=True, reference=(stock[0], '0'*64))
