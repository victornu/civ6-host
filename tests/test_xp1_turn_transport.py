"""Actual shared methods, explicit byte/native-call fixtures; no DLL execution."""
from pathlib import Path
import ctypes as C
import hashlib
import json
import os
import struct
import sys
import types
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent;HOST=HERE.parent;LAB=HOST.parent/'civ6-rl-lab'
os.environ['CIV6_HOST_RESOURCE_ROOT']=str(LAB)
sys.path[:0]=[str(HOST/'src'),str(HOST/'tools')]
from extraction_xp1_turns import parameterize
from civ6_host.runtime import xp1_turn_profile as profiles, turn_requests
from civ6_host.runtime.native import native_host


def transformed(name):
    path=HOST/'src/civ6_host/runtime/native'/(name+'.py')
    raw=path.read_text()
    if 'civ6_host.runtime.xp1_turn_profile' not in raw:
        raw=parameterize('civ6rl.'+name,raw)
    module=types.ModuleType('test_'+name)
    exec(compile(raw,str(path)+' [isolated turn extraction]','exec'),module.__dict__)
    return module


TRANSPORT=transformed('native_action_transport')
FORCED=transformed('native_forced_endturn')
COMPLETE=transformed('native_game_turn_complete')


class Memory:
    base=0x180000000
    context=0x200000000
    def __init__(self,profile):
        self.profile=profile;self.bytes={};self.regions=[];self.owned=[];self.calls=[];self.value=0
        if profile is profiles.XP1:
            source=profiles.source()
            for body in source['functions']['xp1'].values():
                for f in profiles._body(body)['fragments']:
                    for r in f['instructions']:self.put(int(r['va'],16),bytes.fromhex(r['bytes']))
            for vt,slots in source['tables'].values():
                for slot,target in slots.items():self.put(self.base+vt+int(slot),struct.pack('<Q',self.base+target))
            self.put(self.context,struct.pack('<Q',self.base+0x8a8df0))
        else:
            source=profiles.source()['functions']['base']['unready_wrapper']
            for f in profiles._body(source)['fragments']:
                for r in f['instructions']:self.put(int(r['va'],16),bytes.fromhex(r['bytes']))
        self.put(self.base+profile.processor_flags_rva,b'\x01\x01\0\0')
    def put(self,address,data):self.bytes.update({address+i:v for i,v in enumerate(data)})
    def read(self,address,size):
        if all(address+i in self.bytes for i in range(size)):return bytes(self.bytes[address+i] for i in range(size))
        if any(start<=address and address+size<=end for start,end in self.regions):return C.string_at(address,size)
        raise ValueError('Fixture refused unowned memory: '+hex(address))
    def allocate(self,size):
        obj=C.create_string_buffer(size);self.owned.append(obj);self.regions.append((C.addressof(obj),C.addressof(obj)+size));return C.addressof(obj)
    def factory(self,restype,*args):
        def bind(address):
            rva=address-self.base;p=self.profile
            self.calls.append(('bind',rva,restype,args))
            if rva in (p.tree_ctor_rva,p.vector_ctor_rva):
                def ctor(ptr):
                    size=112 if rva==p.tree_ctor_rva else 88
                    self.regions.append((ptr,ptr+size));self.value=0
                    C.memmove(ptr,struct.pack('<Q',self.base+(p.tree_vtable_rva if rva==p.tree_ctor_rva else p.vector_vtable_rva)),8)
                    self.calls.append(('ctor',rva));return ptr
                return ctor
            if rva in (p.tree_dtor_rva,p.vector_dtor_rva):return lambda ptr:self.calls.append(('dtor',rva))
            if rva==p.reason_converter_rva:return lambda ptr:1913349224
            raise ValueError('Unexpected fixture ABI target '+hex(rva))
        return bind
    def virtual(self,core,pointer,slot,rva,result,*args):
        p=self.profile;self.calls.append(('virtual',slot,rva,result,args))
        if rva in (p.tree_lookup_rva,p.vector_lookup_rva):return lambda pointer,key:self.value
        if rva==p.string_setter_rva:
            def setter(pointer,key,text):
                stringptr=C.cast(text,C.c_void_p).value
                self.regions.append((stringptr,stringptr+11))
                self.value=self.allocate(24)
                C.memmove(self.value,struct.pack('<H6xQII',5,stringptr,0,1<<29),24)
                return self.value
            return setter
        if rva==p.request_rva:
            def request(context,action,player,parameters):
                reason=1913349224 if self.value else 0xb6fa1284
                self.transport.pending.append(struct.pack('<III',0xd7c02786,player,reason))
                if getattr(self,'damage_canary',False):C.memset(parameters+96,0,1)
            return request
        if rva==p.unready_wrapper_rva:
            def unready(context,action,player):
                mode=getattr(self,'unready_mode','queued')
                if mode=='queued':self.transport.pending.append(struct.pack('<II',0xe8a26b84,player))
                elif mode=='invalid':self.transport.pending.append(b'bad-native-fixture')
            return unready
        raise ValueError('Unexpected fixture virtual '+hex(rva))
    def owner(self):
        t=object.__new__(TRANSPORT.NativeActionTransport)
        t.transport_abi=types.SimpleNamespace(core_sha256=self.profile.core_sha256)
        t.core=types.SimpleNamespace(_handle=self.base);t.context=self.context;t.read=self.read;t.pending=[]
        t.emit=lambda *a,**k:None;self.transport=t;return t


class TurnTests(unittest.TestCase):
    def bind(self,memory):
        return patch.multiple(TRANSPORT,virtual=memory.virtual),patch.object(C,'WINFUNCTYPE',memory.factory)
    def test_pinned_profile_live_identity_and_corruption(self):
        memory=Memory(profiles.XP1)
        profiles.verify_live(memory.base,memory.context,memory.read)
        memory.bytes[memory.base+profiles.XP1.unready_wrapper_rva]^=1
        with self.assertRaisesRegex(ValueError,'native body'):profiles.verify_live(memory.base,memory.context,memory.read)
        with self.assertRaises(ValueError):profiles.turn_profile('unknown')
        with self.assertRaises(ValueError):profiles.require_profile(profiles.BASE,profiles.XP1.core_sha256)
        memory=Memory(profiles.XP1);memory.put(memory.base+0x8a8df0+0x1f8,struct.pack('<Q',memory.base+profiles.BASE.request_rva))
        with self.assertRaisesRegex(ValueError,'native slot'):profiles.verify_live(memory.base,memory.context,memory.read)
    def test_shared_normal_requests_base_and_xp1_and_canary(self):
        for profile in (profiles.BASE,profiles.XP1):
            memory=Memory(profile);t=memory.owner();a,b=self.bind(memory)
            with a,b:t.request_end_turn(0,player_ids=(0,))
            self.assertEqual(t.pending,[struct.pack('<III',0xd7c02786,0,0xb6fa1284)])
            self.assertIn(('dtor',profile.tree_dtor_rva),memory.calls)
            requests=[r for r in memory.calls if r[0]=='virtual' and r[1]==0x1f8]
            self.assertEqual(requests[0][2:4],(profile.request_rva,None))
        memory=Memory(profiles.XP1);t=memory.owner();memory.damage_canary=True;a,b=self.bind(memory)
        with a,b,self.assertRaisesRegex(RuntimeError,'source-sized'):t.request_end_turn(0,player_ids=(0,))
        self.assertIn(('dtor',profiles.XP1.tree_dtor_rva),memory.calls)
    def test_shared_forced_string_route_xp1(self):
        memory=Memory(profiles.XP1);t=memory.owner();a,b=self.bind(memory)
        with a,b,patch.object(FORCED,'virtual',memory.virtual),patch.dict(sys.modules,{'civ6_host.runtime.native.native_forced_endturn':FORCED}):
            t.request_end_turn(0,player_ids=(0,),user_forced=True)
        self.assertEqual(t.pending,[struct.pack('<III',0xd7c02786,0,1913349224)])
        self.assertIn(('dtor',profiles.XP1.vector_dtor_rva),memory.calls)
        self.assertTrue(any(r[:3]==('virtual',0x108,profiles.XP1.string_setter_rva) for r in memory.calls))
        self.assertFalse(any(r[0]=='bind' and r[1] in (profiles.BASE.vector_ctor_rva,profiles.BASE.reason_converter_rva) for r in memory.calls))
    def test_unready_profile_queue_and_refusals(self):
        for profile in (profiles.BASE,profiles.XP1):
            memory=Memory(profile);t=memory.owner();t.pending=[b'earlier']
            with patch.object(native_host,'virtual',memory.virtual):
                result=turn_requests.request_unready_turn(t,0,player_ids=(0,),profile=profile)
            self.assertTrue(result['queued']);self.assertEqual(t.pending[0],b'earlier')
            self.assertEqual(t.pending[1],struct.pack('<II',0xe8a26b84,0))
            self.assertFalse(result['action_applied'])
        memory=Memory(profiles.XP1);t=memory.owner()
        with self.assertRaises(ValueError):turn_requests.request_unready_turn(t,0,player_ids=(0,))
        self.assertEqual(memory.calls,[])
        memory.unready_mode='none'
        with patch.object(native_host,'virtual',memory.virtual):
            self.assertFalse(t.request_unready_turn(0,player_ids=(0,))['queued'])
        memory.unready_mode='invalid'
        with patch.object(native_host,'virtual',memory.virtual),self.assertRaises(RuntimeError):t.request_unready_turn(0,player_ids=(0,))
        self.assertEqual(t.pending,[b'bad-native-fixture'])
    def test_completion_phase_and_payload_never_fabricated(self):
        for profile in (profiles.BASE,profiles.XP1):
            memory=Memory(profile);t=memory.owner();t.pending=[struct.pack('<II',0x1bdb4f5c,0)]
            t.deliver_one=lambda:t.pending.pop(0)
            with patch.dict(sys.modules,{'civ6_host.runtime.native.native_game_turn_complete':COMPLETE}):
                t.deliver_completed_round_echo(0,player_ids=(0,))
                self.assertEqual(t.pending,[])
                t.pending=[struct.pack('<II',0x1bdb4f5c,0)]
                memory.put(memory.base+profile.processor_flags_rva,b'\0'*4)
                with self.assertRaisesRegex(RuntimeError,'Late'):t.deliver_completed_round_echo(0,player_ids=(0,))
                self.assertEqual(t.pending,[struct.pack('<II',0x1bdb4f5c,0)])
        with self.assertRaises(ValueError):COMPLETE.decode_archive(struct.pack('<II',0x1bdb4f5c,0),core_sha256='unknown')


if __name__=='__main__':unittest.main(verbosity=2)
