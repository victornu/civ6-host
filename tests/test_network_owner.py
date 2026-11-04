import unittest
from types import SimpleNamespace
from unittest.mock import patch

from civ6_host.runtime import network_owner as owner_api


class NetworkOwnerTests(unittest.TestCase):
    def setUp(self):
        self.owner = SimpleNamespace(network_reference={
            'major_player_ids': tuple(range(6)), 'human_player_ids': (0,)})
        self.session = dict(turn=1, local_player_id=0, human_player_ids=[0],
                            active_human_player_ids=[0])

    def test_roster_syntax_is_not_human_control_admission(self):
        self.assertEqual(owner_api.roster(tuple(range(6))), tuple(range(6)))
        for bad in ((0, False), (0, 0), (), (64,), [0]):
            with self.assertRaises(ValueError):
                owner_api.roster(bad)
        with patch.object(owner_api, 'state', return_value=self.session):
            with self.assertRaisesRegex(ValueError, 'not a captured human'):
                owner_api.require_actor(self.owner, 1, tuple(range(6)))

    def test_prepare_hands_off_the_restored_boundary_comparator(self):
        initial = dict(player_id=0, turn=1)
        reference = dict(state=initial, major_player_ids=(0, 1))
        self.owner.inputs = SimpleNamespace(profile=owner_api.LAN_PROFILE,
                                            checkpoint=('checkpoint.json', 'digest'))
        self.owner.stage = 'official-public-observed-awaiting-controlled-stop'
        self.owner.captured_bundle = SimpleNamespace(initial_turn=1)
        self.owner.control = self.owner.emit = lambda *args, **kwargs: None
        with patch.object(owner_api, 'reference_state', return_value=reference), \
             patch.object(owner_api, 'require_actor', return_value=self.session), \
             patch('civ6_host.runtime.native.native_controller_state.prepare_session_controller'), \
             patch('civ6_host.runtime.network_ui.admit'), \
             patch('civ6_host.runtime.network_checkpoint.prepare_owner') as restore:
            session, compare = owner_api.prepare(self.owner, initial)
        restore.assert_called_once_with(self.owner, initial)
        self.assertIs(session, self.session)
        self.assertIs(compare, restore.return_value)

    def _execute(self, action, offers):
        readers = 'civ6_host.runtime.native.native_saved_actions'
        with patch.object(owner_api, 'require_actor', return_value=self.session), \
                patch(readers + '.read_decisions', return_value=(
                    {'turn': 1, 'player_id': 0},
                    {'candidates': [{'action': a} for a in offers]})) as read, \
                patch(readers + '.apply_choice', return_value={
                    'turn': 1, 'player_id': 0}) as apply:
            result = owner_api.execute(self.owner, action, player_id=0,
                sequence=17, rounds=0, round_limit=8)
            return result, read.call_count, apply.call_count

    def test_changed_native_availability_refuses_without_submission(self):
        result, reads, applies = self._execute({'kind': 'found_city'}, [])
        self.assertEqual((result['status'], reads, applies), ('refused', 1, 0))
        self.assertEqual(result['reason'], 'native_availability_changed')

    def test_rpc_revision_is_not_a_legality_rule(self):
        action = {'kind': 'found_city', 'unit_id': 65536}
        result, reads, applies = self._execute(action, [action])
        self.assertEqual((result['status'], reads, applies), ('completed', 1, 1))

    def test_policy_removed_from_open_slot_is_refused_without_submission(self):
        action = dict(kind='policies', candidate=dict(status='candidate',
            player_id=0, turn=1, slot_count=1, assignments=[[0, 10]]))
        offer = dict(kind='policies', slots=[dict(slot=0, prior_index=-1,
            options=[dict(index=0, hash=20, native_hash=20, policy_type='POLICY_OTHER')])])
        result, reads, applies = self._execute(action, [offer])
        self.assertEqual(result, dict(status='refused',
            reason='native_availability_changed', requested_action=action))
        self.assertEqual((reads, applies), (1, 0))
        offer['slots'][0]['slot'] = 1
        with self.assertRaisesRegex(ValueError, 'Malformed policy slot'):
            self._execute(action, [offer])

    def test_forced_network_turn_without_ui_gate_is_refused(self):
        result, reads, applies = self._execute({'kind': 'force_end_turn'}, [])
        self.assertEqual((result['status'], reads, applies), ('refused', 0, 0))
        self.assertEqual(result['reason'], 'native_forced_turn_gate_unavailable')

    def test_forced_choice_bypasses_normal_blockers_without_resolving_them(self):
        with patch('civ6_host.runtime.network_ui.force_available', return_value=True), \
             patch('civ6_host.runtime.network_turns.controls', return_value={
                 'active_complete':True, 'can_unready':False}), \
             patch('civ6_host.runtime.network_turns.submit', return_value={
                 'status':'completed'}) as submit:
            result, reads, applies = self._execute({'kind':'force_end_turn'}, [])
        self.assertEqual((result['status'], reads, applies), ('completed', 0, 0))
        submit.assert_called_once_with(self.owner, {'kind':'force_end_turn'}, 0)

    def test_world_war_prompt_cannot_be_bypassed_by_fast_network_routes(self):
        self.owner.world_input_prompts={0:dict(attacking_player=0,defending_player=1,war_type=0)}
        with patch('civ6_host.runtime.network_turns.submit') as submit, \
             patch('civ6_host.runtime.network_dialogue.initiate') as initiate:
            for action in ({'kind':'force_end_turn'}, {'kind':'end_turn'},
                           {'kind':'unready_turn'}, {'kind':'diplomacy_initiate'},
                           {'kind':'found_city'}):
                result,reads,applies=self._execute(action,[action])
                self.assertEqual((result['status'],result['reason'],reads,applies),
                                 ('refused','world_war_choice_required',0,0))
        submit.assert_not_called()
        initiate.assert_not_called()

    def test_world_war_response_still_uses_native_revalidation(self):
        self.owner.world_input_prompts={0:dict(attacking_player=0,defending_player=1,war_type=0)}
        action={'kind':'world_war_response','accept':False}
        result,reads,applies=self._execute(action,[action])
        self.assertEqual((result['status'],reads,applies),('completed',1,1))

    def test_wrapper_does_not_add_forced_turn_during_world_war_prompt(self):
        choices=[{'action':{'kind':'world_war_response','accept':v}} for v in (False,True)]
        self.owner.unit_work_information_by_player = {0: None}
        decisions=dict(schema='legacy',candidates=choices,unsupported=[],unit_work=None,
                       world_input=dict(war_prompt={'defending_player':1}))
        with patch.object(owner_api,'require_actor',return_value=self.session), \
             patch('civ6_host.runtime.network_turns.controls',return_value=dict(
                 active=True,active_complete=True,can_unready=False,timer_elapsed=False)), \
             patch('civ6_host.runtime.native.native_saved_actions.read_decisions',
                   return_value=({'player_id':0,'turn':1},decisions)), \
             patch('civ6_host.runtime.network_dialogue.control'), \
             patch('civ6_host.runtime.unit_work_state.observe', return_value=None), \
             patch('civ6_host.contracts.unit_work_info.validate', return_value=None), \
             patch('civ6_host.runtime.city_growth.observe', return_value=None), \
             patch('civ6_host.runtime.production_inputs.attach'), \
             patch('civ6_host.runtime.network_dialogue.read_overview') as overview, \
             patch('civ6_host.runtime.network_ui.force_available',return_value=True) as forced:
            _,value=owner_api.read(self.owner,17,0,player_id=0,round_limit=8)
        self.assertEqual(value['candidates'],choices)
        forced.assert_not_called()
        overview.assert_not_called()

    def test_endturn_uses_network_boundary_after_native_revalidation(self):
        with patch('civ6_host.runtime.network_turns.submit', return_value={
                'status': 'completed'}) as submit:
            result, reads, applies = self._execute({'kind': 'end_turn'}, [{'kind': 'end_turn'}])
        self.assertEqual((result['status'], reads, applies), ('completed', 1, 0))
        submit.assert_called_once()

    def test_initial_diplomacy_uses_fresh_overview_adapter(self):
        action = dict(kind='diplomacy_initiate', target_player_id=2,
                      choice='CHOICE_DECLARE_FRIENDSHIP')
        with patch('civ6_host.runtime.network_dialogue.initiate',
                   return_value=dict(status='completed')) as initiate:
            result, reads, applies = self._execute(action, [])
        self.assertEqual((result['status'],reads,applies),('completed',0,0))
        initiate.assert_called_once_with(self.owner,action,0,1)


if __name__ == '__main__':
    unittest.main()
