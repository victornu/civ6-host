"""Offline tests execute the transformed shared query bodies, never GameCore."""
import ast
import ctypes as C
import importlib
import inspect
import struct
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

HOST = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HOST/'tools'))
from extraction_xp1_turn_units import parameterize, TARGETS, BASE
from civ6_host.runtime import turn_unit_event_profile as profile
XP1 = profile.XP1_CORE_SHA256


def transformed(name):
    original=importlib.import_module('civ6_host.runtime.native.'+name)
    raw=Path(original.__file__).read_text(encoding='utf-8')
    # This also runs against the installed extraction after root integration.
    fn=next(iter(TARGETS[name]))
    already='core_sha256' in inspect.signature(getattr(original,fn)).parameters
    cooked=raw if already else parameterize('civ6rl.'+name,raw)
    module=types.ModuleType('turn_unit_fixture_'+name)
    sys.modules[module.__name__]=module
    exec(compile(cooked,str(original.__file__),'exec'),module.__dict__)
    return module,cooked


class Memory:
    base=0x10000000
    def __init__(self, tables):
        self.blocks={};self.objects={};self.reads=[]
        for i,(name,(table,slots)) in enumerate(tables.items()):
            pointer=0x20000000+0x1000*i;self.objects[name]=pointer
            self.put(pointer,(self.base+table).to_bytes(8,'little'))
            entries=slots.items() if isinstance(slots,dict) else slots
            for slot,rva in entries:self.put(self.base+table+slot,(self.base+rva).to_bytes(8,'little'))
    def put(self,address,data):self.blocks[address]=bytes(data)
    def read(self,address,size):
        self.reads.append((address,size))
        for start,raw in self.blocks.items():
            if start<=address and address+size<=start+len(raw):return raw[address-start:address-start+size]
        raise AssertionError(f'Unallocated read {address:#x}/{size}')


class TurnUnits(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules={name:transformed(name) for name in TARGETS}
        cls.created=cls.modules['native_unit_created_event'][0]
        cls.moved=cls.modules['native_event_6e7ef927'][0]
        cls.improvement=cls.modules['native_event_a625c726'][0]
        cls.added=cls.modules['native_event_e5b20b82'][0]
        cls.added.shared=cls.improvement

    def test_source_membership_and_live_guard(self):
        p=profile.verify_source();self.assertEqual(p['validation']['kind_count'],5)
        from civ6_host.runtime.xp1_status_profiles import _instruction_spans
        memory=Memory(profile.TABLES)
        for rva,raw in _instruction_spans(p):memory.put(memory.base+rva,raw)
        self.assertGreater(profile.verify_live(memory.base,memory.read),0)
        owner=types.SimpleNamespace(check_thread=lambda:None,load_abi=types.SimpleNamespace(core_sha256=XP1))
        owner.core=types.SimpleNamespace(_handle=memory.base)
        one=profile.bind_owner(owner,owner.core,memory.read);before=len(memory.reads)
        self.assertIs(one,profile.bind_owner(owner,owner.core,memory.read))
        self.assertEqual(before,len(memory.reads))
        ptable,slots=profile.TABLES['unit'];memory.put(memory.base+ptable+0xb8,b'\0'*8)
        with self.assertRaisesRegex(ValueError,'vtable'):profile.verify_live(memory.base,memory.read)
        self.assertEqual(set(profile.event_profile().record_types_by_kind),set(profile.KINDS))

    def test_base_independent_and_all_native_specs_selected(self):
        for mod in (self.moved,self.improvement):
            with patch.object(profile,'verify_source',side_effect=AssertionError('XP1 source touched by Base')):
                self.assertIs(profile.select_tables(BASE,mod._TABLES),mod._TABLES)
                self.assertEqual(profile.unit_live_offset(BASE),16)
            calls=[]
            def factory(result,*args):
                return lambda address: calls.append((address,result,args)) or (lambda *values:None)
            with patch.object(C,'WINFUNCTYPE',factory):api=mod._api(0x10000000,None,core_sha256=XP1)
            self.assertEqual(len(calls),len(api))
            for name,(address,_,_) in zip(api,calls):
                if name=='string_empty':expected=0x839d30
                elif name=='string_free':expected=0x836b10
                else:
                    table,slot=profile.OPERATIONS[name];expected=profile.TABLES[table][1][slot]
                self.assertEqual(address,0x10000000+expected,name)
        with self.assertRaises(ValueError):profile.select_tables('unknown',self.moved._TABLES)

    def test_created_releases_after_enqueue_and_game_mode(self):
        mod=self.created;memory=Memory(profile.select_tables(XP1,mod.TABLES));obj=memory.objects;calls=[]
        for addr,text in ((0x600000,b'UNIT_A\0'),(0x600100,b'UNIT_B\0'),(0x600200,b'CIV_A\0')):memory.put(addr,text)
        values={('outer',0xb8):obj['player'],('player',0x110):obj['units'],('units',0x10):obj['unit'],
                ('unit',0x28):1,('outer',0x100):obj['data'],('data',0x368):0x600000,
                ('unit',0x50):2,('data',0x260):0x600100,('player',0x18):3,
                ('data',0x308):0x600200,('unit',0x58):9,('unit',0x88):1,
                ('player',0x28):2,('outer',0x90):obj['game'],('game',0x128):2}
        def invoke(table,slot,pointer,*args):
            self.assertEqual(pointer,obj[table]);calls.append((table,slot,args))
            if (slot==8 and table!='outer') or (table=='unit' and slot==16):return None
            return values[table,slot]
        with mod.query_native_values(memory.base,obj['outer'],1,3,read=memory.read,invoke=invoke,
                application_mode_reader=lambda application:123,core_sha256=XP1) as result:
            self.assertTrue(result['local_team']);self.assertTrue(result['special'])
            self.assertEqual(calls[-2:],[('game',8,()),('data',8,())])
            self.assertFalse(any(t=='unit' and s==16 for t,s,_ in calls))
        self.assertEqual(calls[-3:],[('unit',16,(1,)),('units',8,()),('player',8,())])

    def test_move_snapshot_live_offset_string_cleanup_and_null(self):
        mod=self.moved;memory=Memory(profile.select_tables(XP1,mod._TABLES));obj=memory.objects;calls=[]
        memory.put(obj['unit']+8,(0x30000000).to_bytes(8,'little'))
        core=types.SimpleNamespace(_handle=memory.base)
        fields=mod.EventFields(0,struct.pack('<HHI',1,1,9),1,9,struct.pack('<ii',3,4))
        def snapshot(unit,address,flags):
            self.assertEqual((unit,flags),(obj['unit'],0));calls.append('snapshot')
            C.memmove(address+16,struct.pack('<QI',0x710008,123),12)
            C.memmove(address+28,struct.pack('<I',998),4)
        api={'get_player':lambda *args:obj['player'],'release_player':lambda *args:calls.append('player-release'),
             'player_units':lambda *args:obj['units'],'release_units':lambda *args:calls.append('units-release'),
             'units_index':lambda *args:obj['unit'],'release_unit':lambda u,f:calls.append(('unit-release',u,f)),
             'unit_snapshot':snapshot,'string_empty':lambda:0x700000,'string_free':lambda p:calls.append(('free',p))}
        options=dict(normalizer_transform_present=False,per_thread_hook_present=False,
                     writer_metadata_callback_present=False,read=memory.read,native_api=api,core_sha256=XP1)
        with mod.produce_record_lease(1,core,obj['outer'],fields,**options) as record:
            self.assertEqual(struct.unpack_from('<I',record,112)[0],998)
            self.assertEqual(calls,['units-release','player-release','snapshot',('free',0x710000)])
        self.assertEqual(calls[-1],('unit-release',obj['unit'],1))
        self.assertNotIn((obj['unit']+16,8),memory.reads)
        calls.clear();api['get_player']=lambda *args:0
        with mod.produce_record_lease(2,core,obj['outer'],fields,**options) as record:
            self.assertEqual(struct.unpack_from('<I',record,112)[0],mod.NULL_UNIT_SCALAR)
        self.assertEqual(calls,[])

    def test_move_overflow_refused_and_cleanup(self):
        mod=self.moved;memory=Memory(profile.select_tables(XP1,mod._TABLES));obj=memory.objects;calls=[]
        memory.put(obj['unit']+8,(123).to_bytes(8,'little'))
        api={'get_player':lambda *a:obj['player'],'release_player':lambda *a:None,
             'player_units':lambda *a:obj['units'],'release_units':lambda *a:None,
             'units_index':lambda *a:obj['unit'],'release_unit':lambda *a:calls.append('release'),
             'unit_snapshot':lambda u,p,f:C.memset(p+184,0,1),'string_empty':lambda:0x700000,
             'string_free':lambda *a:calls.append('free')}
        fields=mod.EventFields(0,struct.pack('<HHI',1,1,9),1,9,struct.pack('<ii',3,4))
        with self.assertRaisesRegex(RuntimeError,'exceeded'):
            with mod.produce_record_lease(1,types.SimpleNamespace(_handle=memory.base),obj['outer'],fields,
                    normalizer_transform_present=False,per_thread_hook_present=False,
                    writer_metadata_callback_present=False,read=memory.read,native_api=api,core_sha256=XP1):pass
        self.assertEqual(calls,['release'])

    def test_improvement_getters_snapshots_inner_engine_and_release(self):
        mod=self.improvement;memory=Memory(profile.select_tables(XP1,mod._TABLES));obj=memory.objects;calls=[]
        def snapshot180(p,addr,f):
            raw=bytearray(24);struct.pack_into('<h',raw,4,-5);C.memmove(addr,bytes(raw),24)
        def snapshot178(p,addr,f):
            raw=bytearray(24);struct.pack_into('<I',raw,4,44);raw[20]=2;C.memmove(addr,bytes(raw),24)
        api={'outer_map':lambda *a:obj['map'],'get_plot':lambda *a:obj['plot'],
             'release_map':lambda *a:calls.append('map-release'),'release_plot':lambda *a:calls.append('plot-release'),
             'plot_component':lambda *a:obj['component'],'release_component':lambda *a:calls.append('component-release'),
             'snapshot180':snapshot180,'snapshot178':snapshot178,'component10':lambda *a:6,
             'component18':lambda *a:1,'component30':lambda *a:8,'plot30':lambda *a:10,
             'plotc8':lambda *a:1,'plotc0':lambda *a:2,'plote0':lambda *a:1}
        def inner(*args,**kwargs):
            self.assertEqual(kwargs['core_sha256'],XP1);calls.append('inner');return 12
        fields=mod.EventFields(struct.pack('<ii',3,4),3,4,0,0)
        with patch.object(mod,'query_secondary_value',inner),patch.object(mod,'read_player_civilization_type_id',inner):
            result=mod.query_native_values(types.SimpleNamespace(_handle=memory.base),obj['outer'],fields,
                    read=memory.read,native_api=api,core_sha256=XP1)
        self.assertEqual((result.city_owner,result.city_id,result.snapshot180_word4),(2,44,-5))
        self.assertEqual(calls,['map-release','inner','inner','component-release','plot-release'])

    def test_local_flag_real_mode_provider_forwarding_and_release(self):
        mod=self.added
        retained={'outer':(7987232,((144,4382432),)),'game':(7990488,((8,4409168),(296,4410112)))}
        memory=Memory(profile.select_tables(XP1,retained));obj=memory.objects;calls=[]
        app=types.SimpleNamespace(require_context=lambda b,c:self.assertEqual((b,c),(memory.base,obj['outer'])))
        core=types.SimpleNamespace(_handle=memory.base,_civ6rl_application_configuration=app)
        backend=types.SimpleNamespace(owner=app,load_abi=types.SimpleNamespace(core_sha256=XP1))
        api={'get_game':lambda *a:obj['game'],'get_local_team':lambda *a:2,'release_game':lambda *a:calls.append('release')}
        from civ6_host.runtime.native import native_app_ownership
        def mode(actual,*,candidate_backend=None):
            self.assertIs(actual,app);self.assertIs(candidate_backend,backend);return 123
        with patch.object(native_app_ownership,'read_application_mode',mode):
            self.assertTrue(mod.query_local_flag(core,obj['outer'],2,read=memory.read,native_api=api,
                              core_sha256=XP1,candidate_backend=backend))
            self.assertEqual(calls,['release'])
            self.assertFalse(mod.query_local_flag(core,obj['outer'],-1,read=memory.read,native_api=api,
                              core_sha256=XP1,candidate_backend=backend))
            with self.assertRaisesRegex(ValueError,'exact application'):
                mod.query_local_flag(core,obj['outer'],2,read=memory.read,native_api=api,core_sha256=XP1)

    def test_explicit_propagation_and_dispatch_only_four_query_branches(self):
        for name,(_,cooked) in self.modules.items():
            tree=ast.parse(cooked)
            funcs={n.name:n for n in tree.body if isinstance(n,ast.FunctionDef)}
            for name in TARGETS[name]:self.assertTrue(any(a.arg=='core_sha256' for a in funcs[name].args.kwonlyargs))
        path=HOST/'src/civ6_host/runtime/native/native_host_events.py'
        raw=path.read_text(encoding='utf-8')
        cooked=raw if 'turn_unit_core_sha256' in raw else parameterize('civ6rl.native_host_events',raw)
        self.assertEqual(cooked.count("getattr(self, 'turn_unit_core_sha256'"),4)
        self.assertEqual(cooked.count("getattr(self, 'turn_unit_backend'"),2)
        self.assertEqual(parameterize('civ6rl.native_entity_event','unchanged'),'unchanged')


if __name__=='__main__':unittest.main()
