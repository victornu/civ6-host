"""Local memory/invocation fixtures; no DLL or native process is executed."""
import ctypes as C
import hashlib
from pathlib import Path
import struct
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from civ6_host.runtime import application_mirror_profiles as profiles
from civ6_host.runtime import xp2_application_mirror_source as source
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from civ6_host.runtime.native import native_game_value_prelude_mutation as mutation
from civ6_host.runtime.native import native_application_mirror_dispatch as dispatch
from civ6_host.runtime.native.native_application_property_copy import copy_existing


class Fixture:
    """Scalar and empty-map test seam; never used as a runtime substitute."""
    def __init__(self):
        self.base=0x180000000;self.context=0x123400;self.memory={};self.cells={}
        self.calls=[];self.next_node=0x400000;self.next_map=0x800000;self.next_nodes={}
        self.fail=None;self.abi=profiles.mirror_abi(XP2_CORE_SHA256)
        self.methods=dict(self.abi.methods)
        _,keys,self.fields,root=profiles.snapshot_sources(XP2_CORE_SHA256)
        self.a=self.side(0x100000);self.b=self.side(0x200000)
        for side in (self.a,self.b):
            values=(side['normalized'],side['map_normalized'],*side['players'])
            for key,pointer in zip((root,0x12345678,*keys),values):
                self.upsert(side['descriptor'],key,self.variant(10,pointer,0x05000000))
        cfg=self.abi.configuration
        self.put(self.base+cfg.root_key_rva,struct.pack('<I',root))
        self.put(self.base+cfg.map_key_rva,struct.pack('<I',0x12345678))
        for index,key in enumerate(keys):self.put(self.base+cfg.player_key_table_rva+index*68,struct.pack('<I',key))
        p=source.source()
        for _,rva,raw in source.fragments(p):self.put(self.base+rva,raw)
        for key,value in p['slots'].items():
            table,slot=(int(v,16) for v in key.split('+'))
            self.q(self.base+table+slot,self.base+int(value,16))
        self.put(self.base+self.abi.phase_key_rva,struct.pack('<I',dispatch.LAST_TURN_PHASE))
        self.put(self.base+0xb68d40,b'\1')
        def require(base,context):
            if (base,context)!=(self.base,self.context):raise ValueError('Foreign owner context')
        self.owner=NS(_configuration_abi=cfg,require_context=require,snapshot=lambda:self.b,
            pointer=self.b['descriptor'],player=lambda i:dict(provider=self.b['descriptor'],pointer=self.b['players'][i]))
    def put(self,p,raw):self.memory.update({p+i:v for i,v in enumerate(raw)})
    def read(self,p,n):return bytes(self.memory[p+i] for i in range(n))
    def q(self,p,v):self.put(p,struct.pack('<Q',v))
    @staticmethod
    def variant(tag,payload,flags=0):return struct.pack('<IIQII',tag,0,payload,0,flags)
    def empty(self,p):
        self.put(p,bytes(88));self.q(p,self.base+self.abi.configuration.vtable_rva)
        self.q(p+32,self.base+0x100);self.q(p+48,p+48);self.q(p+56,p+48)
    def side(self,start):
        values=tuple(start+index*256 for index in range(67))
        for p in values:self.empty(p)
        return dict(descriptor=values[0],normalized=values[1],map_normalized=values[2],players=values[3:])
    def upsert(self,owner,key,raw):
        pointer=self.cells.get((owner,key))
        if pointer:self.put(pointer,raw);return pointer
        node=self.next_node;self.next_node+=128;pointer=node+40
        self.put(node,bytes(64));self.put(node+32,struct.pack('<I',key));self.put(pointer,raw)
        self.cells[owner,key]=pointer
        nodes=[value-40 for (provider,_),value in sorted(self.cells.items()) if provider==owner]
        for current,next_node in zip(nodes,(*nodes[1:],owner+48)):self.next_nodes[current]=next_node
        self.put(owner+48,struct.pack('<QQQ',nodes[-1],nodes[0],nodes[0]))
        self.put(owner+80,struct.pack('<I',len(nodes)))
        return pointer
    def invoke(self,address,result,types,*args):
        if address==self.base+self.abi.variant_assign_rva:
            self.calls.append(('assign',args));assert result is None
            if self.fail=='assign':raise RuntimeError('fixture assignment failure')
            self.put(args[0],self.read(args[1],24));return 0xDEAD
        if address==self.base+self.abi.argument_getter_rva:
            self.calls.append(('argument',args))
            return self.argument_variants[args[1]]
        name=next(k for k,v in self.methods.items() if address==self.base+v)
        self.calls.append((name,args))
        if name==self.fail:raise RuntimeError('fixture '+name+' failure')
        if name=='lookup':return self.cells.get(tuple(args),0)
        if name=='tree_next':return self.next_nodes[args[0]]
        if name in ('hash','integer'):return self.upsert(args[0],args[1],self.variant(3 if name=='hash' else 2,args[2]))
        if name=='allocator_get':return struct.unpack('<Q',self.read(args[0]+32,8))[0]
        if name=='allocator_set':self.q(args[0]+32,args[1]);return None
        if name=='allocate':
            assert types==(C.c_size_t,) and args==(88,)
            p=self.next_map;self.next_map+=256;self.put(p,b'\xdd'*88);return p
        if name=='constructor':self.empty(args[0]);return args[0]
        if name=='owned_map':return self.upsert(args[0],args[1],self.variant(10,args[2],0x05000000))
        if name=='finish':return 0
        raise AssertionError('Unexpected native fixture call '+name)
    def call(self,address,result,types,receiver,*args):
        return self.invoke(address,result,(C.c_void_p,*types),receiver,*args)
    def attempt(self):
        return mutation.NativePreludeAttempt(self.base,self.context,self.owner,read=self.read,
            invoke=self.invoke,current_thread_id=lambda:91,core_sha256=XP2_CORE_SHA256)
    def dispatcher(self):
        return dispatch.BorrowedApplicationDispatcher(self.base,self.context,self.owner,read=self.read,
            invoke=self.invoke,current_thread_id=lambda:91,journal=[],journal_limit=4096,
            diagnostic_profile=dispatch.PROFILE,logging_enabled=False,core_sha256=XP2_CORE_SHA256)
    def arguments(self,kind,key,index=63):
        fields=[(dispatch.PROPERTY,self.variant(3,key))]
        if kind==dispatch.PLAYER:fields.append((dispatch.INDEX,self.variant(2,index)))
        ptr,entries=0xd00000,0xd00100
        self.q(ptr,self.base+self.abi.argument_vtable_rva)
        self.put(ptr+40,struct.pack('<QQQ',entries,entries+32*len(fields),entries+128))
        self.put(entries,b''.join(struct.pack('<II',k,0)+v for k,v in fields))
        self.argument_variants={k:entries+i*32+8 for i,(k,_) in enumerate(fields)}
        return ptr


class XP2MirrorTests(unittest.TestCase):
    def test_preflight_pins_and_real_owner_body_join(self):
        pins=profiles.source_dependencies(XP2_CORE_SHA256)
        self.assertTrue(all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==s for p,s in pins.items()))
        proof=profiles.copy_source(XP2_CORE_SHA256)
        self.assertEqual(proof['source_sha256'],source.SOURCE[1])
        owner=profiles.application_source(XP2_CORE_SHA256)
        owner['core_functions']['lookup']['fragments'][0]['instructions'][0]['bytes']='00'
        with patch.object(profiles,'application_source',return_value=owner):
            with self.assertRaisesRegex(ValueError,'owner instruction join'):profiles.copy_source(XP2_CORE_SHA256)
        with self.assertRaisesRegex(ValueError,'engine identities'):
            profiles.owner_abi(NS(_configuration_abi=profiles.configuration_abi(XP1_CORE_SHA256)),XP2_CORE_SHA256)

    def test_full_live_guards_cover_tail_branch_slots_selector_and_gate(self):
        f=Fixture();self.assertFalse(profiles.verify_live(f.base,f.read,core_sha256=XP2_CORE_SHA256)['native_callback_observed'])
        targets=(f.base+0x9a5dc7,f.base+0x9a429f,f.base+0xabf918+0x68,f.base+0xb8c424,f.base+0xb68d40)
        for address in targets:
            with self.subTest(address=hex(address)):
                old=f.memory[address];f.memory[address]^=1
                with self.assertRaises(ValueError):profiles.verify_live(f.base,f.read,core_sha256=XP2_CORE_SHA256)
                f.memory[address]=old

    def test_prelude_runs_existing_algorithm_and_transfers_64_maps(self):
        f=Fixture();attempt=f.attempt();receipt=attempt.apply(f.a['descriptor'],f.a)
        self.assertEqual(receipt['planned_new_cells'],dict(annotations=66,player_ids=64,map_pins=64,team_assignments=0,total=194))
        self.assertEqual(receipt['observed_new_cells'],194)
        self.assertEqual(receipt['native_scalar_calls'],130)
        self.assertEqual(len(receipt['allocations']),64)
        self.assertTrue(all(row['state']=='transferred' and not row['freed'] for row in receipt['allocations']))
        self.assertFalse(receipt['acknowledgement_permitted'])
        self.assertFalse(receipt['whole_EXE_wrapper_emulated'])
        self.assertFalse(any(name=='delete' for name,_ in f.calls))
        with self.assertRaisesRegex(ValueError,'one-attempt'):attempt.apply(f.a['descriptor'],f.a)

    def test_failed_transfer_is_retained_and_fatal_without_guessed_cleanup(self):
        f=Fixture();f.fail='owned_map';attempt=f.attempt()
        with self.assertRaises(mutation.PreludeMutationFailure) as caught:attempt.apply(f.a['descriptor'],f.a)
        self.assertTrue(caught.exception.requires_fatal_worker_exit)
        self.assertTrue(attempt.poisoned)
        self.assertEqual(attempt.allocations,[dict(pointer=0x800000,state='transfer_in_flight',freed=False)])
        self.assertFalse(any(name=='delete' for name,_ in f.calls))

    def test_active_observer_refuses_before_any_provider_mutation(self):
        f=Fixture();f.q(f.a['descriptor']+16,0xbad);attempt=f.attempt()
        with self.assertRaisesRegex(mutation.PreludeMutationFailure,'Active observer'):attempt.apply(f.a['descriptor'],f.a)
        self.assertTrue(all(name in ('lookup','tree_next','allocator_get') for name,_ in f.calls))

    def test_copy_missing_branches_and_actual_assignment(self):
        f=Fixture();a=f.a['players'][0];b=f.b['players'][0];key=123
        def copy():return copy_existing(f.base,a,b,key,read=f.read,call=f.call,core_sha256=XP2_CORE_SHA256)
        self.assertEqual(copy()['native_branch'],'missing_source')
        src=f.upsert(a,key,f.variant(2,123));self.assertEqual(copy()['native_branch'],'missing_destination')
        dest=f.upsert(b,key,f.variant(2,12));self.assertTrue(copy()['mirrored'])
        self.assertEqual(f.read(src,24),f.read(dest,24))
        self.assertEqual([name for name,_ in f.calls].count('assign'),1)

    def test_player_dispatch_copies_then_appends_actual_pair(self):
        f=Fixture();d=f.dispatcher();key=123
        src=f.upsert(f.a['players'][63],key,f.variant(2,999))
        dst=f.upsert(f.b['players'][63],key,f.variant(2,0))
        argument=f.arguments(dispatch.PLAYER,key)
        with patch.object(dispatch.setup,'_linked_snapshot',return_value=f.a):
            receipt=d.dispatch(dispatch.PLAYER,argument,f.a['descriptor'])
        self.assertEqual(f.read(src,24),f.read(dst,24));self.assertEqual(d.journal,[(63,key)])
        self.assertEqual(receipt['native_dispatch_return'],0)
        self.assertFalse(receipt['whole_EXE_application_equivalent']);d.close()

    def test_unknown_kind_and_foreign_argument_getter_poison_without_return(self):
        for mode in ('kind','getter'):
            with self.subTest(mode=mode):
                f=Fixture();d=f.dispatcher();argument=f.arguments(dispatch.PLAYER,123)
                if mode=='getter':f.argument_variants[dispatch.PROPERTY]=f.base+0xb90c60
                with self.assertRaises(dispatch.ApplicationDispatchFailure):
                    d.dispatch(123 if mode=='kind' else dispatch.PLAYER,argument,f.a['descriptor'])
                self.assertTrue(d.poisoned);self.assertEqual(d.journal,[])
                self.assertFalse(any(name in ('assign','allocate','hash') for name,_ in f.calls))

    def test_game_phase_copy_never_appends_player_journal(self):
        for present in (False,True):
            with self.subTest(destination_present=present):
                f=Fixture();d=f.dispatcher();key=dispatch.LAST_TURN_PHASE
                f.upsert(f.a['normalized'],key,f.variant(2,7))
                dst=f.upsert(f.b['normalized'],key,f.variant(2,1)) if present else None
                argument=f.arguments(dispatch.GAME,key)
                with patch.object(dispatch.setup,'_linked_snapshot',return_value=f.a):
                    receipt=d.dispatch(dispatch.GAME,argument,f.a['descriptor'])
                self.assertEqual(receipt['mirrored'],present);self.assertEqual(d.journal,[])
                self.assertEqual(receipt['native_branch'],'copy_without_journal' if present else 'missing_destination')
                if present:self.assertEqual(f.read(dst,24),f.variant(2,7))

    def test_assignment_failure_cannot_append_or_acknowledge_player_pair(self):
        f=Fixture();d=f.dispatcher();key=123;f.fail='assign'
        f.upsert(f.a['players'][63],key,f.variant(2,999))
        f.upsert(f.b['players'][63],key,f.variant(2,0))
        argument=f.arguments(dispatch.PLAYER,key)
        with patch.object(dispatch.setup,'_linked_snapshot',return_value=f.a):
            with self.assertRaises(dispatch.ApplicationDispatchFailure) as caught:
                d.dispatch(dispatch.PLAYER,argument,f.a['descriptor'])
        self.assertTrue(caught.exception.requires_fatal_worker_exit)
        self.assertTrue(d.poisoned);self.assertEqual(d.journal,[]);self.assertEqual(d.completed_calls,0)

    def test_source_extractor_passes_explicit_engine_to_generated_guard(self):
        # Inspect the generator input; the parent owns global extraction.
        path=Path(__file__).resolve().parents[1]/'tools/extraction_application_mirror.py'
        self.assertIn('_mirror_profiles.verify_live(self.base, self.read, core_sha256=core_sha256)',path.read_text())


if __name__=='__main__':unittest.main()
