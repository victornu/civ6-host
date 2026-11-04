"""XP2 notification source and shared algorithms; no GameCore execution."""
import ctypes as C
import ast,inspect
from contextlib import contextmanager
from pathlib import Path
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from civ6_host.runtime import turn_unit_event_profile as turn
from civ6_host.runtime import xp1_private_notification_profile as private
from civ6_host.runtime import xp2_turn_notification_source as source
from civ6_host.runtime import a0_private_notifications as private_events
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256,configuration_abi
from test_xp1_turn_units import Memory
import test_xp1_private_notifications as private_tests
from civ6_host.runtime.native import native_event_6e7ef927 as complete
from civ6_host.runtime.native import native_unit_created_event as created


def source_memory():
    values={}
    memory=NS(base=0x10000000)
    memory.put=lambda address,data:values.update({address+i:b for i,b in enumerate(data)})
    memory.read=lambda address,size:bytes(values[address+i] for i in range(size))
    for table,slots in source.TABLES.values():
        for slot,rva in slots.items():memory.put(memory.base+table+slot,struct.pack('<Q',memory.base+rva))
    for b in source.bodies():
        for f in b['fragments']:memory.put(memory.base+int(f['start_rva'],16),bytes.fromhex(f['raw_hex']))
    return memory


class XP2SourceTests(unittest.TestCase):
    def test_full_cfg_source_slots_and_canonical_selection(self):
        p=source.source();self.assertEqual((len(p['functions']),p['validation']['total_bytes']),(186,37453))
        self.assertIn(source.SOURCE[1],source.source_dependencies().values())
        m=source_memory();receipt=source.verify_live(m.base,m.read)
        self.assertEqual(receipt['core_sha256'],XP2_CORE_SHA256)
        self.assertFalse(receipt['native_execution'])
        self.assertEqual(turn.unit_live_offset(XP2_CORE_SHA256),16)
        self.assertEqual(turn.unit_live_offset(XP1_CORE_SHA256),8)
        self.assertEqual(turn.select_tables(XP2_CORE_SHA256,complete._TABLES)['unit'][0],0xA128E8)
        self.assertEqual(turn.event_profile(core_sha256=XP2_CORE_SHA256).source_sha256,source.SOURCE[1])
        # The component's distant conditional successor after its NULL return
        # must be present in the live source guard, not a first-RET window.
        address=m.base+0x4BA50;old=m.read(address,8);m.put(address,bytes([old[0]^1])+old[1:])
        with self.assertRaisesRegex(ValueError,'code differs'):source.verify_live(m.base,m.read)
        m.put(address,old);m.put(m.base+0xA128E8+0xB8,b'\0'*8)
        with self.assertRaisesRegex(ValueError,'vtable'):source.verify_live(m.base,m.read)
        with self.assertRaises(ValueError):turn.select_tables('unknown',complete._TABLES)

    def test_native_signatures_and_selected_strings_preserve_shared_algorithm(self):
        calls=[]
        def factory(result,*args):return lambda target:calls.append((target,result,args)) or (lambda *a:None)
        with patch.object(C,'WINFUNCTYPE',factory):api=complete._api(0x10000000,None,core_sha256=XP2_CORE_SHA256)
        expected={n:source.SNAPSHOT[n] if n.startswith('string_') else source.TABLES[turn.OPERATIONS[n][0]][1][turn.OPERATIONS[n][1]] for n in api}
        self.assertEqual([a for a,_,_ in calls],[0x10000000+expected[n] for n in api])
        self.assertEqual(calls[list(api).index('release_unit')][1:],(C.c_void_p,(C.c_void_p,C.c_uint32)))
        self.assertEqual(calls[list(api).index('unit_snapshot')][1:],(None,(C.c_void_p,C.c_void_p,C.c_uint32)))

    def test_snapshot_live_offset_guard_buffer_and_release_order(self):
        m=Memory(turn.select_tables(XP2_CORE_SHA256,complete._TABLES));o=m.objects;calls=[]
        m.put(o['unit']+8,b'\0'*8);m.put(o['unit']+16,(0x1234).to_bytes(8,'little'))
        def snapshot(unit,address,flags):
            calls.append('snapshot');self.assertEqual((unit,flags),(o['unit'],0))
            C.memmove(address+28,struct.pack('<I',998),4);C.memmove(address+16,struct.pack('<Q',0x710008),8)
        api=dict(get_player=lambda *a:o['player'],release_player=lambda *a:calls.append('player'),player_units=lambda *a:o['units'],release_units=lambda *a:calls.append('units'),units_index=lambda *a:o['unit'],release_unit=lambda *a:calls.append(('unit',a)),unit_snapshot=snapshot,string_empty=lambda:0x700008,string_free=lambda p:calls.append(('free',p)))
        fields=complete.EventFields(0,struct.pack('<HHI',1,1,9),1,9,struct.pack('<ii',3,4))
        options=dict(normalizer_transform_present=False,per_thread_hook_present=False,writer_metadata_callback_present=False,read=m.read,native_api=api,core_sha256=XP2_CORE_SHA256)
        with complete.produce_record_lease(1,NS(_handle=m.base),o['outer'],fields,**options) as record:
            self.assertEqual(struct.unpack_from('<I',record,112)[0],998)
            self.assertEqual(calls,['units','player','snapshot',('free',0x710000)])
        self.assertEqual(calls[-1],('unit',(o['unit'],1)));self.assertNotIn((o['unit']+8,8),m.reads)
        m.put(o['unit']+16,b'\0'*8);calls.clear()
        with self.assertRaisesRegex(ValueError,'live Unit'):
            with complete.produce_record_lease(2,NS(_handle=m.base),o['outer'],fields,**options):pass
        self.assertEqual(calls,['units','player',('unit',(o['unit'],1))])


class XP2PrivateTests(private_tests.PrivateNotificationTests):
    """Replay the existing real A0/FIFO/ring cases with exact XP2 code guards."""
    def fixture(self):
        f=private_tests.fixture.Fixture();f.deferred.cache_core_sha256=XP2_CORE_SHA256
        m=source_memory();f.deferred.core._handle=m.base
        f.owner.read=m.read
        private_events.enable(f.owner)
        f.owner.read=f.read
        self.assertEqual(f.owner.private_notification_profile.source_sha256,source.SOURCE[1])
        return f

    def test_source_closure_and_relocated_producer_bytes(self):
        m=source_memory();r=private.verify_live(m.base,m.read,core_sha256=XP2_CORE_SHA256)
        self.assertEqual(r['source_sha256'],source.SOURCE[1])
        self.assertIn(source.SOURCE[1],private.source_dependencies(core_sha256=XP2_CORE_SHA256).values())
        f=self.fixture();f.deferred.cache_core_sha256=XP1_CORE_SHA256
        with self.assertRaisesRegex(ValueError,'lifetime changed'):private_events.get_ring(f.owner)


@contextmanager
def pending_civilization_render():
    """Run the exact changed extraction chain in memory until root regenerates."""
    from civ6_host.runtime.native import native_event_fa5b1159 as original
    from civ6_host.runtime.native import native_event_a625c726 as improvement
    if XP2_CORE_SHA256 in inspect.getsource(original.read_player_civilization_type_id):
        yield
        return
    from civ6_host.runtime.paths import resource_root
    from extraction_foundation_facades import transform as facades
    from extraction_foundation_queries import transform as queries
    from extraction_civilization_getter import transform as civilization
    name='civ6rl.native_event_fa5b1159'
    raw=(resource_root()/'civ6rl/native_event_fa5b1159.py').read_text()
    rendered=civilization(name,queries(name,facades(name,raw)))
    fn=next(n for n in ast.parse(rendered).body if isinstance(n,ast.FunctionDef) and n.name=='read_player_civilization_type_id')
    namespace=dict(vars(original))
    exec(compile(ast.Module(body=[fn],type_ignores=[]),'<exact pending civilization extraction>','exec'),namespace)
    # The shared function itself runs, including its real configuration owner,
    # player map, native getter code and repeated-read checks.
    with patch.object(improvement,'read_player_civilization_type_id',namespace[fn.name]):yield


class XP2ComposedNotifications(unittest.TestCase):
    def test_queue_notifications_use_the_existing_xp2_owner_and_fifo(self):
        from test_xp1_turn_a0 import scalar
        from civ6_host.runtime.native import native_event_92492f56 as queue_event
        from civ6_host.runtime.native import native_event_2842ce14 as head_event
        g=self.graph();address=0xA10000
        g.memory.put(address,struct.pack('<HHI',0,2,5))
        descriptor=struct.pack('<H6xQII',1024,address,8,553648129)
        fields={queue_event.SELECTOR_KEY:scalar(3,0),queue_event.DESCRIPTOR_KEY:descriptor,
            queue_event.D6_KEY:scalar(2,101),queue_event.A1FBC_KEY:scalar(2,0)}
        for event in (queue_event,head_event):
            self.assertEqual(g.owner.dispatch(event.EVENT_KIND,fields,0),0)
        self.assertEqual([struct.unpack_from('<I',r,4)[0] for r in g.event.deferred.pending],[98,95])
        for record in g.event.deferred.pending:
            self.assertEqual(len(record),112)
            self.assertEqual(struct.unpack_from('<HHIII',record,88),(0,2,5,101,0))
        self.assertEqual(g.event.deferred.drain(),2)
        self.assertEqual(g.event.deferred.pending,[])
        self.assertEqual(g.event.deferred.consumed_count,2)
        g.owner.close()

    def graph(self):
        import threading
        from civ6_host.runtime import a0_family_source,a0_foundation_events as events
        from civ6_host.runtime.a0_family_service import A0FamilyService
        from civ6_host.runtime.loaded_cache_publication import LoadedCachePublication
        from civ6_host.runtime.native.native_ui_cache_backend import NativeCacheFacadeBackend
        from civ6_host.runtime.native.native_player_view import NativePlayerViewPublisher
        from civ6_host.runtime.native import native_application_configuration as app_module
        from civ6_host.runtime import xp1_load_capability as capability
        from civ6_host.runtime.xp2_bundle_inputs import REFERENCE
        from civ6_host.runtime.xp1_continuation import SavedContinuation,ACTIVE
        from civ6_host.runtime.native.native_episode_identity import initialize_episode
        from test_xp2_cache_publication import XP2CacheTests
        private_tests.fixture.PROFILE=a0_family_source.family_profile()
        event=private_tests.fixture.Fixture()
        f,a,_=XP2CacheTests().graph();b=a.owner;p=b.prefix;h=b.host;d=event.deferred;args=event.arguments
        from civ6_host.runtime.foundation_event_profile import project_core_fragments, pillage_source
        for rva, raw in project_core_fragments():
            f.put(f.core_base + rva, raw)
        for rva, body in pillage_source()['core_producer'].items():
            f.put(f.core_base + int(rva, 16), bytes.fromhex(body['raw_hex']))
        d.host=args.host=h;d.core=b.core;d.context=b.context;d.cache_core_sha256=XP2_CORE_SHA256
        h._deferred_service_owner=d;h._event_argument_owner=args;h._a0_family_owner=event.owner
        for slot,value in d.addresses.items():h.vtable[slot//8]=value
        h.vtable[0xA0//8]=args.address
        p.deferred_events=d;p.event_arguments=args;event.host=h
        event.owner.read=args.reader.read=f.read;event.owner.arguments=args
        for body in source.bodies():
            for frag in body['fragments']:f.put(f.core_base+int(frag['start_rva'],16),bytes.fromhex(frag['raw_hex']))
        for table,slots in source.TABLES.values():
            for slot,rva in slots.items():f.q(f.core_base+table+slot,f.core_base+rva)
        objects={n:0x800000+0x1000*i for i,n in enumerate(source.TABLES)};objects['outer']=b.context
        for n,ptr in objects.items():f.q(ptr,f.core_base+source.TABLES[n][0])
        f.q(objects['unit']+16,0xAABBCC);f.q(objects['data']+8,f.core_base+0xA10CA8)
        for addr,value in ((0x600000,b'UNIT_A\0'),(0x600100,b'UNIT_B\0'),(0x600200,b'CIV_A\0')):f.put(addr,value)
        app=app_module.NativeApplicationConfiguration.__new__(app_module.NativeApplicationConfiguration)
        app.storage=C.create_string_buffer(app_module._GUARD+b'\0'*app_module.STORAGE_SIZE+app_module._GUARD,app_module.STORAGE_SIZE+32)
        app.closed=False;app.base=f.core_base;app.context=b.context;app.pointer=0x910000
        app._configuration_abi=configuration_abi(XP2_CORE_SHA256);app.read=f.read;app.emit=event.emit
        b.owner=app;h.application_configuration=app;b.core._civ6rl_application_configuration=app
        b.profile=NS(core_sha256=XP2_CORE_SHA256);b._saved_load_candidate=True
        b.captured_bundle=NS(inputs=b.inputs,reference=REFERENCE)
        abi=app._configuration_abi;table=f.core_base+abi.vtable_rva
        for address,value in ((app.pointer,table),(table+0x58,f.core_base+abi.lookup_rva),(table+0x68,f.core_base+0x99F680),(0x930000,table),(0x950000,table)):f.q(address,value)
        f.put(f.core_base+abi.root_key_rva,struct.pack('<I',0x871D5B63));f.put(f.core_base+0xB8C44C,struct.pack('<I',0x0623E593))
        f.put(0x920000,struct.pack('<H6xQ4xI',10,0x930000,0x05000000))
        f.put(0x940000,struct.pack('<H6xQ4xI',2,0x0138409A,0))
        f.put(0x960000,struct.pack('<H6xQ4xI',10,0x950000,0x05000000))
        f.put(0x970000,struct.pack('<H6xQ4xI',2,777,0))
        keys=app_module.verify_source(core_sha256=XP2_CORE_SHA256)['player_keys']
        f.put(f.core_base+abi.player_key_table_rva+68,struct.pack('<I',keys[1]['hash']))
        from civ6_host.runtime.application_mirror_profiles import civilization_source
        for frag in civilization_source(XP2_CORE_SHA256)['core_functions']['value_getter']['fragments']:
            for row in frag['instructions']:f.put(f.core_base+int(row['va'],16)-0x180000000,bytes.fromhex(row['bytes']))
        config_calls=[]
        def app_call(address,*arguments):
            key=arguments[-1];config_calls.append((address-f.core_base,key))
            if address==f.core_base+abi.lookup_rva:return 0x920000 if key==0x871D5B63 else 0x960000
            if address==f.core_base+0x99F680:return 0x940000 if key==0x0623E593 else 0x970000
            raise AssertionError('Unexpected configuration invocation')
        app.call=app_call
        capability._bind_source_receipt(b)
        # Independent family installation binds the actual prepared command
        # backend. No unrelated foundation membership is fabricated.
        b._xp1_commands_requested=True;b.stage='prepared';b.prefix=None
        events.enable_turn_units(event.owner,b);private_events.enable(event.owner)
        b.prefix=p;b.stage='observed-awaiting-post160';b.busy=True
        lease=LoadedCachePublication(a)
        facades=f.acquire();facades._copy_cache_outputs()
        pub=NativePlayerViewPublisher(b.core,b.context,NS(),read=f.read,core_sha256=XP2_CORE_SHA256)
        a.publisher=p.view_publisher=pub
        backend=NativeCacheFacadeBackend(b.core,NS(),context_alive=lambda:True,read=f.read,core_sha256=XP2_CORE_SHA256,publication_owner=lease)
        lease.attach(pub,backend);pub._facades=facades;facades.backend=backend
        pub.cache_map_snapshot=f.output;lease.entered=lease.returned=lease.copied=True
        a.publication_owner=lease;lease.publication_finished=True
        token=SavedContinuation.__new__(SavedContinuation)
        publication=NS(owner=b,lease=lease,completed=True);view=NS(owner=b,publication=publication,completed=True)
        token.owner=b;token.prefix=p;token.runtime=p.runtime;token.lease=lease;token.publisher=pub
        token.publication=publication;token.view=view;token.poisoned=False
        p.ui_child=object();token.ui_child=p.ui_child;token.game_child=p.game_child
        p.actions=NS(backend=b);token.transport=p.actions
        token.identity=initialize_episode(p);b._xp1_continuation=token;lease.continuation=token;pub._xp1_continuation=token
        lease.publication_attempt=publication;b._xp1_player_view=view;b.stage=ACTIVE;b.busy=True
        token.check(active=True)
        calls=[]
        results={('outer',0xB8):objects['player'],('player',0x110):objects['units'],('units',0x10):objects['unit'],('unit',0x28):1,('outer',0x100):objects['data'],('data',0x368):0x600000,('unit',0x50):2,('data',0x260):0x600100,('player',0x18):3,('data',0x308):0x600200,('unit',0x58):9,('unit',0x88):1,('player',0x28):1,('outer',0x90):objects['game'],('game',0x128):1,('outer',0xA8):objects['map'],('map',0x40):objects['plot'],('plot',0x60):objects['component'],('component',0x10):6,('component',0x18):1,('component',0x30):8,('plot',0x30):10,('plot',0xC8):1,('plot',0xC0):2,('plot',0xE0):1,('data',0xC8):12}
        targets={rva:(name,slot) for name,(_,ss) in source.TABLES.items() for slot,rva in ss.items()}
        def factory(result,*types):
            def bind(target):
                rva=target-f.core_base
                def invoke(*values):
                    calls.append((rva,values));pair=targets.get(rva)
                    if rva==source.SNAPSHOT['string_empty']:return 0x700008
                    if rva==source.SNAPSHOT['string_free']:return None
                    if pair==('unit',0xB8):C.memmove(values[1]+28,struct.pack('<I',998),4);return None
                    if pair in (('plot',0x178),('plot',0x180)):
                        raw=bytearray(24)
                        if pair[1]==0x180:struct.pack_into('<h',raw,4,-5)
                        else:struct.pack_into('<I',raw,4,44);raw[20]=2
                        C.memmove(values[1],bytes(raw),24);return 0
                    if pair and (pair[1]==8 and pair[0]!='outer' or pair==('unit',16)):return None
                    if pair in results:return results[pair]
                    raise AssertionError('Unselected native call '+hex(rva))
                return invoke
            return bind
        return NS(memory=f,event=event,owner=event.owner,backend=b,prefix=p,lease=lease,continuation=token,calls=calls,factory=factory,config_calls=config_calls)

    def fields(self,g):
        scalar=private_tests.fixture.scalar
        def blob(tag,address,value):
            g.memory.put(address,value);return struct.pack('<H6xQII',tag,address,8,553648129)
        identity=blob(1024,0xA00000,struct.pack('<HHI',1,1,9))
        position=struct.pack('<ii',3,4)
        common={0xA1E5A149:scalar(3,0)}
        return {
          0xB8515A41:{**common,0xF0548BB7:identity,0x8C468E3C:blob(13,0xA00100,position),0xD6FCF3E4:scalar(2,0),0xA1FBC372:scalar(2,17),0x15808E44:scalar(3,0),0x6E3A8F43:scalar(1,0)},
          0xC50D66D6:{**common,0xF0548BB7:identity,0xD6FCF3E4:struct.pack('<H6xf12x',4,2.5)},
          0x6E7EF927:{**common,0xF0548BB7:identity,0x8C468E3C:blob(0,0xA00200,position)},
          0xA625C726:{**common,0x8C468E3C:blob(0,0xA00300,position),0xD6FCF3E4:scalar(2,99)},
          0xE5B20B82:{**common,0x8C468E3C:blob(0,0xA00400,position),0xD6FCF3E4:scalar(2,99)},
          0x1BE52206:private_tests.fields54(),0x66ADE3B3:private_tests.fields57()}

    def test_all_seven_real_shared_dispatches_same_cache_owner_and_fifo(self):
        from civ6_host.runtime import xp1_load_capability as capability
        g=self.graph()
        from civ6_host.runtime.native.native_host import EventFilterRegistry
        g.backend.host.filters=EventFilterRegistry();g.backend.host.filters.declare(0xC50D66D6,0xF0548BB7,1)
        with pending_civilization_render(),patch.object(C,'WINFUNCTYPE',g.factory),capability.capability_source_scope(g.backend,'continuation'):
            for kind,fields in self.fields(g).items():self.assertEqual(g.owner.dispatch(kind,fields,0),0)
        self.assertEqual([struct.unpack_from('<I',r,4)[0] for r in g.event.deferred.pending],[28,25,24,148,143,5])
        self.assertEqual(g.owner.entity_event_count,1)
        self.assertEqual(g.owner.private_progress_ring.cursors,(256,0))
        self.assertIsNone(g.owner._foundation_borrow)
        self.assertTrue(any(rva==0x5934E0 for rva,_ in g.calls))
        self.assertTrue(any(key==0x0623E593 for _,key in g.config_calls))
        self.assertTrue(any(key==3352777051 for _,key in g.config_calls))
        self.assertEqual(g.event.deferred.drain(),6)
        self.assertEqual(g.owner.private_progress_ring.selector,1)
        self.assertFalse(g.lease.publisher.native_cache_gate)

    def test_cache_or_continuation_identity_refuses_before_native_queries(self):
        g=self.graph();fields=self.fields(g)[0x6E7EF927]
        g.memory.put(g.memory.owner+0x38,b'\0')
        with patch.object(C,'WINFUNCTYPE',g.factory),self.assertRaises((ValueError,RuntimeError)):
            g.owner.dispatch(0x6E7EF927,fields,0)
        self.assertEqual(g.calls,[]);self.assertEqual(g.event.deferred.pending,[])
        self.assertTrue(g.owner.quarantined);self.assertIsNone(g.owner._foundation_borrow)

    def test_missing_created_variant_and_wrong_entity_filter_remain_refused(self):
        from civ6_host.runtime.native.native_host import EventFilterRegistry
        for kind in (0xB8515A41,0xC50D66D6):
            with self.subTest(kind=hex(kind)):
                g=self.graph();fields=self.fields(g)[kind]
                g.backend.host.filters=EventFilterRegistry()
                if kind==0xB8515A41:
                    fields={k:v for k,v in fields.items() if k in (0xA1E5A149,0xF0548BB7,0x8C468E3C,0xD6FCF3E4)}
                else:g.backend.host.filters.declare(kind,0xF0548BB7,2)
                with patch.object(C,'WINFUNCTYPE',g.factory),self.assertRaises(ValueError):g.owner.dispatch(kind,fields,0)
                self.assertEqual(g.calls,[]);self.assertEqual(g.event.deferred.pending,[])
                self.assertTrue(g.owner.quarantined)


if __name__=='__main__':unittest.main()
