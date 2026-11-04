"""Shared Lua and parsers exercised on boundary fixtures, not a native claim."""
from contextlib import ExitStack
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import unittest

from civ6_host.runtime.xp1_choice_queries import read
from test_xp1_session_view import observation
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256


class Queries(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        for module in ('xp1_research_profile','xp1_production_profile'):
            self.stack.enter_context(patch('civ6_host.runtime.'+module+'.bind_owner'))
            self.stack.enter_context(patch('civ6_host.runtime.'+module+'.verify_source'))
        self.obs=observation()
        self.obs['cities']=[dict(id=3)]
        self.queue=b'C,3,0,0,0,0,100,0,-1,N,-1,-1,-1,-1\nP1|0|1|1'
        self.catalog=(b'production-v1|0|3|1|catalog|1|7|12|90|13|11|14|15|16|1'
                      b'|unit:UNIT_WARRIOR:21:123')
        self.queries=[]
        runtime=NS(evaluate_text=self.evaluate,read=Mock())
        self.saved=NS(backend=NS(core=object(),runtime=runtime,load_abi=NS(core_sha256=XP1_CORE_SHA256)),
                      prefix=NS(runtime=runtime,ui_child=object()),continuation=NS())

    def evaluate(self,child,source,label,**kwargs):
        self.queries.append((source,label))
        if label in (b'@explicit_research_catalog',b'@explicit_current_research'):
            kind=b'civic' if b'local kind="civic"' in source else b'research'
            if label==b'@explicit_research_catalog':
                return kind+b',0,1,7,11,12,90,2,0:100,1:101'
            return kind+b',0,1,-1,0'
        if label==b'@explicit_queue_snapshot':return self.queue
        if label==b'@explicit_production_catalog':return self.catalog
        raise AssertionError(label)

    def test_all_query_choices_reach_catalogue_with_exact_current_state(self):
        candidates,families,state=read(self.saved,self.obs)
        self.assertEqual(len(candidates),5)
        self.assertEqual([r['action']['index'] for r in candidates[:4]],[0,1,0,1])
        self.assertEqual(state['research'],dict(research=None,civic=None))
        self.assertEqual(families['production']['status'],'queried_partial')
        self.assertIn('unit_corps_and_armies',families['production']['unqualified'])
        self.assertEqual(self.saved.continuation.explicit_production_snapshot['cities'][0]['production_yield'],100)
        self.assertNotIn('production_yield',state['production'][0])
        self.assertIn(b'local replaceCurrent=true', self.queries[-1][0])

    def test_wrong_turn_or_foreign_owned_city_never_publishes_partial_success(self):
        for data in (self.queue.replace(b'P1|0|1|1',b'P1|0|2|1'),
                     self.queue.replace(b'C,3,',b'C,4,')):
            self.queue=data
            with self.assertRaisesRegex(RuntimeError,'crossed'):
                read(self.saved,self.obs)
            self.assertFalse(hasattr(self.saved.continuation,'explicit_production_snapshot'))

    def test_nonempty_queue_is_not_accepted_as_unqueried_empty_production(self):
        self.catalog=b'production-v1|0|3|1|queue_nonempty|0|7|12|90|13|11|14|15|16|0'
        with self.assertRaisesRegex(RuntimeError,'enumerate'):
            read(self.saved,self.obs)


if __name__=='__main__':unittest.main()
