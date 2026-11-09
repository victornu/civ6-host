"""Composed service owners and FIFO with source bytes, no native GameCore run."""
import ctypes as C
import hashlib
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp2_preload_source as source
from civ6_host.runtime import cache_update_profiles as cache
from civ6_host.runtime.configuration_profiles import _copy
from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256
from civ6_host.runtime.deferred_service import DeferredService
from civ6_host.runtime.control_input_service import ControlInputService
from civ6_host.runtime.event_argument_service import EventArgumentService
from civ6_host.runtime.native.native_cache_update_dispatch import dispatch_cache_update_payload
from test_control_input_service import Host, Code
from test_event_argument_service import variant


class XP2PreloadServices(unittest.TestCase):
    def memory(self):
        self.base,self.context,self.inner = 0x300000000,0x1000,0x2000
        memory = {}
        self.put = lambda addr,data:memory.update({addr+i:b for i,b in enumerate(data)})
        self.read = lambda addr,n:bytes(memory[addr+i] for i in range(n))
        p=source.source()
        for name in p['body_sources']:
            for f in source.body(name)['fragments']:
                self.put(self.base+int(f['start_rva'],16),bytes.fromhex(f['raw_hex']))
        for address,value in ((self.context,self.base+0xA101E8),(self.context+8,self.inner),
                (self.inner,self.base+0xA44F70),(self.base+0xB8AA60,self.inner),
                (self.base+0xB8AA80,123),(self.base+0xA101E8+0x198,self.base+0x591920),
                (self.base+0xABF080+0x1D8,self.base+0x84E260)):
            self.put(address,struct.pack('<Q',value))
        self.put(self.base+0xB61E10,struct.pack('<QII',0x3000,1,1))
        self.put(0x3000,struct.pack('<QQ',0x3100,0x3999))
        node=bytearray(48)
        struct.pack_into('<I',node,0,7)
        struct.pack_into('<QQQ',node,8,0x4000,0x4020,0x4020)
        struct.pack_into('<Q',node,40,0x3999)
        self.put(0x3100,node)
        # The callback pairs share one vector, but A0 and cache use different pairs.
        self.put(0x4000,struct.pack('<QQQQ',0,0,0x4444,0x5555))

    def compose(self):
        self.memory()
        for target in ('civ6_host.runtime.control_input_service.NativeControllerCode',
                       'civ6_host.runtime.native.native_controller_state.NativeControllerCode'):
            patcher=patch(target,Code);patcher.start();self.addCleanup(patcher.stop)
        h=Host();core=NS(_handle=self.base)
        self.original_slots=list(h.vtable);self.original_bindings=dict(h._slot_bindings)
        d=DeferredService(h,core,self.context,core_sha256=XP2_CORE_SHA256,
            read=self.read,emit=Mock(),optional_preprocessor=None,queue_metadata_service=None)
        ctl=ControlInputService(h,core,self.context,d,core_sha256=XP2_CORE_SHA256,
            local_player_id=7,read=self.read,emit=Mock())
        a=EventArgumentService(h,core,self.context,d,core_sha256=XP2_CORE_SHA256,
            read=self.read,emit=Mock(),normalizer_transform=None,dynamic_registrations=())
        return h,d,ctl,a

    def tree(self, values):
        pointer=0x6000
        header=bytearray(88)
        struct.pack_into('<Q',header,0,self.base+0xABF080)
        struct.pack_into('<QQ',header,56,0x7000 if values else pointer+48,0x7000 if values else 0)
        struct.pack_into('<I',header,80,len(values))
        self.put(pointer,header)
        nexts={}
        for index,(key,value) in enumerate(sorted(values.items())):
            node=0x7000+index*0x80
            raw=bytearray(64);struct.pack_into('<I',raw,32,key);raw[40:64]=value
            self.put(node,raw)
            nexts[node]=node+0x80 if index+1<len(values) else pointer+48
        return pointer,nexts.__getitem__

    def test_composed_owner_transports_complete_fields_feedback_and_shared_controller(self):
        h,d,ctl,a=self.compose()
        values={k:variant(2,k*10) for k in range(1,7)}
        pointer,a.reader.next_node=self.tree(values)
        self.assertEqual(a.reader.fields(pointer),values)
        pointer,a.reader.next_node=self.tree({0xA1E5A149:variant(3),0xD6FCF3E4:variant(2,7)})
        self.assertEqual(a.dispatch(h.pointer,0x237DDDA8,pointer),0)
        self.assertEqual(a.count,1)
        local=C.WINFUNCTYPE(C.c_uint32,C.c_void_p)(h.vtable[0xD0//8])
        self.assertEqual(local(h.pointer),7)
        self.assertIs(ctl.turn_begin_state,d.turn_begin_state)
        self.assertEqual(ctl.controller_flag(h.pointer),0)
        d.turn_begin_state.controller_byte_0d=0xA5
        self.assertEqual(ctl.controller_flag(h.pointer),0xA5)
        d.cache_update(h.pointer,7,(9<<32)|3)
        seen=[]
        def invoke(target,receiver,args):
            self.assertEqual((target,receiver),(self.base+0x591920,self.context))
            seen.append(tuple(args))
        def dispatch(*args,**kwargs):
            return dispatch_cache_update_payload(*args,**kwargs,invoke=invoke)
        with patch('civ6_host.runtime.native.native_cache_update_dispatch.dispatch_cache_update_payload',side_effect=dispatch):
            self.assertEqual(d.drain(),1)
        self.assertEqual(seen,[(7,0,3,9)])
        self.assertEqual((d.consumed_count,len(d.pending)),(1,0))
        d.host_notification(h.pointer,0x5A9A0329)
        with self.assertRaises(RuntimeError):a.close()
        d.host_notification_end(h.pointer,0x5A9A0329)
        d.host_notification_end(h.pointer,0x5A9A0329)
        a.close();ctl.close();d.close()
        self.assertEqual(list(h.vtable),self.original_slots)
        self.assertEqual(h._slot_bindings,self.original_bindings)

    def test_foreign_code_owner_empty_registry_and_changed_layout_refuse(self):
        self.memory()
        self.put(self.base+0xB61E18,struct.pack('<I',0))
        with self.assertRaisesRegex(ValueError,'uninitialized'):
            source.verify_cache(self.base,self.context,self.read)
        self.put(self.base+0xB61E18,struct.pack('<I',1))
        self.put(self.base+0xB8AA60,struct.pack('<Q',0x2010))
        with self.assertRaisesRegex(ValueError,'owner'):
            source.verify_control(self.base,self.context,self.read,host_pointer=123)
        self.put(self.base+0xB8AA60,struct.pack('<Q',self.inner))
        self.put(self.base+0x994DB4,b'\0')  # The previously omitted iterator branch.
        with self.assertRaisesRegex(ValueError,'live code'):
            source.verify_reader(self.base,self.read)
        proof=_copy(source.source());proof['deferred']['cache_registry']['receiver']=0
        with patch.object(source,'_source',return_value=proof),self.assertRaises(ValueError):
            source.source()

    def test_cache_drain_reuses_sources_but_rechecks_registry_per_record(self):
        host, deferred, _, _ = self.compose()
        deferred.cache_update(host.pointer, 7, (9 << 32) | 3)
        deferred.cache_update(host.pointer, 7, (10 << 32) | 3)
        invoked = []

        def invoke(target, receiver, args):
            invoked.append(tuple(args))
            self.put(self.base + 0xB61E18, struct.pack('<I', 0))

        def dispatch(*args, **kwargs):
            return dispatch_cache_update_payload(*args, **kwargs, invoke=invoke)

        with (patch.object(source, '_validated_source', wraps=source._validated_source) as validation,
              patch('civ6_host.runtime.native.native_cache_update_dispatch.dispatch_cache_update_payload',
                    side_effect=dispatch)):
            with self.assertRaisesRegex(ValueError, 'uninitialized'):
                deferred.drain()
            self.assertEqual(validation.call_count, 1)
        self.assertEqual(invoked, [(7, 0, 3, 9)])
        self.assertTrue(deferred._deferred_drain_poisoned)
        self.assertIsNone(source._CACHE_DISPATCH_SCOPE.get())

    def test_unknown_a0_event_is_not_returned_as_success(self):
        h,d,ctl,a=self.compose()
        pointer,a.reader.next_node=self.tree({0x77777777:variant(2,9)})
        with self.assertRaises(ValueError):a.dispatch(h.pointer,0xDEADBEEF,pointer)
        self.assertTrue(a.quarantined)
        self.assertEqual(a.count,0)
        self.assertEqual(d.pending,[])

    def test_update_reuses_static_cache_proof_but_checks_live_context_each_time(self):
        from civ6_host.runtime import retained_game_source, xp2_cache_source

        profile = xp2_cache_source.source()['profile']
        ownership = profile['ownership']
        base, context, inner, service, owner, game = 0x300000000, 0x1000, 0x2000, 0x3000, 0x4000, 0x5000
        values = {
            context: base + profile['outer_vtable_rva'],
            context + 8: inner,
            inner: base + profile['inner_vtable_rva'],
            base + ownership['inner_global_rva']: inner,
            inner + 0x1A68: service,
            service: base + ownership['service_vtable_rva'],
            base + ownership['service_global_rva']: service,
            service + 8: owner,
            owner: base + ownership['owner_vtable_rva'],
            owner + 0x20: service,
            inner + 0x60: game,
            base + ownership['game_global_rva']: game,
        }

        def read(address, size):
            self.assertEqual(size, 8)
            return struct.pack('<Q', values[address])

        with patch.object(xp2_cache_source, '_verified_source',
                          wraps=xp2_cache_source._verified_source) as verify:
            with xp2_cache_source.update_source_scope():
                self.assertEqual(retained_game_source.context_state(
                    base, context, read, core_sha256=XP2_CORE_SHA256)['game'], game)
                values[base + ownership['game_global_rva']] = 0
                with self.assertRaisesRegex(ValueError, 'live identity differs'):
                    retained_game_source.context_state(base, context, read, core_sha256=XP2_CORE_SHA256)
                self.assertEqual(verify.call_count, 1)
            self.assertEqual(verify.call_count, 2)

    def test_cache_source_scope_rejects_changed_dependency_before_publication(self):
        from civ6_host.runtime import xp2_cache_source
        from civ6_host.runtime.paths import resource_root

        proof = _copy(xp2_cache_source.source())
        original = b'original pinned contents'
        with TemporaryDirectory(dir=resource_root()/'work') as temp:
            dependency = Path(temp)/'source.txt'
            dependency.write_bytes(original)
            proof['references'] = {'test': {
                'path': dependency.relative_to(resource_root()).as_posix(),
                'sha256': hashlib.sha256(original).hexdigest(),
            }}
            with patch.object(xp2_cache_source, '_source', return_value=proof):
                with self.assertRaisesRegex(ValueError, 'cache source dependency differs'):
                    with xp2_cache_source.update_source_scope():
                        dependency.write_bytes(b'changed contents')
                with self.assertRaisesRegex(ValueError, 'cache source dependency differs'):
                    xp2_cache_source.source()


if __name__=='__main__':unittest.main()
