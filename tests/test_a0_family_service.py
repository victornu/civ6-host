"""Shared event routing/lifetime; native transport is qualified separately."""
import ast
from contextlib import contextmanager
import hashlib
import struct
import sys
from types import ModuleType,SimpleNamespace as NS
import unittest
from unittest.mock import Mock,patch

from civ6_host.runtime.a0_family_source import family_profile
from civ6_host.runtime.deferred_service import DeferredService
from civ6_host.runtime.event_argument_service import EventArgumentService
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from civ6_host.runtime.native.native_host_events import SharedHostEventDispatch,NativeDeferredHostEvents
from civ6_host.runtime.paths import resource_root
from test_deferred_service import Host

PROFILE=dict(observer_registered=False,state_pointer_nonnull=True,pre_hook=None,post_hook=None,subscriber_count=0,state_flags=0)


def scalar(tag,value):return struct.pack('<H6xQII',tag,value,0,0)


def retained_module(name):
    path=resource_root()/'tests'/(name+'.py')
    tree=ast.parse(path.read_text(encoding='utf-8'))
    class Imports(ast.NodeTransformer):
        def visit_ImportFrom(self,node):
            if node.module in ('civ6rl.native_event_d3f37746','civ6rl.native_event_d35e'):
                # Independent historical reference encoders are fixture-only;
                # they are not production dependencies or alternate runtimes.
                filename=node.module.split('.')[-1]
                key='retained_a0_template_'+filename
                if key not in sys.modules:
                    source=resource_root()/'civ6rl'/(filename+'.py')
                    reference=ModuleType(key);reference.__file__=str(source)
                    exec(compile(source.read_text(encoding='utf-8'),str(source),'exec'),reference.__dict__)
                    sys.modules[key]=reference
                node.module=key
                return node
            if node.module=='civ6rl':node.module='civ6_host.runtime.native'
            elif node.module and node.module.startswith('civ6rl.'):
                node.module='civ6_host.runtime.native.'+node.module[7:]
            return node
    module=ModuleType('retained_a0_'+name);module.__file__=str(path)
    exec(compile(ast.fix_missing_locations(Imports().visit(tree)),str(path),'exec'),module.__dict__)
    return module


class A0FamilyServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.profile=family_profile()

    def fixture(self, core_sha256=XP1_CORE_SHA256, *, execution_image=None):
        h=Host();core=NS(_handle=1000);before=list(h.vtable);bindings=dict(h._slot_bindings)
        if execution_image is not None:
            core._civ6_host_execution_image = execution_image
        for target in ('cache_update_profiles.verify_dispatch_live','cache_update_profiles.verify_notification_live',
                       'event_argument_source.verify_host_live'):
            p=patch('civ6_host.runtime.'+target,return_value={});p.start();self.addCleanup(p.stop)
        reader=NS(fields=Mock(),read=Mock(),close=Mock(),core_sha256=core_sha256)
        p=patch('civ6_host.runtime.event_argument_service.EventArgumentReader',return_value=reader)
        p.start();self.addCleanup(p.stop)
        p=patch('civ6_host.runtime.a0_family_source.family_profile',return_value=self.profile)
        p.start();self.addCleanup(p.stop)
        d=DeferredService(h,core,2000,core_sha256=core_sha256,read=reader.read,emit=Mock(),
            optional_preprocessor=None,queue_metadata_service=None)
        a=EventArgumentService(h,core,2000,d,core_sha256=core_sha256,read=reader.read,emit=Mock(),
            normalizer_transform=None,dynamic_registrations=())
        c=a.install_consumers(receiver_state=dict(PROFILE),pre_turn_immediate_state=dict(PROFILE),entity_listener_count=0)
        return h,d,a,c,reader,before,bindings

    def send(self,h,a,reader,kind,values):
        reader.fields.return_value={0xA1E5A149:scalar(3,0),0xD6FCF3E4:scalar(2,values[0])}
        if len(values)>1:reader.fields.return_value[0xA1FBC372]=scalar(2,values[1])
        return a.dispatch(h.pointer,kind,0x9000)

    def test_one_dispatcher_and_pinned_kind_receiver_closure(self):
        self.assertEqual(len(self.profile.record_types_by_kind),156)
        self.assertEqual(len(self.profile.record_sizes),143)
        for name in ('_dispatch_fields','_enqueue_city_command_started','_enqueue_unit_embarked_state_changed'):
            self.assertIs(getattr(NativeDeferredHostEvents,name),getattr(SharedHostEventDispatch,name))
        with self.assertRaises(TypeError):self.profile.record_types_by_kind[1]=frozenset()

    def test_installed_xp2_deal_history_uses_the_owned_record_135_receiver(self):
        import pefile
        from civ6_host.runtime import xp2_deal_history as history
        from civ6_host.runtime.execution_images import _PROFILE

        host, deferred, arguments, owner, reader, _, _ = self.fixture(
            XP2_CORE_SHA256, execution_image=_PROFILE)
        self.assertEqual(owner.diplomacy_event_profile.record_types_by_kind[history.KIND],
                         frozenset((135,)))
        proof = history.source()
        image = pefile.PE(proof['images']['core']['path'], fast_load=True)
        self.addCleanup(image.close)
        reader.read.side_effect = lambda address,size: image.get_data(address-1000,size)
        fields = {0xa1e5a149:scalar(3,0), 0xd6fcf3e4:scalar(2,0),
                  0xa1fbc372:scalar(2,1), 0x38f292c8:scalar(2,1000)}
        reader.fields.return_value = fields
        self.assertEqual(arguments.dispatch(host.pointer,history.KIND,0x9000),0)
        record, = deferred.pending
        self.assertEqual(struct.unpack_from('<IIII',record), (96,135,1,0))
        self.assertEqual(struct.unpack_from('<III',record,80), (1,0,1))
        self.assertEqual(deferred.drain(),1)
        self.assertEqual((deferred.consumed_count,deferred.pending), (1,[]))
        self.assertEqual(reader.fields.return_value,fields)
        for changed in ({**fields, 0x38f292c8:scalar(3,1000)},
                        {**fields, 0xa1fbc372:scalar(2,0)},
                        {k:v for k,v in fields.items() if k!=0x38f292c8}):
            with self.subTest(fields=len(changed)), self.assertRaises(ValueError):
                history.encode_record(2,changed)

    def test_installed_xp1_project_completion_reuses_ordered_native_records(self):
        from civ6_host.runtime.execution_images import _XP1_PROFILE
        from civ6_host.runtime.foundation_event_profile import (
            PROJECT_KIND, XP1_PROJECT_SOURCE, event_profile, verify_project_live,
            xp1_project_source, xp1_project_source_dependencies)
        from civ6_host.runtime.native import native_event_3182bc8e as event

        _, deferred, _, owner, reader, _, _ = self.fixture(execution_image=_XP1_PROFILE)
        profile = event_profile(execution_image=_XP1_PROFILE)
        self.assertEqual(event_profile().record_types_by_kind[PROJECT_KIND], frozenset((96,)))
        self.assertEqual(profile.record_types_by_kind[PROJECT_KIND], frozenset((96, 99, 100)))
        pins = xp1_project_source_dependencies(_XP1_PROFILE)
        self.assertIn(XP1_PROJECT_SOURCE[1], pins.values())
        spans = xp1_project_source(_XP1_PROFILE)['spans']
        memory = {1000 + span['rva']: bytes.fromhex(span['raw_hex']) for span in spans.values()}
        verify_project_live(1000, lambda address, size: memory[address], xp1_image=_XP1_PROFILE)
        with self.assertRaisesRegex(ValueError, 'live bytes'):
            verify_project_live(1000, lambda address, size: bytes(size), xp1_image=_XP1_PROFILE)

        owner.foundation_event_profile = owner._foundation_event_profile = profile
        owner.active_kind = PROJECT_KIND
        reader.read.return_value = struct.pack('<HHI', 15, 2, 0x10000)
        fields = {event.DESCRIPTOR_KEY: struct.pack('<H6xQII', 1024, 123, 8, 0x21000001),
                  event.SELECTOR_KEY: scalar(3, 0), event.D6_KEY: scalar(2, 3),
                  event.A1FBC_KEY: scalar(2, 15), event.NORMALIZED_58_KEY: scalar(2, 0xffffffff)}
        cache, facades = object(), object()
        lease = Mock(backend=cache)
        lease.require.return_value = facades
        token = NS(owner=NS(load_abi=NS(core_sha256=XP1_CORE_SHA256)), lease=lease,
                   publisher=NS(_facades=facades))

        def retained(passed_facades, read, *, core_sha256):
            self.assertIs(passed_facades, facades)
            self.assertIs(read, reader.read)
            self.assertEqual(core_sha256, XP1_CORE_SHA256)
            self.assertEqual([struct.unpack_from('<I', row, 4)[0] for row in deferred.pending], [96])
            return 15

        with (patch('civ6_host.runtime.a0_foundation_events.require_borrow', return_value=token),
              patch('civ6_host.runtime.native.native_retained_game_getter.read_retained_game_value',
                    side_effect=retained) as getter):
            with self.assertRaisesRegex(ValueError, 'lookup branch'):
                owner._enqueue_project_completion(fields | {event.NORMALIZED_58_KEY: scalar(2, 1)})
            self.assertFalse(deferred.pending)
            self.assertEqual(owner._enqueue_project_completion(fields), 0)
            getter.assert_called_once()
        self.assertEqual([struct.unpack_from('<III', row) for row in deferred.pending],
                         [(112, 96, 1), (128, 99, 2), (128, 100, 3)])
        for row in deferred.pending[1:]:
            self.assertEqual(struct.unpack_from('<I', row, 72), (22,))
            self.assertEqual(struct.unpack_from('<HHIIIii', row, 88),
                             (15, 2, 0x10000, 15, 0xffffffff, -9999, -9999))
        owner.active_kind = None
        self.assertEqual(deferred.drain(), 3)
        self.assertFalse(deferred.pending)

    def test_xp2_terminal_notifications_use_the_shared_fifo(self):
        h,d,a,c,reader,_,_ = self.fixture(XP2_CORE_SHA256)
        d.host_notification_counter = 1
        d.host_metadata_counter = 2
        with patch('civ6_host.runtime.a0_family_service.verify_xp2_producer') as verify:
            for sequence, (kind, record_type) in enumerate(((477734356, 18), (2175010909, 14)), 1):
                self.assertEqual(self.send(h, a, reader, kind, (3, 7)), 0)
                verify.assert_called_with(kind, d.core._handle, reader.read)
                self.assertEqual(struct.unpack_from('<III', d.pending[-1]), (96, record_type, sequence))
                self.assertEqual((d.host_notification_counter, d.host_metadata_counter), (1, 2))
        d.host_notification_counter = d.host_metadata_counter = 0
        self.assertEqual(d.drain(), 2)
        self.assertEqual(d.pending, [])

    def test_current_xp2_war_and_peace_keep_distinct_native_receiver_rows(self):
        import pefile
        from civ6_host.runtime.execution_images import _PROFILE
        from civ6_host.runtime.native.native_deferred_empty_profile import resolve_empty_receiver_row

        h, d, a, _, reader, _, _ = self.fixture(XP2_CORE_SHA256, execution_image=_PROFILE)
        core = pefile.PE(str(_PROFILE.path), fast_load=True)
        self.addCleanup(core.close)
        reader.read.side_effect = lambda address, size: core.get_data(address - d.core._handle, size)
        cases = ((0x7dddaff1, 126, 'GameCoreEvent::DiplomacyDeclareWar'),
                 (0x41d2c9c0, 127, 'GameCoreEvent::DiplomacyMakePeace'))
        for sequence, (kind, record_type, name) in enumerate(cases, 1):
            self.assertEqual(self.send(h, a, reader, kind, (0, 2)), 0)
            record = d.pending[-1]
            self.assertEqual(struct.unpack_from('<III', record), (112, record_type, sequence))
            self.assertEqual(struct.unpack_from('<I4xII', record, 80), (sequence, 0, 2))
            self.assertEqual(resolve_empty_receiver_row(record_type, execution_image=_PROFILE)['event_name'], name)
        self.assertEqual(d.drain(), 2)
        self.assertEqual(d.pending, [])
        self.assertEqual(resolve_empty_receiver_row(127)['event_name'], cases[0][2])
        a.close()
        d.close()

    def test_current_xp2_culture_changed_preserves_scope_and_owned_fifo(self):
        import pefile
        from civ6_host.runtime import xp2_culture_changed as culture
        from civ6_host.runtime.execution_images import _PROFILE
        from civ6_host.runtime.native.native_deferred_empty_profile import resolve_empty_receiver_row

        host, deferred, arguments, owner, reader, _, _ = self.fixture(
            XP2_CORE_SHA256, execution_image=_PROFILE)
        core = pefile.PE(str(_PROFILE.path), fast_load=True)
        self.addCleanup(core.close)
        reader.read.side_effect = lambda address, size: core.get_data(address - deferred.core._handle, size)
        fields = {
            culture.SELECTOR: bytes.fromhex('030000005f574f5200000000000000000000000000000000'),
            culture.FIRST_VALUE: scalar(2, 1),
            culture.SECOND_VALUE: scalar(2, 19),
        }
        reader.fields.return_value = fields
        deferred.host_notification_counter = 1
        deferred.host_metadata_counter = 2
        self.assertTrue(owner.handles_kind(culture.KIND))
        self.assertTrue(owner.handles_record(culture.RECORD_TYPE))
        self.assertEqual(arguments.dispatch(host.pointer, culture.KIND, 0x9000), 0)
        record, = deferred.pending
        self.assertEqual(struct.unpack_from('<4I', record), (96, 0x10d, 1, 0))
        self.assertEqual(struct.unpack_from('<I', record, 72), (4,))
        self.assertEqual(struct.unpack_from('<4I', record, 80), (1, 1, 19, 0))
        self.assertEqual((deferred.host_notification_counter, deferred.host_metadata_counter), (1, 2))
        self.assertEqual(resolve_empty_receiver_row(0x10d, execution_image=_PROFILE)['event_name'],
                         'GameCoreEvent::CultureChanged')
        self.assertIsNone(resolve_empty_receiver_row(0x10d))
        with self.assertRaises(ValueError):
            culture.encode_record(2, {**fields, culture.SELECTOR: scalar(3, 1)})
        deferred.host_notification_counter = deferred.host_metadata_counter = 0
        self.assertEqual(deferred.drain(), 1)
        self.assertEqual(deferred.pending, [])
        arguments.close()
        deferred.close()

    def test_installed_xp1_foundation_events_use_the_owned_receivers(self):
        import pefile
        from civ6_host.runtime import a0_foundation_events, foundation_event_profile
        from civ6_host.runtime.execution_images import _XP1_PROFILE
        from civ6_host.runtime.native import native_event_great_work as codec
        from civ6_host.runtime.xp1_continuation import SavedContinuation
        from civ6_host.runtime import xp2_building_removal as building
        from civ6_host.runtime import xp2_city_occupation_event as transfer
        from civ6_host.runtime import xp2_player_can_construct_event as player

        h, deferred, arguments, owner, reader, _, _ = self.fixture(execution_image=_XP1_PROFILE)
        image = pefile.PE(str(_XP1_PROFILE.path), fast_load=True)
        self.addCleanup(image.close)
        backend = NS(host=h, core=deferred.core, context=deferred.context, prefix=None,
                     check_thread=Mock(), stage='prepared', _xp1_commands_requested=True,
                     load_abi=NS(core_sha256=XP1_CORE_SHA256))
        token = SavedContinuation.__new__(SavedContinuation)
        token.owner = backend
        backend._xp1_continuation = token
        position, component = 0x90000, 0x90010
        payloads = {position: struct.pack('<ii', 3, 4),
                    component: struct.pack('<HHI', 0, 1, 0xffffffff)}
        reader.read.side_effect = lambda address, size: (
            payloads[address] if address in payloads
            else image.get_data(address - deferred.core._handle, size))
        reader.fields.return_value = {
            0x8c468e3c: struct.pack('<H6xQII', 0, position, 8, 0x21000001),
            0xa1e5a149: scalar(3, 0),
            0xa1fbc372: scalar(2, 0),
            0xd6fcf3e4: scalar(2, 1),
            0xf0548bb7: struct.pack('<H6xQII', 1024, component, 8, 0x21000001),
        }
        calls = []

        @contextmanager
        def native_plot(core, context, fields, *, read, include_flag148, core_sha256):
            self.assertEqual((core, context, read), (backend.core, backend.context, reader.read))
            self.assertEqual((include_flag148, core_sha256), (False, XP1_CORE_SHA256))
            self.assertEqual(fields['position_bytes'], payloads[position])
            calls.append('borrow')
            yield dict(owner=0, city_id=44, district_id=0)
            self.assertEqual(len(deferred.pending), 1)
            calls.append('release')

        @contextmanager
        def building_plot(core, context, fields, *, read, core_sha256):
            self.assertEqual((core, context, read), (backend.core, backend.context, reader.read))
            self.assertEqual(core_sha256, XP1_CORE_SHA256)
            self.assertEqual(fields['position_bytes'], payloads[position])
            yield dict(owner=0, city_id=44, district_id=51, flag148=1)
            self.assertEqual(len(deferred.pending), 1)

        legacy = foundation_event_profile.event_profile(core_sha256=XP1_CORE_SHA256)
        self.assertNotIn(codec.EVENT_KIND, legacy.record_types_by_kind)
        self.assertNotIn(transfer.KIND, legacy.record_types_by_kind)
        with patch('civ6_host.runtime.foundation_facade_profiles.verify_xp1_once'):
            a0_foundation_events.enable(owner, backend)
        self.assertTrue(owner.handles_kind(codec.EVENT_KIND))
        with (patch.object(SavedContinuation, 'check', autospec=True),
              patch('civ6_host.runtime.xp1_visibility_cache_gate.require_internal_cache',
                    return_value={'callback_gate_enabled': True}),
              patch('civ6_host.runtime.native.native_event_07c83dae.plot_snapshot', native_plot)):
            self.assertEqual(arguments.dispatch(h.pointer, codec.EVENT_KIND, 0x9000), 0)
            record, = deferred.pending
            self.assertEqual(struct.unpack_from('<III', record), (160, 220, 1))
            self.assertEqual(struct.unpack_from('<HHI', record, 96), (0, 2, 44))
            self.assertEqual(record[144:152], payloads[component])
            self.assertEqual(deferred.drain(), 1)
            self.assertEqual(deferred.pending, [])
            great_work_fields = reader.fields.return_value
            self.assertEqual(calls, ['borrow', 'release'])
            self.assertEqual((owner._foundation_borrow, deferred.pending), (None, []))
            self.assertTrue(owner.handles_kind(transfer.KIND))
            payloads[component] = struct.pack('<HHI', 0, 2, 131073)
            reader.fields.return_value = {
                transfer.SELECTOR: scalar(3, 0),
                transfer.CITY: struct.pack('<H6xQII', 1024, component, 8, 0x21000001),
                transfer.PRIOR_OWNER: scalar(2, 1),
                transfer.TRANSFER: scalar(2, 3),
            }
            self.assertEqual(arguments.dispatch(h.pointer, transfer.KIND, 0x9000), 0)
            record, = deferred.pending
            self.assertEqual(struct.unpack_from('<III', record), (112, 115, 2))
            self.assertEqual(struct.unpack_from('<HHIII', record, 88), (0, 2, 131073, 1, 3))
            self.assertEqual(deferred.drain(), 1)
            self.assertEqual((owner._foundation_borrow, deferred.pending), (None, []))
            reader.fields.return_value = {
                building.SELECTOR: scalar(3, 0),
                building.POSITION: struct.pack('<H6xQII', 0, position, 8, 0x21000001),
                building.VALUE: scalar(2, 17),
            }
            with patch.object(building, 'plot_snapshot', building_plot):
                self.assertEqual(arguments.dispatch(h.pointer, building.KIND, 0x9000), 0)
            self.assertEqual(struct.unpack_from('<III', deferred.pending[0]), (128, 168, 3))
            self.assertEqual(deferred.drain(), 1)
            for sequence, active, record_type in ((4, 0, 272), (5, 1, 273)):
                reader.fields.return_value = {
                    player.SELECTOR: scalar(3, 0), player.AVAILABLE: scalar(1, active),
                    player.PLAYER: scalar(2, 1),
                }
                self.assertEqual(arguments.dispatch(h.pointer, player.KIND, 0x9000), 0)
                self.assertEqual(struct.unpack_from('<III', deferred.pending[0]),
                                 (96, record_type, sequence))
                self.assertEqual(struct.unpack_from('<II', deferred.pending[0], 80), (sequence, 1))
                self.assertEqual(deferred.drain(), 1)
            payloads[component] = struct.pack('<HHI', 0, 2, 1)
            with self.assertRaisesRegex(ValueError, 'component type differs'):
                owner.dispatch(codec.EVENT_KIND, great_work_fields, 0)
            self.assertEqual(calls, ['borrow', 'release'])
            self.assertEqual((owner._foundation_borrow, deferred.pending), (None, []))

    def test_scalar_families_through_service_preserve_bits_sequence_and_cleanup(self):
        from qualify_xp1_configuration import a0_scalar_cases
        h,d,a,c,r,before,bindings=self.fixture();cases,excluded=a0_scalar_cases(self.profile)
        for seq,row in enumerate(cases,1):
            self.assertEqual(self.send(h,a,r,row['kind'],row['values']),0)
            record=d.pending[-1]
            self.assertEqual(struct.unpack_from('<III',record),(96,row['record_type'],seq))
            self.assertEqual(struct.unpack_from('<I',record,84)[0],row['values'][0])
            if row['boolean']:self.assertEqual(record[88],1)
            elif row['family'] in ('integer','two_values','two_values_missing_second'):
                self.assertEqual(struct.unpack_from('<I',record,88)[0],row['values'][1] if len(row['values'])==2 else 0)
        digest=hashlib.sha256(b''.join(d.pending)).hexdigest()
        self.assertEqual(d.drain(),len(cases));self.assertEqual(d.consumed_digest.hexdigest(),digest)
        self.assertEqual(a.count,len(cases));self.assertEqual(d.pending,[])
        a.close();self.assertTrue(c.closed);r.close.assert_called_once();d.close()
        self.assertEqual(list(h.vtable),before);self.assertEqual(h._slot_bindings,bindings)

    def test_pointer_payload_is_copied_synchronously_then_consumed_without_rereading(self):
        h,d,a,c,r,_,_=self.fixture();memory=bytearray(struct.pack('<HHI',3,0xBEEF,0x20001))
        r.read.side_effect=lambda addr,n:bytes(memory[:n])
        from civ6_host.runtime.native.native_simple_unit_aliases import UNIT_KEY
        r.fields.return_value={0xA1E5A149:scalar(3,0x12345678),
            UNIT_KEY:struct.pack('<H6xQII',0x400,0x9000,8,0x21000001)}
        self.assertEqual(a.dispatch(h.pointer,0x35C46E9E,0x8000),0)
        expected=d.pending[0];memory[:]=b'\xff'*len(memory)
        self.assertEqual(struct.unpack_from('<HHI',expected,88),(3,1,0x20001))
        self.assertEqual(d.drain(),1);r.read.assert_called_once_with(0x9000,8)
        a.close();d.close()

    def test_pre_turn_immediate_and_deferred_delivery_have_distinct_lifetimes(self):
        h,d,a,c,r,_,_=self.fixture()
        self.assertEqual(self.send(h,a,r,0x1E39E493,(17,)),0)
        self.assertEqual(len(d.pending),1);self.assertEqual(d.consumed_count,0)
        c.emit.assert_any_call('native_pre_turn_immediate_empty_dispatch',turn=17,handler_rva='0xefd90',
            subscriber_count=0,original_exe_listeners_captured=False,native_profiling_reproduced=False,eligible_for_training=False)
        self.assertEqual(d.drain(),1);a.close();d.close()

    def test_native_query_and_new_product_key_refuse_before_memory_or_enqueue(self):
        for kind in (0x8953F126,0x45B517D6):
            h,d,a,c,r,_,_=self.fixture()
            self.assertFalse(c.handles_kind(kind))
            with self.assertRaises(ValueError):c.dispatch(kind,{},None)
            r.read.assert_not_called();self.assertEqual(d.pending,[])

    def test_nonzero_scopes_and_changed_registration_fail_without_reset(self):
        for name,value in (('host_notification_counter',1),('host_metadata_counter',1)):
            h,d,a,c,r,_,_=self.fixture();setattr(d,name,value)
            with self.assertRaises(ValueError):self.send(h,a,r,0x52E2805C,(1,1))
            self.assertTrue(a.quarantined);self.assertEqual(getattr(d,name),value);self.assertEqual(d.pending,[])
        for name,value in (('entity_listener_count',1),('dynamic_event_registration_present',True),
                           ('normalizer_transform_present',True)):
            h,d,a,c,r,_,_=self.fixture();setattr(c,name,value)
            with self.assertRaises(RuntimeError):self.send(h,a,r,0x52E2805C,(1,1))
            self.assertTrue(a.quarantined);self.assertEqual(d.pending,[])

    def test_receiver_change_invalid_envelope_and_queue_bound_do_not_publish(self):
        for fault in ('receiver','envelope','queue'):
            h,d,a,c,r,_,_=self.fixture()
            if fault=='receiver':c.empty_receiver_state['subscriber_count']=1
            if fault=='queue':d.limit=0
            r.fields.return_value={0xA1E5A149:scalar(3,1 if fault=='envelope' else 0),
                0xD6FCF3E4:scalar(2,1),0xA1FBC372:scalar(2,1)}
            with self.assertRaises((ValueError,RuntimeError)):a.dispatch(h.pointer,0x52E2805C,0x9000)
            self.assertEqual(d.pending,[]);self.assertTrue(a.quarantined)

    def test_uncertain_consumer_failure_poison_prevents_replay(self):
        h,d,a,c,r,_,_=self.fixture();self.send(h,a,r,0x52E2805C,(1,1))
        d.emit.side_effect=OSError('receipt sink failed after commit')
        with self.assertRaises(OSError):d.drain()
        self.assertEqual(d.consumed_count,1);self.assertEqual(d.pending,[])
        with self.assertRaisesRegex(RuntimeError,'poisoned'):d.drain()
        self.assertEqual(d.emit.call_count,1)

    def test_borrowers_and_open_queue_prevent_teardown(self):
        h,d,a,c,r,_,_=self.fixture();self.send(h,a,r,0x52E2805C,(1,1))
        with self.assertRaises(RuntimeError):a.close()
        self.assertFalse(c.closed);r.close.assert_not_called()
        d.drain()
        with self.assertRaisesRegex(RuntimeError,'borrows'):d.close()
        a.close();d.close()

    def test_detached_close_preserves_borrower_checks_without_querying_freed_context(self):
        from civ6_host.runtime.xp1_loaded_lifetime import LoadedLifetime
        h,d,a,c,r,_,_=self.fixture()
        player=NS(check=Mock(side_effect=AssertionError('freed context read')),_a0_event_owner=c)
        c.player_query_owner=player
        with self.assertRaisesRegex(AssertionError,'freed context'):c.close()
        player.check.reset_mock()
        token=LoadedLifetime.__new__(LoadedLifetime)
        token.check_a0_owner=Mock();token.check_a0_release=Mock()
        a.close(loaded_lifetime=token)
        token.check_a0_owner.assert_called_once_with(c)
        token.check_a0_release.assert_called_once_with(c)
        player.check.assert_not_called()
        self.assertIsNone(player._a0_event_owner);self.assertTrue(c.closed)
        r.close.assert_called_once()

    def test_extracted_embarked_helper_keeps_historical_record_and_poison_rules(self):
        from civ6_host.runtime.native import native_event_84c1fdd6 as event
        # Reuse the pinned witness as data. A worker may already have enabled
        # the installed-host boundary; never execute private lab Python here.
        proof=event.verify_source_evidence()
        fields={int(k,16):bytes.fromhex(v) for k,v in proof['witness']['fields'].items()}
        unit=struct.unpack_from('<Q',fields[event.UNIT_KEY],8)[0]
        memory={unit:bytes.fromhex(proof['witness']['f054_pointer_bytes'])}
        def read(pointer,size):
            if pointer not in memory:raise AssertionError('unexpected native-memory read')
            return memory[pointer][:size]
        h,d,a,c,r,_,_=self.fixture()
        r.fields.return_value=fields;r.read.side_effect=read
        self.assertEqual(a.dispatch(h.pointer,event.EVENT_KIND,0x8000),0)
        self.assertFalse(c._84c1fdd6_poisoned);self.assertEqual(d.drain(),1)
        a.close();d.close()
        h,d,a,c,r,_,_=self.fixture();r.fields.return_value=fields;r.read.side_effect=OSError('borrow expired')
        with self.assertRaises(OSError):a.dispatch(h.pointer,event.EVENT_KIND,0x8000)
        self.assertTrue(c._84c1fdd6_poisoned);self.assertFalse(c._84c1fdd6_producing)
        self.assertTrue(c.quarantined);self.assertTrue(a.quarantined)


def load_tests(loader,tests,pattern):
    for name in ('test_native_host_events','test_native_unary_event_family','test_native_two_value_event_family',
                 'test_native_two_value_missing_b','test_native_scalar_no_metadata_family','test_native_event_84c1fdd6'):
        tests.addTests(loader.loadTestsFromModule(retained_module(name)))
    return tests
