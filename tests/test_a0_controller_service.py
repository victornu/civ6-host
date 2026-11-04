"""Controller/event ownership and source ordering; no native calls in fixtures."""
import struct
import unittest
from unittest.mock import patch,Mock

from civ6_host.runtime.a0_family_source import family_profile
from civ6_host.runtime.control_input_service import ControlInputService
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.native.native_host import DiagnosticHost
import test_a0_family_service as fixture_module
import test_control_input_service as control_fixture


class A0ControllerServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.profile=family_profile()

    def fixture(self,*,install=True):
        h,d,a,c,r,before,bindings=fixture_module.A0FamilyServiceTests.fixture(self)
        h.configure_local_player_id=DiagnosticHost.configure_local_player_id.__get__(h,type(h))
        for target,value in (
            ('civ6_host.runtime.control_input_source.verify_xp1',Mock(return_value={})),
            ('civ6_host.runtime.control_input_service.NativeControllerCode',control_fixture.Code),
            ('civ6_host.runtime.native.native_controller_state.NativeControllerCode',control_fixture.Code)):
            p=patch(target,value);p.start();self.addCleanup(p.stop)
        control=ControlInputService(h,d.core,d.context,d,core_sha256=XP1_CORE_SHA256,
            local_player_id=7,read=r.read,emit=Mock())
        if install:c.enable_controller_events(control)
        return h,d,a,c,r,control,before,bindings

    def send(self,h,a,r,kind,values,selector=0):
        r.fields.return_value={0xA1E5A149:fixture_module.scalar(3,selector),
            0xD6FCF3E4:fixture_module.scalar(2,values[0])}
        if len(values)==2:r.fields.return_value[0xA1FBC372]=fixture_module.scalar(2,values[1])
        return a.dispatch(h.pointer,kind,0x9000)

    def test_binding_requires_shared_owner_and_preserves_existing_state(self):
        h,d,a,c,r,control,_,_=self.fixture(install=False)
        self.assertFalse(c.handles_kind(0x21535587));self.assertFalse(c.handles_kind(0x8953F126))
        control.controller_flag(h.pointer);control.turn_begin_state.controller_byte_0d=0xA5
        c.enable_controller_events(control)
        self.assertIs(c.turn_begin_state,control.turn_begin_state)
        self.assertIs(c.turn_begin_state,d.turn_begin_state)
        self.assertEqual(control.controller_flag(h.pointer),0xA5);self.assertEqual(control.code.creates,1)
        with self.assertRaises(ValueError):c.enable_controller_events(control)
        with self.assertRaisesRegex(RuntimeError,'borrows'):control.close()
        a.close();control.close();d.close()

    def test_before_and_after_enqueue_orders_share_flag_and_telemetry(self):
        h,d,a,c,r,control,before,bindings=self.fixture();state=control.turn_begin_state
        original=d._enqueue;observed=[]
        def enqueue(record):
            observed.append((state.controller_initialized,state.controller_byte_0d,
                state.service_flags,list(state.turn_values_by_thread.get(0,()))))
            return original(record)
        d._enqueue=enqueue
        self.send(h,a,r,0x8953F126,(7,0xFFFFFFFF),selector=0xFFFFFFFF)
        self.assertEqual(observed,[(False,None,0,[])])
        self.assertEqual(control.controller_flag(h.pointer),0)
        state.controller_byte_0d=0xA5;state.service_flags=0xE7
        self.send(h,a,r,0x21535587,(0x80000000,))
        self.assertEqual(observed[-1],(True,0,0xA7,[]))
        self.assertEqual(state.turn_values_by_thread,{0:[0x80000000]})
        state.controller_byte_0d=0xA5
        self.send(h,a,r,0x8953F126,(7,0))
        self.assertEqual(observed[-1],(True,0xA5,0xA7,[0x80000000]))
        self.assertEqual(control.controller_flag(h.pointer),0);self.assertEqual(control.code.creates,1)
        self.assertEqual([struct.unpack_from('<II',x,80) for x in d.pending],[(1,7),(2,0x80000000),(3,7)])
        self.assertEqual(d.drain(),3)
        self.assertEqual(d.unit_panel_event_state.view(7)['event_sequence'],3)
        self.assertFalse(d.unit_panel_event_state.latest[7]['first_time'])
        a.close();control.close();d.close()
        self.assertEqual(list(h.vtable),before);self.assertEqual(h._slot_bindings,bindings)

    def test_queue_failure_preserves_source_effect_order_and_quarantines(self):
        for kind,values,expected in ((0x21535587,(11,),0),(0x8953F126,(7,1),0xA5)):
            with self.subTest(kind=hex(kind)):
                h,d,a,c,r,control,_,_=self.fixture();state=control.turn_begin_state
                control.controller_flag(h.pointer);state.controller_byte_0d=0xA5;d.limit=0
                with self.assertRaisesRegex(RuntimeError,'queue bound'):self.send(h,a,r,kind,values)
                self.assertEqual(state.controller_byte_0d,expected)
                self.assertEqual(state.turn_values_by_thread,{})
                self.assertEqual(d.pending,[])
                self.assertTrue(a.quarantined and c.quarantined and control.quarantined)
                with self.assertRaises(RuntimeError):control.close()

    def test_post_enqueue_setter_failure_retains_record_and_forbids_replay(self):
        h,d,a,c,r,control,_,_=self.fixture();control.controller_flag(h.pointer)
        control.code.flag.set_flag=Mock(side_effect=OSError('native setter failed'))
        with self.assertRaises(OSError):self.send(h,a,r,0x8953F126,(7,1))
        self.assertEqual(len(d.pending),1);self.assertEqual(d._sequence,1)
        with self.assertRaises(RuntimeError):self.send(h,a,r,0x8953F126,(7,1))
        self.assertEqual(control.code.flag.set_flag.call_count,1)
        self.assertTrue(control.quarantined)

    def test_full_telemetry_refuses_before_state_change_not_as_game_rule(self):
        h,d,a,c,r,control,_,_=self.fixture();state=control.turn_begin_state
        control.controller_flag(h.pointer);state.controller_byte_0d=0xA5;state.service_flags=0xFF
        state.turn_values_by_thread[0]=[0]*32768
        with self.assertRaisesRegex(ValueError,'capacity'):self.send(h,a,r,0x21535587,(11,))
        self.assertEqual(state.controller_byte_0d,0xA5);self.assertEqual(state.service_flags,0xFF)
        self.assertEqual(d.pending,[]);self.assertEqual(len(state.turn_values_by_thread[0]),32768)

    def test_replaced_shared_state_is_not_repaired_or_used(self):
        h,d,a,c,r,control,_,_=self.fixture();d.turn_begin_state=object()
        with self.assertRaisesRegex(RuntimeError,'replaced'):self.send(h,a,r,0x21535587,(11,))
        self.assertEqual(d.pending,[]);self.assertEqual(control.code.creates,0)

    def test_native_key_requires_explicit_install_and_invalid_fields_do_not_create_controller(self):
        h,d,a,c,r,control,_,_=self.fixture(install=False)
        with self.assertRaises(ValueError):self.send(h,a,r,0x21535587,(11,))
        self.assertEqual(control.code.creates,0)
        h,d,a,c,r,control,_,_=self.fixture()
        with self.assertRaisesRegex(ValueError,'turn-begin'):self.send(h,a,r,0x21535587,(11,),selector=1)
        self.assertEqual(control.code.creates,0);self.assertEqual(d.pending,[])

    def test_foreign_controller_and_active_queue_reject_installation(self):
        h,d,a,c,r,control,_,_=self.fixture(install=False)
        _,_,_,_,_,foreign,_,_=self.fixture(install=False)
        with self.assertRaises(ValueError):c.enable_controller_events(foreign)
        self.send(h,a,r,0x52E2805C,(1,1))
        with self.assertRaises(ValueError):c.enable_controller_events(control)
        self.assertFalse(hasattr(control,'_a0_event_owner'))
