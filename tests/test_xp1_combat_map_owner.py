"""Shared map lifetime and XP1 F8 FIFO, with only native memory/calls simulated."""
import ast
import ctypes as C
import hashlib
from pathlib import Path
import struct
import threading
import types
import unittest

from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as BASE, XP1_CORE_SHA256 as XP1, XP2_CORE_SHA256 as XP2
from civ6_host.runtime import combat_map_profiles as profiles
from civ6_host.runtime.native import native_combat_map_owner as maps
from civ6_host.runtime.native.native_combat_receiver import BASE_STATE
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.a0_family_service import A0FamilyService
from civ6_host.runtime.event_argument_service import EventArgumentService
import test_deferred_service as deferred_tests


def memory_fixture(engine=XP1):
    """Reuse retained Base memory simulator with its primitive constants selected."""
    abi=profiles.profile_for_sha(engine)
    shim=types.SimpleNamespace(SIZE=maps.SIZE,VTABLE_RVA=abi.vtable_rva,
        CTOR_RVA=abi.constructor_rva,ASSIGN_RVA=abi.assign_rva,DTOR_RVA=abi.destructor_rva,
        verify_source_evidence=lambda:maps.verify_source_evidence(core_sha256=engine))
    path=resource_root()/'tests/test_native_combat_map_owner.py'
    tree=ast.parse(path.read_text(encoding='utf-8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='CombatMapMemory')
    ns={'C':C,'struct':struct,'combat_map':shim}
    exec(compile(ast.Module(body=[cls],type_ignores=[]),str(path),'exec'),ns)
    memory=ns['CombatMapMemory']()
    # Retained fixture's one literal Base copy slot is engine-selected here.
    memory.qword(memory.base+abi.vtable_rva+0x178,memory.base+abi.copy_rva)
    memory.abi=abi;memory.engine=engine
    return memory


def new_owner(memory,core=None,**kwargs):
    return maps.NativeCombatMapOwner(core or types.SimpleNamespace(_handle=memory.base),memory.source,
        read=memory.read,call=memory.call,**kwargs)


def f8_record(sequence,token):
    row=bytearray(128)
    struct.pack_into('<IIII',row,0,128,0xF8,sequence,0)
    struct.pack_into('<I',row,80,sequence)
    struct.pack_into('<I',row,120,token)
    return bytes(row)


class NativeMapTests(unittest.TestCase):
    def test_selected_primitives_preserve_default_base_and_exact_return_abi(self):
        for engine in (BASE,XP1):
            with self.subTest(engine=engine):
                m=memory_fixture(engine)
                kwargs={} if engine==BASE else {'core_sha256':engine}
                owner=new_owner(m,**kwargs)
                self.assertEqual(owner.core_sha256,engine)
                self.assertEqual(m.read(m.source,88),m.read(owner.pointer,88))
                self.assertNotEqual(owner.pointer,m.source)
                owner.close();owner.close()
                self.assertEqual([c[0] for c in m.calls],[m.abi.constructor_rva,m.abi.assign_rva,m.abi.destructor_rva])
                self.assertEqual([(c[1],c[2]) for c in m.calls],[(C.c_void_p,()),(C.c_void_p,(C.c_void_p,)),(None,())])

    def test_instruction_slot_source_and_unknown_engine_refuse_before_calls(self):
        changes=(lambda m:m.qword(m.source,m.base+m.abi.vtable_rva+8),
                 lambda m:m.qword(m.base+m.abi.vtable_rva+0x178,m.base+m.abi.assign_rva),
                 lambda m:m.put(m.base+m.abi.destructor_rva,b'\x00'))
        for change in changes:
            m=memory_fixture();change(m)
            with self.assertRaises(ValueError):new_owner(m,core_sha256=XP1)
            self.assertEqual(m.calls,[])
        m=memory_fixture()
        for engine in ('unknown',None):
            with self.assertRaises(ValueError):new_owner(m,core_sha256=engine)
            with self.assertRaises(ValueError):maps.CombatMapRegistry(core_sha256=engine)
        self.assertEqual(m.calls,[])

    def test_partial_failure_and_canaries_do_not_guess_cleanup(self):
        for stage in ('constructor_rva','assign_rva'):
            m=memory_fixture();m.fail_at=getattr(m.abi,stage)
            with self.assertRaises(RuntimeError) as error:new_owner(m,core_sha256=XP1)
            owner=error.exception.native_combat_map_owner
            self.assertTrue(owner.poisoned)
            self.assertNotIn(m.abi.destructor_rva,[c[0] for c in m.calls])
        m=memory_fixture();m.corrupt_guard_at=m.abi.assign_rva
        with self.assertRaisesRegex(RuntimeError,'guarded'):new_owner(m,core_sha256=XP1)
        self.assertNotIn(m.abi.destructor_rva,[c[0] for c in m.calls])
        m=memory_fixture();owner=new_owner(m,core_sha256=XP1);m.corrupt_guard_at=m.abi.destructor_rva
        with self.assertRaisesRegex(RuntimeError,'guarded'):owner.close()
        with self.assertRaisesRegex(RuntimeError,'poisoned'):owner.close()
        self.assertEqual(sum(c[0]==m.abi.destructor_rva for c in m.calls),1)

    def test_registry_preserves_ownership_until_success_and_refuses_other_engine(self):
        m=memory_fixture();owner=new_owner(m,core_sha256=XP1)
        registry=maps.CombatMapRegistry(core_sha256=XP1)
        with self.assertRaisesRegex(ValueError,'another engine'):maps.CombatMapRegistry().insert(owner)
        token=registry.insert(owner)
        with self.assertRaisesRegex(ValueError,'distinct'):registry.insert(owner)
        self.assertIs(registry.lookup(token),owner)
        m.fail_at=m.abi.destructor_rva
        with self.assertRaises(RuntimeError):registry.release(token)
        self.assertTrue(registry.poisoned);self.assertIs(registry.entries[token][0],owner)
        with self.assertRaisesRegex(RuntimeError,'poisoned'):registry.release(token)
        self.assertEqual(sum(c[0]==m.abi.destructor_rva for c in m.calls),1)


class DeferredCombatTests(unittest.TestCase):
    def fixture(self):
        # Actual callbacks/guards/FIFO, replacing only the live native code checks.
        host,d,_,_=deferred_tests.DeferredServiceTests.fixture(self)
        m=memory_fixture();d.core._handle=m.base;d.base=m.base;d.read=m.read
        a=EventArgumentService.__new__(EventArgumentService)
        a.host,a.deferred,a.reader,a.emit=host,d,types.SimpleNamespace(read=m.read),d.emit
        a.thread=threading.get_ident();a.closed=a.quarantined=False;a.depth=a.count=0
        host._event_argument_owner=a
        host._bind(host.vtable,0xA0,C.c_int32,[C.c_void_p,C.c_uint32,C.c_void_p],a.dispatch)
        a.address=host.vtable[0xA0//8]
        a0=A0FamilyService(a,receiver_state=dict(BASE_STATE),pre_turn_immediate_state=dict(BASE_STATE),entity_listener_count=0)
        a.consumer=a0
        from civ6_host.runtime.combat_event_profile import event_profile
        a0.combat_event_profile=a0._combat_event_profile=event_profile()
        d.combat_map_registry=maps.CombatMapRegistry(core_sha256=XP1)
        return host,d,a0,m

    def append(self,d,m,*,core=None):
        owner=new_owner(m,core or d.core,core_sha256=XP1)
        token=d.combat_map_registry.insert(owner)
        record=f8_record(d._sequence+1,token)
        d._enqueue(record)
        return owner,token,record

    def test_actual_fifo_runs_post_hook_before_commit_and_releases_each_copy_once(self):
        host,d,a0,m=self.fixture()
        first,token1,row1=self.append(d,m);second,token2,row2=self.append(d,m)
        original=m.call
        def observed(*args):
            if args[0]-m.base==m.abi.destructor_rva:
                token=token1 if args[3]==first.pointer else token2
                self.assertIn(token,d.combat_map_registry.entries)
                self.assertEqual(d.pending[0],row1 if token==token1 else row2)
                self.assertEqual(d.consumed_count,0 if token==token1 else 1)
            return original(*args)
        first.call=second.call=observed
        self.assertEqual(d.drain(),2);self.assertEqual(d.drain(),0)
        self.assertTrue(first.closed and second.closed)
        self.assertEqual(d.combat_map_registry.entries,{})
        self.assertEqual(d.pending,[]);self.assertEqual(d.consumed_bytes,256)
        self.assertEqual(d.consumed_digest.hexdigest(),hashlib.sha256(row1+row2).hexdigest())
        self.assertEqual(sum(c[0]==m.abi.destructor_rva for c in m.calls),2)
        with self.assertRaisesRegex(RuntimeError,'borrows'):d.close()

    def test_failure_retains_head_and_owned_map_without_retry(self):
        host,d,a0,m=self.fixture();owner,token,row=self.append(d,m)
        m.fail_at=m.abi.destructor_rva
        with self.assertRaises(RuntimeError):d.drain()
        self.assertEqual(d.pending,[row]);self.assertEqual(d.consumed_count,0)
        self.assertIs(d.combat_map_registry.entries[token][0],owner)
        self.assertTrue(d.combat_receiver.poisoned and d.combat_map_registry.poisoned)
        with self.assertRaisesRegex(RuntimeError,'poisoned'):d.drain()
        with self.assertRaisesRegex(RuntimeError,'poisoned'):d.close()
        self.assertEqual(sum(c[0]==m.abi.destructor_rva for c in m.calls),1)

    def test_foreign_owner_profile_receiver_and_active_producer_refuse_without_release(self):
        mutations=(lambda h,d,a,m:setattr(a,'_combat_event_profile',object()),
                   lambda h,d,a,m:setattr(a,'active_kind',0x8256DBE1),
                   lambda h,d,a,m:setattr(a.arguments,'depth',1),
                   lambda h,d,a,m:setattr(d,'combat_receiver',object()),
                   lambda h,d,a,m:setattr(h,'_a0_family_owner',None))
        for mutate in mutations:
            host,d,a0,m=self.fixture();owner,token,row=self.append(d,m);mutate(host,d,a0,m)
            with self.assertRaises((ValueError,RuntimeError,TypeError)):d.drain()
            self.assertEqual(d.pending,[row]);self.assertFalse(owner.closed)
            self.assertNotIn(m.abi.destructor_rva,[c[0] for c in m.calls])
        host,d,a0,m=self.fixture()
        owner,token,row=self.append(d,m,core=types.SimpleNamespace(_handle=m.base))
        with self.assertRaisesRegex(ValueError,'foreign native map'):d.drain()
        self.assertFalse(owner.closed);self.assertEqual(d.pending,[row])

    def test_unqueued_live_map_prevents_close_without_synthetic_release(self):
        host,d,a0,m=self.fixture();owner=new_owner(m,d.core,core_sha256=XP1)
        d.combat_map_registry.insert(owner)
        with self.assertRaisesRegex(RuntimeError,'live or uncertain combat'):d.close()
        self.assertFalse(owner.closed)
        self.assertNotIn(m.abi.destructor_rva,[c[0] for c in m.calls])


if __name__=='__main__':unittest.main()
