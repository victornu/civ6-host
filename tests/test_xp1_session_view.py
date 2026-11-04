"""Pure reader fixtures: actual shared parsers/contracts, no GameCore execution."""
import ast
from contextlib import ExitStack
from copy import deepcopy
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

HOST = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST / 'src'))
sys.path.insert(0, str(HOST / 'tools'))
from extraction_xp1_session_readers import parameterize
from civ6_host.runtime import xp1_session_view as view
from civ6_host.runtime import network_turns
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE
from civ6_host.runtime.xp1_saved_load import REFERENCE
from civ6_host.runtime.unit_operation_ui_profile import SOURCE, CALLBACKS
from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
from civ6_host.runtime.native import native_unit_actions as units
from civ6_host.contracts import network_turn as contract
from civ6_host.runtime.lan_load import _LAN_MODE, _SIMULTANEOUS_PHASE


def extracted_namespace():
    """Exercise the new extraction hook until the parent regenerates the module."""
    raw = Path(units.__file__).read_text(encoding='utf-8')
    tree = ast.parse(raw)
    target = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                  and node.name == 'found_city_catalog_source')
    # A regenerated module already contains the same transformed function.
    if target.args.kwonlyargs:
        return units.__dict__, raw, None
    transformed = parameterize('civ6rl.native_unit_actions', raw)
    namespace = {'__name__': '_xp1_session_reader_fixture'}
    exec(compile(transformed, '<xp1-reader-extraction>', 'exec'), namespace)
    return namespace, raw, transformed


def observation():
    return dict(schema='civ6rl-player-observation-v1', player_id=0, turn=1,
        width=74, height=46, plots=[], visible_enemy_units=[], cities=[],
        units=[dict(id=uid, type=1, x=x, y=y, damage=0, moves=2, max_moves=2, owner=0)
               for uid, x, y in ((17,3,4), (23,6,7))],
        economy=dict(science=1, culture=1, gold=20, faith=0))


class ReaderFixtures(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        namespace, _, _ = extracted_namespace()
        self.stack.enter_context(patch.object(units, 'found_city_catalog_source',
                                             namespace['found_city_catalog_source']))
        self.bound = self.stack.enter_context(patch(
            'civ6_host.runtime.xp1_status_profiles.bind_owner'))
        self.status_source = self.stack.enter_context(patch(
            'civ6_host.runtime.xp1_status_profiles.verify_source'))
        self.unit_source = self.stack.enter_context(patch(
            'civ6_host.runtime.unit_operation_ui_profile.source'))
        self.timer = self.stack.enter_context(patch(
            'civ6_host.runtime.network_timer.read', return_value=False))
        self.turn_gates = self.stack.enter_context(patch(
            'civ6_host.runtime.xp1_turn_ui_profile.read', return_value=dict(
                turn_availability=dict(end_turn=False, force_end_turn=None,
                                       unready_turn=False))))
        self.choices = self.stack.enter_context(patch(
            'civ6_host.runtime.xp1_choice_queries.read', return_value=([], {
                'research': dict(status='queried_complete', candidate_ids=[]),
                'civic': dict(status='queried_complete', candidate_ids=[]),
                'production': dict(status='queried_partial', candidate_ids=[],
                                   unqualified=['fixture_other_production_actions'])},
                dict(research=dict(research=None, civic=None), production=[]))))
        self.base_source = self.stack.enter_context(patch(
            'civ6_host.runtime.native.native_endturn_gate.verify_source'))
        self.humans = b'0=1|1=0'
        self.activity = b'1|0|0|0,1,1,0;1,0,0,0'
        self.founders = b'0,1,2;17,3,4;23,6,7'
        self.observation = observation()
        self.world = self.stack.enter_context(patch(
            'civ6_host.runtime.xp1_world_input.read',side_effect=self.world_reply))
        self.orders = self.stack.enter_context(patch(
            'civ6_host.runtime.xp1_unit_orders.read',side_effect=self.orders_reply))
        self.attacks = self.stack.enter_context(patch(
            'civ6_host.runtime.xp1_unit_attacks.read',side_effect=self.attacks_reply))
        self.attack_admin = self.stack.enter_context(patch(
            'civ6_host.runtime.xp1_unit_attacks.administrative_readback',side_effect=self.admin_reply))
        self.production_queues = self.stack.enter_context(patch(
            'civ6_host.runtime.xp1_production_queue.read',return_value=dict(production_queues=[],actions=[])))
        self.placements = self.stack.enter_context(patch(
            'civ6_host.runtime.xp1_production_placement.read',return_value=dict(
                placement_offers=[],placements=[],placement_observation_scope='host_tracked',actions=[])))
        self.inventory_source = self.stack.enter_context(patch(
            'civ6_host.runtime.placement_inventory_profile.bind_owner'))
        self.inventory = self.stack.enter_context(patch(
            'civ6_host.runtime.placement_inventory.read',side_effect=lambda p,pid,turn,obs,**kw:
                dict(schema='civ6-host.placement-inventory.v1',scope='native_visible_own_city',
                     player_id=pid,turn=turn,rows=[])))
        self.queries = []
        self.runtime = SimpleNamespace(evaluate_text=self.evaluate, read=Mock())
        p = SimpleNamespace(runtime=self.runtime, ui_child=object(), game_child=object(),
                            quarantined=False)
        inputs = SimpleNamespace(profile=XP1_LAN_PROFILE, official_bundle=REFERENCE)
        bundle = SimpleNamespace(inputs=inputs, reference=REFERENCE)
        b = SimpleNamespace(prefix=p, core=object(), host=object(), context=17,
            inputs=inputs, raw_load_result=object(), runtime=self.runtime,
            captured_bundle=bundle, load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256),
            _saved_load_candidate=True, _xp1_commands_requested=True,
            stage='xp1-continuation-ready', busy=False, poisoned=False, destroyed=False,
            check_thread=Mock(), control=Mock())
        saved = object.__new__(SavedLoadOwner)
        saved.emit = Mock()
        saved.thread = threading.get_ident()
        saved.phase, saved.poisoned, saved._running = 'commands', False, False
        saved.requested = dict(unit_commands_candidate=True)
        saved.backend = saved._backend = b
        saved._engine_sha256=XP1_CORE_SHA256
        b._saved_stage_owner=saved
        saved.prefix, saved.core, saved.host = p, b.core, b.host
        saved.context, saved.inputs, saved.receipt = b.context, inputs, b.raw_load_result
        saved.facade = saved.post = saved.publication = saved.player_view = None
        saved.continuation = SimpleNamespace(owner=b, check=Mock(),
            identity=DiagnosticEpisodeIdentity('7a3edb8d-669b-4fda-98f6-5ce5f36a8d35',
                                              'native-7a3edb8d-669b-4fda-98f6-5ce5f36a8d35'),
            observation=deepcopy(self.observation),
            unit_source=dict(source_sha256=SOURCE[1], callbacks=dict(CALLBACKS)),
            transport=SimpleNamespace(require_empty_native_queue=Mock()), poisoned=False)
        b._xp1_continuation = saved.continuation
        saved.network_reference = dict(capture_manifest_sha256=REFERENCE[1],
            state=dict(player_id=0, observer_id=0, game_mode_u32=_LAN_MODE,
                       turn_phase_u32=_SIMULTANEOUS_PHASE),
            major_player_ids=(0,1), human_player_ids=(0,))
        self.saved = saved

    def world_reply(self,saved,obs):
        """Fixture for native world reads; enclosing query owner is real."""
        from civ6_host.contracts.capability_world_input import actions
        saved._check_query()
        state=dict(schema='civ6rl.world_input.v1',player_id=obs['player_id'],turn=obs['turn'],
            width=obs['width'],height=obs['height'],
            units=[dict(unit_id=u['id'],ignore_moves=False) for u in obs['units']],
            selected_unit_id=None,war_prompt=None)
        queued=dict(player_id=obs['player_id'],turn=obs['turn'],width=obs['width'],height=obs['height'],
            units=[dict(unit_id=u['id'],plot_id=None) for u in obs['units']])
        saved.continuation.explicit_world_input=deepcopy(state)
        return dict(world_input=state,queued_orders=queued,actions=actions(state))

    def attacks_reply(self,saved,obs):
        state=dict(player_id=obs['player_id'],turn=obs['turn'],width=obs['width'],height=obs['height'],
            units=[dict(unit_id=u['id'],unit_type=u['type'],x=u['x'],y=u['y'],damage=u['damage'],
                        moves=u['moves'],attacks_remaining=1) for u in obs['units']],
            cities=[],relationships=[],offers=[])
        queued=dict(player_id=obs['player_id'],turn=obs['turn'],width=obs['width'],height=obs['height'],
            units=[dict(unit_id=u['id'],plot_id=None) for u in obs['units']])
        return dict(unit_attacks=state,queued_orders=queued,actions=[])

    def admin_reply(self,saved,obs,sequence):
        from civ6_host.contracts.capability_unit_attacks import PUBLIC_PRECISION_SHA256
        identity=saved.continuation.identity
        return dict(stage='native_combat_administrative_readback',episode_id=identity.episode_id,
            game_generation=identity.game_generation,player_id=obs['player_id'],sequence=sequence,
            turn=obs['turn'],source_sha256=PUBLIC_PRECISION_SHA256,actor_channel=False,cities=[])

    def orders_reply(self,saved,obs):
        """Native catalogue fixture; real view/contract must retain native offers."""
        from civ6_host.contracts.capability_unit_orders import actions
        saved._check_query()
        state=dict(player_id=obs['player_id'],turn=obs['turn'],
            units=[dict(unit_id=u['id'],activity_type=-2147483648,
                        fortify_turns=0,ready=False) for u in obs['units']],
            offers=[dict(action=dict(kind='unit_order',unit_id=u['id'],
                        route=route,item_type=name,hash=hashed),legal=legal)
                    for u in obs['units'] for route,name,hashed,legal in (
                        ('command','UNITCOMMAND_WAKE',11,True),
                        ('operation','UNITOPERATION_FORTIFY',12,False))])
        saved.continuation.explicit_unit_orders=deepcopy(state)
        return dict(unit_orders=state,actions=actions(state))

    def evaluate(self, child, source, label, *, capacity):
        self.queries.append((child, source, label, capacity))
        p = self.saved.prefix
        if label == b'@lan_session_humans':
            self.assertIs(child, p.game_child)
            self.assertIn(b':IsHuman()', source)
            return self.humans
        self.assertIs(child, p.ui_child)
        if label == b'@lan_turn_activity':
            self.assertIn(b':IsTurnActiveComplete()', source)
            return self.activity
        if label == b'@native_player_observation':
            return json.dumps(self.observation, separators=(',', ':')).encode()
        if label == b'@native_found_city_catalog':
            self.assertIn(b'Game.IsAllowStrategicCommands(pid)==true', source)
            self.assertIn(b'p:IsTurnActiveComplete()==true', source)
            if isinstance(self.founders, Exception):
                raise self.founders
            return self.founders
        self.fail('Unexpected native reader')

    def labels(self):
        return [row[2] for row in self.queries]

    def test_complete_actual_query_exposes_all_legal_founders(self):
        session, obs, decisions = view.read(self.saved, 0, 9)
        self.assertEqual(session['human_player_ids'], [0])
        self.assertEqual(session['active_human_player_ids'], [0])
        self.assertEqual(obs, self.observation)
        self.assertEqual([c['action']['unit_id'] for c in decisions['candidates']
                          if c['action']['kind']=='found_city'], [17,23])
        self.assertEqual(decisions['families']['found_city']['status'], 'queried_complete')
        self.assertEqual(decisions['sequence'], 9)
        self.assertNotIn('player_map', decisions)
        self.assertNotIn('production', decisions)
        self.assertIs(decisions['complete_action_space'], False)
        self.timer.assert_called_once_with(self.saved.backend, core_sha256=XP1_CORE_SHA256)
        self.base_source.assert_not_called()
        self.assertEqual(self.labels(), [b'@lan_session_humans',b'@lan_turn_activity',
                                        b'@native_player_observation',b'@native_found_city_catalog'])

    def test_completed_zero_is_real_query(self):
        self.founders = b'0,1,0'
        _, _, decisions = view.read(self.saved, 0, 0)
        self.assertEqual(decisions['families']['found_city'],
                         dict(status='queried_complete', candidate_ids=[]))
        self.assertIn(b'@native_found_city_catalog', self.labels())

    def test_v3_waiting_exposes_native_unready_without_economy_queries(self):
        self.activity=b'1|0|0|0,0,0,1;1,0,0,0'
        self.turn_gates.return_value=dict(turn_availability=dict(
            end_turn=False,force_end_turn=None,unready_turn=True))
        _,_,decisions=view.read(self.saved,0,4)
        self.assertEqual(decisions['schema'],contract.CAPABILITY_COMBAT_READINESS_SCHEMA)
        self.assertEqual([row['action'] for row in decisions['candidates']],[dict(kind='unready_turn')])
        self.assertIsNone(decisions['choice_state'])
        self.assertEqual(decisions['families']['end_turn'],dict(status='queried_complete',candidate_ids=[]))
        self.assertEqual(decisions['families']['force_end_turn']['status'],'unqualified')
        self.choices.assert_not_called()
        self.world.assert_not_called()
        self.orders.assert_not_called()
        self.placements.assert_not_called()
        self.attacks.assert_not_called()
        self.assertIsNone(decisions['unit_attacks'])
        self.assertIsNone(decisions['placements']);self.assertIsNone(decisions['placement_offers'])
        self.assertIsNone(decisions['placement_observation_scope'])
        self.assertIsNone(decisions['unit_orders'])
        self.assertIsNone(decisions['world_input']);self.assertIsNone(decisions['queued_orders'])
        self.assertNotIn(b'@native_found_city_catalog',self.labels())
        self.turn_gates.assert_called_once_with(self.saved,0,1)
        self.assertEqual(decisions['placement_inventory']['rows'],[])
        self.inventory.assert_called_once()

    def test_v3_closed_never_reads_turn_gates_or_current_choice_queries(self):
        self.turn_gates.side_effect=AssertionError('closed native gate must not run')
        _,_,decisions=view.read(self.saved,0,0,actions_closed=True)
        self.turn_gates.assert_not_called();self.choices.assert_not_called()
        self.world.assert_not_called()
        self.orders.assert_not_called()
        self.placements.assert_not_called()
        self.assertIsNone(decisions['placements']);self.assertIsNone(decisions['placement_offers'])
        self.assertIsNone(decisions['unit_orders'])
        self.assertEqual(decisions['candidates'],[])
        self.assertEqual(decisions['turn_availability'],dict(
            end_turn=None,force_end_turn=None,unready_turn=None))
        self.assertTrue(all(row['status']=='unqualified' for row in decisions['families'].values()))
        self.assertIsNone(decisions['choice_state'])
        self.inventory.assert_called_once()

    def test_inventory_failure_is_not_an_empty_public_inventory(self):
        self.inventory.side_effect=RuntimeError('native placement inventory failed')
        with self.assertRaisesRegex(RuntimeError,'native placement inventory failed'):
            view.read(self.saved,0,0)
        self.assertTrue(self.saved.poisoned)

    def test_attack_catalogue_failure_is_not_an_empty_action_family(self):
        self.attacks.side_effect=RuntimeError('native attack query failed')
        with self.assertRaisesRegex(RuntimeError,'native attack query failed'):view.read(self.saved,0,0)
        self.assertTrue(self.saved.poisoned)

    def test_attack_and_world_queue_disagreement_quarantines(self):
        def changed(saved,obs):
            result=self.attacks_reply(saved,obs)
            result['queued_orders']['units'][0]['plot_id']=1
            return result
        self.attacks.side_effect=changed
        with self.assertRaisesRegex(ValueError,'different native queued orders'):view.read(self.saved,0,0)
        self.assertTrue(self.saved.poisoned)

    def test_inventory_receipt_is_joined_to_exact_public_revision(self):
        _,obs,decisions=view.read(self.saved,0,9)
        self.inventory.assert_called_once_with(self.saved.prefix,0,obs['turn'],obs,
                                               core_sha256=XP1_CORE_SHA256)
        event=next(c for c in self.saved.emit.call_args_list if c.args==('native_placement_inventory_readback',))
        self.assertEqual(event.args,('native_placement_inventory_readback',))
        self.assertEqual(event.kwargs['sequence'],9)
        self.assertEqual(event.kwargs['episode_id'],decisions['episode_id'])
        self.assertEqual(event.kwargs['inventory'],decisions['placement_inventory'])
        self.assertIs(event.kwargs['host_tracking_used'],False)
        admin=self.saved.combat_administrative_by_player[0]
        self.assertEqual(admin['sequence'],9)
        self.assertIs(admin['actor_channel'],False)
        self.assertNotIn('cities_raw',decisions)

    def test_world_read_failure_does_not_become_empty_capability(self):
        self.world.side_effect=RuntimeError('native world query failed')
        with self.assertRaisesRegex(RuntimeError,'native world query failed'):
            view.read(self.saved,0,0)
        self.assertTrue(self.saved.poisoned)

    def test_v7_preserves_partial_native_placement_query_and_tracking_scope(self):
        from civ6_host.contracts import placement
        _,_,decisions=view.read(self.saved,0,0)
        self.placements.assert_called_once()
        self.assertEqual(decisions['placements'],[]);self.assertEqual(decisions['placement_offers'],[])
        self.assertEqual(decisions['placement_observation_scope'],'host_tracked')
        for kind in placement.ACTION_FIELDS:
            self.assertEqual(decisions['families'][kind],dict(status='queried_partial',candidate_ids=[],unqualified=list(placement.GAPS[kind])))

    def test_placement_read_failure_quarantines_instead_of_empty_success(self):
        self.placements.side_effect=RuntimeError('native placement query failed')
        with self.assertRaisesRegex(RuntimeError,'native placement query failed'):view.read(self.saved,0,0)
        self.assertTrue(self.saved.poisoned)

    def test_unit_orders_preserve_native_visibility_legality_and_public_state(self):
        _,_,decisions=view.read(self.saved,0,9)
        catalogue=decisions['unit_orders']
        self.assertEqual(catalogue,self.saved.continuation.explicit_unit_orders)
        self.assertEqual(len(catalogue['offers']),4)
        actions=[row['action'] for row in decisions['candidates'] if row['action']['kind']=='unit_order']
        self.assertEqual([a['unit_id'] for a in actions],[17,23])
        self.assertEqual({a['item_type'] for a in actions},{'UNITCOMMAND_WAKE'})
        self.assertTrue(all(not u['ready'] for u in catalogue['units']))
        self.assertEqual(decisions['families']['unit_order']['status'],'queried_partial')

    def test_unit_orders_read_failure_quarantines_instead_of_empty_success(self):
        self.orders.side_effect=RuntimeError('native unit orders query failed')
        with self.assertRaisesRegex(RuntimeError,'unit orders query failed'):
            view.read(self.saved,0,0)
        self.assertTrue(self.saved.poisoned)

    def test_protocol_inactive_force_requires_exact_native_true_v3_offer(self):
        from civ6_host.runtime.network_protocol import NetworkProtocol
        self.activity=b'1|0|0|0,0,0,0;1,0,0,0'
        self.turn_gates.return_value=dict(turn_availability=dict(
            end_turn=False,force_end_turn=True,unready_turn=False))
        session,_,decisions=view.read(self.saved,0,0)
        protocol=NetworkProtocol(self.saved.continuation.identity,'a'*32,initial_turn=1)
        protocol.session=session;protocol.catalogues={0:decisions}
        request=dict(schema=protocol.schema,nonce=protocol.nonce,
            episode_id=protocol.identity.episode_id,game_generation=protocol.identity.game_generation,
            operation='act',sequence=1,player_id=0,
            selection=dict(decision_id=decisions['decision_id'],candidate_id=decisions['candidates'][0]['candidate_id']))
        self.assertEqual(protocol.validate(request),'act')
        for unavailable in (False,None,1):
            changed=deepcopy(decisions);changed['turn_availability']['force_end_turn']=unavailable
            changed['decision_id']=contract.digest({k:v for k,v in changed.items() if k!='decision_id'})
            protocol.catalogues[0]=changed;request['selection']['decision_id']=changed['decision_id']
            with self.subTest(availability=unavailable),self.assertRaises(ValueError):protocol.validate(request)

    def test_waiting_and_closed_have_no_invented_empty_query(self):
        for state, closed in ((b'0,0,0',False),(b'1,0,0',False),
                              (b'1,1,1',False),(b'1,1,0',True)):
            with self.subTest(state=state, closed=closed):
                self.queries.clear()
                self.activity = b'1|0|0|0,' + state + b';1,0,0,0'
                _, _, decisions = view.read(self.saved, 0, 0, actions_closed=closed)
                family = decisions['families']['found_city']
                self.assertEqual(family['status'], 'unqualified')
                self.assertNotIn('candidate_ids', family)
                self.assertEqual(decisions['candidates'], [])
                self.assertNotIn(b'@native_found_city_catalog', self.labels())

    def test_reads_are_fresh_without_replaying_capture_state(self):
        view.read(self.saved, 0, 0)
        self.activity = b'2|0|0|0,1,1,0;1,1,0,0'
        self.observation['turn'] = 2
        self.observation['economy']['gold'] = 33
        self.founders = b'0,2,0'
        session, obs, decisions = view.read(self.saved, 0, 1)
        self.assertEqual(session['turn'], 2)
        self.assertEqual(obs['economy']['gold'], 33)
        self.assertEqual([row for row in decisions['candidates'] if row['action']['kind']=='found_city'], [])
        self.assertEqual(decisions['world_input']['turn'],2)
        self.assertEqual(decisions['unit_orders']['turn'],2)
        self.assertEqual(self.timer.call_count, 2)

    def test_state_reuses_live_readers_without_observation_or_catalogue(self):
        result = view.state(self.saved)
        self.assertEqual(result['turn'], 1)
        self.assertEqual(self.labels(), [b'@lan_session_humans',b'@lan_turn_activity'])
        self.timer.assert_not_called()

    def test_failed_query_is_not_an_empty_success(self):
        self.founders = RuntimeError('official Lua strategic gate refused')
        with self.assertRaisesRegex(RuntimeError, 'strategic gate'):
            view.read(self.saved, 0, 0)
        self.assertTrue(self.saved.poisoned)

    def test_failed_turn_gate_read_poisons_before_catalogue_attempt(self):
        self.turn_gates.side_effect=RuntimeError('native gate read failed')
        with self.assertRaisesRegex(RuntimeError,'native gate read failed'):
            view.read(self.saved,0,0)
        self.assertTrue(self.saved.poisoned)
        self.assertEqual(self.queries,[])

    def test_human_change_refuses_and_poison_retains_no_fake_session(self):
        self.humans = b'0=1|1=1'
        with self.assertRaisesRegex(RuntimeError, 'human ownership'):
            view.read(self.saved, 0, 0)
        self.assertTrue(self.saved.poisoned)
        self.assertEqual(self.labels(), [b'@lan_session_humans'])

    def test_cross_boundary_observation_refuses(self):
        self.observation['turn'] = 2
        with self.assertRaisesRegex(RuntimeError, 'different boundaries'):
            view.read(self.saved, 0, 0)
        self.assertNotIn(b'@native_found_city_catalog', self.labels())

    def test_foreign_founder_refuses_actual_catalogue(self):
        self.founders = b'0,1,1;19,3,4'
        with self.assertRaisesRegex(ValueError, 'own-unit'):
            view.read(self.saved, 0, 0)
        self.assertTrue(self.saved.poisoned)

    def test_bad_capture_admission_refuses_before_read(self):
        self.saved.network_reference['capture_manifest_sha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'exact admitted capture'):
            view.read(self.saved, 0, 0)
        self.assertEqual(self.queries, [])

    def test_closed_owner_refuses_before_read(self):
        self.saved.phase = 'closed'
        with self.assertRaisesRegex(RuntimeError, 'phase'):
            view.state(self.saved)
        self.assertEqual(self.queries, [])

    def test_read_activity_explicit_engine_and_base_compatibility(self):
        result = network_turns.read_activity(self.saved)
        self.base_source.assert_called_once_with()
        self.assertEqual(result['turn'], 1)
        self.queries.clear()
        with self.assertRaisesRegex(ValueError, 'Unknown engine'):
            network_turns.read_activity(self.saved, core_sha256='f'*64)
        self.assertEqual(self.queries, [])


class ExtractionTests(unittest.TestCase):
    def test_profile_selection_preserves_catalogue_lua_and_other_functions(self):
        namespace, raw, transformed = extracted_namespace()
        fn = namespace['found_city_catalog_source']
        with patch('civ6_host.runtime.native.native_unit_skip.verify_source') as base, \
             patch('civ6_host.runtime.xp1_status_profiles.verify_source') as xp1, \
             patch('civ6_host.runtime.unit_operation_ui_profile.source') as unit:
            first = fn(0, 1)
            self.assertEqual(base.call_count, 1)
            second = fn(0, 1, core_sha256=XP1_CORE_SHA256)
            xp1.assert_called_once_with(XP1_CORE_SHA256)
            unit.assert_called_once_with(core_sha256=XP1_CORE_SHA256)
            self.assertEqual(first, second)
            self.assertIn(b'p:IsTurnActiveComplete()==true', second)
            with self.assertRaisesRegex(ValueError, 'Unknown engine'):
                fn(0, 1, core_sha256='f'*64)
        if transformed is not None:
            before = {n.name: ast.dump(n) for n in ast.parse(raw).body
                      if isinstance(n, ast.FunctionDef)}
            after = {n.name: ast.dump(n) for n in ast.parse(transformed).body
                     if isinstance(n, ast.FunctionDef)}
            self.assertEqual(set(before), set(after))
            for name in before:
                if name != 'found_city_catalog_source':
                    self.assertEqual(before[name], after[name])
        self.assertEqual(parameterize('unrelated.module', 'unchanged'), 'unchanged')


if __name__ == '__main__':
    unittest.main()
