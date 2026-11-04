"""Composed parent/worker boundaries, with process creation replaced by fixtures."""
import json,tempfile
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.captured_session_profile import for_family
from civ6_host.runtime.native.network_session import NativeNetworkSession
from civ6_host.runtime.xp1_session_result import result_provenance
from civ6_host.runtime import xp1_session_inputs as inputs
import test_xp1_network_session as fixtures


class XP2SharedSession(unittest.TestCase):
    def test_model_independent_backend_forwards_capture_and_pins_only_combat_admin(self):
        from civ6_host.runtime.backend import NetworkBackend
        args=dict(resources='fixture-resource',official_bundle={'fixture':'capture'},
            prepared_capture={'fixture':'prepared'},input_profile='xp2-lan')
        with patch('civ6_host.runtime.backend._prepare_runtime') as prepare, \
                patch('civ6_host.runtime.native.network_session.NativeNetworkSession') as native:
            backend=NetworkBackend(**args)
            native.assert_called_once_with(official_bundle=args['official_bundle'],
                prepared_capture=args['prepared_capture'],input_profile='xp2-lan',
                public_display_diagnostic=False)
            backend.reset();native.return_value.reset.assert_called_once_with()
            prepare.reset_mock();native.reset_mock()
            admin=NetworkBackend(**args,administrative_information=True)
            from civ6_host.runtime.xp1_unit_attack_profile import precision_reference
            self.assertEqual(admin._information_store._pins,{'combat':precision_reference(XP2_CORE_SHA256)[1]})
            self.assertIs(admin._information_store,native.return_value._information_store)
            prepare.assert_called_once();native.assert_called_once()

    def test_reset_uses_same_worker_private_inputs_and_protocol_with_xp2_identity(self):
        selected=for_family('xp2-lan')
        with fixtures.Fixture() as f:
            f.captured.reference=selected.candidate.reference
            from civ6_host.runtime.paths import resource_root
            from civ6_host.runtime.xp2_session_inputs import XP2_UI_HOST
            f.executable=resource_root()/XP2_UI_HOST[0]
            def reply(session):
                value=fixtures.reset_reply(session)
                value['outcome']['native_victory'].update(result_provenance(XP2_CORE_SHA256))
                return value
            with patch.object(NativeNetworkSession,'_receive',reply):
                session=f.session(input_profile='xp2-lan',
                    official_bundle=dict(zip(('path','sha256'),selected.candidate.reference)))
                response=session.reset()
            f.consume.assert_called_once_with('xp2-lan',f.package)
            f.sources.assert_called_once_with(f.captured,f.package,postload160=True,
                publish_cache=True,close_loaded=True,observe_player=True,unit_commands=True,
                core_sha256=XP2_CORE_SHA256)
            self.assertEqual(session.protocol.core_sha256,XP2_CORE_SHA256)
            self.assertEqual(session.protocol.catalogues[0],response['decisions'])
            closure=json.loads((session.run/'closure.json').read_bytes())
            self.assertEqual(closure['input_profile'],'xp2-lan')
            self.assertEqual(closure['stdout_transport']['core_sha256'],XP2_CORE_SHA256)
            self.assertNotIn('network_checkpoint',closure)
            from civ6_host.runtime.xp2_unit_orders_source import SOURCE, TRANSPORT_SOURCE, UI_SOURCE
            self.assertEqual(session._xp1_unit_order_source_admission, dict(
                official_bundle=session.official_bundle,
                source_sha256=(SOURCE[1], TRANSPORT_SOURCE[1], UI_SOURCE[1])))
            self.assertEqual(len(f.spawns),1)
            self.assertEqual(len(f.copies),1)
            self.assertEqual(f.spawns[0][0][2].split('\\')[-1],'network_worker.py')

    def test_checkpoint_and_cross_capture_refuse_before_process_launch(self):
        selected=for_family('xp2-lan')
        with fixtures.Fixture() as f:
            for options in ({'checkpoint_on_close':True},{'checkpoint':{}},{}):
                with self.subTest(options=options),self.assertRaises(ValueError):
                    f.session(input_profile='xp2-lan',**options)
            self.assertEqual(f.spawns,[])

    def test_turn_boundary_uses_selected_core_and_rejects_cross_engine(self):
        from civ6_host.runtime.xp1_turn_boundary import select,BOUNDARY
        self.assertIs(select(XP1_CORE_SHA256),BOUNDARY)
        boundary=select(XP2_CORE_SHA256)
        backend=NS(load_abi=NS(core_sha256=XP2_CORE_SHA256))
        owner=NS(_check_active=Mock(),backend=backend,network_turn_rows={0:dict(
            active=True,active_complete=True,can_unready=False)})
        with patch('civ6_host.runtime.network_timer.read',return_value=False) as timer:
            value=boundary.controls(owner,{'turn':1},0)
            timer.assert_called_once_with(backend,core_sha256=XP2_CORE_SHA256)
            self.assertIs(value['timer_elapsed'],False)
            backend.load_abi.core_sha256=XP1_CORE_SHA256
            with self.assertRaisesRegex(ValueError,'another engine'):
                boundary.controls(owner,{'turn':1},0)
            self.assertEqual(timer.call_count,1)

    def test_combat_gate_admits_selected_family_and_refuses_unknown_before_transition(self):
        from civ6_host.runtime.xp1_continuation import SavedContinuation
        owner=object.__new__(SavedContinuation)
        owner.owner=NS(load_abi=NS(core_sha256=XP2_CORE_SHA256))
        with patch('civ6_host.runtime.xp1_continuation.validate_command'), \
                patch.object(owner,'_transition') as transition:
            owner.execute({'kind':'unit_attack'})
            transition.assert_called_once_with({'kind':'unit_attack'},session=None,pump=False)
            transition.reset_mock()
            with self.assertRaisesRegex(ValueError,'not yet source-qualified'):
                owner.execute({'kind':'unqualified_family'})
            transition.assert_not_called()
            owner.execute({'kind':'end_turn'})
            transition.assert_called_once_with({'kind':'end_turn'},session=None,pump=False)

    def test_ui_build_selector_is_exact_and_never_falls_back_to_xp1(self):
        from civ6_host.runtime.xp2_session_inputs import XP2_UI_HOST
        pins={}
        path=inputs.saved_load_build_pins(pins,ui=True,core_sha256=XP2_CORE_SHA256)
        self.assertEqual(pins[str(path)],XP2_UI_HOST[1])
        self.assertTrue(pins)
        for sha,ui in ((XP2_CORE_SHA256,False),('0'*64,True)):
            with self.assertRaises(ValueError):inputs.saved_load_build_pins({},ui=ui,core_sha256=sha)

    def test_close_reader_requires_xp2_continuation_and_owned_child_receipts(self):
        # Compose wire fixtures around the retained XP2 postload lifetime data.
        # This checks the reader only; it is not a native continuation witness.
        from civ6_host.runtime.paths import resource_root
        from civ6_host.runtime.xp2_loaded_lifetime_source import SOURCE
        from civ6_host.runtime.xp2_action_transport_source import SOURCE as COMMAND_SOURCE
        from civ6_host.runtime.native.network_session import xp1_loaded_close_evidence
        old=fixtures.XP1LoadedCloseReportingTests(methodName='runTest')
        if not fixtures._REVIEW.is_file():self.skipTest('Private close references absent')
        old.review=json.loads(fixtures._REVIEW.read_bytes())
        reference=resource_root()/'work/native-xp2-saved-load/run-20261102T123739Z-2187ab257657/loaded-lifetime-result.json'
        with tempfile.TemporaryDirectory() as folder:
            run=Path(folder).resolve()
            report,pins,_,events=old.copy_fixture(run)
            result=json.loads(reference.read_bytes())
            result.update(postload_candidate_only=False,continuation_closed=True,
                command_transport_closed=True,command_source_sha256=COMMAND_SOURCE[1],
                continuation_source_pin_count=188)
            closure=json.loads((run/'closure.json').read_bytes())
            closure.update(input_profile='xp2-lan',official_bundle=dict(zip(('path','sha256'),
                for_family('xp2-lan').candidate.reference)))
            proof=str((resource_root()/SOURCE[0]).resolve())
            closure['pins'][proof]=pins[proof]=SOURCE[1]
            (run/'closure.json').write_text(json.dumps(closure),encoding='utf-8')
            pins[str(run/'closure.json')]=fixtures.digest(run/'closure.json')
            report['source_unchanged']={name:True for name in pins}
            lifetime_stages = {
                'before_xp1_loaded_unload', 'xp1_loaded_unload_returned',
                'before_xp1_loaded_destroy', 'xp1_loaded_destroy_returned',
                'xp1_loaded_lifetime_closed',
            }
            for event in events:
                if 'source_sha256' in event:event['source_sha256']=SOURCE[1]
                if event['stage']=='before_xp1_loaded_unload':event['target_rva']='0x591860'
                if event['stage']=='xp1_loaded_unload_returned':
                    event.update(jobs_unloaded=result['jobs_unloaded'],jobs_transition=result['jobs_transition'])
                if event['stage'] in lifetime_stages:
                    event['stage'] = event['stage'].replace('xp1', 'xp2', 1)
            old.write_fixture(run, result, events, engine='xp2')
            receipt=xp1_loaded_close_evidence(run,report,pins,core_sha256=XP2_CORE_SHA256)
            self.assertEqual(receipt['schema'],'civ6-host.xp2-loaded-close-evidence.v1')
            self.assertFalse(receipt['native_calls_during_verification'])
            for key in ('command_transport_closed','ui_child_released','continuation_closed'):
                changed=dict(result);changed[key]=False
                old.write_fixture(run, changed, events, engine='xp2')
                with self.subTest(key=key),self.assertRaises(ValueError):
                    xp1_loaded_close_evidence(run,report,pins,core_sha256=XP2_CORE_SHA256)


if __name__=='__main__':unittest.main()
