"""Offline dispatch/source tests. No native call or loaded-cache qualification."""
import ctypes as C
from dataclasses import FrozenInstanceError, replace
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import postload160_source as source
from civ6_host.runtime.native import native_checkpoint_postload160 as post
from civ6_host.runtime.native import native_official_postload as official


class Post160SourceTests(unittest.TestCase):
    def test_exact_profile_and_runtime_refusal_are_separate(self):
        base = source.profile_for_sha(source.BASE_CORE_SHA256)
        xp1 = source.profile_for_sha(source.XP1_CORE_SHA256)
        self.assertEqual((xp1.outer_vtable_rva,xp1.outer_slot,xp1.target_rva,
                          xp1.inner_vtable_rva,xp1.inner_slot,xp1.inner_target_rva),
                         (0x8A8DF0,0x160,0x4BD5C0,0x8D7168,0x60,0x3D300))
        self.assertIs(source.require_runtime_admission(base),base)
        with self.assertRaisesRegex(ValueError,'AUX\\+90 category2/NULL'):
            source.require_runtime_admission(xp1)
        with self.assertRaises(ValueError):
            source.require_runtime_admission(replace(base,target_rva=xp1.target_rva))
        with self.assertRaises(FrozenInstanceError):
            xp1.target_rva=0
        for value in (None,False,[], '0'*64):
            with self.subTest(value=value), self.assertRaises(ValueError):
                source.profile_for_sha(value)

    def test_retained_complete_route_is_not_inner_script_postload_or_one_byte_leaf(self):
        p=source.xp1_source()
        c=p['contract'];f=p['functions']['xp1']
        self.assertEqual((f['transition']['fragment_count'],f['transition']['total_length']),(7,469))
        self.assertEqual(c['outer_slot'],0x160)
        self.assertEqual(c['inner_slot'],0x60)
        self.assertEqual((c['callback']['raw_kind'],c['callback']['category'],c['callback']['arguments']),(1,2,None))
        self.assertTrue(c['callback']['own_core_scope_bracketing'])
        self.assertFalse(c['post160_runtime_admitted'])
        self.assertFalse(c['full_load_admitted'])

    def memory(self):
        proof=source.xp1_source();base=0x200000000;cells={}
        for body in proof['functions']['xp1'].values():
            for fragment in source._body(body)['fragments']:
                for row in fragment['instructions']:
                    raw=bytes.fromhex(row['bytes'])
                    cells[base+int(row['va'],16)-source.CORE_IMAGE_BASE,len(raw)]=raw
        for row in proof['tables']['xp1'].values():
            cells[base+row['vtable_rva']+row['slot'],8]=struct.pack('<Q',base+row['target_rva'])
        for address,literal in proof['literals'].items():
            cells[base+int(address,16)-source.CORE_IMAGE_BASE,literal['bytes']]=literal['text'].encode()+b'\0'
        return proof,base,cells

    def test_complete_code_and_virtual_targets_are_compared_without_dispatch(self):
        proof,base,cells=self.memory()
        read=lambda address,size:cells[address,size]
        source.verify_xp1_live(base,read,proof,core_sha256=source.XP1_CORE_SHA256)
        # Mutate a late fragment that a first-RET capture would miss.
        row=proof['functions']['xp1']['transition']['fragments'][-1]['instructions'][0]
        key=(base+int(row['va'],16)-source.CORE_IMAGE_BASE,len(bytes.fromhex(row['bytes'])))
        cells[key]=bytes(key[1])
        with self.assertRaisesRegex(ValueError,'instruction differs'):
            source.verify_xp1_live(base,read,proof,core_sha256=source.XP1_CORE_SHA256)

    def test_each_virtual_dispatch_and_event_name_is_pinned(self):
        proof,base,cells=self.memory()
        targets=[(base+r['vtable_rva']+r['slot'],8) for r in proof['tables']['xp1'].values()]
        targets += [(base+int(a,16)-source.CORE_IMAGE_BASE,r['bytes']) for a,r in proof['literals'].items()]
        for key in targets:
            old=cells[key];cells[key]=bytes(key[1])
            with self.subTest(key=key), self.assertRaises(ValueError):
                source.verify_xp1_live(base,lambda a,n:cells[a,n],proof,core_sha256=source.XP1_CORE_SHA256)
            cells[key]=old

    def test_xp1_native_attempt_refuses_before_live_reads_or_function_binding(self):
        backend=post.NativePostload160Backend.__new__(post.NativePostload160Backend)
        backend.owner=SimpleNamespace(check_thread=Mock())
        backend.post160_abi=source.profile_for_sha(source.XP1_CORE_SHA256)
        with patch.object(post,'check_live_post160') as read, patch.object(C,'WINFUNCTYPE') as bind:
            with self.assertRaisesRegex(ValueError,'XP1 outer\\+160 is not admitted'):
                backend.call_post160_once()
            read.assert_not_called();bind.assert_not_called()

    def test_base_single_call_retains_void_uint8_and_one_attempt(self):
        backend=post.NativePostload160Backend.__new__(post.NativePostload160Backend)
        backend.owner=SimpleNamespace(check_thread=Mock(),busy=True,
            core=SimpleNamespace(_handle=0x200000000),context=0x300000000,
            runtime=SimpleNamespace(read=Mock()))
        backend.post160_abi=source.profile_for_sha(source.BASE_CORE_SHA256)
        backend.native_call_attempted=False;backend._facade_attempt=object();backend.proof=object()
        native=Mock(return_value=0xDEADBEEF);binder=Mock(return_value=native)
        with patch.object(post,'check_live_post160'), patch.object(C,'WINFUNCTYPE',return_value=binder) as signature:
            self.assertIsNone(backend.call_post160_once())
            signature.assert_called_once_with(None,C.c_void_p,C.c_uint8)
            binder.assert_called_once_with(0x200000000+0x42E4C0)
            native.assert_called_once_with(0x300000000,1)
            with self.assertRaisesRegex(RuntimeError,'first exclusive attempt'):
                backend.call_post160_once()
            native.assert_called_once()

    def test_official_adapter_cannot_turn_profile_metadata_into_admission(self):
        owner=SimpleNamespace(load_abi=SimpleNamespace(core_sha256=source.XP1_CORE_SHA256))
        with patch.object(post,'verify_source') as verify:
            with self.assertRaisesRegex(ValueError,'loaded cache facade publication'):
                official.OfficialPost160Backend(owner,object(),{})
            verify.assert_not_called()


if __name__=='__main__':
    unittest.main()
