"""XP2 reviewer selection over existing typed fixtures; no native qualification."""
import copy
import unittest
from unittest.mock import patch

import qualify_xp1_configuration as q
import test_xp1_session_world_review as world
import test_xp1_session_order_review as orders
from civ6_host.runtime import xp1_action_job_ledger as jobs
from civ6_host.runtime import xp1_world_input_profile as xp1_world
from civ6_host.runtime import xp2_unit_orders_source as xp2_orders
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256


class XP2WorldUnitReviewTests(unittest.TestCase):
    def ledger(self):
        # Fixture job snapshots cannot attest native execution. Keep every
        # source selector, request decoder and FIFO validator real.
        return patch.object(jobs,'reconcile_action_jobs',return_value={'offline_scheduler_fixture':True})

    def check_job_selection(self, reconcile, result, interval):
        selected=q.saved_load_review_profile(XP2_CORE_SHA256)
        self.assertEqual(selected['job']['execute_rva'],0x536b00)
        reconcile.assert_called_once_with(result['jobs_before'],result['jobs_after'],interval['jobs'],
                                         victory_execute_rva=selected['job']['execute_rva'])

    @staticmethod
    def select_order(result, interval):
        receipt=result['effect']['receipt'];receipt['source_proof_sha256']=xp2_orders.SOURCE[1]
        if result['action']['item_type']=='UNITCOMMAND_CANCEL':
            receipt['cancel_source_proof_sha256']=xp2_orders.SOURCE[1]
        interval['commands'][-1]=dict(stage='official_explicit_unit_order_effect',**copy.deepcopy(receipt))

    def test_world_move_uses_xp2_job_profile_and_real_request_fifo_checks(self):
        fixture=world.WorldFixture(world.functions())
        fixture.choose('world_select_unit',unit_id=17)
        fixture.choose('world_plot_click',unit_id=17,plot_id=4)
        result,interval=fixture.native[-1],fixture.intervals[-1]
        with self.ledger() as reconcile:
            receipt=q.saved_load_validate_world_input(result,interval,result['jobs_before'],core_sha256=XP2_CORE_SHA256)
            self.check_job_selection(reconcile,result,interval)
        self.assertTrue(receipt['native_request_delivered'])
        self.assertFalse(receipt['network_ack_inferred'])
        for change in ('source','missing_receive'):
            altered=copy.deepcopy(result);events=copy.deepcopy(interval)
            if change=='source':
                altered['effect']['receipt']['request']['source_sha256']=xp1_world.SOURCE[1]
                events['commands'][-1]=dict(stage='official_world_input_result',**copy.deepcopy(altered['effect']['receipt']))
            else:events['commands'].pop(1)
            with self.subTest(change=change),self.ledger() as reconcile:
                with self.assertRaises(ValueError):
                    q.saved_load_validate_world_input(altered,events,altered['jobs_before'],core_sha256=XP2_CORE_SHA256)
                reconcile.assert_not_called()

    def test_order_uses_xp2_source_and_job_entry_and_rejects_xp1_proof(self):
        fixture=orders.OrderFixture(orders.functions())
        fixture.choose('unit_order',unit_id=17,item_type='UNITOPERATION_FORTIFY')
        result,interval=fixture.native[-1],fixture.intervals[-1]
        self.select_order(result,interval)
        with self.ledger() as reconcile:
            receipt=q.saved_load_validate_unit_order(result,interval,result['jobs_before'],core_sha256=XP2_CORE_SHA256)
            self.check_job_selection(reconcile,result,interval)
        self.assertEqual(receipt['source_proof_sha256'],xp2_orders.SOURCE[1])
        self.assertFalse(receipt['network_ack_inferred'])
        result['effect']['receipt']['source_proof_sha256']=orders.ORDER_SOURCE[1]
        interval['commands'][-1]=dict(stage='official_explicit_unit_order_effect',**copy.deepcopy(result['effect']['receipt']))
        with self.ledger() as reconcile:
            with self.assertRaisesRegex(ValueError,'source-selected'):
                q.saved_load_validate_unit_order(result,interval,result['jobs_before'],core_sha256=XP2_CORE_SHA256)
            reconcile.assert_not_called()

    def test_cancel_requires_both_xp2_proofs_and_complete_fifo(self):
        fixture=orders.OrderFixture(orders.functions(),release='UNITCOMMAND_CANCEL')
        fixture.choose('unit_order',unit_id=17,item_type='UNITOPERATION_FORTIFY')
        fixture.choose('unit_order',unit_id=17,item_type='UNITCOMMAND_CANCEL')
        result,interval=fixture.native[-1],fixture.intervals[-1]
        self.select_order(result,interval)
        with self.ledger() as reconcile:
            receipt=q.saved_load_validate_unit_order(result,interval,result['jobs_before'],core_sha256=XP2_CORE_SHA256)
            self.check_job_selection(reconcile,result,interval)
        self.assertTrue(receipt['native_request_delivered'])
        for change in ('cancel_source','missing_drain'):
            altered=copy.deepcopy(result);events=copy.deepcopy(interval)
            if change=='cancel_source':
                altered['effect']['receipt']['cancel_source_proof_sha256']=orders.ORDER_SOURCE[1]
                events['commands'][-1]=dict(stage='official_explicit_unit_order_effect',**copy.deepcopy(altered['effect']['receipt']))
            else:events['commands'].pop(-2)
            with self.subTest(change=change),self.ledger() as reconcile:
                with self.assertRaises(ValueError):
                    q.saved_load_validate_unit_order(altered,events,altered['jobs_before'],core_sha256=XP2_CORE_SHA256)
                reconcile.assert_not_called()


if __name__=='__main__':unittest.main()
