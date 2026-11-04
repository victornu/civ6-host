"""Grouped composition fixtures. No DLL, host executable or gameplay is run."""
import ast
import ctypes as C
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

from civ6_host.runtime import profile_script_binding as binding
from civ6_host.runtime import script_binding_profiles as profiles
from civ6_host.runtime import core_script_services as services
from civ6_host.runtime.native import native_core_context_profiles as contexts
from civ6_host.runtime.native import native_probe, native_setup
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
from test_script_binding_profiles import Memory

HOST = Path(__file__).resolve().parents[1]
CORE = Path("C:/Program Files (x86)/Steam/steamapps/common/Sid Meier's Civilization VI/DLC/Expansion2/Binaries/Win64/GameCore_XP2_FinalRelease.dll")
BUILD = HOST/'work/xp2-script-api/build01/civ6rl-native-python.exe'


class ServiceMemory(Memory):
    """Exact static source bytes plus an explicitly initialized owned context."""
    def __init__(self,profile):
        super().__init__(profile)
        source=services._source(services.INIT_SOURCE)
        imported=services._source(services.TYPE_SOURCE)['create_connection_import']
        dispatch=source['init_dispatch']
        self.blocks[self.base+0x45d90]=bytes.fromhex(dispatch['complete_body']['raw_hex'])
        self.blocks[self.base+0x5905f0]=bytes.fromhex(''.join(row['bytes'] for row in dispatch['outer_thunk_instructions']))
        self.blocks[self.base+0x99d7b2]=bytes.fromhex(imported['thunk_bytes'])
        self.inner=0x50000000
        self.configuration,self.gameplay=0x50010000,0x50020000
        self.database_base,self.localization_base=0x7ffb00000000,0x7ffc00000000
        self.create_connection=self.database_base+0x1230
        self.put(self.base+0x9b7000,self.create_connection)
        self.put(self.base+0xa101e8+0x28,self.base+0x5905f0)
        self.put(self.base+0xa44f70+8,self.base+0x45d90)
        self.put(self.context+8,self.inner)
        self.put(self.inner,self.base+0xa44f70)
        self.blocks[self.inner+0x40]=b'\x01'
        self.put(self.inner+0x50,self.configuration)
        self.put(self.inner+0x58,self.gameplay)
        self.put(self.base+0xb8aa60,self.inner)
        self.put(self.base+0xb8aa78,self.inner+0xd80)


class _ScriptBindingFixture:
    def setUp(self):
        self.profile = profiles.profile_for_sha(profiles.XP2_CORE_SHA256)
        self.memory = ServiceMemory(self.profile)
        self.child = object()
        self.child_pointer = 0x60001000
        self.stacks = {0x60000000:0,self.child_pointer:0}
        self.runtime = NativeScriptRuntime.__new__(NativeScriptRuntime)
        self.runtime.root = 0x60000000
        self.runtime.registry = NS(validate=Mock(side_effect=self.validate_child),_check=Mock())
        self.runtime.database_bound = self.runtime.configuration_bound = self.runtime.locale_bound = False
        self.runtime.emit = Mock()
        self.runtime.lua = dict(gettop=lambda pointer:self.stacks[pointer],
                                settop=lambda pointer,count:self.stacks.__setitem__(pointer,count))
        self.version = Mock(return_value=1)
        self.install = Mock(return_value=0)
        self.runtime.host = NS(LAB_ProfileScriptCoreBindingsVersion=self.version,
                               LAB_ProfileScriptCoreBindingsInstall=self.install)
        self.core = NS(_name=str(CORE),_handle=self.memory.base)
        selected = contexts.profile_for_core(CORE,mode='context')
        modules = [str(selected.core_path),*[str(selected.shared_dependency_directory/name)
                                           for name in selected.dependency_sha256]]
        self.owner=NS(localization_initialized=True,
            database=NS(_name=str(selected.shared_dependency_directory/'DatabaseDLL_FinalRelease.dll'),
                        _handle=self.memory.database_base),
            localization_library=NS(_name=str(selected.shared_dependency_directory/'Localization_FinalRelease.dll'),
                                    _handle=self.memory.localization_base))
        symbol=services._source(services.TYPE_SOURCE)['create_connection_import']['symbol']
        setattr(self.owner.database,symbol,C.c_void_p(self.memory.create_connection))
        self.service_calls=[]
        for name in ('LAB_ParameterDatabaseBind','LAB_DBConfigurationBorrow','LAB_LocaleBind','LAB_DBConfigurationBind'):
            def call(*args,_name=name):
                self.service_calls.append((_name,args))
                return 0
            setattr(self.runtime.host,name,Mock(side_effect=call))
        self.getter = Mock(return_value=self.memory.interface)
        self.addresses = []
        def factory(*signature):
            def at(address):
                self.addresses.append(address)
                return self.getter
            return at
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(patch.object(native_probe,'Windows',return_value=NS(modules=lambda:modules)))
        self.patches.enter_context(patch.object(native_setup,'local_reader',return_value=self.memory.read))
        self.patches.enter_context(patch.object(binding,'_current_executable',return_value=BUILD))
        self.patches.enter_context(patch.object(binding.C,'WINFUNCTYPE',side_effect=factory))
        self.bind_services()
        self.runtime.emit.reset_mock()

    def validate_child(self, child):
        if child is not self.child: raise ValueError('Unowned fixture child')
        return self.child_pointer

    def bind(self, **kwargs):
        return self.runtime.bind_native_game_api(self.child,self.memory.context,self.core,
            core_sha256=kwargs.get('core_sha256',profiles.XP2_CORE_SHA256))

    def bind_services(self):
        return self.runtime.bind_core_services(self.owner,self.memory.context,
            core_library=self.core,core_sha256=profiles.XP2_CORE_SHA256)

    def assert_no_native_entry(self):
        self.getter.assert_not_called()
        self.install.assert_not_called()
        self.assertEqual(self.addresses,[])
        self.assertFalse(getattr(self.runtime,'_profile_script_bind_attempted',False))


class ProfileScriptBindingIntegrationTests(_ScriptBindingFixture,unittest.TestCase):
    def test_null_registration_owner_refuses_before_official_getter_or_attempt(self):
        self.memory.put(self.memory.base+0xb8aa78,0)
        with self.assertRaisesRegex(ValueError,'owner is null'):self.bind()
        self.assert_no_native_entry()

    def test_changed_code_and_source_build_component_refuse_before_native_entry(self):
        body=self.profile.bodies[0]
        self.memory.blocks[self.memory.base+body.rva] = b'\0'*body.bytes
        with self.assertRaisesRegex(ValueError,'body changed'):self.bind()
        self.assert_no_native_entry()
        self.memory.blocks[self.memory.base+body.rva] = body.raw
        with patch.object(binding,'PROFILE_COMPONENT_SHA','0'*64),self.assertRaisesRegex(ValueError,'component'):
            self.bind()
        self.assert_no_native_entry()

    def test_all_services_and_owned_empty_stacks_are_required(self):
        for field in ('database_bound','configuration_bound','locale_bound','service_owner'):
            with self.subTest(field=field):
                saved=getattr(self.runtime,field);setattr(self.runtime,field,None)
                with self.assertRaisesRegex(ValueError,'fresh bound services'):self.bind()
                setattr(self.runtime,field,saved)
                self.assert_no_native_entry()
        for pointer in self.stacks:
            with self.subTest(pointer=pointer):
                self.stacks[pointer]=1
                with self.assertRaisesRegex(ValueError,'empty owned stacks'):self.bind()
                self.stacks[pointer]=0
                self.assert_no_native_entry()
        with self.assertRaisesRegex(ValueError,'Unowned fixture child'):
            binding.bind_game_api(self.runtime,object(),self.memory.context,self.core,core_sha256=profiles.XP2_CORE_SHA256)
        self.assert_no_native_entry()

    def test_unknown_engine_missing_export_and_unknown_version_refuse(self):
        with self.assertRaisesRegex(ValueError,'engine is not admitted'):self.bind(core_sha256='0'*64)
        self.assert_no_native_entry()
        del self.runtime.host.LAB_ProfileScriptCoreBindingsInstall
        with self.assertRaisesRegex(ValueError,'lacks its source-qualified'):self.bind()
        self.runtime.host.LAB_ProfileScriptCoreBindingsInstall=self.install
        self.version.return_value=2
        with self.assertRaisesRegex(ValueError,'ABI version'):self.bind()
        self.assert_no_native_entry()

    def test_foreign_interface_consumes_attempt_and_never_enters_installer(self):
        self.getter.return_value=self.memory.interface+8
        with self.assertRaisesRegex(ValueError,'foreign interface'):self.bind()
        self.assertTrue(self.runtime._profile_script_bind_attempted)
        self.getter.assert_called_once_with(self.memory.context)
        self.install.assert_not_called()
        with self.assertRaisesRegex(ValueError,'fresh bound services'):self.bind()
        self.assertEqual(self.getter.call_count,1)

    def test_actual_dispatch_build_identity_and_success_remain_scoped(self):
        receipt=self.bind()
        self.assertEqual(self.addresses,[self.memory.base+self.profile.getter_rva])
        self.getter.assert_called_once_with(self.memory.context)
        self.install.assert_called_once_with(self.runtime.root,self.child_pointer,self.memory.interface,
                                             self.memory.base,self.profile.profile_id)
        self.assertEqual(receipt['native_host_sha256'],'a17a82af1a9e5a429af4a1ef82e88b80d3213699118ec1cece14e88516d761d4')
        self.assertEqual(receipt['source_sha256'],profiles.SOURCE_SHA)
        self.assertEqual(receipt['service_init_source_sha256'],services.INIT_SOURCE[1])
        self.assertEqual(receipt['service_type_source_sha256'],services.TYPE_SOURCE[1])
        self.assertEqual(receipt['outer_protected_status'],0)
        self.assertIs(receipt['registration_returned'],True)
        for field in ('complete_api_verified','game_created','saved_load_admitted'):
            self.assertIs(receipt[field],False)
        with self.assertRaisesRegex(ValueError,'fresh bound services'):self.bind()
        self.assertEqual(self.install.call_count,1)

    def test_native_outer_error_never_emits_success(self):
        self.install.return_value=-1741
        with self.assertRaisesRegex(RuntimeError,'native status -1741'):self.bind()
        self.assertTrue(self.runtime._profile_script_bind_attempted)
        self.assertEqual([call.args[0] for call in self.runtime.emit.call_args_list],['before_profile_script_api_bind'])
        with self.assertRaisesRegex(ValueError,'fresh bound services'):self.bind()
        self.assertEqual(self.install.call_count,1)

    def test_nonempty_return_never_emits_success(self):
        def dirty(*args):
            self.stacks[self.child_pointer]=1
            return 0
        self.install.side_effect=dirty
        with self.assertRaisesRegex(RuntimeError,'nonempty Lua stack'):self.bind()
        self.assertEqual([call.args[0] for call in self.runtime.emit.call_args_list],
                         ['before_profile_script_api_bind'])


class CoreScriptServiceTests(_ScriptBindingFixture,unittest.TestCase):
    def fresh_services(self):
        self.runtime.unbind_services()
        self.service_calls.clear()
        self.runtime.emit.reset_mock()

    def test_exact_borrowed_connections_shared_bind_order_and_release_ownership(self):
        m=self.memory;root=self.runtime.root
        self.assertEqual(self.service_calls,[
            ('LAB_ParameterDatabaseBind',(root,m.database_base,m.gameplay)),
            ('LAB_DBConfigurationBorrow',(root,m.database_base,m.configuration)),
            ('LAB_LocaleBind',(root,m.localization_base))])
        lease=services.check_bound(self.runtime,m.context,self.core)
        self.assertEqual((lease.inner,lease.configuration,lease.gameplay),(m.inner,m.configuration,m.gameplay))
        self.assertIs(lease.owner,self.owner)
        self.service_calls.clear()
        invalidated=[]
        original=self.runtime.host.LAB_LocaleBind.side_effect
        def locale(*args):
            invalidated.append(self.runtime._profile_borrowed_services is None)
            return original(*args)
        self.runtime.host.LAB_LocaleBind.side_effect=locale
        self.runtime.unbind_services()
        self.assertEqual(invalidated,[True])
        self.assertEqual(self.service_calls,[('LAB_LocaleBind',(root,None)),
            ('LAB_DBConfigurationBind',(root,None,None,0)),('LAB_ParameterDatabaseBind',(root,None,None))])
        self.assertFalse(self.runtime.database_bound or self.runtime.configuration_bound or self.runtime.locale_bound)
        with self.assertRaisesRegex(ValueError,'ownership or lifetime'):services.check_bound(self.runtime,m.context,self.core)

    def test_unknown_or_incomplete_explicit_engine_refuses_before_any_lua_bind(self):
        self.fresh_services()
        for sha,core in (('0'*64,self.core),(profiles.XP2_CORE_SHA256,None),(None,self.core)):
            with self.subTest(sha=sha,core=core),self.assertRaises(ValueError):
                self.runtime.bind_core_services(self.owner,self.memory.context,core_library=core,core_sha256=sha)
        self.assertEqual(self.service_calls,[])
        self.assert_no_native_entry()

    def test_unready_or_foreign_context_and_null_connections_refuse_before_bind(self):
        self.fresh_services();m=self.memory
        changes=[(m.inner+0x40,b'\0'),(m.base+0xb8aa60,(m.inner+8).to_bytes(8,'little')),
                 (m.base+0xb8aa78,(m.inner+0xd88).to_bytes(8,'little')),
                 (m.inner+0x50,b'\0'*8),(m.inner+0x58,b'\0'*8)]
        for address,raw in changes:
            with self.subTest(address=address):
                old=m.blocks[address];m.blocks[address]=raw
                with self.assertRaises(ValueError):self.bind_services()
                m.blocks[address]=old
                self.assertEqual(self.service_calls,[])
                self.assertFalse(self.runtime.database_bound)
        self.assert_no_native_entry()

    def test_changed_source_code_import_or_shared_owner_library_refuses_before_bind(self):
        self.fresh_services();m=self.memory
        for address in (m.base+0x45d90,m.base+0x5905f0,m.base+0x99d7b2,m.base+0x9b7000):
            with self.subTest(address=address):
                old=m.blocks[address];m.blocks[address]=bytes([old[0]^1])+old[1:]
                with self.assertRaises(ValueError):self.bind_services()
                m.blocks[address]=old
                self.assertEqual(self.service_calls,[])
        name=self.owner.database._name;self.owner.database._name=str(CORE)
        with self.assertRaisesRegex(ValueError,'owner library differs'):self.bind_services()
        self.owner.database._name=name
        self.assertEqual(self.service_calls,[])

    def test_partial_bind_failure_has_no_lease_and_cleanup_keeps_core_ownership(self):
        self.fresh_services()
        self.runtime.host.LAB_DBConfigurationBorrow.side_effect=None
        self.runtime.host.LAB_DBConfigurationBorrow.return_value=-123
        with self.assertRaisesRegex(RuntimeError,'native status -123'):self.bind_services()
        self.assertTrue(self.runtime.database_bound)
        self.assertFalse(self.runtime.configuration_bound or self.runtime.locale_bound)
        self.assertIsNone(self.runtime._profile_borrowed_services)
        with self.assertRaises(ValueError):self.bind()
        self.runtime.unbind_services()
        self.assertFalse(self.runtime.database_bound)
        self.assert_no_native_entry()

    def test_connection_replacement_is_refused_before_gamecore_registration(self):
        self.memory.put(self.memory.inner+0x50,self.memory.configuration+8)
        with self.assertRaisesRegex(ValueError,'connection identities changed'):self.bind()
        self.assert_no_native_entry()

    def test_plain_service_flags_do_not_substitute_for_source_bound_ownership(self):
        self.runtime._profile_borrowed_services=None
        with self.assertRaisesRegex(ValueError,'ownership or lifetime'):self.bind()
        self.assert_no_native_entry()

    def test_foreign_thread_or_localization_lifetime_refuses_bound_lease(self):
        with patch.object(services.threading,'get_ident',return_value=-1):
            with self.assertRaisesRegex(ValueError,'ownership or lifetime'):self.bind()
        self.owner.localization_initialized=False
        with self.assertRaisesRegex(ValueError,'ownership or lifetime'):self.bind()
        self.assert_no_native_entry()


class ExtractionAndBuildTests(unittest.TestCase):
    def test_service_hook_preserves_legacy_reads_and_all_native_binding_calls(self):
        from extraction_script_binding_profiles import parameterize_services
        from civ6_host.runtime.paths import resource_root
        import copy
        source=ast.parse((resource_root()/'civ6rl/native_script_runtime.py').read_text(encoding='utf-8-sig'))
        cls=next(node for node in source.body if isinstance(node,ast.ClassDef) and node.name=='NativeScriptRuntime')
        original=copy.deepcopy(cls)
        transformed=parameterize_services(copy.deepcopy(source))
        with self.assertRaisesRegex(ValueError,'signature changed'):parameterize_services(copy.deepcopy(transformed))
        cls=next(node for node in transformed.body if isinstance(node,ast.ClassDef) and node.name=='NativeScriptRuntime')
        def method(c,name):return next(node for node in c.body if isinstance(node,ast.FunctionDef) and node.name==name)
        bind=method(cls,'bind_core_services');old=method(original,'bind_core_services')
        self.assertEqual([a.arg for a in bind.args.kwonlyargs],['core_library','core_sha256'])
        bind.args.kwonlyargs=[];bind.args.kw_defaults=[]
        at=next(i for i,node in enumerate(bind.body) if isinstance(node,ast.Assign)
                and ast.unparse(node.targets[0])=='profiled_services')
        branch=bind.body[at+1]
        self.assertEqual(ast.unparse(branch.test),'core_library is not None or core_sha256 is not None')
        bind.body[at:at+2]=branch.orelse
        self.assertEqual(ast.unparse(bind.body[-2].test),'profiled_services is not None')
        del bind.body[-2]
        self.assertEqual(ast.dump(bind),ast.dump(old))
        unbind=method(cls,'unbind_services');old_unbind=method(original,'unbind_services')
        self.assertEqual(ast.unparse(unbind.body[1]),'self._profile_borrowed_services = None')
        del unbind.body[1]
        self.assertEqual(ast.dump(unbind),ast.dump(old_unbind))

    def test_extraction_inserts_one_explicit_branch_preserving_legacy_method(self):
        from extraction_script_binding_profiles import parameterize
        import copy
        raw='''class NativeScriptRuntime:
    def bind_native_game_api(self, context, core_context, core_library, *, core_sha256="base"):
        """Legacy registration."""
        if core_sha256 == "xp1":
            return original_xp1(context)
        if core_sha256 != "base":
            raise ValueError("unknown")
        return original_base(context)
'''
        old=ast.parse(raw)
        new=parameterize(copy.deepcopy(old))
        method=new.body[0].body[0]
        branch=method.body.pop(1)
        self.assertEqual(ast.literal_eval(branch.test.comparators[0]),profiles.XP2_CORE_SHA256)
        self.assertEqual(ast.dump(new),ast.dump(old))
        with self.assertRaisesRegex(ValueError,'already selected'):
            parameterize(parameterize(ast.parse(raw)))

    def test_new_manifest_is_exact_shared_transitive_source_closure(self):
        import json
        from build_native_host import source_inputs,staging_paths
        path=HOST/'native/profiles/xp2-script-api/source-manifest.json'
        manifest=json.loads(path.read_bytes())
        entries=source_inputs(HOST,manifest)
        names={name.as_posix():file for file,name in staging_paths(HOST,manifest).items()}
        self.assertEqual(len(entries),23)
        self.assertEqual(names['script_core_bindings_xp1_legacy.inc'],
                         HOST/'native/profiles/xp1-ui/script_core_bindings_xp1.inc')
        self.assertEqual(names['script_core_binding_profiles.inc'],
                         HOST/'native/script_core_binding_profiles.inc')
        self.assertEqual(names['gamecore_python_host.c'],HOST/'native/profiles/xp1-jobs/gamecore_python_host.c')
        self.assertEqual(manifest['qualification'],'unqualified_source_build')


if __name__=='__main__':unittest.main(verbosity=2)
