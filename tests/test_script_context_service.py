import ctypes as C
import hashlib
from pathlib import Path
import struct
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime.script_context_service import ScriptContextService, snapshot_scripts, script_name
from civ6_host.runtime.native.native_gameplay_script_registry import NativeGameplayScriptRegistry, GameplayScriptEntry
from civ6_host.runtime.native.native_context_lifetime import RetainedScriptContexts
from civ6_host.runtime import script_context_source
import test_script_event_service as event_tests


class ContextServiceTests(unittest.TestCase):
    def test_utf8_stem_uses_whole_character_prefix_and_final_extension(self):
        self.assertEqual(script_name(Path('A.b.lua')),b'A.b')
        self.assertEqual(script_name(Path('漢'*100+'.lua')),('漢'*86).encode())

    def fixture(self, wire_paths=None):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        root=Path(temp.name);p=root/'Un.é.lua';p.write_bytes(b'answer=42')
        registry=NativeGameplayScriptRegistry([root],selected_scripts=[GameplayScriptEntry(root,p.name)]*2,
                                              wire_paths=wire_paths)
        self.addCleanup(registry.close)
        host=event_tests.Host(); host._script_context_service=None
        states={};claims={};owner_thread=threading.get_ident()
        def check():
            if threading.get_ident()!=owner_thread:raise RuntimeError('cross-thread')
        def acquire():
            child=SimpleNamespace(pointer=0x1000+len(states)*0x100,active=True)
            states[child.pointer]=child;return child
        def validate(c):
            check()
            if states.get(c.pointer) is not c:raise ValueError('foreign')
            return c.pointer
        def claim(c,token):validate(c);claims[c.pointer]=token
        def release(c,owner=None):
            validate(c)
            if claims[c.pointer] is not owner:raise ValueError('wrong owner')
            del states[c.pointer];del claims[c.pointer];c.active=False
        rt=SimpleNamespace(closed=False,context_owner=None,notification_service=None,host=SimpleNamespace(),
            registry=SimpleNamespace(_check=check,validate=validate,claim=claim,release=release),
            acquire=acquire,execute=Mock())
        with patch('civ6_host.runtime.native.native_context_lifetime.verify_loaded_host'), \
             patch('civ6_host.runtime.script_context_service.NativeContextNotification'):
            service=ScriptContextService(host,rt,registry,
                expected_hashes={p:hashlib.sha256(p.read_bytes()).hexdigest()},bootstrap=Mock(),read=C.string_at)
        return host,rt,service,registry,p

    def test_shared_owner_loads_exact_snapshot_and_requires_native_release(self):
        h,r,s,g,p=self.fixture();this=s.receiver
        self.assertIsInstance(s.lifetime,RetainedScriptContexts)
        self.assertEqual(s.script_count(this),2)
        self.assertEqual(s.file_exists(this,g.get(0),1),1)
        ptr=s.acquire(this,script_name(p),0)
        self.assertEqual(s.load(this,ptr,g.get(0)),1)
        self.assertEqual(r.execute.call_args.args[1],b'answer=42')
        with self.assertRaisesRegex(RuntimeError,'still owned'):s.close()
        with self.assertRaisesRegex(ValueError,'fresh'):s.load(this,ptr,g.get(0))
        s.release(this,ptr);s.close();s.close()
        self.assertIsNone(r.context_owner)
        self.assertIsNone(h._script_context_service)

    def test_missing_mismatched_unselected_paths_never_report_success(self):
        h,r,s,g,p=self.fixture();this=s.receiver
        with self.assertRaisesRegex(ValueError,'hashes'):snapshot_scripts(g,{})
        with self.assertRaisesRegex(ValueError,'identity'):snapshot_scripts(g,{p:'0'*64})
        raw=C.create_string_buffer(str(p.with_name('Other.lua')).encode('utf-16-le')+b'\0\0')
        with self.assertRaisesRegex(ValueError,'unselected'):s.file_exists(this,C.addressof(raw),1)
        with self.assertRaisesRegex(ValueError,'resolution'):s.file_exists(this,g.get(0),0)
        p.unlink()
        with self.assertRaisesRegex(ValueError,'disappeared'):s.file_exists(this,g.get(0),1)
        s.close()

    def test_partial_execution_quarantines_no_cleanup_or_success(self):
        h,r,s,g,p=self.fixture();this=s.receiver
        ptr=s.acquire(this,script_name(p),0)
        r.execute.side_effect=RuntimeError('Lua failed')
        with self.assertRaisesRegex(RuntimeError,'Lua failed'):s.load(this,ptr,g.get(0))
        self.assertTrue(s.quarantined)
        self.assertIn(ptr,s.lifetime._contexts)
        with self.assertRaisesRegex(RuntimeError,'quarantined'):s.close()
        with self.assertRaisesRegex(RuntimeError,'quarantined'):s.release(this,ptr)

    def test_foreign_context_flags_receiver_and_thread_fail_before_effect(self):
        h,r,s,g,p=self.fixture();this=s.receiver
        for fn in (lambda:s.acquire(this,b'Map Script',0),lambda:s.acquire(this,script_name(p),1),
                   lambda:s.release(this,999),lambda:s.script_count(999)):
            with self.assertRaises(ValueError):fn()
        errors=[]
        def other():
            try:s.close()
            except RuntimeError as e:errors.append(str(e))
        t=threading.Thread(target=other);t.start();t.join()
        self.assertEqual(errors,['cross-thread'])
        self.assertFalse(r.execute.called);s.close()

    def test_source_identity_and_installed_manager_are_required(self):
        base=0x200000000;inner=0x400000000;aux=0x410000000;manager=0x420000000
        cells={};proof=script_context_source.source()
        from civ6_host.runtime.configuration_profiles import _body
        for body in script_context_source.live_bodies(proof).values():
            for fragment in _body(body)['fragments']:
                for ins in fragment['instructions']:
                    raw=bytes.fromhex(ins['bytes']);cells[base+int(ins['va'],16)-0x180000000,len(raw)]=raw
        for address,value in ((base+0x9F2620,inner),(base+0x9F2648,aux),(inner+0x1A58,manager)):
            cells[address,8]=struct.pack('<Q',value)
        cells[manager,0x30]=bytes(0x30)
        def verify():return script_context_source.verify_xp1(base,lambda a,n:cells[a,n],inner=inner,auxiliary=aux)
        self.assertEqual(verify(),manager)
        cells[inner+0x1A58,8]=bytes(8)
        with self.assertRaisesRegex(ValueError,'not constructed'):verify()
        cells[inner+0x1A58,8]=struct.pack('<Q',manager)
        first=next(iter(cells));cells[first]=bytes(first[1])
        with self.assertRaisesRegex(ValueError,'code differs'):verify()
