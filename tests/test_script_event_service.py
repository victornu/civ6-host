"""Lifecycle and retained payload contracts; native HKS has a grouped receipt."""
import ast
import ctypes as C
import importlib.util
from pathlib import Path
import threading
import struct
import types
import unittest
from unittest.mock import Mock

from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.native.native_host import DiagnosticHost
from civ6_host.runtime.native.native_map_script import NativeMapScriptPrefix, NativeGameEventCallbacks
from civ6_host.runtime.script_event_service import ScriptEventService
from civ6_host.runtime import script_event_source


class Host:
    _bind = DiagnosticHost._bind

    def __init__(self):
        self.aux_vtable = (C.c_void_p*32)()
        self.aux_object = (C.c_void_p*2)(C.addressof(self.aux_vtable),1)
        self.functions, self.emit = [], Mock()
        for slot in ScriptEventService.SLOTS:
            self._bind(self.aux_vtable,slot,None,[C.c_void_p],lambda _:None)

    def _fatal(self, *args, **kwargs):
        raise AssertionError((args,kwargs))


class ScriptEventServiceTests(unittest.TestCase):
    def test_qualification_ledger_preserves_lifecycle_and_gameplay_names(self):
        path=Path(__file__).resolve().parents[1]/'tools/qualify_xp1_configuration.py'
        spec=importlib.util.spec_from_file_location('event_qualification_telemetry',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        rows=[]
        def emit(event_name,**fields):rows.append(dict(event_name=event_name,**fields))
        host=types.SimpleNamespace(emit=emit)
        module.event_telemetry(host,'native_game_event_dispatched',event_name='Example',result_non_nil=False)
        self.assertEqual(rows,[{'event_name':'native_game_event_dispatched',
                              'gameplay_event_name':'Example','result_non_nil':False}])
        with self.assertRaisesRegex(ValueError,'Ambiguous'):
            module.event_telemetry(host,'event',event_name='Example',gameplay_event_name='Other')

    def test_xp1_source_bytes_and_installed_interfaces_are_both_required(self):
        base=0x200000000; cells={}; proof=script_event_source.source()
        for name in script_event_source.FUNCTIONS:
            body=proof['functions']['xp1'][name]
            for fragment in body.get('fragments',[body]):
                for instruction in fragment['instructions']:
                    raw=bytes.fromhex(instruction['bytes'])
                    cells[base+int(instruction['va'],16)-0x180000000,len(raw)]=raw
        cells[base+0x9F2640,8]=struct.pack('<Q',0x1000)
        cells[base+0x9F2648,8]=struct.pack('<Q',0x2000)
        read=lambda address,size:cells[address,size]
        def verify():return script_event_source.verify_xp1(base,read,host_pointer=0x1000,auxiliary_pointer=0x2000)
        self.assertFalse(verify()['saved_game_load_admitted'])
        cells[base+0x9F2648,8]=bytes(8)
        with self.assertRaisesRegex(ValueError,'global'):verify()
        cells[base+0x9F2648,8]=struct.pack('<Q',0x2000)
        first=next(iter(cells));cells[first]=bytes(first[1])
        with self.assertRaisesRegex(ValueError,'code differs'):verify()

    def fixture(self):
        host=Host()
        runtime=types.SimpleNamespace(registry=types.SimpleNamespace(_check=Mock()),
            dispatch_game_event_result=Mock(return_value=(True,0)))
        previous=dict(host._slot_bindings); old_functions=tuple(host.functions)
        service=ScriptEventService(host,runtime)
        return host,runtime,service,previous,old_functions

    def test_extracted_methods_have_identical_ast_and_old_prefix_inherits_them(self):
        old=ast.parse((resource_root()/'civ6rl/native_map_script.py').read_text(encoding='utf-8'))
        new=ast.parse(Path(__import__(NativeMapScriptPrefix.__module__,fromlist=['x']).__file__).read_text(encoding='utf-8'))
        def methods(tree, cls):
            c=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
            return {n.name:n for n in c.body if isinstance(n,ast.FunctionDef)}
        oldm=methods(old,'NativeMapScriptPrefix'); newm=methods(new,'NativeGameEventCallbacks')
        for name in ('check','game_event_call','game_event_test_all'):
            a,b=oldm[name],newm[name]
            # Extraction changes only the local import's package path.
            for n in ast.walk(b):
                if isinstance(n,ast.ImportFrom): n.module='native_script_arguments';n.level=1
            self.assertEqual(ast.dump(a),ast.dump(b))
            self.assertIs(getattr(NativeMapScriptPrefix,name),getattr(NativeGameEventCallbacks,name))

    def test_restores_slots_metadata_and_callback_roots_without_newgame(self):
        h,r,s,previous,functions=self.fixture()
        with self.assertRaisesRegex(ValueError,'owner'):ScriptEventService(h,r)
        s.close();s.close()
        self.assertEqual(h._slot_bindings,previous)
        self.assertEqual(tuple(h.functions),functions)
        for (table,slot),(address,callback) in previous.items():self.assertEqual(h.aux_vtable[slot//8],address)
        with self.assertRaisesRegex(ValueError,'closed'):s.script_arguments._create(C.addressof(h.aux_object))

    def test_live_payload_blocks_close_then_release_restores_service(self):
        h,r,s,_,_=self.fixture();owner=C.addressof(h.aux_object)
        payload=s.script_arguments._create(owner)
        with self.assertRaisesRegex(ValueError,'live payload'):s.close()
        s.script_arguments._release(owner,payload);s.close()

    def test_thread_slot_and_inflight_guards_prevent_unsafe_teardown(self):
        h,r,s,_,_=self.fixture();errors=[]
        def wrong_thread():
            for fn in (s.close,lambda:s.script_arguments._create(C.addressof(h.aux_object))):
                try:fn()
                except ValueError as error:errors.append(str(error))
        t=threading.Thread(target=wrong_thread);t.start();t.join()
        self.assertEqual(len(errors),2)
        s.dispatch_depth=1
        with self.assertRaisesRegex(ValueError,'dispatch'):s.close()
        s.dispatch_depth=0;h.aux_vtable[0x60//8]=123
        with self.assertRaisesRegex(ValueError,'ownership'):s.close()
        h.aux_vtable[0x60//8]=s.installed[0x60];s.close()

    def test_inherited_call_and_testall_keep_nil_output_distinction(self):
        h,r,s,_,_=self.fixture();owner=C.addressof(h.aux_object)
        payload=s.script_arguments._create(owner)
        s.script_arguments._append(payload,payload,0xffffffff)
        out=C.c_uint8(0xa5);r.dispatch_game_event_result.return_value=(False,0)
        self.assertFalse(s.game_event_call(owner,b'Event',payload,C.addressof(out)))
        self.assertEqual(out.value,0)
        out.value=0xa5;r.dispatch_game_event_result.return_value=(False,0xa5)
        self.assertFalse(s.game_event_test_all(owner,b'Event',payload,C.addressof(out)))
        self.assertEqual(out.value,0xa5)
        r.dispatch_game_event_result.assert_called_with(b'Event',(0xffffffff,),method='TestAll',output_initial=0xa5)
        s.script_arguments._release(owner,payload);s.close()


# Retained factory ABI/refusal cases exercise the newly shared product import.
retained=types.ModuleType('retained_script_argument_tests')
raw=(resource_root()/'tests/test_native_script_arguments.py').read_text(encoding='utf-8')
raw=raw.replace('from civ6rl.native_script_arguments import (',
                'from civ6_host.runtime.native.native_script_arguments import (',1)
exec(compile(raw,'<retained script argument tests>','exec'),retained.__dict__)


def load_tests(loader, tests, pattern):
    tests.addTests(loader.loadTestsFromTestCase(retained.NativeScriptArgumentsTests))
    return tests
