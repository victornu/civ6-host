"""Shared attack readback/reviewer and public exploration fixtures; no engine."""
from copy import deepcopy
from unittest.mock import patch
import unittest
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.native import native_saved_combat as combat
from civ6_host.runtime.xp1_unit_attack_profile import SOURCE
from civ6_host.runtime.xp1_world_input_profile import SOURCE as QUEUED_SOURCE
from review_unit_attacks import validate_native_attack
from qualify_xp1_configuration import saved_load_validate_turn_transport
from unit_attack_preparation import select_exploration
from unit_attack_preparation import native_remaining
from types import SimpleNamespace


def fixture():
    action=dict(kind='unit_attack',unit_id=17,operation='RANGE_ATTACK',input_route='dedicated_ranged',
                plot_id=6,x=2,y=1)
    unit=dict(unit_id=17,unit_type=2,x=1,y=1,damage=0,moves=2,attacks_remaining=1)
    unit_after=dict(unit,moves=0,attacks_remaining=0)
    def obs(u,damage):
        return dict(player_id=0,turn=11,width=4,height=4,
            units=[dict(id=u['unit_id'],type=u['unit_type'],owner=0,x=1,y=1,
                        damage=u['damage'],moves=u['moves'],max_moves=2)],
            visible_enemy_units=[dict(owner=1,id=44,type=2,x=2,y=1,damage=damage)])
    before,after=obs(unit,10),obs(unit_after,30)
    queued=dict(unit_present=True,plot_id=None)
    effect=combat.effect(before,after,[unit],[unit_after],action,player_id=0,
        cities_before=[],cities_after=[],queued_before=queued,queued_after=queued,core_sha256=XP1_CORE_SHA256)
    receipt=dict(action=action,effect=effect,observation_before=before,observation_after=after,
        automatic_choices_applied=False,native_defender_selection=True,
        source_proof_sha256=SOURCE[1],city_target_source_sha256=None)
    read=dict(stage='official_explicit_unit_attack_readback',action=action,own_units_before=[unit],
        own_units_after=[unit_after],observation_before=before,observation_after=after,
        queued_before=queued,queued_after=queued,queued_source_sha256=QUEUED_SOURCE[1],
        relationships=[dict(owner=1,at_war=True)],native_defender_selection=True,effect_verified=False)
    rows=[dict(stage='native_command_archive_queued',archive_hex='cafe',bytes=2,queue_count=1,
               delivery_pending=True,action_applied=False),
          dict(stage='native_command_received_in_core_queue',archive_hex='cafe',native_owned_copy=True,action_applied=False),
          dict(stage='before_native_command_queue_drain'),
          dict(stage='native_command_queue_drained',native_dispatcher_used=True),
          read,dict(stage='official_explicit_unit_attack_effect',**receipt)]
    jobs={'fixture':'same actual owner'}
    result=dict(action=action,observation_before=before,observation_after=after,jobs_before=jobs,jobs_after=jobs,
        game_update_called=False,effect=dict(status='completed',refusal_code=None,observation=after,receipt=receipt))
    return result,dict(commands=rows,jobs=[]),jobs


class AttackIntegration(unittest.TestCase):
    def test_preparation_uses_native_deadline_instead_of_parent_load_duration(self):
        backend=SimpleNamespace(_session=SimpleNamespace(lifetime_seconds=300,started=200.0))
        with patch('unit_attack_preparation.time.perf_counter',return_value=330.0):
            self.assertEqual(native_remaining(backend),170.0)
        with patch('unit_attack_preparation.time.perf_counter',return_value=520.0):
            self.assertEqual(native_remaining(backend),0.0)
    def validate(self,result,interval,jobs):
        with patch('civ6_host.runtime.xp1_action_job_ledger.reconcile_action_jobs',return_value={'fixture':'reconciled'}):
            return validate_native_attack(result,interval,jobs,transport=saved_load_validate_turn_transport)

    def test_real_shared_effect_and_fifo_are_joined_without_defender_or_kill_inference(self):
        result,interval,jobs=fixture();summary=self.validate(result,interval,jobs)
        self.assertTrue(summary['native_unit_attack_delivered'])
        self.assertTrue(summary['effect']['target_visible_damage_increased'])
        self.assertFalse(summary['death_or_capture_inferred_from_absence'])

    def test_stale_readback_source_and_fabricated_effect_or_archive_are_refused(self):
        original,events,jobs=fixture()
        for mode in ('damage','source','queue','duplicate','defender','turn'):
            result,interval=deepcopy(original),deepcopy(events)
            if mode=='damage':interval['commands'][-2]['own_units_after'][0]['moves']=1
            elif mode=='source':result['effect']['receipt']['source_proof_sha256']='foreign'
            elif mode=='queue':interval['commands'][1]['archive_hex']='dead'
            elif mode=='duplicate':interval['commands'].append(deepcopy(interval['commands'][-1]))
            elif mode=='defender':result['effect']['receipt']['effect']['selected_defender_claimed']=True
            else:result['observation_after']['turn']=12
            with self.subTest(mode=mode),self.assertRaises((ValueError,RuntimeError)):
                self.validate(result,interval,jobs)

    def test_public_selector_uses_only_current_choices_and_does_not_rewrite_action_masks(self):
        select=dict(kind='world_select_unit',unit_id=17)
        click=dict(kind='world_plot_click',x=2,y=1)
        fortify=dict(kind='unit_order',unit_id=17,item_type='UNITOPERATION_FORTIFY')
        view=dict(observation=dict(width=4,height=4,cities=[dict(x=0,y=1)],
            plots=[dict(index=6,x=2,y=1,visible=True,water=False,impassable=False)]),
            decisions=dict(unit_attacks=dict(units=[dict(unit_id=17,moves=2,x=1,y=1)]),
                candidates=[dict(action=a) for a in (select,click,fortify)],
                world_input=dict(selected_unit_id=None)))
        original=deepcopy(view);self.assertEqual(select_exploration(view,set()),select)
        self.assertEqual(view,original)
        view['decisions']['world_input']['selected_unit_id']=17
        self.assertEqual(select_exploration(view,set()),click)
        self.assertIsNone(select_exploration(view,{(17,6)}))
        view['decisions']['unit_attacks']=None
        self.assertIsNone(select_exploration(view,set()))

    def test_selection_is_possible_before_native_click_catalogue_exists(self):
        select=dict(kind='world_select_unit',unit_id=17)
        fortify=dict(kind='unit_order',unit_id=17,item_type='UNITOPERATION_FORTIFY')
        view=dict(observation=dict(width=4,height=4,cities=[],plots=[dict(index=6,x=2,y=1,
            visible=True,water=False,impassable=False)]),decisions=dict(
                unit_attacks=dict(units=[dict(unit_id=17,moves=2,x=1,y=1)]),
                candidates=[dict(action=a) for a in (select,fortify)],world_input=dict(selected_unit_id=None)))
        self.assertEqual(select_exploration(view,set()),select)
        view['decisions']['world_input']['selected_unit_id']=17
        self.assertIsNone(select_exploration(view,set()))

    def test_other_mobile_unit_can_be_selected_without_its_selected_only_order(self):
        select=dict(kind='world_select_unit',unit_id=18)
        view=dict(observation=dict(width=4,height=4,cities=[],plots=[dict(index=6,x=2,y=1,
            visible=True,water=False,impassable=False)]),decisions=dict(
                unit_attacks=dict(units=[dict(unit_id=17,moves=0,x=1,y=1),
                                        dict(unit_id=18,moves=2,x=1,y=1)]),
                candidates=[dict(action=select)],world_input=dict(selected_unit_id=17)))
        self.assertEqual(select_exploration(view,set()),select)
