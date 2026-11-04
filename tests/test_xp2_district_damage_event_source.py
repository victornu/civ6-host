"""District source and actual XP2 A0/FIFO graph, with native calls replaced."""
import ast
from contextlib import ExitStack,contextmanager
import ctypes as C
import inspect,json,struct
import unittest
from unittest.mock import patch

from civ6_host.runtime import xp2_district_damage_event_source as source
from civ6_host.runtime import district_damage_profile as selected
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.native import native_event_f74afc79 as damage,native_event_47261a7d as combat
import test_xp2_improvement_event_source as previous


@contextmanager
def pending_render():
    """Use the unique source hook in memory until root's global extraction."""
    from extraction_xp1_district_damage import parameterize
    with ExitStack() as stack:
        for module in (damage,combat):
            if 'verify_once(core, read, core_sha256=core_sha256)' in inspect.getsource(module.produce_record_lease):continue
            name=module.__name__.rsplit('.',1)[-1]
            raw=(resource_root()/'civ6rl'/f'{name}.py').read_text()
            rendered=parameterize(name,raw)
            fn=next(n for n in ast.parse(rendered).body if isinstance(n,ast.FunctionDef) and n.name=='produce_record_lease')
            calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call) and ast.unparse(n.func)=='_district_source.verify_once']
            assert len(calls)==1 and [(k.arg,ast.unparse(k.value)) for k in calls[0].keywords]==[('core_sha256','core_sha256')]
            namespace=dict(vars(module))
            exec(compile(ast.Module(body=[fn],type_ignores=[]),'<exact pending district extraction>','exec'),namespace)
            stack.enter_context(patch.object(module,fn.name,namespace[fn.name]))
        yield


def fields(g,kind):
    scalar=lambda tag,value:struct.pack('<IIQII',tag,0,value,0,0)
    def blob(address,owner,tag,index):
        g.memory.put(address,struct.pack('<HHI',owner,tag,index))
        return struct.pack('<IIQII',1024,0,address,8,0x21000001)
    values={0xa1e5a149:scalar(3,0x5e97d629 if kind==damage.EVENT_KIND else combat.SELECTOR),
            0xf343dc5a:blob(0xa31000,0,3,13)}
    if kind==damage.EVENT_KIND:values.update({0xd6fcf3e4:scalar(2,27),0xa1fbc372:scalar(2,0)})
    if kind==source.SIBLING_KIND:
        values[0xa1e5a149]=scalar(3,0);values[0xf0548bb7]=blob(0xa32000,1,1,19)
    return values


class DistrictSourceTests(unittest.TestCase):
    def test_exact_source_and_independent_exe_slot_authority(self):
        p=source.source()
        self.assertEqual(len(p['functions']),32)
        self.assertFalse(p['contract']['omission_admitted'])
        self.assertEqual(set(source.event_profile().record_types_by_kind),{0xf74afc79,0x47261a7d})
        self.assertIn(source.SOURCE[1],source.source_dependencies().values())
        self.assertEqual(p['query_operations']['district_hash']['slot'],0x58)
        self.assertEqual(p['query_operations']['district_position']['slot'],0x38)
        self.assertEqual(p['families']['0x754cbd1b']['normalized_second_unit'],(65535,1,4294967295))
        for mutation in (
            lambda p:p['query_operations']['district_type'].__setitem__('slot',0x30),
            lambda p:p['families']['0xf74afc79']['fields'].__setitem__('0xa1e5a149',2),
            lambda p:p['families']['0x47261a7d'].__setitem__('record_type',159),
            lambda p:p['families']['0x754cbd1b'].__setitem__('normalized_second_unit',[0,1,0]),
            lambda p:p['contract'].__setitem__('omission_admitted',True),
        ):
            doc=json.loads((resource_root()/source.SOURCE[0]).read_text());mutation(doc)
            with self.assertRaises(ValueError):source._verify(doc)

    def test_typed_field_decoding_retains_actual_scalar_and_descriptor_domains(self):
        memory={}
        class Memory:
            def put(self,p,b):memory[p]=b
            def read(self,p,n):return memory[p][:n]
        from types import SimpleNamespace
        g=SimpleNamespace(memory=Memory())
        for kind in source.CALLBACKS:
            raw=fields(g,kind);decoded=source.decode_fields(kind,raw,g.memory.read)
            self.assertEqual(decoded.district_id if kind==source.SIBLING_KIND else decoded.item_id,13)
            for key in raw:
                bad=dict(raw);value=bytearray(bad[key]);value[0]=2 if key==0xa1e5a149 else 3;bad[key]=bytes(value)
                with self.assertRaises(ValueError):source.decode_fields(kind,bad,g.memory.read)
        raw=fields(g,combat.EVENT_KIND);raw[0xa1e5a149]=struct.pack('<IIQII',3,0,0,0,0)
        with self.assertRaisesRegex(ValueError,'selector'):source.decode_fields(combat.EVENT_KIND,raw,g.memory.read)
        raw=fields(g,damage.EVENT_KIND);raw[0xa1e5a149]=struct.pack('<IIQII',3,0,0xffffffff,0,0)
        self.assertEqual(source.decode_fields(damage.EVENT_KIND,raw,g.memory.read).selector,0xffffffff)


class DistrictComposedTests(unittest.TestCase):
    def graph(self):
        g=previous.ImprovementQueriesTests.graph(self)
        from civ6_host.runtime.foundation_facade_profiles import query_abi
        abi=query_abi(XP2_CORE_SHA256,resource_root())
        g.objects.update(district_collection=0xb10000,district=0xb20000)
        for name in ('district_collection','district'):g.memory.q(g.objects[name],g.memory.core_base+abi.table(name))
        g.memory.q(g.objects['district']+8,0xb21000)
        from civ6_host.runtime.event_argument_service import EventArgumentReader
        from civ6_host.runtime.event_argument_source import reader_abi
        reader_layout=reader_abi(XP2_CORE_SHA256)
        g.memory.q(g.memory.core_base+reader_layout.vtable_rva+0x1d8,g.memory.core_base+reader_layout.count_rva)
        def no_native_successor(*args):raise AssertionError('No native iterator is executed by the copied-field fixture')
        with patch.object(C,'WINFUNCTYPE',lambda *types:lambda address:no_native_successor):
            g.event.arguments.reader=EventArgumentReader(g.backend.core,core_sha256=XP2_CORE_SHA256,read=g.owner.read)
        self.addCleanup(g.event.arguments.reader.close)
        for rva,raw in source.core_fragments():g.memory.put(g.memory.core_base+rva,raw)
        self.assertIs(source.bind_owner(g.backend,g.backend.core,g.owner.read),source.event_profile())
        g.live.update(district_collection=0,district=0)
        g.missing=None;g.failure=None;g.district_calls=[]
        old_factory=g.factory
        targets={g.memory.core_base+abi.rva(operation):name for name,operation in selected.OPERATIONS.items()}
        def factory(result,*types):
            fallback=old_factory(result,*types)
            def bind(target):
                name=targets.get(target)
                if name is None:return fallback(target)
                def invoke(pointer,*args):
                    g.district_calls.append((name,pointer,*args))
                    if name==g.failure:raise RuntimeError('fixture district query failed')
                    if name in ('get_player','player_collection','collection_index'):
                        label={'get_player':'player','player_collection':'district_collection','collection_index':'district'}[name]
                        if g.missing==label:return 0
                        g.live[label]+=1;return g.objects[label]
                    if name.startswith('release_'):
                        label={'release_player':'player','release_collection':'district_collection','release_item':'district'}[name]
                        self.assertEqual(pointer,g.objects[label]);self.assertEqual(g.live[label],1);g.live[label]-=1;return None
                    self.assertEqual(pointer,g.objects['district']);self.assertEqual(g.live['district'],1)
                    if name in ('item_variant','item_position'):
                        out=args[0];raw=struct.pack('<HHI',0,2,65536) if name=='item_variant' else struct.pack('<ii',3,4)
                        C.memmove(out,raw,8)
                        if g.failure=='canary':C.memset(out+8,0,1)
                        return out+1 if g.failure=='return' else out
                    if name=='item_raw':return 13
                    if name=='item_hash':self.assertEqual(args,(0x5e97d629,));return 0xaabbccdd
                    raise AssertionError(name)
                return invoke
            return bind
        g.factory=factory
        from civ6_host.runtime import a0_foundation_events as foundation,a0_district_damage as admission
        b=g.backend;stage,prefix=b.stage,b.prefix;b.stage='prepared';b.prefix=None
        try:foundation.enable(g.owner,b);admission.enable(g.owner,b)
        finally:b.stage=stage;b.prefix=prefix
        self.assertIs(g.owner.district_damage_profile,source.event_profile())
        return g

    def dispatch(self,g,kind):
        with pending_render(),patch.object(C,'WINFUNCTYPE',g.factory):return g.owner.dispatch(kind,fields(g,kind),0)

    def test_three_actual_branches_share_fifo_and_hold_item_until_append(self):
        g=self.graph();seen=[];original=g.event.deferred._enqueue
        def enqueue(record):seen.append((struct.unpack_from('<I',record,4)[0],dict(g.live)));return original(record)
        with patch.object(g.event.deferred,'_enqueue',side_effect=enqueue):
            for kind in (source.SIBLING_KIND,damage.EVENT_KIND,combat.EVENT_KIND):self.assertEqual(self.dispatch(g,kind),0)
        self.assertEqual([r for r,_ in seen],[30,159,161])
        for record,live in seen:
            self.assertEqual(live['district'],int(record!=30));self.assertEqual(live['player'],0);self.assertEqual(live['district_collection'],0)
        sibling,first,second=g.event.deferred.pending
        self.assertEqual(struct.unpack_from('<HHI',sibling,96),(65535,1,0xffffffff))
        self.assertEqual(struct.unpack_from('<iiI',first,96),(3,4,13))
        self.assertEqual(struct.unpack_from('<IIII',first,120),(0x5e97d629,27,0,0xaabbccdd))
        self.assertEqual(struct.unpack_from('<I',second,112)[0],13)
        self.assertFalse(any(g.live.values()));self.assertIsNone(g.owner._foundation_borrow)
        self.assertEqual(g.event.deferred.drain(),3)
        self.assertEqual(g.event.deferred.consumed_count,3)

    def test_actual_null_lookup_preserves_sentinels_without_invented_queries(self):
        for kind in (damage.EVENT_KIND,combat.EVENT_KIND):
            for missing in ('player','district'):
                g=self.graph();g.missing=missing
                self.assertEqual(self.dispatch(g,kind),0);record=g.event.deferred.pending[0]
                self.assertEqual(struct.unpack_from('<ii',record,96 if kind==damage.EVENT_KIND else 104),(-9999,-9999))
                self.assertFalse(any(g.live.values()))
                self.assertFalse(any(name.startswith('item_') for name,*_ in g.district_calls))
                self.assertEqual(g.event.deferred.drain(),1)

    def test_query_canary_return_and_append_failures_release_and_poison(self):
        for kind,failure in ((damage.EVENT_KIND,'item_hash'),(combat.EVENT_KIND,'item_raw'),
                             (damage.EVENT_KIND,'canary'),(combat.EVENT_KIND,'return'),(damage.EVENT_KIND,'append')):
            g=self.graph();g.failure=failure
            with patch.object(g.event.deferred,'_enqueue',side_effect=RuntimeError('fixture append')) if failure=='append' else ExitStack():
                with self.assertRaises((ValueError,RuntimeError)):self.dispatch(g,kind)
            self.assertFalse(any(g.live.values()));self.assertEqual(g.event.deferred.pending,[])
            self.assertTrue(g.owner.quarantined);self.assertIsNone(g.owner._foundation_borrow)
            name='damage' if kind==damage.EVENT_KIND else 'combat'
            self.assertTrue(getattr(g.owner,'_district_'+name+'_poisoned'))
            self.assertFalse(getattr(g.owner,'_district_'+name+'_producing'))

    def test_wrong_engine_source_bytes_and_foreign_source_receipt_refuse(self):
        g=self.graph()
        with self.assertRaises(ValueError):source.bind_owner(g.backend,object(),g.owner.read)
        old=g.backend.load_abi
        from types import SimpleNamespace
        g.backend.load_abi=SimpleNamespace(core_sha256=XP1_CORE_SHA256)
        with self.assertRaises(ValueError):source.bind_owner(g.backend,g.backend.core,g.owner.read)
        g.backend.load_abi=old
        g.memory.put(g.memory.core_base+0x5fb103,b'\0')
        with self.assertRaisesRegex(ValueError,'live source'):source.verify_live(g.memory.core_base,g.owner.read)
        g.backend._xp2_district_damage_source=object()
        with self.assertRaisesRegex(ValueError,'lifetime'):source.bind_owner(g.backend,g.backend.core,g.owner.read)

    def test_existing_dispatch_scope_and_exact_sibling_borrow_remain_required(self):
        g=self.graph();g.event.deferred.host_notification_counter=2;g.event.deferred.host_metadata_counter=1
        # The callback itself does not read N/M. The shared dispatcher's stricter
        # existing scope admission remains in force; this port does not widen it.
        with self.assertRaisesRegex(ValueError,'Nonzero native notification metadata'):
            self.dispatch(g,source.SIBLING_KIND)
        self.assertEqual((g.event.deferred.host_notification_counter,g.event.deferred.host_metadata_counter),(2,1))
        self.assertEqual(g.event.deferred.pending,[])
        g.event.deferred.host_notification_counter=g.event.deferred.host_metadata_counter=0
        for kind in (damage.EVENT_KIND,combat.EVENT_KIND):
            g=self.graph();g.event.deferred.host_notification_counter=1
            with self.assertRaises((ValueError,RuntimeError)):self.dispatch(g,kind)
            self.assertEqual(g.district_calls,[]);self.assertFalse(g.event.deferred.pending)
            g.event.deferred.host_notification_counter=0
        g=self.graph();g.backend._xp2_district_damage_source=object()
        with self.assertRaises(ValueError):self.dispatch(g,source.SIBLING_KIND)
        self.assertFalse(g.event.deferred.pending);self.assertIsNone(g.owner._foundation_borrow)


if __name__=='__main__':unittest.main()
