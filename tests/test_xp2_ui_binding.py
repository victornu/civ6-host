"""Full-source/real-owner fixtures; no GameCore, Lua VM or host is executed."""
import ast
import ctypes as C
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import struct
import threading
from types import MethodType, SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import xp2_ui_binding_source as ui
from civ6_host.runtime import xp1_ui_binding as views
from civ6_host.runtime import profile_script_binding as game_binding
from civ6_host.runtime import script_binding_profiles as profiles
from civ6_host.runtime import core_script_services as services
from civ6_host.runtime.source_build_identity import verify_source_build
from civ6_host.runtime.native import native_probe, native_setup
from civ6_host.runtime.native.native_core_context_profiles import profile_for_core
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
from civ6_host.runtime.paths import resource_root
import extraction_xp1_ui_binding as hook
import build_native_host as builder
import test_profile_script_binding_integration as service_fixtures
import test_xp2_cache_publication as cache_fixtures
import test_xp2_player_view as view_fixtures

HOST=Path(__file__).resolve().parents[1]
BUILD=resource_root()/'work/native-host-xp2-ui-build01/civ6rl-native-python.exe'
BUILD_SHA='a3d977a4aa09d3f4f88a393f59e32f5a34d12d79db48606c39c4b9e09994f799'


class SourceMemory:
    def __init__(self):
        self.base=0x180000000;self.bytes={};self.proof=ui.source();self.reads=[]
        for _,body in ui._bodies(self.proof):
            for f in body['fragments']:
                self.put(self.base+int(f['start_rva'],16),bytes.fromhex(f['raw_hex']))
        for r in self.proof['slots']:
            self.put(self.base+r['table_rva']+r['slot'],struct.pack('<Q',self.base+r['target_rva']))
        for rva,row in self.proof['error_literals'].items():
            self.put(self.base+int(rva,16),bytes.fromhex(row['raw_hex']))

    def put(self,at,raw):self.bytes.update((at+i,b) for i,b in enumerate(raw))
    def read(self,at,size):
        # Match native_setup.local_reader, including in the composed binder.
        if not at or not 0<size<=native_setup.INNER_SIZE:
            raise ValueError('Invalid local native read')
        self.reads.append((at,size))
        return bytes(self.bytes[at+i] for i in range(size))


class UIProfileTests(unittest.TestCase):
    def test_complete_profile_and_transitive_dependencies(self):
        p=ui.source();pins=ui.source_dependencies()
        self.assertEqual(len(pins),23)
        for path,sha in pins.items():self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),sha)
        self.assertEqual(sum(b['bytes'] for _,b in ui._bodies(p)),43500)
        self.assertFalse(p['contract']['protected_registration']['enclosing_registration_tests_result'])
        self.assertFalse(p['contract']['error']['outer_zero_status_proves_all_nested_registrations'])
        self.assertEqual(p['abi']['ui_thunk_rva'],ui.UI_THUNK_RVA)

    def test_all_complete_bodies_slots_literals_are_read(self):
        m=SourceMemory();ui.verify_live(m.base,m.read)
        addresses=[]
        for name,b in ui._bodies(m.proof):
            f=b['fragments'][-1];addresses.append((name,m.base+int(f['start_rva'],16)+f['length']-1))
        addresses.extend(('slot',m.base+r['table_rva']+r['slot']) for r in m.proof['slots'])
        addresses.extend(('literal',m.base+int(rva,16)) for rva in m.proof['error_literals'])
        for label,address in addresses:
            with self.subTest(source=label):
                m.bytes[address]^=1
                with self.assertRaisesRegex(ValueError,'differs'):ui.verify_live(m.base,m.read)
                m.bytes[address]^=1
        with self.assertRaisesRegex(ValueError,'image/reader'):ui.verify_live(m.base+1,m.read)

    def test_hook_selects_xp2_without_changing_base_or_xp1_call(self):
        raw='class NativeScriptRuntime:\n def bind_native_ui_api(self,game_context,ui_context,core_context,core_library):\n  return original(game_context,ui_context,core_context,core_library)\n'
        generated=hook.parameterize('civ6rl.native_script_runtime',raw)
        tree=ast.parse(generated);fn=tree.body[0].body[0]
        self.assertEqual(ast.dump(fn.body[-1]),ast.dump(ast.parse(raw).body[0].body[0].body[0]))
        self.assertEqual(ast.literal_eval(fn.args.kw_defaults[0]),hook.BASE)
        original=Mock(return_value='base');namespace={'original':original}
        exec(compile(tree,'fixture','exec'),namespace);instance=namespace['NativeScriptRuntime']()
        args=tuple(object() for _ in range(4))
        with patch.object(ui,'bind_ui_api',return_value='xp2') as xp2,patch.object(views,'bind_xp1_ui_api',return_value='xp1') as xp1:
            self.assertEqual(instance.bind_native_ui_api(*args),'base')
            self.assertEqual(instance.bind_native_ui_api(*args,core_sha256=hook.XP1),'xp1')
            self.assertEqual(instance.bind_native_ui_api(*args,core_sha256=hook.XP2),'xp2')
            xp2.assert_called_once_with(instance,*args);xp1.assert_called_once_with(instance,*args)
            with self.assertRaisesRegex(ValueError,'not admitted'):instance.bind_native_ui_api(*args,core_sha256='0'*64)
        self.assertEqual(hook.parameterize('other',raw),raw)

    def test_large_registration_keeps_every_chunk_under_native_reader_bound(self):
        m=SourceMemory();ui.verify_live(m.base,m.read)
        self.assertLessEqual(max(size for _,size in m.reads),4096)
        large=max((f for _,b in ui._bodies(m.proof) for f in b['fragments']),key=lambda f:f['length'])
        self.assertGreater(large['length'],native_setup.INNER_SIZE)
        start=m.base+int(large['start_rva'],16);size=large['length']
        self.assertTrue(all((start+i,min(4096,size-i)) in m.reads for i in range(0,size,4096)))
        # Both the first byte beyond a boundary and the final partial chunk
        # must remain authenticated, not merely the first read of the body.
        for offset in (4096,size-1):
            m.bytes[start+offset]^=1
            with self.assertRaisesRegex(ValueError,'native body differs'):ui.verify_live(m.base,m.read)
            m.bytes[start+offset]^=1
        with self.assertRaisesRegex(ValueError,'native body differs'):
            ui.verify_live(m.base,lambda at,n:m.read(at,n)[:-1])

    def test_additive_build_preserves_all_old_components_and_exports(self):
        old=json.loads((HOST/'native/profiles/xp2-jobs/source-manifest.json').read_text())
        new=json.loads((HOST/'native/profiles/xp2-ui/source-manifest.json').read_text())
        self.assertEqual(len(builder.source_inputs(HOST,new)),len(old['sources'])+1)
        old_rows={r['build_path']:r for r in old['sources']}
        new_rows={r['build_path']:r for r in new['sources']}
        for key,row in old_rows.items():
            if key!='script_core_bindings_xp1.inc':self.assertEqual(new_rows[key],row)
        result=verify_source_build(BUILD,required_components={
            'script_core_ui_binding_profiles.inc':ui.UI_COMPONENT_SHA,
            'script_core_binding_profiles.inc':game_binding.PROFILE_COMPONENT_SHA,
            'script_core_bindings.inc':game_binding.SHARED_COMPONENT_SHA})
        self.assertEqual(result['host_sha256'],BUILD_SHA)
        self.assertFalse(result['native_compatibility_claimed'])
        raw=BUILD.read_bytes();pe=struct.unpack_from('<I',raw,0x3c)[0]
        count=struct.unpack_from('<H',raw,pe+6)[0]
        table=pe+24+struct.unpack_from('<H',raw,pe+20)[0]
        sections=[struct.unpack_from('<IIII',raw,table+40*i+8) for i in range(count)]
        def offset(rva):
            for _,start,size,at in sections:
                if start<=rva<start+size:return at+rva-start
            raise AssertionError('Export outside file-backed PE')
        export=offset(struct.unpack_from('<I',raw,pe+24+112)[0])
        count=struct.unpack_from('<I',raw,export+24)[0]
        table=offset(struct.unpack_from('<I',raw,export+32)[0]);names=set()
        for i in range(count):
            at=offset(struct.unpack_from('<I',raw,table+4*i)[0]);names.add(raw[at:raw.index(b'\0',at)])
        self.assertTrue({b'LAB_ProfileScriptCoreUIBindingsInstall',b'LAB_ProfileScriptCoreBindingsInstall',
            b'LAB_XP1ScriptCoreUIBindingsInstall',b'LAB_ScriptCoreUIBindingsInstall'}<=names)


class UIBinderTests(unittest.TestCase):
    def setUp(self):
        self.patches=ExitStack();self.addCleanup(self.patches.close)
        # Build the actual cache/publication/view graph with valid source addresses.
        with patch.object(cache_fixtures.XP1FixtureBackend,'outer',0x40000000),patch.object(
                cache_fixtures.XP1FixtureBackend,'inner',0x50000000):
            b,lease,pub,_=view_fixtures.PlayerViewTests().graph()
        self.backend=b;self.view=views.SavedPlayerView(pub);self.lease=lease
        p=b.prefix;rt=p.runtime;self.runtime=rt;self.prefix=p
        p.core_sha256=ui.XP2_CORE_SHA256
        self.game=p.game_child;self.child=object();p.ui_child=self.child
        self.view.child=self.child;self.view.attempted=True;b.stage=views.ACTIVE_STAGE;b.busy=True
        self.pointers={self.game:0x60001000,self.child:0x60002000}
        rt.root=0x60000000;self.stacks={rt.root:0,**{v:0 for v in self.pointers.values()}}
        rt.registry=NS(validate=lambda child:self.pointers[child],_check=Mock())
        rt.closed=False;rt.database_bound=rt.configuration_bound=rt.locale_bound=True
        rt._profile_script_bind_attempted=True
        rt.lua={'gettop':lambda p:self.stacks[p],'settop':lambda p,n:self.stacks.__setitem__(p,n)}
        rt._status=MethodType(NativeScriptRuntime._status,rt);rt.emit=Mock()
        self.version=Mock(return_value=1);self.install=Mock(return_value=0)
        rt.host=NS(LAB_ProfileScriptCoreBindingsVersion=self.version,LAB_ProfileScriptCoreUIBindingsInstall=self.install)
        b.core._name=str(service_fixtures.CORE)
        selected=profile_for_core(b.core._name,mode='context')
        modules=[str(selected.core_path),*[str(selected.shared_dependency_directory/n) for n in selected.dependency_sha256]]
        sm=service_fixtures.ServiceMemory(profiles.profile_for_sha(ui.XP2_CORE_SHA256))
        self.memory=SourceMemory()
        for at,raw in sm.blocks.items():self.memory.put(at,raw)
        h=b.host;h.localization_initialized=True
        h.database=NS(_name=str(selected.shared_dependency_directory/'DatabaseDLL_FinalRelease.dll'),_handle=sm.database_base)
        h.localization_library=NS(_name=str(selected.shared_dependency_directory/'Localization_FinalRelease.dll'),_handle=sm.localization_base)
        symbol=services._source(services.TYPE_SOURCE)['create_connection_import']['symbol']
        setattr(h.database,symbol,C.c_void_p(sm.create_connection))
        rt._profile_borrowed_services=services.BorrowedCoreServices(rt,h,b.core,rt.root,b.context,
            sm.inner,sm.configuration,sm.gameplay,threading.get_ident(),services.INIT_SOURCE[1],services.TYPE_SOURCE[1])
        self.imports={};self.import_addresses={}
        for n,row in enumerate(self.memory.proof['imports'].values()):
            library=self.imports.setdefault(row['dll'],NS());target=0x7ffa00001000+n*16
            setattr(library,row['name'],C.c_void_p(target));self.import_addresses[row['name']]=target
            self.memory.put(sm.base+int(row['iat_rva'],16),struct.pack('<Q',target))
        rt.library=self.imports['HavokScript_FinalRelease.dll']
        rt.library._name=str(selected.shared_dependency_directory/'HavokScript_FinalRelease.dll')
        self.getter=Mock(return_value=sm.interface);self.native_addresses=[]
        def factory(*sig):
            def at(address):self.native_addresses.append(address);return self.getter
            return at
        self.patches.enter_context(patch.object(native_probe,'Windows',return_value=NS(modules=lambda:modules)))
        self.patches.enter_context(patch.object(native_setup,'local_reader',return_value=self.memory.read))
        self.patches.enter_context(patch.object(game_binding,'_current_executable',return_value=BUILD))
        self.patches.enter_context(patch.object(ui.C,'WINFUNCTYPE',side_effect=factory))
        self.patches.enter_context(patch.object(ui.C,'WinDLL',side_effect=lambda name:self.imports[name]))

    def bind(self):return ui.bind_ui_api(self.runtime,self.game,self.child,self.backend.context,self.backend.core)

    def test_real_shared_owners_source_imports_and_selected_protected_call(self):
        receipt=self.bind()
        self.assertEqual(self.native_addresses,[self.memory.base+0x590440])
        self.getter.assert_called_once_with(self.backend.context)
        self.install.assert_called_once_with(self.pointers[self.game],self.pointers[self.child],
            self.memory.base+0xb8f0e0,self.memory.base,2)
        self.assertEqual((receipt['core_sha256'],receipt['source_sha256'],receipt['method_rva']),
            (ui.XP2_CORE_SHA256,ui.SOURCE[1],hex(ui.UI_THUNK_RVA)))
        self.assertEqual(receipt['native_host_sha256'],BUILD_SHA)
        self.assertTrue(self.runtime._xp2_ui_bind_entered)
        self.assertFalse(receipt['complete_registration_verified'])
        self.assertFalse(receipt['gameplay_api_copied'])
        self.assertEqual([call.args[0] for call in self.runtime.emit.call_args_list],
            ['before_xp1_ui_api_bind','xp1_ui_api_bind_returned'])
        with self.assertRaisesRegex(ValueError,'fresh distinct'):self.bind()

    def test_replaced_service_view_children_and_borrowed_owner_refuse(self):
        cases=[(self.backend.host,'_saved_load_services',object()),
            (self.backend,'_xp1_player_view',NS(owner=self.backend)),
            (self.prefix,'game_child',object()),(self.prefix,'ui_child',object()),
            (self.runtime,'service_owner',object()),(self.view,'source_sha256','0'*64),
            (self.view,'completed',True)]
        for owner,name,value in cases:
            with self.subTest(field=name),patch.object(owner,name,value),self.assertRaises((ValueError,KeyError)):
                self.bind()
            self.getter.assert_not_called();self.install.assert_not_called()
            self.assertFalse(getattr(self.runtime,'_xp2_ui_bind_entered',False))

    def test_stack_source_slot_import_build_and_version_refuse_before_getter(self):
        for pointer in self.stacks:
            self.stacks[pointer]=1
            with self.assertRaisesRegex(ValueError,'managed children'):self.bind()
            self.stacks[pointer]=0
        addresses=[self.memory.base+ui.UI_THUNK_RVA,self.memory.base+0xa126c8+0x18,self.memory.base+0x9b7038]
        for at in addresses:
            self.memory.bytes[at]^=1
            with self.assertRaisesRegex(ValueError,'differs'):self.bind()
            self.memory.bytes[at]^=1
        with patch.object(ui,'UI_COMPONENT_SHA','0'*64),self.assertRaisesRegex(ValueError,'component'):self.bind()
        self.version.return_value=2
        with self.assertRaisesRegex(ValueError,'ABI version'):self.bind()
        self.getter.assert_not_called();self.install.assert_not_called()

    def test_foreign_interface_consumes_attempt_and_outer_error_is_not_success(self):
        self.getter.return_value+=8
        with self.assertRaisesRegex(ValueError,'foreign interface'):self.bind()
        self.assertTrue(self.runtime._xp2_ui_bind_entered);self.install.assert_not_called()
        with self.assertRaisesRegex(ValueError,'fresh distinct'):self.bind()

    def test_actual_protected_error_is_retained_and_retry_refused(self):
        self.install.return_value=-1751
        with self.assertRaisesRegex(RuntimeError,'native status -1751'):self.bind()
        self.assertTrue(self.runtime._xp2_ui_bind_entered)
        self.assertEqual([c.args[0] for c in self.runtime.emit.call_args_list],['before_xp1_ui_api_bind'])
        with self.assertRaisesRegex(ValueError,'fresh distinct'):self.bind()

    def test_nonempty_native_return_never_emits_success(self):
        def dirty(*args):self.stacks[self.pointers[self.child]]=1;return 0
        self.install.side_effect=dirty
        with self.assertRaisesRegex(RuntimeError,'nonempty Lua stack'):self.bind()
        self.assertEqual([c.args[0] for c in self.runtime.emit.call_args_list],['before_xp1_ui_api_bind'])


if __name__=='__main__':unittest.main(verbosity=2)
