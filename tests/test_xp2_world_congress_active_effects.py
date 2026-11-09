"""Owned active-effects join; only the native query and control IO are mocked."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_world_congress_active_effects as effects
from civ6_host.runtime import xp2_congress_cycle as cycle
from civ6_host.runtime.native import native_world_congress_active_effects as native
from civ6_host.runtime.native import native_world_congress_review as shared
import test_xp2_world_congress_review as review_fixture
import test_xp2_congress_cycle as cycle_fixture
from test_world_congress_active_effects import catalogue


class ActiveEffectsOwnerTests(unittest.TestCase):
    def graph(self):
        return review_fixture.ReviewIntegrationTests().graph()

    def call(self,g):
        with cycle_fixture.CycleTests().quiescent_control(g):
            return effects.catalogue(g.saved,g.continuation.observation,sequence=3,congress=g.public)

    def test_exact_owner_uses_shared_pipeline_without_review_or_cycle_bookkeeping(self):
        g=self.graph();value=catalogue(0,61,3,g.public['turn_segment'])
        with cycle_fixture.CycleTests().mode(g,active=False),patch.object(shared,'query',return_value=value) as query, \
             patch.object(cycle,'prepare_review_readback',side_effect=AssertionError('Active effects are not Review')), \
             patch.object(cycle,'observe_review',side_effect=AssertionError('Active effects are not an ACK')):
            result=self.call(g)
        self.assertIs(query.call_args.kwargs['projection'],native)
        self.assertIs(query.call_args.kwargs['backend'],g.backend)
        self.assertEqual(query.call_args.kwargs['admission'],dict(public=g.record.public,private=g.record.private))
        self.assertEqual(result,dict(world_congress_active_effects=value,world_congress_active_effects_status='available'))
        result['world_congress_active_effects']['resolutions'].clear();self.assertEqual(len(value['resolutions']),1)

    def test_closed_ui_and_waiting_do_not_read_native_or_fabricate_empty_results(self):
        g=self.graph()
        with cycle_fixture.CycleTests().mode(g,active=False),patch.object(shared,'query') as query:
            result=effects.catalogue(g.saved,g.continuation.observation,sequence=3,congress=None)
            self.assertEqual(result,dict(world_congress_active_effects=None,world_congress_active_effects_status='waiting_or_closed'))
            query.assert_not_called()
        g=self.graph();g.public['paused']=g.record.public['paused']=True
        g.public['offers']['confirm_proposals']=g.record.public['offers']['confirm_proposals']=False
        g.continuation.explicit_world_congress=deepcopy(g.public)
        with cycle_fixture.CycleTests().mode(g,active=False):
            result=self.call(g)
        self.assertEqual(result,dict(world_congress_active_effects=None,world_congress_active_effects_status='active_effects_ui_unavailable'))

    def test_foreign_revision_queues_and_native_result_segment_cannot_cross(self):
        for mutate in (lambda g:setattr(g.continuation,'sequence',9),lambda g:g.prefix.actions.pending.append(b'pending')):
            g=self.graph();mutate(g)
            with cycle_fixture.CycleTests().mode(g,active=False),patch.object(shared,'query') as query:
                with self.assertRaises((ValueError,RuntimeError)):self.call(g)
                query.assert_not_called()
        g=self.graph();value=catalogue(0,61,3,g.public['turn_segment']+1)
        with cycle_fixture.CycleTests().mode(g,active=False),patch.object(shared,'query',return_value=value):
            with self.assertRaisesRegex(ValueError,'segment'):self.call(g)

    def test_prepared_source_closure_contains_the_fixed_active_projection(self):
        from civ6_host.runtime.execution_images import known_path,select
        from civ6_host.runtime.xp2_world_congress_review import source_dependencies
        name='xp2-gamecore-current-092abfbb'
        pins=source_dependencies(execution_image=select(name,core_path=known_path(name)))
        for digest in (native.SOURCE[1],native.UI_SOURCE[1],native.cards.SOURCE[1],
                       shared.SOURCE[1],shared.NUMERIC_SOURCE[1],cycle.SOURCE[1]):
            self.assertIn(digest,pins.values())


if __name__=='__main__':unittest.main()
