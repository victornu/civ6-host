"""Explicit city query additions preserve every previously known save field."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import unittest

from civ6_host.contracts import network_turn, capability_city_controls
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.native.native_session_resume import semantic_decisions
from civ6_host.runtime import expansion_city_controls_profile as source


class CityQueryCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root=resource_root()
        proof=json.loads((root/'evidence/host-bbg751-public-economy-native.json').read_bytes())
        ref=proof['native']['checkpoint_out'];data=(root/ref['path']).read_bytes()
        if sha256(data).hexdigest()!=ref['sha256']:raise ValueError('Retained v30 checkpoint changed')
        checkpoint=json.loads(data)
        cls.saved=checkpoint['decisions'];cls.observation=checkpoint['observation']
        stock=json.loads((root/'evidence/host-xp2-player-display.json').read_bytes())['samples'][0]['view']
        raw=Path(stock['path']).read_bytes()
        if sha256(raw).hexdigest()!=stock['sha256']:raise ValueError('Retained stock city query changed')
        stock_view=json.loads(raw)
        cls.focus_template=stock_view['decisions']['city_focus_catalogs'][0]

    def queries(self):
        current=deepcopy(self.saved)
        current['city_focus_catalogs']=[];current['citizen_catalogs']=[]
        for city in self.observation['cities']:
            focus=deepcopy(self.focus_template)
            focus.update(city_id=city['id'],player_id=self.observation['player_id'],turn=self.observation['turn'])
            current['city_focus_catalogs'].append(focus)
            # Synthetic target fixture, not a claim that this plot is offered.
            row=dict(plot_id=city['y']*self.observation['width']+city['x'],x=city['x'],y=city['y'],
                     occupied=True,locked=False,workers=None,capacity=None)
            current['citizen_catalogs'].append(dict(schema='civ6rl.native_city_citizens.v1',
                city_id=city['id'],player_id=self.observation['player_id'],turn=self.observation['turn'],plots=[row]))
        return self.rebuild(current)

    def rebuild(self,current):
        offers=capability_city_controls.validate_catalogs(current['city_focus_catalogs'],current['citizen_catalogs'],
            self.observation['player_id'],self.observation['turn'],observation=self.observation)
        current['candidates']=[r for r in current['candidates'] if r['action']['kind'] not in offers]
        for kind,actions in offers.items():
            rows=[dict(candidate_id=network_turn.digest(a),action=a) for a in actions]
            current['candidates'].extend(rows)
            key='city_focus_catalogs' if kind=='city_focus' else 'citizen_catalogs'
            current['families'][kind]=(dict(status='queried_complete',candidate_ids=[r['candidate_id'] for r in rows])
                if current[key] is not None else deepcopy(self.saved['families'].get(kind,
                    dict(status='unqualified',reason='fixture query not requested'))))
        current.pop('decision_id',None);current['decision_id']=network_turn.digest(current)
        return current

    def test_defaults_do_not_exclude_unrequested_city_differences(self):
        current=self.queries()
        projected,transition=network_turn.checkpoint_city_query_projection(current,self.saved,self.observation)
        self.assertIs(projected,current);self.assertIsNone(transition)
        self.assertNotEqual(semantic_decisions(projected),semantic_decisions(self.saved))

    def test_explicit_query_addition_uses_detached_comparison_only(self):
        current=self.queries();original=deepcopy(current)
        projected,transition=network_turn.checkpoint_city_query_projection(current,self.saved,self.observation,
                                                                          requested=(True,True))
        self.assertEqual(semantic_decisions(projected),semantic_decisions(self.saved))
        self.assertEqual(current,original);self.assertIsNot(projected,current)
        self.assertEqual(transition['added_action_families'],['city_focus','city_citizen'])
        self.assertEqual(transition['explicit_city_query_opt_in'],[True,True])
        self.assertTrue(transition['historical_fields_unchanged'])

    def test_previously_known_city_state_remains_compared(self):
        current=self.queries();focus_only=deepcopy(current)
        focus_only['citizen_catalogs']=None;self.rebuild(focus_only)
        projected,transition=network_turn.checkpoint_city_query_projection(current,focus_only,self.observation,
                                                                          requested=(True,True))
        self.assertEqual(transition['added_action_families'],['city_citizen'])
        self.assertEqual(semantic_decisions(projected),semantic_decisions(focus_only))
        current['city_focus_catalogs'][0]['yields'][0]['favored']=True;self.rebuild(current)
        projected,_=network_turn.checkpoint_city_query_projection(current,focus_only,self.observation,
                                                                  requested=(True,True))
        self.assertNotEqual(semantic_decisions(projected),semantic_decisions(focus_only))

    def test_forged_candidates_and_catalogue_versions_are_refused(self):
        current=self.queries();current['candidates'].pop()
        current.pop('decision_id');current['decision_id']=network_turn.digest(current)
        with self.assertRaises(ValueError):
            network_turn.checkpoint_city_query_projection(current,self.saved,self.observation,requested=(True,True))
        current=self.queries();current['schema']=network_turn.CAPABILITY_XP2_POLICY_RECONFIRM_SCHEMA
        with self.assertRaises(ValueError):
            network_turn.checkpoint_city_query_projection(current,self.saved,self.observation,requested=(True,True))
        for flags in ([True,True],(1,True),(False,True),(True,)):
            with self.assertRaises(ValueError):
                network_turn.checkpoint_city_query_projection(self.queries(),self.saved,self.observation,requested=flags)

    def test_bbg_gate_uses_exact_capture_and_retains_native_target_requirement(self):
        from civ6_host.runtime import xp2_bbg_inputs as bbg
        gate=source.bbg_gate(source.XP2_CORE_SHA256,bbg.REFERENCE)
        self.assertIs(gate['selected_city_presentation_required'],False)
        self.assertIs(gate['native_targets_and_revalidation_required'],True)
        pins=source.source_dependencies(source.XP2_CORE_SHA256,official_bundle=bbg.REFERENCE)
        self.assertTrue(any(Path(p).name=='bbg751-ui-gate-source-v1.json' for p in pins))
        self.assertTrue(any(Path(p).name=='ui-availability-before.json' for p in pins))
        self.assertIsNone(source.bbg_gate(source.XP1_CORE_SHA256,bbg.REFERENCE))


if __name__=='__main__':unittest.main()
