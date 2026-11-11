"""Bounded XP1 configuration qualification using the retained Init-only worker.

The unchanged 822 supervisor owns private DB copies and job limits. Its retained
worker is explicitly adapted to call the shared product configuration lifecycle
instead of the old Init-only orchestration. The explicit scripts stage adds
Prepare/Lua/Destroy qualification; no imports or NewGame are reconstructed.
Previous configuration qualification is retained separately.
The reference runner is a private prerequisite, not distributed game content.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import MethodType, SimpleNamespace

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'src'))
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.provenance import installed_source_pins, verify_installation

REFERENCE = ('tools/run_native_xp1_context822.py',
             '29b1d011d0e2cec314dd324709faf3bfd7ad59274ca8aa0b47f02c356d313bf3')
PIN_ENV = 'CIV6_HOST_CONFIGURATION_QUALIFICATION_SHA'
STAGE_ENV = 'CIV6_HOST_XP1_QUALIFICATION_STAGE'
WIRE_ENV = 'CIV6_HOST_CONTEXT_WIRE_PATHS'
SCRIPT_HOST = ('work/native-script-services-host42-xp1/civ6rl-native-python.exe',
               '962ff8ca95ffed4fbaf40f0a0c37c47dd7d9c27b0bfc25beb4ae5dc76a2cfd0c')
SCALAR_HOST = (REPO/'work/xp1-configuration-lua/build-01/civ6rl-native-python.exe',
               'e8bd76baa4e775c836d9f06bf7f0d3af1aed84dc929d6de2de5ff327b24683ae')
MAP_HOST = (REPO/'work/xp1-parameter-maps/build-01/civ6rl-native-python.exe',
            'd4809c48bce8b427338980ca3a2a2fccdf0c1038f50f3d54fa0b2763140eb2eb')
EVENT_MAP_HOST = (REPO/'work/xp1-script-map-arguments/build-02/civ6rl-native-python.exe',
                  'c65738fdb17e23341a22c26b44c7e27095c45594bee43c42dcb6d14dd2332bba')
CONTEXT_HOST = (REPO/'work/xp1-script-contexts/build-01/civ6rl-native-python.exe',
                '11993e669bc00bbeab60414abc50466e388c9c589a70d3a8428c8873c8d16581')
AUX90_HOST = ('work/native-host-xp1-postload-build01/civ6rl-native-python.exe',
              'ef3d85f1baa913888a1c48802e0862592cecf1e1dffff0e6964ffba1f146411f')
from civ6_host.runtime.xp2_session_inputs import XP2_UI_HOST
AUX90_MANIFEST = (REPO/'native/profiles/xp1-postload/source-manifest.json',
                  '7dffc41201d312d8b4c8c8dd4e67591c118a1d624ea1000cb76f967daacc4f20')
LOCALIZATION_MANIFEST = ('work/native-base-fixture04/manifest.json',
                         'daff5fa5bd1968958cf2088c47808dc1433a3532b1475754a6776cb6109f0e86')
STDOUT_REFERENCE = ('tools/run_native_xp1_application_setup891.py',
                    'ea0a9db0df0febaa50e6008035a5278a71a2500aded8a0273f9e0a2218017df0')
STDOUT_FUNCTION_SHA256 = '6f8502b255a7888ee35c0ed929bd9c43f71308c21c6ac5775066ad531c0ece57'
SCRIPT_EVENTS = {
    'xp1_prepare_registry_installed', 'xp1_archive_access_installed', 'host_descriptor_context',
    'xp1_archive_registration_installed', 'before_localization_connection',
    'before_localization_initialize', 'localization_initialize_result', 'localization_initialized',
    'before_xp1_prepare', 'xp1_prepare_returned', 'host_type_register', 'host_autoarchive',
    'host_archive_register', 'host_archive_remove', 'diagnostic_fault_enabled',
    'diagnostic_tuner_unavailable', 'native_script_core_services_bound',
    'before_xp1_script_api_bind', 'xp1_script_api_bind_returned',
    'native_script_runtime_closed', 'localization_shutdown', 'localization_connection_released',
    'icu_fixture_unchanged', 'native_script_buffer_executed',
    'native_aux_map_callback_installed', 'native_aux_map_callback_closed',
    'native_aux_map_snapshot_ready', 'native_aux_map_snapshot_refused',
    'native_core_execution_lock_enabled', 'native_core_execution_lock_closed',
    'native_game_event_dispatched', 'native_game_event_test_all',
    'native_gameplay_context_acquired','native_gameplay_context_loaded','native_gameplay_context_released','native_include_snapshot','official_saved_configuration_lua_readback_verified',
    'native_application_mirror_initialized','native_application_game_notification','native_application_player_notification',
    'native_host_notification_counter_updated','native_cache_update_enqueued',
    'before_native_cache_update_dispatch','native_cache_update_dispatched',
    'host_local_player_configured','host_local_player_id','native_host_controller_flag_read',
    'native_owned_controller_constructed','native_owned_controller_flag_read',
    'native_shared_absent_scalar_event','native_a0_family_event',
    'native_deferred_host_event_enqueued','native_host_status_message_completed',
    'native_deferred_empty_record_consumed',
    'native_postload_aux90_observed',
}

# Diagnostic native registration copies a non-owning callback pair. Keep these
# allocations until process exit: prepared Game destruction need not unregister
# the entry. They are never installed by the product service or shipped to it.
_DIAGNOSTIC_PINS=[]


def selected_stage():
    stage = os.environ.get(STAGE_ENV, 'configuration')
    if stage not in ('configuration', 'scripts', 'copy', 'values', 'maps', 'events', 'event_maps', 'contexts', 'load_services', 'application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90','saved_load'):
        raise ValueError('Unknown XP1 qualification stage')
    return stage


def selected_wire_mode():
    value=os.environ.get(WIRE_ENV,'0')
    if value not in ('0','1'):
        raise ValueError('Context wire-path mode requires an explicit Boolean')
    if value=='1' and selected_stage()!='contexts':
        raise ValueError('Wire-path qualification is scoped to the contexts stage')
    return value=='1'


def stage_host():
    return {'values':SCALAR_HOST,'maps':MAP_HOST,'events':MAP_HOST,'event_maps':EVENT_MAP_HOST,'contexts':CONTEXT_HOST,'load_services':CONTEXT_HOST,'application':CONTEXT_HOST,'deferred':CONTEXT_HOST,'control':CONTEXT_HOST,'arguments':CONTEXT_HOST,'status':CONTEXT_HOST,'a0':CONTEXT_HOST,'a0_control':CONTEXT_HOST,'facades':CONTEXT_HOST,'player_queries':CONTEXT_HOST,'a0_scope':CONTEXT_HOST,'aux90':AUX90_HOST}.get(selected_stage(),SCRIPT_HOST)


def parse_script_stdout(stdout):
    """Reuse 891's exact empty-job/worker parser, without importing its runner."""
    raw = (resource_root()/STDOUT_REFERENCE[0]).read_bytes()
    if digest(raw) != STDOUT_REFERENCE[1]:
        raise ValueError('Retained native telemetry parser source changed')
    text = raw.decode('utf-8').replace('\r\n', '\n')
    tree = ast.parse(text)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'parse_worker_stdout')
    source = ast.get_source_segment(text, fn)
    if digest(source.encode('utf-8')) != STDOUT_FUNCTION_SHA256:
        raise ValueError('Retained native telemetry parser function changed')
    namespace = {'json': json, 'MAX_REPORT_BYTES': 512*1024}
    exec(compile(source, '<retained 891 stdout parser>', 'exec'), namespace)
    # 822's print adds one blank line after its newline-terminated JSON record.
    if stdout.endswith('\n\n'):
        stdout = stdout[:-1]
    return namespace['parse_worker_stdout'](stdout)
# The provider session fixes its limits on first use. Reuse the common
# backend's existing stream bounds for serialization, restore and sealing.
from civ6_host.runtime.native.native_checkpoint_configuration_only import MAX_BYTES, MAX_CALLS
# Explicit new diagnostic closure, not a reinterpretation of the old 822 result.
# Current Init/teardown were used by 891; Windows supervision methods retain
# their old bodies. XP1 rebinds host callbacks to its verified allowlist. The
# localization implementation is pinned by 822 but is not called in this route.
SOURCE_MIGRATION = {
    'civ6rl/native_xp1_context_init.py': (
        '046549890d607ac48165ca4ffe85353bd81a80cc65ca2b9eb719503f98106d49',
        '6e3172c2a69168bda640aba91284d828b89e0b1b5e02b2e5ecc417d6b08f547e'),
    'civ6rl/native_xp1_teardown_adapter.py': (
        '5818745cabf07dcc644a0989f75dc5c7c81b5db6105d911d702cb06050c0d9e1',
        '3fcde8a9ab8f26363ba44ffa7fba60661c1bdd2439587732ac74abf2e0df4b3d'),
    'civ6rl/native_host.py': (
        'f654046847e70b3306e2a2b371a3c39268d35d8e3b1639ab2faeedbe005bbec1',
        'ebd7d0f3e0026e35ef04b89d92698764466887578cc1819351a794dce4b8e3d6'),
    'civ6rl/native_probe.py': (
        '5fb49a2c619895c3eda5d86b501faa18c23307c98be291206b63efcf8fbb1a28',
        '8d6d1cbc1c84e473f7036e3fefb27eb38a161e64c2c1ea0492c6ddc72f2c7dbb'),
    'civ6rl/native_localization.py': (
        '07a3519f50711a964edef0419fdc2e09b0600e79bd379081f45d669d498e5e89',
        '7ddac11af2a3ec117db11de262eec450665c2a8606851dfedb0a8df84d771721'),
}
HELPER_HOST_PARENT = 'daac085ea97d94d2d9ceded07ef90bcc9d7a1f2ab6aa301f3efa155b8cea8db5'
VALUE_PROBE_SOURCES = {
    'civ6rl/native_xp1_map_setup.py':'0368a2c56a78a43dadb0c4864c4ccefb0440afc317b44cd4afb0da81cfc1f113',
    'civ6rl/native_xp1_application_configuration.py':'3cc17f6932b377543292f0341575f119c466ab9c007390d6e3dc48fccb7fedb3',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_once(path, value):
    data = (json.dumps(value, indent=2, sort_keys=True, default=str) + '\n').encode()
    with path.open('xb') as stream:
        stream.write(data)
    return {'path':str(path),'bytes':len(data),'sha256':digest(data)}


def source_state():
    pins = installed_source_pins()
    pins[str(Path(__file__).resolve())] = digest(Path(__file__).read_bytes())
    for relative,expected in VALUE_PROBE_SOURCES.items():
        path=resource_root()/relative
        actual=digest(path.read_bytes())
        if actual!=expected:
            raise ValueError('Typed configuration probe source changed: '+relative)
        pins[str(path)]=actual
    if selected_stage() != 'configuration':
        from civ6_host.runtime.xp1_prepare import NULL_TUNER_PROOF
        host_reference = stage_host()
        for relative, expected in (host_reference, LOCALIZATION_MANIFEST, NULL_TUNER_PROOF, STDOUT_REFERENCE):
            path = resource_root()/relative
            if digest(path.read_bytes()) != expected:
                raise ValueError('Script qualification dependency changed: '+relative)
            pins[str(path)] = expected
    if selected_stage() in ('values','maps','load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90'):
        from civ6_host.runtime.configuration_lua_source import SOURCE, source
        source()
        pins[str(resource_root()/SOURCE[0])] = SOURCE[1]
        manifest = REPO/'native/source-current.json'
        pins[str(manifest)] = digest(manifest.read_bytes())
    if selected_stage() in ('maps','load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90'):
        from civ6_host.runtime.aux_map_profiles import SOURCE, source
        source()
        pins[str(resource_root()/SOURCE[0])] = SOURCE[1]
    if selected_stage() in ('events','event_maps','contexts','load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90'):
        from civ6_host.runtime.script_event_source import SOURCE, source
        proof=source()
        pins[str(resource_root()/SOURCE[0])] = SOURCE[1]
        for item in proof['references'].values():
            pins[str(resource_root()/item['path'])] = item['sha256']
        manifest=REPO/'native/source-current.json'
        pins[str(manifest)]=digest(manifest.read_bytes())
    if selected_stage() in ('event_maps','load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90'):
        from civ6_host.runtime.script_map_argument_source import SOURCE,source
        proof=source();pins[str(resource_root()/SOURCE[0])]=SOURCE[1]
        for item in proof['references'].values():pins[str(resource_root()/item['path'])]=item['sha256']
    if selected_stage() in ('contexts','load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90'):
        from civ6_host.runtime.script_context_source import SOURCE,source
        proof=source();pins[str(resource_root()/SOURCE[0])]=SOURCE[1]
        for item in proof['references'].values():pins[str(resource_root()/item['path'])]=item['sha256']
    if selected_stage()=='application':
        from civ6_host.runtime.application_mirror_profiles import source_pins,prelude_source,XP1_CORE_SHA256
        prelude_source(XP1_CORE_SHA256)
        pins.update(source_pins())
    if selected_stage() in ('deferred','control','arguments','status','a0','a0_control','player_queries','a0_scope'):
        from civ6_host.runtime.cache_update_profiles import source_pins
        pins.update(source_pins())
    if selected_stage() in ('control','a0_control'):
        from civ6_host.runtime.control_input_source import source_pins
        pins.update(source_pins())
    if selected_stage() in ('arguments','status','a0','a0_control','player_queries','a0_scope'):
        from civ6_host.runtime.event_argument_source import source_pins
        pins.update(source_pins())
        from civ6_host.runtime.xp1_absent_event_families import source_dependencies as absent_event_dependencies
        pins.update(absent_event_dependencies())
    if selected_stage()=='status':
        from civ6_host.runtime.retained_game_source import source_pins
        pins.update(source_pins())
    if selected_stage() in ('a0','a0_control','player_queries','a0_scope'):
        from civ6_host.runtime.a0_family_source import source_pins
        pins.update(source_pins())
    if selected_stage()=='a0_control':
        from civ6_host.runtime.a0_controller_source import source_pins
        pins.update(source_pins())
    if selected_stage()=='facades':
        from civ6_host.runtime.cache_facade_profiles import source_pins
        pins.update(source_pins())
    if selected_stage()=='player_queries':
        from civ6_host.runtime.player_notification_profiles import source_pins
        pins.update(source_pins())
    if selected_stage()=='a0_scope':
        pins.update(notification_scope_source_pins())
    if selected_stage()=='aux90':
        from civ6_host.runtime.postload160_source import source_pins
        pins.update(source_pins())
        path,expected=AUX90_MANIFEST
        if digest(path.read_bytes())!=expected:raise ValueError('AUX90 native build manifest changed')
        pins[str(path)]=expected
    raw = json.dumps(dict(files=pins,stage=selected_stage(),script_wire_mode=selected_wire_mode()),
                     sort_keys=True,separators=(',',':')).encode()
    return pins, digest(raw)


def load_reference():
    root = resource_root()
    path = root / REFERENCE[0]
    if digest(path.read_bytes()) != REFERENCE[1]:
        raise ValueError('Retained XP1 Init-only runner changed')
    sys.path.insert(0,str(root))
    spec = importlib.util.spec_from_file_location('_civ6_host_xp1_init_reference', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for relative,(before,after) in SOURCE_MIGRATION.items():
        if module.SOURCE_PINS.get(relative)!=before or digest((root/relative).read_bytes())!=after:
            raise ValueError('Diagnostic migration differs from its reviewed source pair: '+relative)
        module.SOURCE_PINS[relative]=after
    from civ6rl import native_xp1_context_init, native_xp1_teardown_adapter
    for helper in (native_xp1_context_init,native_xp1_teardown_adapter):
        if helper.SOURCE_PINS.get('civ6rl/native_host.py')!=HELPER_HOST_PARENT:
            raise ValueError('XP1 helper host-parent pin differs from reviewed migration')
        helper.SOURCE_PINS['civ6rl/native_host.py']=SOURCE_MIGRATION['civ6rl/native_host.py'][1]
    if selected_stage() != 'configuration':
        host_reference = stage_host()
        module.HOST = root/host_reference[0]
        module.HOST_SHA256 = host_reference[1]
        raw = inspect.getsource(module.validate_worker_report)
        before = 'value.get("prepare_called") is not False'
        if raw.count(before) != 1:
            raise ValueError('Retained Prepare classification boundary changed')
        raw = raw.replace(before, 'value.get("prepare_called") is not True')
        before = '["context_destroy", "database_shutdown"]'
        if raw.count(before) != 1:
            raise ValueError('Retained cleanup classification boundary changed')
        cleanup=['script_services_unbind','context_destroy','script_runtime_close']
        if selected_stage() in ('events','event_maps','contexts','load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90'): cleanup.append('core_lock_close')
        cleanup+=['localization_shutdown','database_shutdown']
        raw = raw.replace(before, repr(cleanup))
        exec(compile(raw, '<XP1 scripts lifecycle validator>', 'exec'), module.__dict__)
        raw = inspect.getsource(module._supervise)
        before = '''            lines = [line for line in stdout.splitlines() if line.strip()]
            if len(lines) != 1 or len(stdout.encode("utf-8", "replace")) > MAX_REPORT_BYTES:
                raise ValueError("Worker stdout is not exactly one bounded JSON record")
            worker = json.loads(lines[0])'''
        if raw.count(before) != 1:
            raise ValueError('Retained supervisor stdout boundary changed')
        raw = raw.replace(before, '''            worker, worker_line, native_telemetry = _parse_script_stdout(stdout)
            lines = [worker_line]''')
        module._parse_script_stdout = parse_script_stdout
        exec(compile(raw, '<XP1 scripts supervised telemetry>', 'exec'), module.__dict__)
    return module, path


def script_group(core, context, run_dir, backend):
    """One native service group, reusing Init and the existing Lua runtime."""
    import ctypes as C
    from civ6_host.runtime.native.native_host import prepare_context
    from civ6_host.runtime.native.native_havok import HAVOK_SHA256
    from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
    from civ6_host.runtime.native.native_core_context_profiles import profile_for_core
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
    root = resource_root()
    staged = provider_group(core,context,run_dir,backend,keep_owner=True) if selected_stage() in ('copy','values','maps','event_maps','load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90') else None
    manifest = json.loads((root/LOCALIZATION_MANIFEST[0]).read_text(encoding='utf-8'))
    host = backend.host
    entries = {'localization': manifest['databases']['localization'],
               'icu_data': manifest['localization_bootstrap']['icu_data']}
    copies = {}
    for key, entry in entries.items():
        source = Path(entry['path']).resolve()
        expected = entry['sha256']
        if not source.is_relative_to(root/'work') or digest(source.read_bytes()) != expected:
            raise ValueError('Localization source differs from retained manifest')
        destination = run_dir/('script-'+key+source.suffix)
        if destination.exists():
            raise ValueError('Private script service input already exists')
        shutil.copyfile(source, destination)
        if digest(destination.read_bytes()) != expected:
            raise ValueError('Private localization copy differs')
        copies[key] = dict(entry, path=str(destination))
    host.manifest['databases']['localization'] = copies['localization']
    host.manifest['localization_bootstrap'] = dict(manifest['localization_bootstrap'], icu_data=copies['icu_data'])
    host.enable_tuner_unavailable_probe()
    profile = profile_for_core(core._name, mode='context')
    prepared = prepare_context(core, context, host.emit, context_profile=profile,
                               null_tuner_diagnostic=True)
    havok = Path(host.dll_directory)/'HavokScript_FinalRelease.dll'
    if digest(havok.read_bytes()) != HAVOK_SHA256:
        raise ValueError('HKS source changed')
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleHandleW.argtypes, kernel.GetModuleHandleW.restype = [C.c_wchar_p], C.c_void_p
    executable = C.WinDLL('', handle=kernel.GetModuleHandleW(None))
    runtime = NativeScriptRuntime(C.WinDLL(str(havok)), executable, host.emit)
    host._qualification_script_runtime = runtime
    runtime.bind_core_services(host, context)
    child = runtime.acquire()
    runtime.attach_standard_libraries(child)
    for name in ('DB', 'GameInfo', 'GlobalParameters', 'Path', 'Locale'):
        runtime.namespaces.register(child, name)
    # Actual native callbacks and borrowed DB/locale services, not a fake API.
    binding = runtime.bind_native_game_api(child, context, core, core_sha256=XP1_CORE_SHA256)
    if staged is None and selected_stage() not in ('events','contexts','load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90'):
        runtime.execute(child, b"""assert(type(Map)=='table' and type(Map.GetGridSize)=='function')
assert(type(Game)=='table' and type(Game.GetCurrentGameTurn)=='function')
assert(type(GameInfo.Units)=='userdata')
assert(type(GlobalParameters.COMBAT_BASE_DAMAGE)=='number')
assert(Locale.IsValidKey('LOC_UNIT_SETTLER_NAME'))
assert(DB.Query('SELECT COUNT(*) AS n FROM Units')[1].n > 0)
""", b'@xp1_common_script_services')
    copy_receipt = None
    event_receipt = events_group(core,host,runtime,child) if selected_stage()=='events' else None
    if staged is not None:
        if selected_stage()=='event_maps':
            event_receipt=events_group(core,host,runtime,child,map_source=backend.owner)
        elif selected_stage() not in ('load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90'):
            copy_receipt = copy_group(core,context,backend,staged)
        if selected_stage() == 'values':
            copy_receipt['lua_configuration_readback'] = values_group(core,context,backend,runtime,child,staged)
        if selected_stage() == 'maps':
            copy_receipt['parameter_map_readback'] = maps_group(core,context,backend,runtime,child,staged)
        if selected_stage() not in ('load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90'):backend.close_owner()
    context_receipt=contexts_group(core,context,run_dir,host,runtime,child,backend=backend,staged=staged) if selected_stage() in ('contexts','load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90') else None
    if selected_stage() in ('load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90'):backend.close_owner()
    runtime.registry.release(child)
    runtime.unbind_services()
    host._qualification_script_inputs = copies
    return {'status':f'native_{selected_stage()}_group_passed', 'prepare':prepared, 'binding':binding,
            'native_api_registered':True, 'borrowed_services_called':staged is None and selected_stage() not in ('events','contexts','load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90'),
            'script_event_services':event_receipt,'script_contexts':context_receipt,
            'staged_configuration':staged,'copied_configuration':copy_receipt,
            'native_callback_game_effects_tested':False, 'null_tuner_diagnostic':True,
            'gameplay_optional_proven':False, 'saved_game_loaded':False,
            'strategic_training_ready':False}


def copy_group(core, context, backend, staged, *, services=None):
    """Exercise the loader copy method with an explicit typed readback adapter.

    Only observers and copy are reused. This diagnostic does not construct a
    NativeLoadBackend or admit XP1 Load; readback is native typed, not Lua.
    """
    from civ6_host.runtime.native.native_checkpoint_load import NativeLoadBackend
    from civ6_host.runtime.native import native_configuration_finalization as setup
    from civ6_host.runtime.native.native_xp1_map_setup import XP1MapSetup
    from civ6_host.runtime.native.native_xp1_application_configuration import read_value
    abi = backend.configuration_abi
    prefix = services if services is not None else SimpleNamespace(configuration_readback_verified=False)
    observed = []
    def verify_values():
        source = XP1MapSetup(core,context,project_root=resource_root())
        current = setup._linked_snapshot(core._handle,context,backend.runtime.read,None,
                                        core_sha256=abi.core_sha256)
        def method(pointer,slot,result,types,*values):
            if slot!=0x58:raise ValueError('Readback only admits native lookup')
            return setup._invoke(None,core._handle+abi.lookup_rva,result,pointer,types,*values)
        borrower=SimpleNamespace(base=core._handle,read=backend.runtime.read,map=source,_method=method)
        for expected in staged['typed_values_after']:
            scope,key=expected['scope'],expected['key']
            target=current['players'][scope] if type(scope) is int else current[scope]
            value,_=read_value(borrower,target,key)
            row={'scope':scope,'key':key,**value}
            if row!=expected:raise ValueError('Copied A typed value differs from restored B')
            observed.append(row)
        source.close()
        prefix.configuration_readback_verified=True
    if services is None:prefix.verify_configuration_scalar_marshalling=verify_values
    probe=SimpleNamespace(core=core,context=context,host=backend.host,runtime=backend.runtime,
        owner=backend.owner,load_abi=abi.load,thread=backend.thread,
        poisoned=False,destroyed=False,prefix=None if services is not None else prefix,stage='prepared')
    for name in ('check_thread','topology','game_flag'):
        setattr(probe,name,MethodType(getattr(NativeLoadBackend,name),probe))
    if services is not None:services.attach(probe)
    receipt=NativeLoadBackend.copy_b_to_a(probe)
    if services is not None:verify_values()
    if probe.stage!='copied' or not prefix.configuration_readback_verified:
        raise ValueError('Shared copy did not complete its readback boundary')
    return {'shared_loader_method_executed':True,'receipt':receipt,
            'typed_values_copied':observed,'source_configuration_sha256':staged['after']['sha256'],
            'lua_configuration_readback':services is not None,'configuration_mutated_by_readback':False,
            'official_saved_game_loaded':False}


def close_script_group(host):
    from civ6_host.runtime.native.native_localization import finish_localization
    if hasattr(host,'_qualification_deferred_registry'):
        from civ6_host.runtime.cache_update_profiles import registry_snapshot
        state=host._qualification_deferred_registry
        after=registry_snapshot(state['base'],state['read'],state['key'])
        if after['subscribers'] not in ((),state['subscribers']):
            raise ValueError('Diagnostic CacheUpdate registration changed unexpectedly at Destroy')
        write_once(state['run_dir']/'deferred-destruction.json',{
            'after_context_destroy':True,'diagnostic_subscriber_retained':bool(after['subscribers']),
            'registry':after,'callbacks_pinned_through_process_exit':True,
            'manual_registry_clear_called':False,'loaded_game_destroy_qualified':False})
    host._qualification_script_runtime.close()
    if hasattr(host,'_qualification_core_lock'):
        host._qualification_core_lock.close()
        host.emit('native_core_execution_lock_closed',after_context_destroy=True)
    finish_localization(host)
    for entry in host._qualification_script_inputs.values():
        if digest(Path(entry['path']).read_bytes()) != entry['sha256']:
            raise ValueError('Native service input changed')


def _lua_bytes(raw):
    return '"' + ''.join('\\%03d' % byte for byte in raw) + '"'


def event_telemetry(host, kind, **fields):
    # The retained 822 ledger reserves event_name for its lifecycle kind. The
    # shared callback's event_name is the gameplay listener name; preserve both.
    if 'event_name' in fields:
        if 'gameplay_event_name' in fields:
            raise ValueError('Ambiguous GameEvents telemetry name')
        fields['gameplay_event_name']=fields.pop('event_name')
    host.emit(kind,**fields)


def events_group(core, host, runtime, child, *, map_source=None):
    """Explicit XP1 forwarding wrappers with diagnostic listeners, no game."""
    import ctypes as C
    from civ6_host.runtime.native.native_setup import local_reader
    from civ6_host.runtime.native.native_core_lock import NativeCoreLock
    from civ6_host.runtime.native.native_game_event_cases import (
        TYPED_ARGUMENT_SETUP,TYPED_ARGUMENT_EVENT,TYPED_ARGUMENTS,TYPED_ARGUMENT_CLEANUP)
    from civ6_host.runtime.script_event_service import ScriptEventService
    from civ6_host.runtime.script_event_source import verify_xp1
    owner=C.addressof(host.aux_object)
    source=verify_xp1(core._handle,local_reader(),host_pointer=host.pointer,auxiliary_pointer=owner)
    lock=NativeCoreLock(host,runtime.host)
    host._qualification_core_lock=lock  # retained through context Destroy
    runtime.attach_game_events(child)
    factory=None
    if map_source is not None:
        from civ6_host.runtime.script_event_maps import MapArgumentFactory
        from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
        factory=MapArgumentFactory(core,core_sha256=XP1_CORE_SHA256)
    service=ScriptEventService(host,runtime,map_factory=factory)
    service.emit=lambda kind,**fields:event_telemetry(host,kind,**fields)
    previous={s:p[0] for s,p in service.previous.items()}
    results=[]; unlocked=[]
    dispatch=runtime.dispatch_game_event_result
    def observed_dispatch(*args,**kwargs):
        if lock.owned(host.pointer):
            raise ValueError('XP1 wrapper did not release Core lock before Lua')
        unlocked.append(True)
        return dispatch(*args,**kwargs)
    runtime.dispatch_game_event_result=observed_dispatch
    create=C.WINFUNCTYPE(C.c_void_p,C.c_void_p)(host.aux_vtable[0x40//8])
    release=C.WINFUNCTYPE(None,C.c_void_p,C.c_void_p)(host.aux_vtable[0x48//8])
    wrappers={name:C.WINFUNCTYPE(C.c_uint8,C.c_void_p,C.c_char_p,C.c_void_p,C.POINTER(C.c_uint8))(
        core._handle+rva) for name,rva in (('Call',0x20CD0),('TestAll',0x20DF0))}
    def invoke(name,arguments,method,held,expected,*,after_append=None):
        payload=create(owner)
        if not payload:raise ValueError('No native script argument payload')
        vt=C.c_void_p.from_address(payload).value
        for index,value in enumerate(arguments):
            boolean=type(value) is bool
            slot,kind=(0x10,C.c_void_p) if type(value) is dict else ((0x38,C.c_uint8) if boolean else (0x28,C.c_uint32))
            append=C.WINFUNCTYPE(C.c_uint32,C.c_void_p,kind)(C.c_void_p.from_address(vt+slot).value)
            actual=value['native_map'] if type(value) is dict else (255 if boolean and value else value)
            if append(payload,actual)!=index:
                raise ValueError('Native argument index differs')
        if after_append is not None:after_append(service.script_arguments.arguments(payload))
        if held:lock.acquire(host.pointer)
        output=C.c_uint8(0xA5)
        valid=wrappers[method](owner,name,payload,C.byref(output))
        after=lock.owned(host.pointer)
        if after!=held or (bool(valid),output.value)!=expected:
            raise ValueError('XP1 wrapper result or restored lock differs')
        if held:lock.release(host.pointer)
        release(owner,payload)
        if service.script_arguments.live_count:raise ValueError('Argument release left a payload')
        results.append({'name':name.decode(),'method':method,'core_lock_initially_owned':held,
            'argument_count':len(arguments),'valid':bool(valid),'output':output.value,
            'lock_restored':True,'payload_released':True})
    for held in (() if map_source is not None else (False,True)):
        for method in wrappers:
            invoke(b'Civ6RL_EmptyProfile',(0xffffffff,),method,held,
                   (False,0 if method=='Call' else 0xA5))
        for literal,truth in ((b'false',0),(b'true',1),(b'0',1)):
            runtime.execute(child,b'GameEvents.Civ6RL_ResultProbe.Add(function(v) '
                b'assert(v==-1); return '+literal+b' end)',b'@xp1_events_result_setup')
            for method in wrappers:invoke(b'Civ6RL_ResultProbe',(0xffffffff,),method,held,(True,truth))
            runtime.execute(child,b'GameEvents.Civ6RL_ResultProbe.RemoveAll()',b'@xp1_events_result_cleanup')
        runtime.execute(child,TYPED_ARGUMENT_SETUP,b'@xp1_typed_event_setup')
        for method in wrappers:invoke(TYPED_ARGUMENT_EVENT,TYPED_ARGUMENTS,method,held,(True,0))
        runtime.execute(child,TYPED_ARGUMENT_CLEANUP,b'@xp1_typed_event_cleanup')
    map_receipt=map_event_cases(core,runtime,child,map_source,invoke,local_reader()) if map_source is not None else None
    service.close()
    if factory is not None:factory.close()
    runtime.dispatch_game_event_result=dispatch
    if any(host.aux_vtable[s//8]!=address for s,address in previous.items()):
        raise ValueError('Shared event callbacks were not restored')
    return {'source':source,'native_wrapper_calls':len(results),'calls':results,
        'observed_unlocked_lua_calls':len(unlocked),'live_payloads':0,'slots_restored':True,
        'gameplay_listeners_loaded':False,'synthetic_listener_names':True,
        'natural_gameplay_publication':False,'unsupported_payload_map_append_still_refused':map_source is None,
        'map_arguments':map_receipt,
        'saved_game_loaded':False}


def map_event_cases(core,runtime,child,owner,invoke,read):
    """Native copy at append, values isolated from later source mutations."""
    import ctypes as C
    from civ6_host.runtime.native import native_configuration_finalization as setup
    from civ6_host.runtime.native.native_application_configuration import provider_snapshot
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
    source=owner.snapshot();abi=owner._configuration_abi
    def set_value(value):
        setup._invoke(None,core._handle+abi.uint_setter_rva,None,source['players'][0],
                      (C.c_uint32,C.c_uint32),0x70000004,value)
    checks=[]
    def after_append(arguments):
        full,empty=arguments[1],arguments[3]
        clone=provider_snapshot(core._handle,full.pointer,read,core_sha256=XP1_CORE_SHA256)
        def pointers(x):return {x['descriptor'],x['normalized'],x['map_normalized'],*x['players']}
        if pointers(source)&pointers(clone):raise ValueError('Event map clone aliases an owned source submap')
        set_value(19)
        key_lookup=setup._invoke(None,core._handle+abi.lookup_rva,C.c_void_p,source['players'][0],(C.c_uint32,),0x70000004)
        import struct
        if struct.unpack('<I',read(key_lookup+8,4))[0]!=19:raise ValueError('Private source mutation did not apply')
        checks.append({'source_changed_after_append':True,'distinct_owned_submaps':66,
                       'empty_clone_distinct':empty.pointer!=source['players'][1]})
    # Exact inner diagnostic keys/values from provider_group; outer names may be
    # resolved or numeric according to the live official name registry.
    script=b'''GameEvents.Civ6RL_MapArguments.Add(function(n,t,b,e)
assert(n==-1 and type(b)=='boolean' and b and type(t)=='table')
assert(type(e)=='table' and next(e)==nil)
local root,mp,p0,p63
for k,v in pairs(t) do
  assert(type(v)=='table')
  if v[1879048193]~=nil then root=v end
  if v[1879048194]~=nil then mp=v end
  if v[1879048196]~=nil then p0=v end
  if v[1879048197]~=nil then p63=v end
end
assert(root and root[1879048193]==-1)
assert(mp and mp[1879048194]==-2035589277)
assert(mp[1879048195]==''' + _lua_bytes('HÃƒÂ´te XP1 Ã¢â‚¬â€œ civilisation'.encode()).encode() + b''')
assert(p0 and p0[1879048196]==0)
assert(p63 and p63[1879048197]==''' + _lua_bytes('Joueur 63 Ã¢â‚¬â€œ Ã¦Â¼Â¢Ã¥Â­â€”'.encode()).encode() + b''')
Civ6RL_MapArgumentHits=Civ6RL_MapArgumentHits+1
return false
end)'''
    runtime.execute(child,b'Civ6RL_MapArgumentHits=0;'+script,b'@xp1_map_arguments_setup')
    for held in (False,True):
        for method in ('Call','TestAll'):
            set_value(0)
            invoke(b'Civ6RL_MapArguments',(0xffffffff,{'native_map':source['descriptor']},True,
                   {'native_map':source['players'][1]}),method,held,(True,0),after_append=after_append)
    runtime.execute(child,b'assert(Civ6RL_MapArgumentHits==4); GameEvents.Civ6RL_MapArguments.RemoveAll()',
                    b'@xp1_map_arguments_cleanup')
    return {'calls':4,'map_copies':8,'checks':checks,'source_changed_after_append':True,
            'copied_values_survived':True,'nested_maps_executed':True,'empty_root_is_table':True,
            'names_resolved_at_dispatch':True,'source_resolver_mutation_tested':False,
            'source_null_nested_map_tested':False,'private_source_player_value_final':19}


def contexts_group(core, context, run_dir, host, runtime, child, *, backend=None,staged=None):
    """Run the actual XP1 selected-script loader, replacement and clear methods.

    Files are diagnostic Lua using prepared services, not official loaded-game
    scripts. The manager is the Core-owned object; Destroy keeps its ownership.
    """
    import ctypes as C
    import struct
    from civ6_host.runtime.script_context_service import ScriptContextService
    from civ6_host.runtime.script_context_source import verify_xp1, SOURCE
    from civ6_host.runtime.script_event_source import verify_xp1 as verify_events
    from civ6_host.runtime.script_event_service import ScriptEventService
    from civ6_host.runtime.native.native_core_lock import NativeCoreLock
    from civ6_host.runtime.native.native_setup import local_reader
    from civ6_host.runtime.native.native_include_registry import IncludeSource
    from civ6_host.runtime.native.native_gameplay_script_registry import NativeGameplayScriptRegistry,GameplayScriptEntry
    read=local_reader();owner=C.addressof(host.aux_object)
    inner=struct.unpack('<Q',read(context+8,8))[0]
    manager=verify_xp1(core._handle,read,inner=inner,auxiliary=owner)
    getter=C.WINFUNCTYPE(C.c_void_p)(core._handle+0x51A9D0)
    if getter()!=manager:raise ValueError('Official script manager getter differs')
    def header():
        raw=read(manager,0x30)
        return {'active_count':struct.unpack_from('<I',raw,0x20)[0],
                'head':struct.unpack_from('<I',raw,0x24)[0],
                'tail':struct.unpack_from('<I',raw,0x28)[0]}
    before=header()
    status_receipt=None;a0_receipt=None;facade_receipt=None;aux90_receipt=None
    if before['active_count'] or before['head']!=0xFFFFFFF or before['tail']!=0xFFFFFFF:
        raise ValueError('Diagnostic requires an empty initialized script manager')
    composed=selected_stage() in ('load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90')
    directory=run_dir/'context-scripts';directory.mkdir()
    common=b"""include('ContextHelper')
assert(ContextHelper==41 and type(Game.GetCurrentGameTurn)=='function')
assert(DB.Query('SELECT COUNT(*) AS n FROM Units')[1].n > 0)
assert(type(GlobalParameters.COMBAT_BASE_DAMAGE)=='number')
local calls=0
GameEvents.CivHostContextProbe.Add(function()
  calls=calls+1; ProbeCalls=calls; return true
end)
"""
    if composed:
        common += b"assert(MapConfiguration.GetValue('CIV6_HOST_LOAD_SEED')==23)\nassert(type(Game.GetProperties())=='table')\n"
        seed=staged['typed_values_after'][-1]['key']
        common=common.replace(b'function()',
            f'function(values) assert(values[{C.c_int32(seed).value}]==23)'.encode(),1)
    wire_mode=selected_wire_mode()
    files=([directory/'bytes-one.lua',directory/'bytes-two.lua'] if wire_mode
           else [directory/'Hote.ÃƒÂ©.lua',directory/'Second.lua'])
    names=['../../../DLC/Expansion2/Scripts/Hote.ÃƒÂ©.lua',
           '../../../DLC/Expansion2/Scripts/Second.lua']
    if wire_mode:
        common+=b"local ok,msg=pcall(function() error('wire-source-check') end)\nassert(not ok)\nSourceName=tostring(msg)\n"
    for i,p in enumerate(files):
        p.write_bytes(common+f"Marker={i+1}\n".encode())
    registry=NativeGameplayScriptRegistry([directory],selected_scripts=[
        GameplayScriptEntry(directory,files[i].name) for i in (0,1,0)],
        wire_paths=[names[i] for i in (0,1,0)] if wire_mode else None)
    native_names=list(registry.wire_paths)
    for index,name in enumerate(native_names):
        expected=name.encode('utf-16-le')+b'\0\0'
        if read(registry.get(index),len(expected))!=expected:
            raise ValueError('Registry changed the selected native UTF-16 path')
    runtime.set_include_sources([IncludeSource('ContextHelper.lua',b'ContextHelper=41')])
    runtime.attach_game_events(child)
    def bootstrap(context_child,name):
        runtime.attach_standard_libraries(context_child)
        runtime.attach_game_events(context_child)
        runtime.attach_include(context_child)
        for namespace in ('DB','GameInfo','GlobalParameters','Path','Locale'):
            runtime.namespaces.register(context_child,namespace)
        runtime.attach_native_game_api(context_child)
        runtime.execute(context_child,b'StateName='+_lua_bytes(name).encode(),b'@diagnostic_context_name')
    services=None;copy_receipt=None;application_receipt=None;deferred_receipt=None;control_receipt=None;argument_receipt=None
    if composed:
        from civ6_host.runtime.saved_load_services import SavedLoadServices
        from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
        services=SavedLoadServices(backend,runtime,child,registry,core_sha256=XP1_CORE_SHA256,
            script_hashes={p:digest(p.read_bytes()) for p in files},bootstrap=bootstrap,
            saved_map_values=(('CIV6_HOST_LOAD_SEED',23),),saved_config_sha=staged['after']['sha256'])
        copy_receipt=copy_group(core,context,backend,staged,services=services)
        if selected_stage()=='application':
            application_receipt=application_group(core,context,backend,services)
        if selected_stage()=='deferred':
            deferred_receipt=deferred_group(core,context,backend,services,run_dir)
        if selected_stage()=='control':
            control_receipt=control_group(core,context,backend,services)
        if selected_stage()=='arguments':
            argument_receipt=argument_group(core,context,backend,services,staged)
        if selected_stage()=='status':
            status_receipt=status_group(core,context,backend,services)
        if selected_stage()=='a0':
            a0_receipt=a0_group(core,context,backend,services)
        if selected_stage()=='a0_scope':
            a0_receipt=a0_scope_group(core,context,backend,services)
        if selected_stage()=='aux90':
            aux90_receipt=aux90_group(core,context,backend,services,runtime)
        if selected_stage()=='a0_control':
            a0_receipt,control_receipt=a0_controller_group(core,context,backend,services)
        if selected_stage()=='facades':
            facade_receipt=facade_group(core,context,backend,services)
        if selected_stage()=='player_queries':
            host._qualification_core_lock=NativeCoreLock(host,runtime.host)
            a0_receipt=player_query_group(core,context,backend,services)
        contexts=services.contexts
    else:
        contexts=ScriptContextService(host,runtime,registry,expected_hashes={p:digest(p.read_bytes()) for p in files},
                                     bootstrap=bootstrap,read=read)
    previous={s:p[0] for s,p in contexts.previous.items()}
    notifications=[]
    def notified(unused,ptr):
        # Never let Python exceptions escape an unmanaged C callback.
        notifications.append(contexts.names[ptr].decode('utf-8')
                             if ptr in contexts.loaded else 'INVALID_NOTIFICATION')
    spy=C.WINFUNCTYPE(None,C.c_void_p,C.c_void_p)(notified)
    hook=runtime.host.LAB_ScriptContextNotifySetHook
    hook.argtypes,hook.restype=[C.c_void_p,C.c_void_p,C.c_void_p],C.c_int
    if hook(runtime.root,None,C.cast(spy,C.c_void_p)):
        raise ValueError('Diagnostic notification hook refused')
    load=C.WINFUNCTYPE(C.c_uint8,C.c_void_p)(core._handle+0x51AAA0)
    result=load(manager)
    loaded=header()
    if result!=1 or loaded['active_count']!=2 or len(contexts.lifetime.handles)!=2 or notifications!=['Hote.ÃƒÂ©','Second','Hote.ÃƒÂ©']:
        raise ValueError('Native script load/replacement/notification differs')
    # Exercise newly loaded listeners through an actual official wrapper.
    verify_events(core._handle,read,host_pointer=host.pointer,auxiliary_pointer=owner)
    if not hasattr(host,'_qualification_core_lock'):
        host._qualification_core_lock=NativeCoreLock(host,runtime.host)
    events=services.events if composed else ScriptEventService(host,runtime)
    events.emit=lambda kind,**fields:event_telemetry(host,kind,**fields)
    wrapper=C.WINFUNCTYPE(C.c_uint8,C.c_void_p,C.c_char_p,C.c_void_p,C.POINTER(C.c_uint8))(core._handle+0x20CD0)
    create=C.WINFUNCTYPE(C.c_void_p,C.c_void_p)(host.aux_vtable[0x40//8])
    release=C.WINFUNCTYPE(None,C.c_void_p,C.c_void_p)(host.aux_vtable[0x48//8])
    payload=create(owner)
    if not payload:raise ValueError('Empty script payload was not allocated')
    if composed:
        vt=C.c_void_p.from_address(payload).value
        append=C.WINFUNCTYPE(C.c_uint32,C.c_void_p,C.c_void_p)(C.c_void_p.from_address(vt+0x10).value)
        if append(payload,backend.owner.snapshot()['map_normalized'])!=0:
            raise ValueError('Composed native map payload append failed')
    output=C.c_uint8(0xA5)
    if wrapper(owner,b'CivHostContextProbe',payload,C.byref(output))!=1 or output.value!=1:
        raise ValueError('Loaded script event listeners did not execute')
    rows=[]
    for ptr in contexts.lifetime.handles:
        ctx=contexts.lifetime._contexts[ptr]
        value=runtime.evaluate_text(ctx,b'return tostring(Marker)..":"..tostring(ProbeCalls)..":"..StateName').decode('utf-8')
        rows.append(value)
    if set(rows)!={'1:1:Hote.ÃƒÂ©','2:1:Second'}:
        raise ValueError('Loaded script environments leaked or lost listeners')
    source_names=[]
    if wire_mode:
        for ptr in contexts.lifetime.handles:
            ctx=contexts.lifetime._contexts[ptr]
            message=runtime.evaluate_text(ctx,b'return SourceName').decode('utf-8')
            source_names.append(message)
    clear=C.WINFUNCTYPE(None,C.c_void_p)(core._handle+0x51B200)
    clear(manager)
    after=header()
    if after['active_count'] or contexts.lifetime.handles or contexts.names:
        raise ValueError('Native manager clear did not release all contexts')
    runtime.lua['gc'](runtime.root,2,0)
    output=C.c_uint8(0xA5)
    if wrapper(owner,b'CivHostContextProbe',payload,C.byref(output))!=0 or output.value!=0:
        raise ValueError('Cleared script contexts retained event listeners')
    release(owner,payload)
    if services is not None:
        services.close()
        if aux90_receipt is not None:
            events=services.events
            table=C.addressof(host.aux_vtable)
            if (not events.closed or events.aux90_poisoned or events.dispatch_depth
                    or host.aux_vtable[0x90//8]!=events.previous[0x90][0]
                    or host._slot_bindings.get((table,0x90))!=events.previous[0x90][1]
                    or host._script_event_owner is not None):
                raise ValueError('Postload AUX90 owner/callback was not restored')
            aux90_receipt.update(callback_slot_restored=True,event_service_closed=True)
        if facade_receipt is not None:
            f=services.cache_facades
            if (not f.closed or f.quarantined or not f.facades._closed
                    or any(getattr(f.facades,k) for k in ('game_facade','cache_service','system_facade','cache_b0_result','cache_c0_result','outer'))):
                raise ValueError('Cache facades did not release all references before Core destruction')
            facade_receipt.update(all_wrappers_released=True,borrowed_context_not_released=True,public_gate_opened=False)
        if status_receipt is not None:
            status=services.status_messages
            if not status.closed or not status.game._closed or status.game.game_facade or host.vtable[0xC0//8]!=status.previous[0]:
                raise ValueError('Status owner did not restore/release its callback and facade')
            status_receipt.update(callback_slot_restored=True,facade_released=True)
        if a0_receipt is not None:
            arguments=services.event_arguments
            if not arguments.closed or not arguments.consumer.closed or host.vtable[0xA0//8]!=arguments.previous[0]:
                raise ValueError('A0 family owner did not restore/close')
            a0_receipt.update(callback_slot_restored=True,consumer_closed=True)
            if selected_stage()=='a0_scope':
                d=services.deferred_events
                if (not d.closed or d.quarantined or d.pending or d.host_notification_counter
                        or d.host_metadata_counter or host._deferred_service_owner is not None
                        or any(host.vtable[slot//8]!=before[0] or
                               host._slot_bindings.get((C.addressof(host.vtable),slot))!=before[1]
                               for slot,before in d.previous.items())):
                    raise ValueError('Scoped transport callbacks/owners were not restored')
                a0_receipt.update(deferred_callback_slots_restored=True,deferred_owner_closed=True)
            if hasattr(services,'player_queries'):
                q=services.player_queries
                if not q.closed or q.depth or q._a0_event_owner is not None:
                    raise ValueError('Player query owner still has consumers after close')
                a0_receipt.update(player_query_owner_closed=True)
        if argument_receipt is not None:
            arguments=services.event_arguments
            if (not arguments.closed or not arguments.reader.closed
                    or host.vtable[0xA0//8]!=arguments.previous[0]):
                raise ValueError('Event argument owner did not restore/release its callback')
            argument_receipt.update(callback_slot_restored=True,reader_closed=True)
        if control_receipt is not None:
            inputs=services.control_inputs
            if (not inputs.closed or not inputs.code.closed or hasattr(services.deferred_events,'turn_begin_state')
                    or hasattr(host,'configured_local_player_id')
                    or any(host.vtable[s//8]!=v[0] for s,v in inputs.previous.items())):
                raise ValueError('Control input lifecycle did not restore/release its owners')
            control_receipt.update(callback_slots_restored=True,native_controller_code_closed=True,
                native_controller_object_closed=True,local_id_binding_removed=True)
    else:events.close();contexts.close()
    registry.close()
    if any(host.aux_vtable[s//8]!=v for s,v in previous.items()):
        raise ValueError('Context callbacks were not restored')
    return {'source_sha256':SOURCE[1],'shared_services_composed':composed,'configuration_copy':copy_receipt,'application_notifications':application_receipt,'deferred_feedback':deferred_receipt,'control_inputs':control_receipt,'argument_transport':argument_receipt,'status_messages':status_receipt,'a0_families':a0_receipt,'cache_facades':facade_receipt,'postload_aux90':aux90_receipt,'official_loader_called':True,'official_clear_called':True,
            'manager_owned_by_core_until_destroy':True,'before':before,'loaded':loaded,'after':after,
            'selected_script_count':3,'distinct_script_count':2,'same_name_context_replaced':True,
            'notifications':notifications,'environment_results':rows,'released_listeners_collected':True,
            'callback_slots_restored':True,'fixture_scripts':True,'complete_exe_context':False,
            'strict_load_error_policy':True,'path_redirection_supported':False,'saved_game_loaded':False,
            'script_wire_mode':wire_mode,'ordered_native_paths':native_names,
            'physical_source_paths':[str(path) for path in files],
            'lua_protected_error_messages':source_names,'lua_debug_source_names_verified':False,
            'source_name_verification':'retained native_script_buffer_executed name records and pinned native loader, not unavailable Lua debug reflection'}


def facade_group(core,context,backend,services):
    """Native prepared-cache lifetime; deliberately no loaded-state publication."""
    import struct
    from civ6_host.runtime.cache_facade_profiles import SOURCE
    f=services.install_cache_facades();read=backend.runtime.read
    rows=[];calls=[];original=f.backend.call
    def traced(target,*arguments):
        result=original(target,*arguments)
        calls.append({'rva':hex(target-core._handle),'receiver':arguments[0]})
        return result
    f.backend.call=traced
    def pointers():
        return {k:getattr(f.facades,k) for k in ('game_facade','cache_service','system_facade','cache_b0_result','cache_c0_result')}
    initial=pointers()
    for index in range(2):
        before=read(f.identity['member']+0x28,28)
        result=f.copy_cached_metadata()
        after=read(f.identity['member']+0x28,28)
        if before!=after or result.output!=before or result.copied_value!=struct.unpack_from('<I',before,24)[0]:
            raise ValueError('Native cache metadata copy differs from its real source bytes')
        if f.public_cache_ready:raise ValueError('Prepared cache incorrectly exposed as public game state')
        rows.append(dict(index=index,output_hex=result.output.hex(),returned_dword=result.copied_value,
            source_bytes_equal=True,pointers=pointers()))
    for attr in ('cache_b0_result','cache_c0_result'):
        if rows[0]['pointers'][attr]==rows[1]['pointers'][attr]:
            raise ValueError('Result factory did not replace its prior live reference')
    value=f.retained_game_value()
    count=len(calls)
    for blocked in (f.facades.refresh,lambda:f.backend.call(core._handle+f.backend.abi.publish_rva,f.facades.game_facade,1)):
        try:blocked()
        except ValueError:pass
        else:raise ValueError('Unqualified full cache publication was admitted')
    if len(calls)!=count or f.quarantined or f.public_cache_ready:
        raise ValueError('Refused cache publication caused an effect')
    return dict(source_sha256=SOURCE[1],identity=f.identity,initial_wrappers=initial,
        metadata_copies=rows,retained_game_native_value=value,native_calls=calls,
        prepared_metadata_only=True,uninitialized_bytes_not_normalized=True,copy_canaries_unchanged=True,
        full_population_refused=True,loaded_game_qualified=False,player_observation=False)


def deferred_group(core,context,backend,services,run_dir):
    """Exercise the shared transport with an actual native registry subscriber.

    The packed identifier is diagnostic data, not a created gameplay snapshot.
    Registration uses the official Core ABI; no memory patching or fake empty
    registry. The real B0 snapshot producer still requires a valid player/Game.
    """
    import ctypes as C
    import struct
    from civ6_host.runtime.cache_update_profiles import verify_bodies,registry_snapshot,SOURCE
    from civ6_host.runtime.native.native_setup import local_reader
    read=local_reader();base=core._handle;host=backend.host;key=0xF051C6AA
    verify_bodies(base,read,('keyed_register','notification_begin','notification_end','notification_vector_insert'))
    before=registry_snapshot(base,read,key)
    if before['node'] is not None:
        raise ValueError('Diagnostic CacheUpdate key already registered')
    service=services.install_deferred_events(optional_preprocessor=None,queue_metadata_service=None,limit=32)
    original={s:p[0] for s,p in service.previous.items()}
    receiver=C.c_uint64(0x1122334455667788);received=[];callback_errors=[];callback_shapes=[]
    enqueue=C.WINFUNCTYPE(C.c_int32,C.c_void_p,C.c_uint32,C.c_uint64)(host.vtable[0xB0//8])
    callback_type=C.WINFUNCTYPE(None,C.c_void_p,C.POINTER(C.c_uint32))
    def receive(pointer,args):
        try:
            if pointer!=C.addressof(receiver):raise ValueError('Cache callback receiver differs')
            received.append(tuple(args[i] for i in range(4)))
            callback_shapes.append([len(service.pending),service.consumed_count])
            if len(received)==1 and enqueue(host.pointer,key,(0x80000001<<32)|0xFFFFFFFE)!=0:
                raise ValueError('Callback feedback enqueue refused')
        except BaseException as error:
            callback_errors.append(type(error).__name__+': '+str(error))
    callback=callback_type(receive)
    internal=(C.c_void_p*2)();cache=(C.c_void_p*2)(C.addressof(receiver),C.cast(callback,C.c_void_p).value)
    _DIAGNOSTIC_PINS.append((core,host,service,receiver,callback,internal,cache,receive))
    registrar=C.WINFUNCTYPE(None,C.c_uint32,C.c_void_p,C.c_void_p)(base+0x706B0)
    registrar(key,internal,cache)
    registered=registry_snapshot(base,read,key)
    expected=((0,0,C.addressof(receiver),C.cast(callback,C.c_void_p).value),)
    if registered['subscribers']!=expected or registered['entry_count']!=before['entry_count']+1:
        raise ValueError('Native CacheUpdate registration differs from the supplied pair')
    host._qualification_deferred_registry={'base':base,'read':read,'key':key,
        'subscribers':registered['subscribers'],'run_dir':run_dir}

    code=0x5A9A0329
    begin=C.WINFUNCTYPE(None,C.c_uint32)(base+0x517880)
    end=C.WINFUNCTYPE(None,C.c_uint32)(base+0x5178F0)
    def scope():
        start,stop,capacity=struct.unpack('<QQQ',read(base+0x9F6BB8,24))
        if stop<start or capacity<stop or (stop-start)%4 or stop-start>4096:
            raise ValueError('Notification stack shape differs')
        values=struct.unpack('<'+'I'*((stop-start)//4),read(start,stop-start)) if stop!=start else ()
        return {'depth':len(values),'codes':list(values),
            'host_count':service.host_notification_counter,'metadata_count':service.host_metadata_counter}
    scopes=[scope()]
    if scopes[0]['depth'] or scopes[0]['host_count'] or scopes[0]['metadata_count']:
        raise ValueError('Notification diagnostic requires a closed initial scope')
    begin(code);scopes.append(scope());begin(code);scopes.append(scope())
    # Both records retain their FIFO position while the first subscriber appends
    # a third. Unsigned words must survive without Python sign conversion.
    for selector,identifier in ((0x3AFC843A,7),(0xFFFFFFFF,0xFFFFFFFF)):
        if enqueue(host.pointer,key,(identifier<<32)|selector)!=0:
            raise ValueError('Native HOST B0 callback did not return its official result')
    pending_before=[r.hex() for r in service.pending]
    count=service.drain()
    end(code);scopes.append(scope());end(code);scopes.append(scope())
    end(code);scopes.append(scope())  # Core empty-stack path must not emit F0.
    counters=[(r['depth'],r['host_count'],r['metadata_count']) for r in scopes]
    if counters!=[(0,0,0),(1,1,0),(2,2,0),(1,1,1),(0,0,0),(0,0,0)]:
        raise ValueError('Native notification scopes differ from shared EXE counters')
    expected_rows=[(key,0,0x3AFC843A,7),(key,0,0xFFFFFFFF,0xFFFFFFFF),(key,0,0xFFFFFFFE,0x80000001)]
    if callback_errors or received!=expected_rows or count!=3 or service.pending:
        raise ValueError('Native CacheUpdate feedback result differs: '+repr((callback_errors,received,count)))
    if callback_shapes!=[[2,0],[2,1],[1,2]] or service.drain()!=0:
        raise ValueError('Native callback consumption order differs or records replayed')
    service.close()
    if any(host.vtable[s//8]!=v for s,v in original.items()):
        raise ValueError('Deferred callbacks were not restored')
    return {'source_sha256':SOURCE[1],'official_registrar_called':True,
        'official_outer_dispatch_called':True,'diagnostic_subscriber':True,
        'before_registry':before,'registered_registry':registered,'received_words':received,
        'callback_queue_shapes':callback_shapes,'initial_queued_records':pending_before,
        'consumed_count':service.consumed_count,'consumed_bytes':service.consumed_bytes,
        'consumed_sha256':service.consumed_digest.hexdigest(),'notification_scopes':scopes,
        'callback_slots_restored':True,'callbacks_pinned_through_process_exit':True,
        'natural_snapshot_publisher_called':False,'snapshot_release_qualified':False,
        'loaded_game_scheduler_qualified':False,'saved_game_loaded':False}


def argument_group(core,context,backend,services,staged):
    """Read real owned maps and Core-built temporary maps without a fake Game."""
    import ctypes as C
    import struct
    from civ6_host.runtime.event_argument_source import verify_wrappers_live,guard_state,SOURCE
    from civ6_host.runtime.cache_update_profiles import registry_snapshot
    from civ6_host.runtime.native.native_setup import local_reader
    read=local_reader();base=core._handle;host=backend.host
    verify_wrappers_live(base,read)
    before=guard_state(base,context,read)
    if not before['a0_open']:
        raise ValueError('Native A0 guard is closed or Session is absent; no flag will be patched')
    kinds=(0x237DDDA8,0x3F5E7F8D)
    for kind in kinds:
        if registry_snapshot(base,read,kind)['node'] is not None:
            raise ValueError('Diagnostic event key has native subscribers; do not overwrite them')
    deferred=services.install_deferred_events(optional_preprocessor=None,queue_metadata_service=None)
    arguments=services.install_event_arguments(normalizer_transform=None,dynamic_registrations=())
    pointer=backend.owner.snapshot()['map_normalized']
    fields=arguments.reader.fields(pointer)
    expected=[r for r in staged['typed_values_after'] if r['scope']=='map_normalized']
    if len(fields)<=3 or any(row['key'] not in fields for row in expected):
        raise ValueError('Owned native map did not exercise the generic tree reader')
    owned=[]
    for row in expected:
        raw=fields[row['key']];tag=struct.unpack_from('<H',raw)[0]
        if tag!=row['tag']:raise ValueError('Owned map variant tag differs from native readback')
        if tag in (2,3) and struct.unpack_from('<I',raw,8)[0]!=row['value']:
            raise ValueError('Owned native scalar bits differ')
        owned.append({'key':row['key'],'tag':tag,'scalar':struct.unpack_from('<I',raw,8)[0] if tag in (2,3) else None,
                      'pointee_data_borrowed':tag not in (2,3)})
    captured=[]
    def emit(kind,**fields):
        if kind=='native_shared_absent_scalar_event':captured.append(fields)
        host.emit(kind,**fields)
    arguments.emit=emit
    two=C.WINFUNCTYPE(C.c_uint32,C.c_uint64,C.c_uint32)(base+0x5195A0)
    three=C.WINFUNCTYPE(C.c_uint32,C.c_uint64,C.c_uint32,C.c_uint32)(base+0x519650)
    result1=two(kinds[0],0xFFFFFFFF)
    result2=three(kinds[1],0x80000000,0xFFFFFFFF)
    after=guard_state(base,context,read)
    if before!=after or not after['a0_open'] or (result1,result2)!=(0,0) or arguments.count!=2 or len(captured)!=2:
        raise ValueError('Official A0 wrapper/guard/callback results differ')
    def values(row):
        return {int(k,16):(struct.unpack_from('<H',bytes.fromhex(v))[0],
                          struct.unpack_from('<I',bytes.fromhex(v),8)[0]) for k,v in row['fields'].items()}
    expected_values=[{0xA1E5A149:(3,0),0xD6FCF3E4:(2,0xFFFFFFFF)},
                     {0xA1E5A149:(3,0),0xD6FCF3E4:(2,0x80000000),0xA1FBC372:(2,0xFFFFFFFF)}]
    if [values(row) for row in captured]!=expected_values:
        raise ValueError('Core-built temporary argument maps differ from source ABI')
    if deferred.pending or deferred._sequence or deferred.consumed_count:
        raise ValueError('Source-absent EXE event unexpectedly created a deferred record')
    return {'source_sha256':SOURCE[1],'owned_native_map_field_count':len(fields),
        'owned_native_variant_headers':owned,'pointer_pointees_deep_copied':False,
        'official_wrapper_rvas':['0x5195a0','0x519650'],'return_values':[result1,result2],
        'temporary_map_callbacks':captured,'guards_before':before,'guards_after':after,
        'core_flags_patched':False,'core_internal_dispatch_preserved':True,
        'registered_exe_events_substituted':False,'callback_slot_restored':False,'reader_closed':False,
        'c0_bound':False,'gameplay_event_effects_qualified':False,'saved_game_loaded':False}


def a0_scalar_cases(profile):
    """Source-family cases, with excluded keys reported rather than substituted."""
    from civ6_host.runtime.native.native_unary_event_family import UNARY_EVENT_SOURCES
    from civ6_host.runtime.native.native_two_value_event_family import MEMBERS
    from civ6_host.runtime.native.native_scalar_no_metadata_family import SOURCES
    from civ6_host.runtime.native.native_host_events import EVENT_KIND,INTEGER_EVENT_KIND
    rows=[];excluded=[]
    def add(kind,values,record_type,family,boolean=False):
        if kind not in profile.record_types_by_kind:
            excluded.append({'kind':hex(kind),'family':family});return
        if record_type not in profile.record_types_by_kind[kind]:
            raise ValueError('Scalar family source and A0 route record types disagree')
        rows.append(dict(kind=kind,values=values,record_type=record_type,family=family,boolean=boolean))
    add(EVENT_KIND,(0x80000000,0xFFFFFFFF),0x10C,'boolean',True)
    add(INTEGER_EVENT_KIND,(0x80000000,0xFFFFFFFF),0x109,'integer')
    for kind,row in UNARY_EVENT_SOURCES.items():add(kind,(0xFFFFFFFF,),row['record_type'],'unary')
    for kind,row in MEMBERS.items():
        add(kind,(0x80000000,0xFFFFFFFF),int(row['record_type'],16),'two_values')
        add(kind,(0xFFFFFFFF,),int(row['record_type'],16),'two_values_missing_second')
    for kind,row in SOURCES.items():add(kind,(0x80000000,),row['record_type'],'scalar_no_metadata')
    if not rows:raise ValueError('No source-admitted scalar family cases')
    return rows,excluded


def a0_group(core,context,backend,services):
    """Exercise registered EXE scalar consumers through real XP1 temporary maps."""
    import ctypes as C
    import struct
    from civ6_host.runtime.native.native_36c9b2b4_pair_codec import EMPTY_RECEIVER_STATE
    from civ6_host.runtime.native.native_setup import local_reader
    from civ6_host.runtime.cache_update_profiles import registry_snapshot
    from civ6_host.runtime.event_argument_source import guard_state
    read=local_reader();base=core._handle;host=backend.host
    before=guard_state(base,context,read)
    if not before['a0_open']:raise ValueError('Official A0 guards are closed')
    deferred=services.install_deferred_events(optional_preprocessor=None,queue_metadata_service=None)
    arguments=services.install_event_arguments(normalizer_transform=None,dynamic_registrations=())
    consumer=arguments.install_consumers(receiver_state=dict(EMPTY_RECEIVER_STATE),
        pre_turn_immediate_state=dict(EMPTY_RECEIVER_STATE),entity_listener_count=0)
    def telemetry(kind,**fields):
        event_telemetry(host,'native_a0_family_event',producer_event_name=kind,**fields)
    deferred.emit=consumer.emit=telemetry
    cases,excluded=a0_scalar_cases(consumer.profile)
    for kind in {row['kind'] for row in cases}:
        if registry_snapshot(base,read,kind)['node'] is not None:
            raise ValueError('A0 scalar diagnostic has native subscribers; do not overwrite/skip their behavior')
    two=C.WINFUNCTYPE(C.c_uint32,C.c_uint64,C.c_uint32)(base+0x5195A0)
    three=C.WINFUNCTYPE(C.c_uint32,C.c_uint64,C.c_uint32,C.c_uint32)(base+0x519650)
    observed=[]
    for row in cases:
        count=len(deferred.pending);values=row['values']
        result=(two(row['kind'],*values) if len(values)==1 else three(row['kind'],*values))
        if result!=0 or len(deferred.pending)!=count+1:
            raise ValueError('Registered A0 scalar consumer did not produce exactly its source record')
        record=deferred.pending[-1]
        if (len(record)!=96 or struct.unpack_from('<III',record)!=(96,row['record_type'],count+1)
                or struct.unpack_from('<I',record,84)[0]!=values[0]):
            raise ValueError('A0 scalar native record header/value differs')
        if row['boolean']:
            if record[88]!=1:raise ValueError('A0 source boolean conversion differs')
        elif row['family'] in ('integer','two_values','two_values_missing_second'):
            if struct.unpack_from('<I',record,88)[0]!=(values[1] if len(values)==2 else 0):
                raise ValueError('A0 second field/default differs')
        observed.append(dict(kind=hex(row['kind']),family=row['family'],record_type=hex(row['record_type']),
            sequence=count+1,record_sha256=digest(record)))
    consumed=deferred.drain()
    if (consumed!=len(cases) or deferred.pending or arguments.count!=len(cases)
            or before!=guard_state(base,context,read)):
        raise ValueError('A0 grouped consumption or native guards differ')
    return {'admitted_source_kind_count':len(consumer.profile.record_types_by_kind),
        'native_scalar_case_count':len(cases),'native_scalar_kinds':len({r['kind'] for r in cases}),
        'cases':observed,'source_excluded_scalar_cases':excluded,'consumed_records':consumed,
        'queue_empty':True,'guards_unchanged':True,'core_registry_mutated':False,
        'callback_slot_restored':False,'consumer_closed':False,
        'all_admitted_event_shapes_executed_natively':False,'natural_gameplay_publication_qualified':False,
        'saved_game_loaded':False,'public_visibility_qualified':False}


def aux90_group(core,context,backend,services,runtime):
    """Prepared transport with explicit Lua fixtures, never outer+160/gameplay.

    Tables below are diagnostic stimuli to the actual protected C dispatcher.
    They are restored by identity before closing services. This does not supply
    missing game listeners or qualify category2 factory/listener creation.
    """
    import ctypes as C
    from civ6_host.runtime.native.native_core_lock import NativeCoreLock
    from civ6_host.runtime.native.native_script_primitives import evaluate_lua
    from civ6_host.runtime.postload160_source import SOURCE,xp1_source
    host=backend.host;proof=xp1_source();traces=[]
    if hasattr(host,'_qualification_core_lock'):
        raise ValueError('AUX90 qualification requires one newly owned Core lock')
    class ObservedLock(NativeCoreLock):
        tracking=False
        def owned(self,this):
            value=super().owned(this)
            if self.tracking:traces.append(dict(slot='0x30',owned=value))
            return value
        def acquire(self,this):
            before=self.calls['owned']();super().acquire(this)
            if self.tracking:traces.append(dict(slot='0x40',before=before,after=self.calls['owned']()))
        def release(self,this):
            before=self.calls['owned']();super().release(this)
            if self.tracking:traces.append(dict(slot='0x38',before=before,after=self.calls['owned']()))
    lock=ObservedLock(host,runtime.host)
    host._qualification_core_lock=lock
    services.install_postload_aux90_null()
    service=services.events
    state_sizes={'current':1,'pending':1,'requested':1,'remaining':4}
    def autoplay_state():
        values={}
        for name,size in state_sizes.items():
            raw=backend.runtime.read(core._handle+proof['contract']['state_globals'][name],size)
            if type(raw) is not bytes or len(raw)!=size:
                raise ValueError('Incomplete AutoPlay state observation')
            values[name]=raw.hex()
        return values
    autoplay_before=autoplay_state()
    service.emit=lambda name,**fields:event_telemetry(host,name,**fields)
    wrapper=C.WINFUNCTYPE(C.c_uint8,C.c_void_p,C.c_uint32,C.c_char_p,C.c_void_p)(
        core._handle+proof['contract']['callback']['wrapper_rva'])
    owner=C.addressof(host.aux_object)
    leave=runtime.host.LAB_ScriptLockLeave
    leave.argtypes,leave.restype=[],C.c_int
    def balanced():
        if runtime.lua['gettop'](runtime.root) or leave()!=0:
            raise ValueError('AUX90 left a root stack value or owned script lock')
    def root_code(source):
        evaluate_lua(runtime.lua,runtime.root,source+'\nreturn 1',b'@xp1_aux90_fixture')
        balanced()
    root_code('''assert(Civ6HostAux90Fixture==nil)
Civ6HostAux90Fixture={original=LuaEventsByContext,calls=0,legacy=0}
''')
    original_dispatch=runtime.dispatch_aux_event_category_null
    observations=[]
    def observed_dispatch(name,*,category,arguments=None):
        # This observes the real wrapper's release, never releases it for Core.
        if lock.calls['owned']()!=0:
            raise ValueError('Official AUX wrapper did not release the Core lock before Lua')
        result=original_dispatch(name,category=category,arguments=arguments)
        traces.append(dict(slot='aux90',category=category,name=name.decode('ascii'),outcome=result))
        observations.append(result)
        return result
    runtime.dispatch_aux_event_category_null=observed_dispatch
    fixtures=(
        ('category_nil','LuaEventsByContext={}'),
        ('event_nil','LuaEventsByContext={[2]={}}'),
        ('call_nil','LuaEventsByContext={[2]={AutoPlayStart={},AutoPlayEnd={}}}'),
        ('call_returned','''local function call(...)
 assert(select('#',...)==0); Civ6HostAux90Fixture.calls=Civ6HostAux90Fixture.calls+1
 return false,'discarded second result',17
end
LuaEventsByContext={[2]={AutoPlayStart={Call=call},AutoPlayEnd={Call=call}}}'''),
    )
    results=[]
    for expected,setup in fixtures:
        root_code(setup)
        for name in (b'AutoPlayStart',b'AutoPlayEnd'):
            for held in (False,True):
                if held:lock.acquire(host.pointer)
                traces.clear();count=len(observations);lock.tracking=True
                try:result=wrapper(owner,1,name,None)
                finally:lock.tracking=False
                if (result!=1 or len(observations)!=count+1 or observations[-1]!=expected
                        or lock.owned(host.pointer)!=held or service.dispatch_depth or service.aux90_poisoned):
                    raise ValueError('Official AUX90 result, lookup outcome or ownership differs')
                expected_trace=[dict(slot='0x30',owned=held)]
                if held:expected_trace.append(dict(slot='0x38',before=1,after=0))
                expected_trace.append(dict(slot='aux90',category=2,name=name.decode(),outcome=expected))
                if held:expected_trace.append(dict(slot='0x40',before=0,after=1))
                if traces!=expected_trace:raise ValueError('Core-owned AUX scope callback order differs')
                if held:lock.release(host.pointer)
                balanced()
                results.append(dict(name=name.decode(),initial_core_lock_owned=held,
                    native_al_result=result,outcome=expected,callback_order=list(traces),root_stack_empty=True))
    runtime.dispatch_aux_event_category_null=original_dispatch
    root_code('assert(Civ6HostAux90Fixture.calls==4)')

    # Protected errors are exercised directly at the C helper boundary. Sending
    # invalid requests through HOST would intentionally terminate the process;
    # no service poison is reset to turn those failures into success.
    errors=[]
    invalid_states=(
        ('registry_nil','LuaEventsByContext=nil','registry is unavailable'),
        ('category_wrong_type','LuaEventsByContext={[2]=false}','event context is unavailable'),
        ('event_wrong_type','LuaEventsByContext={[2]={AutoPlayStart=false}}','event object is not registered'),
        ('call_wrong_type','LuaEventsByContext={[2]={AutoPlayStart={Call=false}}}','Call method is unavailable'),
        ('call_error',"LuaEventsByContext={[2]={AutoPlayStart={Call=function() error('aux90-native-error') end}}}",'aux90-native-error'),
        ('event_lookup_error',"LuaEventsByContext={[2]=setmetatable({},{__index=function() error('aux90-event-lookup-error') end})}",'aux90-event-lookup-error'),
        ('call_lookup_error',"LuaEventsByContext={[2]={AutoPlayStart=setmetatable({},{__index=function() error('aux90-call-lookup-error') end})}}",'aux90-call-lookup-error'),
    )
    for label,setup,marker in invalid_states:
        root_code(setup)
        try:original_dispatch(b'AutoPlayStart',category=2)
        except RuntimeError as error:
            text=str(error)
            if 'native status' not in text or marker not in text:raise
            errors.append(dict(case=label,native_protected_error=text))
        else:raise ValueError('Invalid AUX lookup/call was silently accepted')
        balanced()
        if service.aux90_poisoned or lock.owned(host.pointer):
            raise ValueError('Direct C protected-error case affected the service owner')
    direct=runtime.host.LAB_Aux90DispatchCategoryNull
    direct.argtypes=[C.c_void_p,C.c_uint32,C.c_char_p,C.c_void_p,C.POINTER(C.c_uint32)]
    direct.restype=C.c_int
    refusals=[]
    for label,category,name,args in (
        ('category_zero',0,b'AutoPlayStart',None),('category_three',3,b'AutoPlayStart',None),
        ('empty_name',2,b'',None),('non_ascii_name',2,b'\x80',None),
        ('non_null_arguments',2,b'AutoPlayStart',1)):
        outcome=C.c_uint32(0xA5A5A5A5)
        status=direct(runtime.root,category,name,args,C.byref(outcome))
        if status!=-1700 or outcome.value!=0:
            raise ValueError('Native category/NULL input guard accepted an unsupported request')
        balanced();refusals.append(dict(case=label,status=status,outcome=outcome.value))
    # One control of the unchanged category1 entry point: false/multiple returns
    # are ignored and no new category2 rule changes its historical behavior.
    root_code('''LuaEventsByContext={[1]={Civ6HostAux90Legacy={Call=function(...)
 assert(select('#',...)==0);Civ6HostAux90Fixture.legacy=Civ6HostAux90Fixture.legacy+1
 return false,19
end}}}''')
    runtime.dispatch_aux_event(b'Civ6HostAux90Legacy');balanced()
    root_code('''assert(Civ6HostAux90Fixture.legacy==1 and Civ6HostAux90Fixture.calls==4)
local original=Civ6HostAux90Fixture.original
LuaEventsByContext=original
assert(LuaEventsByContext==original)
Civ6HostAux90Fixture=nil''')
    if lock.owned(host.pointer) or service.dispatch_depth or service.aux90_poisoned:
        raise ValueError('AUX90 group left lock ownership or an uncertain callback')
    autoplay_after=autoplay_state()
    if autoplay_before!=autoplay_after:raise ValueError('AUX transport changed observed AutoPlay globals')
    return dict(source_sha256=SOURCE[1],official_scope_wrapper_rva='0x22ef0',
        wrapper_calls=len(results),calls=results,protected_errors=errors,input_refusals=refusals,
        table_fixtures=True,original_registry_identity_restored=True,real_hks_dispatch=True,
        protected_stack_and_script_lock_closed=True,core_scope_owned_by_core=True,
        observed_fixture_call_count=4,legacy_category1_calls=1,fixture_returns_not_truth_tested=True,
        category2_gameplay_factory_qualified=False,official_gameplay_listeners_qualified=False,
        service_unknown_names_kinds_arguments_native_executed=False,
        service_unknown_inputs_remain_fatal=True,service_poison_reset=False,
        callback_slot_restored=False,event_service_closed=False,
        outer160_called=False,autoplay_globals_before=autoplay_before,autoplay_globals_after=autoplay_after,
        observed_autoplay_globals_unchanged=True,loaded_game_qualified=False,
        native_gameplay_publication_qualified=False,saved_game_loaded=False)


def notification_scope_source_pins():
    """Use the same scope-source closure as the owned saved session."""
    from civ6_host.runtime.a0_notification_scope_source import source_dependencies
    return source_dependencies()


def a0_scope_group(core,context,backend,services):
    """Three scalar shapes through the real XP1 map wrapper and nested scopes.

    This is prepared-context transport qualification, not a loaded-game witness.
    The other six pointer shapes and N=0,M>0 are deliberately not exercised here.
    Native constructors/setters/destructors own the two exact diagnostic maps;
    Python owns only guarded outer storage. No application/configuration map is
    reused, no native guard is patched and no record is consumed on scope exit.
    """
    import ctypes as C
    import struct
    from civ6_host.runtime.native.native_36c9b2b4_pair_codec import EMPTY_RECEIVER_STATE
    from civ6_host.runtime.event_argument_source import _verify_bodies,guard_state,SOURCE as ARGUMENT_SOURCE
    from civ6_host.runtime.cache_update_profiles import verify_bodies,registry_snapshot,SOURCE as SCOPE_SOURCE
    from civ6_host.runtime.configuration_profiles import configuration_abi,XP1_CORE_SHA256
    read=backend.runtime.read;base=core._handle;host=backend.host
    _verify_bodies(base,read,('a0_existing_map','map_constructor','map_base_constructor',
        'map_destructor','set_hash','set_uint32','map_lookup','variant_release'))
    verify_bodies(base,read,('notification_begin','notification_end','notification_vector_insert'))
    guards=guard_state(base,context,read)
    if not guards['a0_open']:raise ValueError('Official A0 guards are closed')
    abi=configuration_abi(XP1_CORE_SHA256)
    if (abi.constructor_rva,abi.destructor_rva,abi.vtable_rva)!=(0x844460,0x844580,0x93F590):
        raise ValueError('Diagnostic ParameterMap constructor/lifetime ABI differs')
    d=services.install_deferred_events(optional_preprocessor=None,queue_metadata_service=None)
    arguments=services.install_event_arguments(normalizer_transform=None,dynamic_registrations=())
    consumer=arguments.install_consumers(receiver_state=dict(EMPTY_RECEIVER_STATE),
        pre_turn_immediate_state=dict(EMPTY_RECEIVER_STATE),entity_listener_count=0)
    consumer.enable_notification_scopes()
    def telemetry(name,**fields):event_telemetry(host,'native_a0_family_event',producer_event_name=name,**fields)
    d.emit=consumer.emit=telemetry
    kinds=(0x8FEF0D8E,0x3FEAAD02,0xBF48FDA8)
    registries={kind:registry_snapshot(base,read,kind) for kind in kinds}
    if any(row['node'] is not None for row in registries.values()):
        raise ValueError('Scope diagnostic has Core subscribers; no replacement or suppression')
    constructor=C.WINFUNCTYPE(C.c_void_p,C.c_void_p)(base+abi.constructor_rva)
    destructor=C.WINFUNCTYPE(None,C.c_void_p)(base+abi.destructor_rva)
    setters={3:C.WINFUNCTYPE(C.c_void_p,C.c_void_p,C.c_uint32,C.c_uint32)(base+0x845FB0),
             2:C.WINFUNCTYPE(C.c_void_p,C.c_void_p,C.c_uint32,C.c_uint32)(base+0x845E90)}
    dispatch=C.WINFUNCTYPE(C.c_uint32,C.c_uint32,C.c_void_p)(base+0x517960)
    begin=C.WINFUNCTYPE(None,C.c_uint32)(base+0x517880)
    end=C.WINFUNCTYPE(None,C.c_uint32)(base+0x5178F0)
    guard=b'\xD6'*16;maps=[]
    expected_fields=[{0xA1E5A149:(3,0xFFFFFFFF)},
        {0xA1E5A149:(3,0xFFFFFFFF),0xD6FCF3E4:(2,0x80000000),
         0xA1FBC372:(2,11),0x38F292C8:(2,0xFFFFFFFF)}]
    def check_outer(storage):
        if storage.raw[:16]!=guard or storage.raw[-16:]!=guard:
            raise ValueError('Native map crossed its 0x58-byte outer allocation')
    for fields in expected_fields:
        storage=C.create_string_buffer(0x58+32)
        C.memmove(C.addressof(storage),guard,16)
        C.memmove(C.addressof(storage)+16+0x58,guard,16)
        pointer=C.addressof(storage)+16
        # Keep storage live on uncertain native failure; supervisor terminates
        # the process. Never guess a destructor during exception unwinding.
        _DIAGNOSTIC_PINS.append(storage)
        if constructor(pointer)!=pointer:raise ValueError('Native ParameterMap constructor result differs')
        check_outer(storage)
        if struct.unpack('<Q',read(pointer,8))[0]!=base+abi.vtable_rva:
            raise ValueError('Native ParameterMap vtable differs')
        if arguments.reader.fields(pointer):raise ValueError('Diagnostic map is not initially empty')
        for key,(tag,value) in fields.items():
            variant=setters[tag](pointer,key,value)
            if not variant:raise ValueError('Native typed setter returned NULL')
            raw=read(variant,24)
            if (struct.unpack_from('<H',raw)[0],struct.unpack_from('<I',raw,8)[0])!=(tag,value):
                raise ValueError('Native typed setter did not retain exact unsigned input')
        actual=arguments.reader.fields(pointer)
        if set(actual)!=set(fields) or any((struct.unpack_from('<H',actual[k])[0],
            struct.unpack_from('<I',actual[k],8)[0])!=v for k,v in fields.items()):
            raise ValueError('Native diagnostic argument tree differs')
        check_outer(storage);maps.append((storage,pointer,actual))
    def scope():
        start,stop,capacity=struct.unpack('<QQQ',read(base+0x9F6BB8,24))
        if stop<start or capacity<stop or (stop-start)%4 or stop-start>4096:
            raise ValueError('Native notification stack is malformed')
        codes=struct.unpack('<'+'I'*((stop-start)//4),read(start,stop-start)) if start!=stop else ()
        return (len(codes),d.host_notification_counter,d.host_metadata_counter,tuple(codes))
    special=0x5A9A0329;scopes=[scope()];observed=[]
    if scopes[0]!=(0,0,0,()):raise ValueError('Scope group requires closed initial counters/stack')
    begin(special);scopes.append(scope());begin(special);scopes.append(scope())
    for scope_index,expected in enumerate(((2,2,0),(1,1,1),(2,2,1))):
        before=scope()
        if before[:3]!=expected or before[3]!=(special,)*expected[0]:
            raise ValueError('Official notification begin/end counters differ')
        for kind in kinds:
            storage,pointer,fields=maps[0 if kind==0x8FEF0D8E else 1]
            count=len(d.pending);sequence=d._sequence+1
            if dispatch(kind,pointer)!=0 or len(d.pending)!=count+1 or scope()!=before:
                raise ValueError('Scoped official event changed counters or did not enqueue exactly once')
            record=d.pending[-1];record_type,size,flag=consumer.notification_scope_profile.records[kind]
            if (len(record)!=size or struct.unpack_from('<III',record)!=(size,record_type,sequence)
                    or struct.unpack_from('<I',record,72)[0]!=flag
                    or struct.unpack_from('<I',record,80)[0]!=sequence):
                raise ValueError('Scoped record identity/metadata/sequence differs')
            if kind!=0x8FEF0D8E and struct.unpack_from('<5I',record,80)!=(sequence,0x80000000,0xFFFFFFFF,11,0xFFFFFFFF):
                raise ValueError('Scoped boost record changed unsigned payload')
            if arguments.reader.fields(pointer)!=fields or d.consumed_count:
                raise ValueError('Official dispatch mutated its input or consumed before explicit drain')
            check_outer(storage)
            observed.append(dict(kind=hex(kind),sequence=sequence,scope=list(before[:3]),
                record_type=hex(record_type),size=size,metadata_flag=flag,record_sha256=digest(record)))
        if scope_index==0:end(special);scopes.append(scope())
        elif scope_index==1:begin(special);scopes.append(scope())
    end(special);scopes.append(scope());end(special);scopes.append(scope())
    end(special);scopes.append(scope()) # empty Core stack emits no HOST F0
    if [s[:3] for s in scopes]!=[(0,0,0),(1,1,0),(2,2,0),(1,1,1),(2,2,1),(1,1,1),(0,0,0),(0,0,0)]:
        raise ValueError('Official scope unwind changed ordering/counters')
    if len(d.pending)!=9 or d.consumed_count or arguments.count!=9:
        raise ValueError('Scope boundaries consumed or duplicated native notifications')
    expected_digest=digest(b''.join(d.pending))
    if d.drain()!=9 or d.pending or d.consumed_digest.hexdigest()!=expected_digest or d.drain()!=0:
        raise ValueError('Scoped FIFO consumption differs or replayed')
    for storage,pointer,fields in reversed(maps):
        if arguments.reader.fields(pointer)!=fields:raise ValueError('Argument map changed before release')
        destructor(pointer);check_outer(storage)
    if (guards!=guard_state(base,context,read)
            or any(registry_snapshot(base,read,k)!=v for k,v in registries.items())
            or consumer.quarantined or consumer.active_kind is not None):
        raise ValueError('Scope group left changed native guards, subscribers or producer state')
    return dict(argument_source_sha256=ARGUMENT_SOURCE[1],notification_source_sha256=SCOPE_SOURCE[1],
        scope_proof_sha256s=list(consumer.notification_scope_profile.proof_sha256s),
        native_cases=observed,native_kind_count=3,source_admitted_kind_count=9,
        unexecuted_pointer_kinds=[hex(k) for k in consumer.notification_scope_profile.records if k not in kinds],
        zero_notification_positive_metadata_executed=False,native_map_count=2,
        native_map_constructors_setters_destructors_executed=True,map_storage_canaries_unchanged=True,
        notification_scopes=[list(s[:3]) for s in scopes],consumed_records=9,queue_empty=True,
        consumed_sha256=expected_digest,guards_unchanged=True,core_registry_mutated=False,
        core_flags_patched=False,implicit_scope_drain=False,callback_slot_restored=False,
        consumer_closed=False,all_admitted_event_shapes_executed_natively=False,
        natural_gameplay_publication_qualified=False,public_visibility_qualified=False,saved_game_loaded=False)


def player_query_group(core,context,backend,services):
    """Official A0 -> Player lookup NULL branches on a real prepared context."""
    import ctypes as C
    from civ6_host.runtime.native.native_36c9b2b4_pair_codec import EMPTY_RECEIVER_STATE
    from civ6_host.runtime.native import native_player_notifications as queries
    from civ6_host.runtime.player_notification_profiles import SOURCE
    from civ6_host.runtime.cache_update_profiles import registry_snapshot
    from civ6_host.runtime.event_argument_source import guard_state
    read=backend.runtime.read;base=core._handle;host=backend.host;kind=0x20F2116E
    before=guard_state(base,context,read)
    if not before['a0_open'] or registry_snapshot(base,read,kind)['node'] is not None:
        raise ValueError('Player query diagnostic requires open guards and no replaced Core subscribers')
    d=services.install_deferred_events(optional_preprocessor=None,queue_metadata_service=None)
    arguments=services.install_event_arguments(normalizer_transform=None,dynamic_registrations=())
    consumer=arguments.install_consumers(receiver_state=dict(EMPTY_RECEIVER_STATE),
        pre_turn_immediate_state=dict(EMPTY_RECEIVER_STATE),entity_listener_count=0)
    owner=services.install_player_queries(core_lock=host._qualification_core_lock)
    consumer.enable_player_queries(owner)
    if read(owner.identity['game']+0x2A4,1)!=b'\0':
        raise ValueError('This diagnostic requires an actual uninitialized Game, never a patched one')
    def telemetry(name,**fields):event_telemetry(host,'native_a0_family_event',producer_event_name=name,**fields)
    d.emit=consumer.emit=telemetry
    observations=[];original=queries._native_calls
    def observed_calls(*args,**kwargs):
        calls=original(*args,**kwargs);get=calls['get_player']
        def get_player(receiver,index):
            result=get(receiver,index)
            observations.append(dict(receiver=receiver,index=index,native_result=int(result or 0)))
            return result
        calls['get_player']=get_player
        return calls
    two=C.WINFUNCTYPE(C.c_uint32,C.c_uint64,C.c_uint32)(base+0x5195A0)
    values=(0,1,63,64,65,0x80000000,0xFFFFFFFF)
    queries._native_calls=observed_calls
    try:
        for value in values:
            if two(kind,value)!=0:raise ValueError('Official Player query event returned a nonzero status')
    finally:queries._native_calls=original
    if (len(observations)!=len(values) or [r['index'] for r in observations]!=list(values)
            or any(r['receiver']!=context or r['native_result'] for r in observations)
            or d.pending or d._sequence or arguments.count!=len(values) or owner.depth
            or before!=guard_state(base,context,read) or host._qualification_core_lock.owned(host.pointer)):
        raise ValueError('Native lookup/null/lease/guard behavior differs')
    return dict(source_sha256=SOURCE[1],event_kind=hex(kind),values=list(values),lookups=observations,
        actual_native_getter_called=True,native_null_preserved=True,records_produced=0,
        positive_getters_executed=False,player_fields_synthesized=False,game_flag_modified=False,
        core_registry_mutated=False,guards_unchanged=True,execution_lock_unowned=True,
        saved_game_loaded=False,public_visibility_qualified=False,consumer_closed=False,
        callback_slot_restored=False,player_query_owner_closed=False)


def a0_controller_group(core,context,backend,services):
    """Two real wrapper paths sharing the existing original native controller."""
    import ctypes as C
    import struct
    from civ6_host.runtime.native.native_36c9b2b4_pair_codec import EMPTY_RECEIVER_STATE
    from civ6_host.runtime.native.native_setup import local_reader
    from civ6_host.runtime.cache_update_profiles import registry_snapshot
    from civ6_host.runtime.event_argument_source import guard_state
    from civ6_host.runtime.a0_controller_source import SOURCE
    from civ6_host.runtime.native.native_controller_code import SOURCE_SHA
    read=local_reader();base=core._handle;host=backend.host
    guards=guard_state(base,context,read)
    if not guards['a0_open']:raise ValueError('Official A0 guards are closed')
    d=services.install_deferred_events(optional_preprocessor=None,queue_metadata_service=None)
    control=services.install_control_inputs(local_player_id=7)
    arguments=services.install_event_arguments(normalizer_transform=None,dynamic_registrations=())
    consumer=arguments.install_consumers(receiver_state=dict(EMPTY_RECEIVER_STATE),
        pre_turn_immediate_state=dict(EMPTY_RECEIVER_STATE),entity_listener_count=0)
    consumer.enable_controller_events(control)
    state=control.turn_begin_state
    if (state.controller_initialized or state is not d.turn_begin_state or state is not consumer.turn_begin_state
            or state.service_flags!=0 or state.turn_values_by_thread):
        raise ValueError('Controller event binding created/reset/substituted state')
    def telemetry(kind,**fields):
        event_telemetry(host,'native_a0_family_event',producer_event_name=kind,**fields)
    d.emit=consumer.emit=telemetry
    for kind in consumer.controller_profile.record_types_by_kind:
        if registry_snapshot(base,read,kind)['node'] is not None:
            raise ValueError('Controller diagnostic has live Core subscribers; no registry substitution')
    two=C.WINFUNCTYPE(C.c_uint32,C.c_uint64,C.c_uint32)(base+0x5195A0)
    three=C.WINFUNCTYPE(C.c_uint32,C.c_uint64,C.c_uint32,C.c_uint32)(base+0x519650)
    query=C.WINFUNCTYPE(C.c_uint8,C.c_void_p,C.c_uint32)(host.vtable[0x120//8])
    native_enqueue=d._enqueue;order=[]
    def observe_enqueue(record):
        # A diagnostic observation around the unchanged enqueue, not a second
        # producer or state update. The native getter never creates an object.
        order.append(dict(record_type=int.from_bytes(record[4:8],'little'),
            controller_initialized=state.controller_initialized,
            controller_flag=state.controller_byte_0d,
            service_flags=state.service_flags,
            turn_values=list(state.turn_values_by_thread.get(0,()))))
        return native_enqueue(record)
    d._enqueue=observe_enqueue
    cases=((0x8953F126,(7,0xFFFFFFFF),0xA5),(0x21535587,(0x80000000,),0),
           (0x8953F126,(7,0),0xFFFFFFFF),(0x21535587,(0xFFFFFFFF,),0))
    observations=[];pointer=None;queries=[]
    for index,(kind,values,selector) in enumerate(cases):
        if index:state.controller_byte_0d=0xA5  # actual original setter, diagnostic stimulus
        packed=kind|(selector<<32)
        result=two(packed,*values) if len(values)==1 else three(packed,*values)
        record=d.pending[-1]
        expected_type=15 if kind==0x8953F126 else 4
        if (result!=0 or len(d.pending)!=index+1
                or struct.unpack_from('<III',record)!=(96,expected_type,index+1)
                or struct.unpack_from('<II',record,80)!=(index+1,values[0])):
            raise ValueError('Controller native event record differs')
        if kind==0x8953F126 and record[88]!=int(values[1]!=0):
            raise ValueError('Controller activation boolean differs')
        actual=query(host.pointer,0xFFFFFFFF);queries.append(actual)
        if actual!=0 or len(control.code.objects)!=1 or state._controller.code is not control.code:
            raise ValueError('Controller event and HOST120 do not share one actual native flag')
        if pointer is None:pointer=state._controller.pointer
        if state._controller.pointer!=pointer:raise ValueError('Controller recreated between events')
        observations.append(dict(kind=hex(kind),selector=selector,values=values,record_sha256=digest(record)))
    d._enqueue=native_enqueue
    expected=[(False,None,[]),(True,0,[]),(True,0xA5,[0x80000000]),(True,0,[0x80000000])]
    if [(r['controller_initialized'],r['controller_flag'],r['turn_values']) for r in order]!=expected:
        raise ValueError('Controller native effects no longer bracket enqueue in source order')
    if state.service_flags!=0 or state.turn_values_by_thread!={0:[0x80000000,0xFFFFFFFF]}:
        raise ValueError('Controller current manager/telemetry state differs')
    if d.drain()!=4 or d.pending or arguments.count!=4 or guards!=guard_state(base,context,read):
        raise ValueError('Controller event FIFO consumption or native guard changed')
    if len(control.code.objects)!=1 or state._controller.pointer!=pointer:
        raise ValueError('Consumption replaced the shared controller')
    a0=dict(source_sha256=SOURCE[1],native_cases=observations,enqueue_observations=order,
        shared_controller_identity=True,source_order_verified=True,consumed_records=4,queue_empty=True,
        guards_unchanged=True,core_registry_mutated=False,callback_slot_restored=False,consumer_closed=False,
        public_visibility_qualified=False,natural_gameplay_publication_qualified=False,saved_game_loaded=False)
    ctrl=dict(original_controller_source_sha256=SOURCE_SHA,controller_instances=1,
        lazy_native_constructor_executed=True,native_getter_results=queries,shared_with_deferred_events=True,
        original_native_setter_stimulus=0xA5,service_flags_observed=state.service_flags,
        thread_zero_turn_telemetry=state.turn_values_by_thread[0],
        native_player_configuration_validated=False,full_controller_scheduler_qualified=False,
        callback_slots_restored=False,native_controller_code_closed=False,
        native_controller_object_closed=False,local_id_binding_removed=False,saved_game_loaded=False)
    return a0,ctrl


def status_group(core,context,backend,services):
    """Official Game facade/getter and C0 wrappers, without populating a fake Game."""
    import ctypes as C
    import struct
    from civ6_host.runtime.native.native_36c9b2b4_pair_codec import EMPTY_RECEIVER_STATE
    from civ6_host.runtime.native import native_locale_diagnostic as locale
    from civ6_host.runtime.native.native_setup import local_reader
    from civ6_host.runtime.event_argument_source import guard_state
    read=local_reader();base=core._handle;host=backend.host
    before=guard_state(base,context,read)
    if not before['c0_enabled'] or before['session_flag'] or before['loading_flag']:
        raise ValueError('Official C0 guards are closed; no guard will be patched')
    deferred=services.install_deferred_events(optional_preprocessor=None,queue_metadata_service=None)
    deferred.emit=lambda kind,**fields:event_telemetry(host,kind,**fields)
    arguments=services.install_event_arguments(normalizer_transform=None,dynamic_registrations=())
    status=services.install_status_messages(receiver_state=dict(EMPTY_RECEIVER_STATE),
        writer_metadata_service=None,per_thread_hook=None)
    getter=status.game.value()
    if getter!=-1:raise ValueError('Prepared native cache does not have its constructor value')
    # The real getter must reject the unmatched target before touching this NULL
    # argument pointer. No artificial map is supplied to that source branch.
    direct=C.WINFUNCTYPE(C.c_uint32,C.c_void_p,C.c_uint32,C.c_uint32,C.c_void_p)(host.vtable[0xC0//8])
    if direct(host.pointer,17,0xFFFFFFFE,None)!=0 or deferred.pending or status.count!=1:
        raise ValueError('C0 unmatched target did not preserve its early-return branch')
    library=C.WinDLL(str(Path(host.dll_directory)/'Localization_FinalRelease.dll'))
    funcs={name:getattr(library,name) for name in locale._EXPORT_RVAS}
    for name,rva in locale._EXPORT_RVAS.items():
        if C.cast(funcs[name],C.c_void_p).value!=library._handle+rva:
            raise ValueError('Localization String export identity changed')
    lookup,convert,destroy=funcs[locale._LOOKUP],funcs[locale._TO_UTF8],funcs[locale._DESTROY]
    lookup.argtypes,lookup.restype=[C.c_void_p,C.c_char_p],C.c_void_p
    convert.argtypes,convert.restype=[C.c_void_p,C.POINTER(C.c_uint),C.c_uint],C.c_void_p
    destroy.argtypes,destroy.restype=[C.c_void_p],None
    allocation=C.create_string_buffer(143);pointer=(C.addressof(allocation)+15)&~15
    initialized=False
    try:
        if lookup(pointer,b'LOC_UNIT_SETTLER_NAME')!=pointer:raise ValueError('Native String construction failed')
        initialized=True;n=C.c_uint()
        text_pointer=convert(pointer,C.byref(n),1)
        if not text_pointer or n.value>=1024:raise ValueError('Diagnostic status text outside native buffer')
        text=C.string_at(text_pointer,n.value+1)
        if not text.endswith(b'\0'):raise ValueError('Native String lacks terminator')
        plain=C.WINFUNCTYPE(None,C.c_uint32,C.c_int32,C.c_void_p)(base+0x51A3A0)
        extended=C.WINFUNCTYPE(None,C.c_uint32,C.c_uint32,C.c_int32,C.c_uint32,C.c_void_p)(base+0x51A450)
        plain(0xFFFFFFFF,getter,pointer)
        extended(0x80000000,17,getter,0xFFFFFFFF,pointer)
    finally:
        if initialized:destroy(pointer)
    if status.count!=3 or len(deferred.pending)!=2:raise ValueError('Official C0 wrappers did not produce two records')
    records=list(deferred.pending)
    for i,record in enumerate(records):
        if (len(record)!=1120 or int.from_bytes(record[4:8],'little')!=0xF7
                or record[84:84+len(text)]!=text or int.from_bytes(record[8:12],'little')!=i+1):
            raise ValueError('Native status text/header or sequence differs')
    values=[struct.unpack_from('<II',r,1108) for r in records]
    if values!=[(103780558,0xFFFFFFFF),(0x80000000,0xFFFFFFFF)]:
        raise ValueError('C0 defaults/explicit unsigned fields differ')
    consumed=deferred.drain()
    if consumed!=2 or deferred.pending or deferred.consumed_count!=2 or before!=guard_state(base,context,read):
        raise ValueError('Status queue/guard state differs after consumption')
    return {'native_getter_signed_value':getter,'native_cache_identity':status.game.identity,
        'facade_acquired_from_outer_factory':True,'facade_refcount_before_close':int.from_bytes(read(status.game.game_facade+0x18,4),'little'),
        'official_wrapper_rvas':['0x51a3a0','0x51a450'],'callback_count':status.count,
        'unmatched_target_skips_null_argument':True,'status_record_count':len(records),
        'status_record_sha256':[digest(r) for r in records],'text_hex':text.hex(),
        'categories_selectors':values,'records_consumed':consumed,'queue_empty':True,
        'guards_unchanged':True,'core_flags_patched':False,'cache_fields_written':False,
        'callback_slot_restored':False,'facade_released':False,'saved_game_loaded':False,
        'populated_game_cache_qualified':False,'public_message_visibility_qualified':False}


def control_group(core,context,backend,services):
    """Exercise original EXE controller code through the composed HOST interface.

    D0/120 are invoked through native callback pointers; the unsafe Game/Player
    callers are not invoked on this prepared context. This tests application
    inputs and lazy native ownership, not player selection or turn scheduling.
    """
    import ctypes as C
    from civ6_host.runtime.control_input_source import SOURCE
    from civ6_host.runtime.native.native_controller_code import SOURCE_SHA
    host=backend.host
    deferred=services.install_deferred_events(optional_preprocessor=None,queue_metadata_service=None)
    inputs=services.install_control_inputs(local_player_id=7)
    state=inputs.turn_begin_state
    if state.controller_initialized or state is not deferred.turn_begin_state:
        raise ValueError('Controller is eager or not shared with deferred consumers')
    local=C.WINFUNCTYPE(C.c_uint32,C.c_void_p)(host.vtable[0xD0//8])
    # The official XP1 caller supplies a player ID in EDX. The EXE method
    # ignores it; the host signature deliberately owns only its RCX receiver.
    query=C.WINFUNCTYPE(C.c_uint8,C.c_void_p,C.c_uint32)(host.vtable[0x120//8])
    local_value=local(host.pointer)
    if local_value!=7 or state.controller_initialized:
        raise ValueError('Local identity was substituted or constructed the controller')
    values=[query(host.pointer,0)]
    controller=state._controller;pointer=controller.pointer
    if values!=[0] or controller.code is not inputs.code or len(inputs.code.objects)!=1:
        raise ValueError('First HOST120 read did not use one original fresh constructor')
    native_snapshot=controller.snapshot()
    for value,ignored_player in ((1,64),(0xA5,0xFFFFFFFF),(0,7)):
        # Diagnostic use of the existing original setter. No Game flag or turn
        # state is changed here; live event consumers must be qualified later.
        state.controller_byte_0d=value
        actual=query(host.pointer,ignored_player);values.append(actual)
        if actual!=value or state._controller.pointer!=pointer or len(inputs.code.objects)!=1:
            raise ValueError('HOST120 recreated the controller, normalized its byte or read another state')
    if local(host.pointer)!=7:raise ValueError('Controller flag reads changed local identity')
    return {'source_sha256':SOURCE[1],'original_controller_source_sha256':SOURCE_SHA,
        'local_player_id_explicit':7,'local_player_id_observed':local_value,
        'native_player_configuration_validated':False,'lazy_native_constructor_executed':True,
        'controller_instances':1,'shared_with_deferred_events':True,'native_getter_results':values,
        'ignored_edx_values':[0,64,0xFFFFFFFF,7],'initial_native_snapshot':native_snapshot,
        'native_setter_called_for_diagnostic_only':True,'core_memory_written':False,
        'unsafe_game_player_callers_invoked':False,'saved_game_loaded':False,
        'full_controller_scheduler_qualified':False,'callback_slots_restored':False,
        'native_controller_code_closed':False,'native_controller_object_closed':False,
        'local_id_binding_removed':False}


def application_group(core,context,backend,services):
    """Exercise the official publisher and retained mirror on private providers.

    These explicit publications do not claim natural saved-Game reachability.
    They qualify the required callback branch and native temporary-map lifetime.
    """
    import ctypes as C
    import struct
    from civ6_host.runtime.application_mirror_profiles import verify_live
    from civ6_host.runtime.native import native_configuration_finalization as setup
    read=backend.runtime.read;base=core._handle;abi=backend.configuration_abi
    source=verify_live(base,read)
    mirror=services.install_application_mirror()
    a=setup._linked_snapshot(base,context,read,None,core_sha256=abi.core_sha256)
    b=backend.owner.snapshot();key=0x24084B20
    get=C.WINFUNCTYPE(C.c_void_p,C.c_void_p,C.c_uint32)(base+abi.lookup_rva)
    setter=C.WINFUNCTYPE(C.c_void_p,C.c_void_p,C.c_uint32,C.c_uint32)(base+abi.uint_setter_rva)
    publisher=C.WINFUNCTYPE(C.c_uint32,C.c_uint64,C.c_void_p)(base+0x5174E0)
    packed=(key<<32)|0x2E6F8494
    if get(a['normalized'],key) or get(b['normalized'],key):
        raise ValueError('Application qualification requires absent diagnostic phase cells')
    before_slot=mirror._previous_callback
    rows=[]
    for phase,present in ((5,False),(7,True),(9,True)):
        if present and not get(b['normalized'],key):
            if not setter(b['normalized'],key,3):raise ValueError('Native B phase setter failed')
        if not setter(a['normalized'],key,phase):raise ValueError('Native A phase setter failed')
        count=getattr(getattr(mirror,'_borrowed_dispatcher',None),'completed_calls',0)
        result=publisher(packed,a['descriptor'])
        dispatcher=mirror._borrowed_dispatcher
        if result!=0 or dispatcher.completed_calls!=count+1 or mirror.mirror.changes:
            raise ValueError('Official application publisher/callback completion differs')
        value=get(b['normalized'],key)
        if bool(value)!=present:
            raise ValueError('Application mirror created or lost the native destination')
        if value and (struct.unpack_from('<H',read(value,24))[0]!=2
                      or struct.unpack_from('<I',read(value,24),8)[0]!=phase):
            raise ValueError('Native application mirror phase copy differs')
        attempt=dispatcher.attempts[-1]
        rows.append({'source_phase':phase,'destination_present':bool(value),
                     'return':result,'native_calls_completed':dispatcher.completed_calls,
                     'new_owned_maps':len(attempt.allocations),
                     'source_and_destination_distinct':a['normalized']!=b['normalized']})
    mirror.close()
    if backend.host.vtable[0x130//8]!=before_slot:
        raise ValueError('Application mirror did not restore its callback slot')
    return {'source':source,'official_publisher_called':True,'rows':rows,
            'shared_saved_services_owner':True,'native_both_presence_branches':True,
            'callback_restored':True,'player_notifications_qualified':False,
            'full_saved_game_load_qualified':False,'natural_phase_change_trigger_qualified':False}


def values_group(core, context, backend, runtime, child, staged):
    """Real official GetValue callbacks after the existing loader copy.

    Extended string cases intentionally modify private A configuration. They
    test the official transport's fixed buffer and surrogate behavior, not
    gameplay. Player generic GetValue does not exist in the native registry.
    """
    import ctypes as C
    import struct
    from civ6_host.runtime.script_scalar_service import ScalarService
    from civ6_host.runtime.native.native_xp1_map_setup import XP1MapSetup
    from civ6_host.runtime.configuration_lua_source import verify_xp1
    source_receipt = verify_xp1(core._handle, backend.runtime.read)
    source = XP1MapSetup(core, context, project_root=resource_root())
    statements, cases = [], []
    for row in staged['typed_values_after']:
        if row['scope'] not in ('normalized','map_normalized'):
            continue  # No PlayerConfigurations:GetValue in the official API.
        table = 'GameConfiguration' if row['scope']=='normalized' else 'MapConfiguration'
        if row['tag'] in (2,3):
            expected = str(C.c_int32(row['value']).value)
        elif row['tag'] == 6:
            expected = _lua_bytes(row['value'].encode('utf-8'))
        else:
            raise ValueError('Unexpected staged Lua configuration type')
        statements.append(f'assert({table}.GetValue({row["key"]})=={expected})')
        cases.append({'scope':row['scope'],'key':row['key'],'tag':row['tag']})
    extras = (
        ('empty', '', None),
        ('unicode', 'ÃƒÂ©Ã¦Â¼Â¢Ã°Å¸Ëœâ‚¬', 'ÃƒÂ©Ã¦Â¼Â¢Ã°Å¸Ëœâ‚¬'.encode('utf-8')),
        ('surrogates', '\ud800A\udc00', b'\xed\xa0\x80A\xed\xb0\x80'),
        ('ascii_limit', 'a'*1023, b'a'*1023),
        ('two_byte_overflow', 'a'*1022+'ÃƒÂ©z', b'a'*1022),
        ('two_byte_fits', 'a'*1021+'ÃƒÂ©z', b'a'*1021+b'\xc3\xa9'),
        ('four_byte_overflow', 'a'*1020+'Ã°Å¸Ëœâ‚¬', b'a'*1020),
        ('four_byte_fits', 'a'*1019+'Ã°Å¸Ëœâ‚¬z', b'a'*1019+b'\xf0\x9f\x98\x80'),
    )
    for label, text, expected in extras:
        name = 'CIV6_HOST_A0_' + label.upper()
        key = source.make_hash(name)
        encoded = text.encode('utf-16-le','surrogatepass') + b'\0\0'
        storage = C.create_string_buffer(encoded,len(encoded))
        source._check()
        source._invoke(0x100,(C.c_uint32,C.c_void_p),key,C.addressof(storage))
        C.memset(C.addressof(storage),88,len(encoded))
        raw,flags = source._variant(key,6)
        pointer = struct.unpack_from('<Q',raw,8)[0]
        copied = (pointer == 0) if text == '' else (
            bool(pointer) and backend.runtime.read(pointer,len(encoded)) == encoded)
        if not flags & (1<<29) or not copied:
            raise ValueError(f'Native UTF16 property differs: {label}, flags={flags:#x}, pointer_present={bool(pointer)}')
        literal = 'nil' if expected is None else _lua_bytes(expected)
        statements.extend((f'assert(MapConfiguration.GetValue("{name}")=={literal})',
                           f'assert(MapConfiguration.GetValue({C.c_int32(key).value})=={literal})'))
        cases.append({'scope':'map_normalized','key':key,'name':name,
                      'label':label,'source_utf16_units':len(encoded)//2-1,
                      'expected_lua_bytes':len(expected) if expected is not None else None,
                      'expected_sha256':digest(expected) if expected is not None else None,
                      'empty_native_string_is_null':text == ''})
    missing_key = source.make_hash('CIV6_HOST_A0_ABSENT')
    statements.extend((
        'assert(GameConfiguration.GetValue("CIV6_HOST_A0_ABSENT")==nil)',
        'assert(MapConfiguration.GetValue("CIV6_HOST_A0_ABSENT")==nil)',
        f'assert(MapConfiguration.GetValue({C.c_int32(missing_key).value})==nil)',
    ))
    service = ScalarService(backend.host,runtime)
    # An exception after a native effect is terminal to this isolated worker;
    # do not guess cleanup or retry in its potentially corrupted state.
    runtime.execute(child,('\n'.join(statements)+'\n').encode('ascii'),b'@xp1_configuration_values')
    service.close()
    source.close()
    return {'official_getters_called':True,'cases':cases,'assertions':len(statements),
            'source_receipt':source_receipt,'callback_restored':service.closed,
            'native_provider_inputs_verified':True,'string_keys_and_signed_numeric_keys':True,
            'missing_key_is_nil':True,'native_utf16_fixed_buffer_behavior':True,
            'extended_cases_mutate_private_configuration_a':True,
            'player_configuration_generic_getvalue_available':False,
            'saved_game_loaded':False}


def maps_group(core, context, backend, runtime, child, staged):
    """Official Game.GetProperties plus real borrowed configuration maps.

    The first path crosses the actual GameCore -> A8 -> snapshot -> HKS
    callback. Filled configuration maps then exercise the same decoded
    transport through the existing protected C diagnostic, including B0.
    """
    import ctypes as C
    from civ6_host.runtime.aux_map_profiles import prepared_game_properties, SOURCE
    from civ6_host.runtime.script_map_service import MapService
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
    from civ6_host.runtime.native.native_aux_map_adapter import AuxMapOp
    from civ6_host.runtime.native.native_aux_map_conversion import snapshot_parameter_map
    from civ6_host.runtime.native import native_configuration_finalization as setup
    from civ6_host.runtime.native.native_xp1_map_setup import XP1MapSetup
    service = MapService(backend.host,runtime,core,core_sha256=XP1_CORE_SHA256,read=backend.runtime.read)
    if service.adapter.transport_version != 2:
        raise ValueError('Extended map qualification requires negotiated V2 transport')
    def snapshot(pointer, names=False):
        return snapshot_parameter_map(core._handle,pointer,backend.runtime.read,
            use_string_keys=names,core_sha256=XP1_CORE_SHA256,transport_version=2)
    properties = prepared_game_properties(core._handle,backend.runtime.read)
    initial = snapshot(properties,True)
    if initial.field_count != 0:
        raise ValueError('Prepared property fixture is no longer empty; qualify its actual fields')
    runtime.execute(child,b"local v=Game.GetProperties(); assert(type(v)=='table' and next(v)==nil)",
                    b'@xp1_official_game_properties')
    pointer = runtime.registry.validate(child)
    native_results = []
    def check(label, data, checks, *, optional=False):
        fn = runtime.host.LAB_AuxOptionalMapDiagnostic if optional else runtime.host.LAB_AuxMapDiagnostic
        fn.argtypes = [C.c_void_p,C.POINTER(AuxMapOp),C.c_uint32,C.c_char_p,C.c_size_t]
        fn.restype = C.c_int
        ops = (AuxMapOp*(len(data.transport)//16)).from_buffer_copy(data.transport)
        code = ('return function(t) '+checks+' end').encode('ascii')
        if runtime.lua['gettop'](pointer) != 0:
            raise ValueError('Native map checker needs an empty child stack')
        status = fn(pointer,ops,len(ops),code,len(code))
        runtime._status(pointer,status,'XP1 native map '+label)
        if runtime.lua['gettop'](pointer) != 0:
            raise ValueError('Native map checker left stack values')
        native_results.append({'label':label,'optional_b0':optional,
            'native_field_count':data.field_count,'transport_sha256':digest(data.transport),
            'source_bytes_read':data.source_bytes_read,'variant_types':data.variant_types})
    indexed = setup._linked_snapshot(core._handle,context,backend.runtime.read,None,
                                    core_sha256=XP1_CORE_SHA256)
    for scope in ('normalized','map_normalized',0,63):
        target = indexed['players'][scope] if type(scope) is int else indexed[scope]
        data = snapshot(target)
        tests = ["assert(type(t)=='table')"]
        for row in staged['typed_values_after']:
            if row['scope'] != scope:
                continue
            expected = str(C.c_int32(row['value']).value) if row['tag'] in (2,3) else _lua_bytes(row['value'].encode('utf-8'))
            tests.append(f'assert(t[{C.c_int32(row["key"]).value}]=={expected})')
        check(str(scope),data,';'.join(tests))
    empty = snapshot(indexed['players'][1])
    if empty.field_count != 0:
        raise ValueError('Expected untouched player1 map for optional-empty qualification')
    check('empty_native_map',empty,'assert(t==nil)',optional=True)
    source = XP1MapSetup(core,context,project_root=resource_root())
    # Borrow player1 through the already verified provider setter ABI. This
    # intentionally creates one empty UTF16 property in private A only.
    source._check()
    empty_text = C.create_string_buffer(b'\0\0',2)
    setup._invoke(None,source.base+source.proof['contract']['slots']['0x100'],
        C.c_void_p,indexed['players'][1],(C.c_uint32,C.c_void_p),
        0x70000100,C.addressof(empty_text))
    source.close()
    nil_only = snapshot(indexed['players'][1])
    if nil_only.field_count != 1:
        raise ValueError('Native nil-only map must preserve its original field count')
    check('nil_only_native_map',nil_only,"assert(type(t)=='table' and next(t)==nil)",optional=True)
    service.close()
    return {'source_sha256':SOURCE[1],'official_game_getproperties_called':True,
        'official_callback_names_enabled':True,'official_callback_native_field_count':initial.field_count,
        'filled_maps_use_existing_protected_c_diagnostic':True,'checks':native_results,
        'transport_version':2,'callbacks_restored':service.closed,
        'native_input_mutation':'one empty UTF16 property in private player1 configuration A',
        'saved_game_loaded':False,'public_observation_admitted':False}


def review_retained_script_run(run_dir, supervisor_sha):
    """Revalidate recorded execution after a parser-only refusal; no DLL load."""
    run_dir = Path(run_dir).resolve()
    if not run_dir.is_relative_to((resource_root()/'work').resolve()):
        raise ValueError('Retained run is outside private work resources')
    raw = (run_dir/'supervisor.json').read_bytes()
    if digest(raw) != supervisor_sha:
        raise ValueError('Retained supervisor differs from explicit input digest')
    report = json.loads(raw)
    if (report['exit_code'] != 0 or report['timed_out'] or not report['reaped']
            or not report['job_object_assigned'] or report['supervisor_error'] is not None
            or not all(report['original_inputs_unchanged'].values())
            or report['worker_parse_error'] != {
                'type':'ValueError','message':'Worker stdout is not exactly one bounded JSON record'}):
        raise ValueError('Retained failure is not solely the expected parser refusal')
    worker, line, telemetry = parse_script_stdout(report['stdout'])
    if (run_dir/'worker-result.json').read_bytes() != (line+'\n').encode('utf-8'):
        raise ValueError('Retained worker differs from captured stdout')
    reference, _ = load_reference()
    reference.validate_worker_report(worker)
    events = (run_dir/'events.jsonl').read_bytes()
    if digest(events) != worker['event_ledger_sha256']:
        raise ValueError('Retained event ledger changed')
    rows = [json.loads(line) for line in events.splitlines()]
    if len(rows) != worker['event_count']:
        raise ValueError('Retained event count differs')
    closures = [row for row in rows if row['event_name']=='native_script_runtime_closed']
    if len(closures)!=1 or closures[0]['live_blocks']!=0:
        raise ValueError('Native script heap was not closed without retained blocks')
    removals = [row for row in rows if row['event_name']=='host_archive_remove']
    if not removals or any(row.get('active') is not True for row in removals) or removals[-1]['registered'] != 0:
        raise ValueError('Native archive teardown was not observed')
    sources = json.loads((run_dir/'configuration-runtime-sources.json').read_text(encoding='utf-8'))
    changed = [path for path, sha in sources['files'].items() if digest(Path(path).read_bytes()) != sha]
    if changed != [str(Path(__file__).resolve())]:
        raise ValueError('An executed runtime source changed beyond the qualification reader')
    # Preserve the executed tool, runtime fingerprint and original failed report.
    group = json.loads((run_dir/'scripts-group.json').read_text(encoding='utf-8'))
    if group['status']!='native_scripts_group_passed':
        raise ValueError('Retained script group did not complete')
    result = {'status':'native_scripts_group_passed',
        'classification':'retained_execution_revalidated_after_parser_only_refusal',
        'new_native_execution':False,'run_directory':str(run_dir),
        'retained_supervisor_sha256':supervisor_sha,
        'executed_runtime_fingerprint':sources['fingerprint'],
        'executed_qualifier_sha256':sources['files'][str(Path(__file__).resolve())],
        'review_qualifier_sha256':digest(Path(__file__).read_bytes()),
        'retained_parser_sha256':STDOUT_FUNCTION_SHA256,
        'exit_code':report['exit_code'],'elapsed_seconds':report['elapsed_seconds'],
        'reaped':True,'job_object_assigned':True,
        'peak_private_bytes':max(row['private_bytes'] for row in report['memory_samples']),
        'peak_commit_bytes':max(row['peak_commit_bytes'] for row in report['memory_samples']),
        'event_count':len(rows),'cleanup_order':worker['cleanup_order'],
        'native_empty_job_telemetry':telemetry,'heap_closed':True,
        'archive_removals':len(removals),'group':group,
        'saved_game_loaded':False,'gameplay_optional_proven':False,'strategic_training_ready':False}
    result['receipt'] = write_once(run_dir/'scripts-qualification-reviewed.json',result)
    print(json.dumps(result,ensure_ascii=False))
    return 0


def provider_group(core, context, run_dir, backend, *, keep_owner=False):
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
    from civ6_host.runtime.native.native_application_configuration import NativeApplicationConfiguration
    from civ6_host.runtime.native import native_checkpoint_provider as provider
    from civ6_host.runtime.native.native_checkpoint_configuration_normalization import compare_configuration_streams
    limits = {'max_bytes':MAX_BYTES,'max_calls':MAX_CALLS}
    if hasattr(core,'_civ6rl_application_configuration'):
        raise ValueError('XP1 diagnostic context already has a provider B owner')
    backend.clone()
    owner = backend.owner
    # Reuse the source-checked typed setter/getter implementation, targeting
    # owned B instead of the borrowed A map. No game setup option is supplied.
    from civ6rl.native_xp1_map_setup import XP1MapSetup
    from civ6rl.native_xp1_application_configuration import read_value
    from civ6_host.runtime.native import native_configuration_finalization as setup
    import ctypes as C
    source = XP1MapSetup(core,int(context),project_root=resource_root())
    abi=owner._configuration_abi
    def target(snapshot,scope):
        return snapshot['players'][scope] if type(scope) is int else snapshot[scope]
    class OwnedValues(XP1MapSetup):
        def __init__(self,scope):
            self.base,self.context,self.read,self.call=source.base,source.context,source.read,source.call
            self.proof,self.closed,self.scope=source.proof,False,scope
            self.state={'map':target(owner.snapshot(),scope)}
        def _check(self):
            source._check()
            owner.require_context(core._handle,int(context))
            if self.closed or target(owner.snapshot(),self.scope)!=self.state['map']:
                raise ValueError('Typed probe provider changed its owned B identity')
    def method(pointer,slot,result,types,*values):
        if slot!=0x58:
            raise ValueError('Typed readback admits only the verified lookup')
        return setup._invoke(None,core._handle+abi.lookup_rva,result,pointer,types,*values)
    borrower=SimpleNamespace(base=core._handle,read=source.read,map=source,_method=method)
    cases=(('normalized',0x70000001,2,0xFFFFFFFF),
           ('map_normalized',0x70000002,3,0x86AB5F63),
           ('map_normalized',0x70000003,6,'HÃƒÂ´te XP1 Ã¢â‚¬â€œ civilisation'),
           (0,0x70000004,2,0),
           (63,0x70000005,6,'Joueur 63 Ã¢â‚¬â€œ Ã¦Â¼Â¢Ã¥Â­â€”'))
    if selected_stage()=='arguments':
        cases += (('map_normalized',0x70000006,2,0),('map_normalized',0x70000007,2,0xFFFFFFFF),('map_normalized',0x70000008,2,0x80000000))
    if selected_stage() in ('load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90'):
        cases += (('map_normalized',source.make_hash('CIV6_HOST_LOAD_SEED'),2,23),)
    for scope,key,tag,value in cases:
        probe=OwnedValues(scope)
        if tag==6:probe.set_utf16(key,value)
        else:probe.set_uint(key,value,hashed=tag==3)
        probe.close()
    def readback():
        snapshot=owner.snapshot();rows=[]
        for scope,key,tag,value in cases:
            observed,_=read_value(borrower,target(snapshot,scope),key)
            if observed!={'tag':tag,'value':value}:
                raise ValueError('Native typed configuration readback differs')
            rows.append({'scope':scope,'key':key,**observed})
        return rows
    typed_before=readback()
    before, first = backend.serialize()
    restored = backend.restore(before, expected_sha256=digest(before))
    after, second = backend.serialize()
    typed_after=readback()
    comparison = compare_configuration_streams(before, after)
    provider.seal_restoration(core, int(context), owner, **limits)
    sealed_refusal = False
    try:
        provider.restore_provider(core, int(context), owner, before,
                                  expected_sha256=digest(before), **limits)
    except ValueError as error:
        if 'unused owned B' not in str(error):
            raise
        sealed_refusal = True
    if not sealed_refusal:
        raise RuntimeError('Sealed native provider unexpectedly accepted a second restore')
    if not keep_owner:
        backend.close_owner()
    for name,data in (('configuration-before.bin',before),('configuration-after.bin',after)):
        with (run_dir/name).open('xb') as stream:
            stream.write(data)
    return {'status':('native_configuration_staged_for_copy' if keep_owner else 'native_configuration_group_passed'),'core_sha256':XP1_CORE_SHA256,
            'before':first,'restore':restored,'after':second,'byte_equal':before==after,
            'comparison':comparison,'restore_after_seal_refused':sealed_refusal,
            'typed_values_before':typed_before,'typed_values_after':typed_after,
            'typed_values_roundtrip_equal':typed_before==typed_after,
            'owner_closed_before_context_destroy':owner.closed,
            'owner_close_deferred_until_copy':keep_owner,
            'provider_bytes_limit':MAX_BYTES,'provider_calls_limit':MAX_CALLS,
            'saved_game_loaded':False,'new_game_called':False,'strategic_training_ready':False}


def use_common_lifecycle(reference):
    """Replace only the worker lifecycle calls; retain its bounds and receipts."""
    source = inspect.getsource(reference._worker_run)
    stage = selected_stage()
    def replace(before, after):
        nonlocal source
        if source.count(before) != 1:
            raise ValueError('Retained worker integration boundary changed: '+before)
        source = source.replace(before, after)
    replace('    host_events = {name for name in allowed_events if name.startswith("host_")}', '''    allowed_events.update({
        'before_database_initialize', 'native_application_configuration_cloned',
        'native_application_configuration_destroyed', 'before_destroy', 'destroyed',
        'fixture_unchanged'})
    host_events = {name for name in allowed_events if name.startswith("host_")}''')
    replace('    event_count = 0', '    event_count = 0\n    adapter_receipt_event = None')
    replace('        nonlocal event_count, event_bytes', '        nonlocal event_count, event_bytes, host, adapter_receipt_event')
    replace('                stream.flush()', '''                stream.flush()
            if event_name == 'xp1_adapter_receipt':
                adapter_receipt_event = verify_adapter_receipt_event(events_path, fields['receipt'])''')
    replace('            result["adapter_receipt_event"] = verify_adapter_receipt_event(events_path, receipt)',
            '            result["adapter_receipt_event"] = adapter_receipt_event')
    replace('        result["failure"] = failure', '''        result["failure"] = failure
        _configuration_write_once(run_dir/'shared-lifecycle-failure.json', failure)''')
    replace('        if event_name == "before_xp1_init":', '''        if event_name == "before_xp1_init":
            host = getattr(core, '_diagnostic_host', None)''')
    start = source.index('        phase = "database_initialize"')
    end = source.index('        result.update({', start)
    source = source[:start] + '''        phase = 'shared_configuration_initialize'
        from civ6_host.runtime.native.native_core_context_profiles import profile_for_core as product_profile
        from civ6_host.runtime.native.native_checkpoint_configuration_only import _NativeBackend
        from civ6_host.runtime.native.native_checkpoint_provider import verify_source as provider_source
        manifest = run_dir / 'configuration-fixture.json'
        _configuration_write_once(manifest, {
            'schema':'civ6rl.native-fixture.v1', 'purpose':'diagnostic common XP1 configuration',
            'eligible_for_training':False, 'databases':{
                'configuration':{'path':str(config_copy),'sha256':CONFIG_SHA256},
                'gameplay':{'path':str(gameplay_copy),'sha256':GAMEPLAY_SHA256}}})
        backend = _NativeBackend(core, int(context), manifest, profile.shared_dependency_directory,
            product_profile(core._name, mode='context'), provider_source(core_sha256=XP1_CORE_SHA256), emit)
        backend.state(False)
        backend.initialize()
        backend.state(True)
        host, database = backend.host, backend.host.database
        receipt = host.context_init_receipt
        db_initialized = True
        db_shutdown = backend.finish_database
        result['database_initialize_returned'] = True
''' + source[end:]
    start = source.index('        teardown_receipt = install_xp1_teardown_callbacks(')
    end = source.index('        if (teardown_receipt.get(',start)
    source = source[:start] + '        teardown_receipt = host.context_teardown_receipt\n' + source[end:]
    replace('        phase = "complete"', '''        _configuration_provider_delivery(core, int(context), run_dir, backend)
        phase = "complete"''')
    if stage != 'configuration':
        replace('    host_events = {name for name in allowed_events if name.startswith("host_")}',
                '    allowed_events.update(_script_events)\n    host_events = {name for name in allowed_events if name.startswith("host_")}')
        replace('        phase = "complete"', '''        result['prepare_called'] = True
        cleanup_order.append('script_services_unbind')
        phase = "complete"''')
        replace('                cleanup_order.append("context_destroy")', '''                cleanup_order.append("context_destroy")
                _close_script_group(host)
                cleanup_order.extend(['script_runtime_close', 'localization_shutdown'])''')
        if stage in ('events','event_maps','contexts','load_services','application','deferred','control','arguments','status','a0','a0_control','facades','player_queries','a0_scope','aux90'):
            replace("cleanup_order.extend(['script_runtime_close', 'localization_shutdown'])",
                    "cleanup_order.extend(['script_runtime_close', 'core_lock_close', 'localization_shutdown'])")
    replace('                destroy(context)', '                backend.destroy_context()')
    # Common Init already emits this exact receipt; retain its verification but
    # do not append a second identical ledger event.
    replace('            emit("xp1_adapter_receipt", receipt=receipt)', '            pass  # emitted by the shared initializer')
    reference._configuration_write_once = write_once
    def delivery(core, context, run_dir, backend):
        try:
            pins, fingerprint = source_state()
            write_once(run_dir/'configuration-runtime-sources.json',{'fingerprint':fingerprint,'files':pins})
            group = provider_group if stage == 'configuration' else script_group
            write_once(run_dir/(stage+'-group.json'),group(core,context,run_dir,backend))
        except BaseException as error:
            write_once(run_dir/(stage+'-group-failure.json'),{
                'type':type(error).__name__,'error':str(error),
                'native_effects_may_have_occurred':True,'retry_permitted':False})
            os._exit(89)
    reference._configuration_provider_delivery = delivery
    reference._script_events = SCRIPT_EVENTS
    reference._close_script_group = close_script_group
    exec(compile(source, '<civ6-host shared configuration lifecycle>', 'exec'), reference.__dict__)


from civ6_host.runtime.xp1_session_inputs import (
    SAVED_LOAD_BUILD, SAVED_LOAD_CLOSURE_ENV, SAVED_LOAD_HOST, SAVED_LOAD_MANIFEST, SAVED_UI_BUILD, SAVED_UI_HOST, SAVED_UI_MANIFEST, saved_load_build_pins, saved_load_pin, saved_load_private_icu
)






def validate_saved_stdout_profile(profile):
    from civ6_host.runtime.stdout_transport_profiles import validate_profile
    return validate_profile(profile)


def decode_saved_stdout_record(line,profile=None,*,line_number):
    """Reuse the bounded decoder; preserve raw physical line identity."""
    from civ6_host.runtime.stdout_transport_profiles import decode_record
    return decode_record(line,profile,line_number=line_number)


def replay_saved_close_parser_refusal(run, supervisor_sha256, *, archive, archive_sha256):
    """Authenticate the single known parent parser refusal, without rewriting it.

    The returned projection is only input to offline semantic verifiers. It is
    not a newly executed supervisor and must never replace the retained file.
    """
    import copy
    import zipfile
    from civ6_host.runtime.native.network_session import xp1_loaded_close_evidence
    run=Path(run).resolve();path=run/'supervisor.json';raw=path.read_bytes()
    if digest(raw)!=supervisor_sha256:
        raise ValueError('Retained stdout-parser supervisor hash differs')
    original=json.loads(raw)
    if (original.get('error')!="JSONDecodeError('Expecting value: line 1 column 1 (char 0)')"
            or original.get('stop_reason')!='xp1_loaded_close_unverified'
            or original.get('normal_destroy_called') is not False
            or not original.get('stdout_native_records')):
        raise ValueError('Retained refusal is not the exact parent stdout parser failure')
    closure=json.loads((run/'closure.json').read_bytes());pins=dict(closure['pins'])
    pins[str(run/'closure.json')]=digest((run/'closure.json').read_bytes())
    archive=Path(archive).resolve();archive_raw=archive.read_bytes()
    if digest(archive_raw)!=archive_sha256:
        raise ValueError('Retained executed-source archive hash differs')
    archived_sources={}
    with zipfile.ZipFile(archive) as saved:
        names=saved.namelist()
        if len(names)!=len(set(names)):
            raise ValueError('Retained executed-source archive repeats a path')
        for filename,sha in closure['pins'].items():
            source=Path(filename)
            if source.is_relative_to(REPO) and source.suffix=='.py':
                name=source.relative_to(REPO).as_posix()
                if (name not in names or saved.getinfo(name).file_size>4*1024*1024
                        or digest(saved.read(name))!=sha):
                    raise ValueError('Archive differs from its executed closure source: '+name)
                archived_sources[name]=sha
    if not archived_sources:
        raise ValueError('Retained source archive has no executed host sources')
    projected=copy.deepcopy(original)
    projected.update(error=None,stop_reason=None)
    evidence=xp1_loaded_close_evidence(run,projected,pins)
    projected.update(normal_destroy_called=True,native_lifetime=evidence)
    correction=dict(schema='civ6-host.retained-xp1-stdout-close-correction.v1',
        original_supervisor=dict(path=str(path),bytes=len(raw),sha256=supervisor_sha256),
        original_error=original['error'],original_stop_reason=original['stop_reason'],
        original_normal_destroy_called=False,normal_destroy_authenticated=True,
        executed_sources_archive=dict(path=str(archive),bytes=len(archive_raw),sha256=archive_sha256),
        executed_host_python_sources=archived_sources,
        native_lifetime=evidence,projection_only=True,original_files_modified=False,
        native_calls_during_review=False,full_job_ledger_requalified=False)
    return projected,correction


def saved_load_events(path, *, require_load_interval=False, require_post160_interval=False,
                      require_interval=None, allow_multiple_commands=False, command_sequence=None,
                      allow_turn_updates=False, allow_world_input=False, allow_unit_orders=False,
                      allow_checkpoint=False, allow_production_queue=False, allow_placements=False,
                      allow_unit_attacks=False, allow_city_controls=False, stdout_transport=None, stdout_native_records=None,
                      stdout_limit_bytes=256*1024*1024):
    """Complete strict stdout; authenticate each requested interval independently."""
    if sum((bool(require_load_interval), bool(require_post160_interval), require_interval is not None)) > 1:
        raise ValueError('Select one native interval per transcript pass')
    if (stdout_transport is None)!=(stdout_native_records is None):
        raise ValueError('Saved stdout source and occurrence ledger must be supplied together')
    selected = ('load' if require_load_interval else 'post160' if require_post160_interval else require_interval)
    if (type(allow_multiple_commands) is not bool or type(allow_turn_updates) is not bool
            or type(allow_world_input) is not bool or type(allow_unit_orders) is not bool
            or type(allow_checkpoint) is not bool or type(allow_production_queue) is not bool
            or type(allow_placements) is not bool or type(allow_unit_attacks) is not bool
            or type(allow_city_controls) is not bool):
        raise ValueError('Exact command-interval mode required')
    repeatable = ('unit_commands', 'turn_update') if allow_turn_updates else ('unit_commands',)
    if allow_turn_updates:
        allow_multiple_commands = True
    if command_sequence is not None:
        if (selected not in repeatable or type(command_sequence) is not int or command_sequence < 1):
            raise ValueError('Command interval requires an explicit positive protocol sequence')
        allow_multiple_commands = True
    elif allow_multiple_commands and selected in repeatable:
        raise ValueError('Multiple commands require an explicit selected sequence')
    intervals = {
        'load': ('before_official_gamecore_load', 'official_gamecore_load_returned', 'Load', ()),
        'post160': ('before_xp1_saved_post160_sequence', 'xp1_saved_post160_sequence_returned', 'post160',
                    ('xp1_saved_raw_load_observed', 'xp1_saved_cache_observed')),
        'publication': ('before_xp1_saved_cache_publication', 'xp1_saved_cache_publication_returned', 'publication',
                        ('xp1_saved_raw_load_observed', 'xp1_saved_cache_observed', 'xp1_saved_post160_sequence_returned')),
        'player_view': ('before_xp1_saved_player_view', 'xp1_saved_player_view_returned', 'player_view',
                       ('xp1_saved_cache_publication_returned',)),
        'unit_commands': ('before_xp1_saved_unit_commands', 'xp1_saved_unit_commands_returned', 'unit_commands',
                          ('xp1_saved_player_view_returned',)),
        'lifetime': ('before_xp1_saved_loaded_close', 'xp1_saved_loaded_close_returned', 'lifetime',
                     ('xp1_saved_raw_load_observed', 'xp1_saved_cache_observed', 'xp1_saved_post160_sequence_returned')),
        'xp2_raw_lifetime': ('before_xp2_raw_loaded_close', 'xp2_saved_load_group_completed', 'XP2 raw lifetime',
                            ('official_gamecore_load_returned',)),
    }
    if allow_turn_updates:
        intervals['turn_update'] = ('before_xp1_saved_turn_update', 'xp1_saved_turn_update_returned',
                                   'turn_update', ('xp1_saved_player_view_returned',))
    if allow_checkpoint:
        intervals['checkpoint']=('before_xp1_saved_checkpoint','xp1_saved_checkpoint_returned',
                                 'checkpoint',('xp1_saved_player_view_returned',))
    if selected is not None and selected not in intervals:
        raise ValueError('Unknown saved native interval')
    begin_stage, return_stage, label, prerequisites = intervals.get(selected, (None, None, '', ()))
    retained = {'unsupported_host_contract', 'xp1_saved_raw_load_observed', 'xp1_saved_cache_observed',
                'native_checkpoint_postload_160_returned', 'xp1_saved_load_controlled_stop', 'xp1_saved_load_refused'}
    retained.add('official_gamecore_load_observed')
    retained.update(('before_xp1_ui_api_bind','xp1_ui_api_bind_returned'))
    retained.update(stage for pair in intervals.values() for stage in pair[:2])
    retained.update(('before_xp1_loaded_wrapper_release','xp1_loaded_wrappers_released',
        'before_xp1_loaded_unload','xp1_loaded_unload_returned','before_xp1_loaded_destroy',
        'xp1_loaded_destroy_returned','xp1_loaded_lifetime_closed'))
    retained.update(('before_xp2_loaded_wrapper_release','before_xp2_loaded_unload',
        'xp2_loaded_wrappers_released',
        'xp2_loaded_unload_returned','before_xp2_loaded_destroy','xp2_loaded_destroy_returned',
        'xp2_loaded_lifetime_closed','xp2_loaded_notifications_consumed','xp2_unloaded_notifications_consumed'))
    if allow_checkpoint:
        retained.update(('before_native_session_checkpoint','native_session_checkpoint_finalized',
                         'official_lan_checkpoint_reloaded'))
    events = {}
    event_lines = {}
    count = 0
    begin = returned = None
    jobs = []
    job_lines = []
    commands = []
    command_stages = {'native_found_city_candidate','native_command_archive_queued',
        'native_command_received_in_core_queue','before_native_command_queue_drain',
        'native_command_queue_drained','native_found_city_effect_verified',
        'native_player_research_preselected_observed','native_player_research_candidate',
        'native_player_research_effect_verified','official_explicit_production_effect'}
    command_begin = 'before_xp1_saved_unit_commands'
    command_return = 'xp1_saved_unit_commands_returned'
    marker_phases = {stage: phase for phase in repeatable for stage in intervals[phase][:2]}
    command_active = None
    command_intervals = []
    transition_intervals = []
    update_intervals = []
    if allow_turn_updates:
        command_stages.update(('xp1_turn_request_ui_revalidated', 'official_lan_turn_request_effect',
                              'official_lan_turn_request_submitted',
            'before_native_end_turn_request', 'native_end_turn_serialization_verified',
            'native_forced_end_turn_parameters_verified', 'before_native_unready_turn_request',
            'native_unready_turn_emission_observed', 'before_native_game_update',
            'native_game_update_returned', 'before_native_game_turn_complete_echo',
            'native_game_turn_complete_echo_verified', 'native_processor_flags_observed'))
    if allow_world_input:
        command_stages.add('official_world_input_result')
    if allow_unit_orders:
        command_stages.add('official_explicit_unit_order_effect')
    if allow_production_queue:
        command_stages.add('official_explicit_production_queue_effect')
    if allow_placements:
        command_stages.update(('official_explicit_placement_effect','official_explicit_production_resume_effect',
                               'official_explicit_placement_progress'))
    if allow_unit_attacks:
        command_stages.update(('official_explicit_unit_attack_readback','official_explicit_unit_attack_effect'))
    if allow_city_controls:
        command_stages.update(_CITY_REVIEW_STAGES)
    transcript_hash, interval_hash = hashlib.sha256(), hashlib.sha256()
    interval_bytes = 0
    from civ6_host.runtime.stdout_transport_profiles import iter_records
    records=iter_records(path,profile=stdout_transport,
                         expected_records=[] if stdout_native_records is None else stdout_native_records,
                         byte_limit=stdout_limit_bytes)
    for count,line,value in records:
        transcript_hash.update(line)
        stage = value['stage']
        if selected == 'xp2_raw_lifetime' and any(word in stage.lower() for word in ('refused','unsupported','controlled_stop')):
            raise ValueError('XP2 raw lifetime contains a refused native service: '+stage)
        if allow_multiple_commands and stage in marker_phases:
            phase = marker_phases[stage]
            seq = value.get('protocol_sequence')
            if type(seq) is not int or seq < 1:
                raise ValueError('Shared command marker lacks its protocol sequence')
            if stage == intervals[phase][0]:
                if (command_active is not None or transition_intervals and
                        seq <= transition_intervals[-1]['protocol_sequence']):
                    raise ValueError('Overlapping or unordered shared command markers')
                command_active = dict(protocol_sequence=seq, first_line=count, phase=phase)
            else:
                if (command_active is None or command_active['protocol_sequence'] != seq
                        or command_active['phase'] != phase):
                    raise ValueError('Unpaired shared command result')
                record = dict(command_active,last_line=count,event=value)
                transition_intervals.append(record)
                if phase == 'unit_commands':
                    command_intervals.append({k:v for k,v in record.items() if k!='phase'})
                else:
                    update_intervals.append(record)
                command_active = None
        if allow_turn_updates and stage == 'before_xp1_saved_loaded_close' and command_active is not None:
            raise ValueError('Loaded close overlaps an unfinished native transition')
        if allow_checkpoint:
            if stage=='before_xp1_saved_checkpoint' and command_active is not None:
                raise ValueError('Checkpoint overlaps an unfinished native action')
            if stage in ('before_xp1_saved_loaded_close',*marker_phases) and (
                    'before_xp1_saved_checkpoint' in events and 'xp1_saved_checkpoint_returned' not in events):
                raise ValueError('Native action/close overlaps an unfinished checkpoint')
        matching = (selected not in repeatable or command_sequence is None
                    or value.get('protocol_sequence') == command_sequence)
        if selected is not None:
            if stage == begin_stage and matching:
                if begin is not None or returned is not None:
                    raise ValueError('Repeated or reversed native '+label+' begin marker')
                if not all(k in events for k in prerequisites):
                    raise ValueError('Native '+label+' precedes its complete prior receipts')
                if (selected == 'lifetime' and 'before_xp1_saved_cache_publication' in events
                        and 'xp1_saved_cache_publication_returned' not in events):
                    raise ValueError('Loaded close precedes its attempted publication result')
                if (selected == 'lifetime' and 'before_xp1_saved_player_view' in events
                        and 'xp1_saved_player_view_returned' not in events):
                    raise ValueError('Loaded close precedes its attempted player observation')
                if (selected == 'lifetime' and 'before_xp1_saved_unit_commands' in events
                        and 'xp1_saved_unit_commands_returned' not in events):
                    raise ValueError('Loaded close precedes its attempted commands')
                begin = dict(line=count, event=value)
            if begin is not None and returned is None:
                interval_hash.update(line)
                interval_bytes += len(line)
                if stage in command_stages:
                    commands.append(value)
                    if len(commands)>1024:raise ValueError('Native command ledger exceeds its bound')
                export = value.get('export')
                if 'job' in stage.lower() or (type(export) is str and export.startswith('EXP_JobManager_')):
                    jobs.append(value)
                    job_lines.append(count)
                    if len(jobs) > 4096:
                        raise ValueError('Native '+label+' job ledger exceeds its bound')
            if stage == return_stage and matching:
                if begin is None or returned is not None:
                    raise ValueError('Missing, repeated or reversed native '+label+' return marker')
                returned = dict(line=count, event=value)
            if selected == 'load' and stage == 'xp1_saved_raw_load_observed' and returned is None:
                raise ValueError('Raw Load receipt precedes the native Load return')
            if selected == 'post160' and stage == 'native_checkpoint_postload_160_returned' and (begin is None or returned is not None):
                raise ValueError('Native post160 return lies outside its exact sequence')
        if stage in retained:
            command_marker = allow_multiple_commands and stage in marker_phases
            if command_marker and selected in repeatable and not matching:
                continue
            if stage in events and not command_marker:
                raise ValueError('Repeated saved Load result event')
            events[stage] = value
            event_lines[stage] = count
    if allow_multiple_commands:
        if command_active is not None:
            raise ValueError('Incomplete shared command interval')
        events['_command_intervals'] = command_intervals
        if allow_turn_updates:
            events['_transition_intervals'] = transition_intervals
            events['_update_intervals'] = update_intervals
    if allow_checkpoint and (('before_xp1_saved_checkpoint' in events)
                             != ('xp1_saved_checkpoint_returned' in events)):
        raise ValueError('Incomplete saved checkpoint interval')
    if selected is not None:
        if begin is None or returned is None:
            raise ValueError('Incomplete native '+label+' stdout interval')
        events[selected+'_job_interval'] = dict(begin=begin, returned=returned, jobs=jobs, job_lines=job_lines,commands=commands,
            interval_sha256=interval_hash.hexdigest(), interval_bytes=interval_bytes,
            stdout_sha256=transcript_hash.hexdigest(), stdout_lines=count)
    events['_event_lines'] = event_lines
    return count, events


def saved_load_review_profile(core_sha256):
    """Select exact retained sources; no Core loading, live reads or ABI inference."""
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256,_source
    from civ6_host.runtime.saved_load_job_observer import CORE_JOB_PROFILES
    from civ6_host.runtime.unit_operation_ui_profile import SOURCE as UNIT_SOURCE
    from civ6_host.runtime.xp1_turn_ui_profile import source_reference
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
        raise ValueError('Unknown saved review Core identity')
    spec=CORE_JOB_PROFILES[core_sha256]
    if _source(spec['source'])['schema']!=spec['schema']:
        raise ValueError('Saved review scheduler source differs')
    if core_sha256==XP2_CORE_SHA256:
        from civ6_host.runtime.xp2_action_transport_source import SOURCE as UNIT_SOURCE
    return dict(core_sha256=core_sha256,xp2=core_sha256==XP2_CORE_SHA256,
                engine='xp2' if core_sha256==XP2_CORE_SHA256 else 'xp1',
                job=dict(spec),unit_source=UNIT_SOURCE,turn_ui_source=source_reference(core_sha256))


def saved_load_validate_engine(snapshot, core_sha256, *, allow_legacy_transition=False):
    """Join a snapshot/transition to the selected canonical Core job ABI."""
    selected=saved_load_review_profile(core_sha256);spec=selected['job']
    core=snapshot.get('core_identity')
    if (core is None and allow_legacy_transition and not selected['xp2']
            and snapshot.get('source_proof_sha256')==spec['source'][1]):
        return selected
    if (type(core) is not dict or core.get('sha256')!=core_sha256
            or core.get('profile')!=spec['profile'] or type(core.get('profile')) is not int
            or (selected['xp2'] or 'source_sha256' in core) and core.get('source_sha256')!=spec['source'][1]
            or (selected['xp2'] or 'host_component_sha' in core) and core.get('host_component_sha')!=spec['host_component_sha']
            or any(core.get(k)!=spec[k] for k in ('execute_rva','destroy_rva','vtable_rva','completed_offset')
                   if selected['xp2'] or k in core)
            or snapshot.get('source_proof_sha256')!=spec['source'][1]
            or type(core.get('base')) is not int or core['base']<=0):
        raise ValueError('Saved scheduler receipt has a foreign Core/source/job ABI')
    return selected


def saved_load_validate_unit_source(receipt, core_sha256):
    selected=saved_load_review_profile(core_sha256)
    if receipt.get('source_sha256')!=selected['unit_source'][1]:
        raise ValueError('Continuation unit source differs from its selected engine')
    if selected['xp2']:
        from civ6_host.runtime.xp2_action_transport_source import CALLBACKS
        if receipt.get('core_sha256')!=core_sha256 or receipt.get('callbacks')!=CALLBACKS:
            raise ValueError('XP2 continuation unit source has a foreign Core/callback ABI')
    return selected['unit_source']


def saved_load_reconcile_later(report, expected_pins, raw_result, result, events, previous_ledger,
                               *, phase, lifetime_seconds, previous_transition=None, reviewed_producers=None,
                               xp2=False, core_sha256=None, session_supervision=False, placement_preparation=False,
                               city_controls=False):
    """Use one transcript/provenance join for publication and loaded lifetime."""
    if phase not in ('publication', 'player_view', 'unit_commands', 'turn_update', 'checkpoint', 'lifetime'):
        raise ValueError('Unknown loaded continuation phase')
    if phase in ('turn_update','checkpoint') and previous_transition is None:
        raise ValueError('Turn update requires an explicit authenticated continuation boundary')
    if previous_transition is not None and phase not in ('unit_commands', 'turn_update','checkpoint'):
        raise ValueError('Continuation identity is only valid for a command or update')
    if type(xp2) is not bool or type(session_supervision) is not bool:
        raise ValueError('Exact saved review engine and supervision modes required')
    if session_supervision and core_sha256 is None:
        raise ValueError('Session review requires an explicit Core identity')
    if core_sha256 is not None:
        selected=saved_load_review_profile(core_sha256)
        if xp2 and not selected['xp2']:raise ValueError('Conflicting saved review engine selectors')
        xp2=selected['xp2']
    if xp2 and (phase not in ('publication','player_view','lifetime')
            and (not session_supervision or phase not in ('unit_commands','turn_update','checkpoint'))):
        raise ValueError('Unqualified XP2 continuation phase')
    if type(city_controls) is not bool or city_controls and (not xp2 or not session_supervision):
        raise ValueError('City review requires explicit XP2 session supervision')
    city_action = (phase=='unit_commands' and result.get('action',{}).get('kind')
                   in ('city_focus','city_citizen'))
    if city_action and not city_controls:
        raise ValueError('City commands require the scoped review group')
    if xp2 and phase=='unit_commands' and not city_action and result.get('action',{}).get('kind') not in (
            'found_city','research','civic','production','end_turn','force_end_turn','unready_turn',
            'world_select_unit','world_deselect_unit','world_plot_click','unit_order',
            'queue_append','queue_remove','queue_swap','production_placement','production_resume','unit_attack'):
        raise ValueError('Unqualified XP2 command review family')
    if placement_preparation and (not xp2 or core_sha256 is None):
        raise ValueError('Placement preparation supervision requires selected XP2')
    saved_load_validate_supervision(report, expected_pins, lifetime_seconds=lifetime_seconds,
                                   xp2_raw=xp2 and not session_supervision,session=session_supervision,
                                   placement_preparation=placement_preparation,core_sha256=core_sha256)
    interval = events[phase+'_job_interval']
    if (previous_ledger.get('ledger_provenance_authenticated') is not True
            or previous_ledger['stdout_sha256'] != interval['stdout_sha256']
            or previous_ledger['last_line'] >= interval['begin']['line']
            or interval['begin']['line'] >= interval['returned']['line']):
        raise ValueError('Loaded continuation lacks its authenticated prior same-transcript interval')
    # The raw Load receipt contains a transition summary, not a registry
    # snapshot. Carry the authenticated snapshot across every later phase.
    jobs = previous_ledger.get('final_jobs')
    if type(jobs) is not dict or result.get('jobs_before') != jobs:
        raise ValueError('Loaded continuation scheduler snapshot differs from its authenticated prior phase')
    if core_sha256 is not None:
        for snapshot in (jobs,result['jobs_unloaded'] if phase=='lifetime' else result['jobs_after']):
            saved_load_validate_engine(snapshot,core_sha256)
    transition = None
    if previous_transition is not None and phase!='checkpoint':
        transition = saved_load_validate_transition(result, interval, previous_transition,
                                                   update=phase=='turn_update',**({} if core_sha256 is None else dict(core_sha256=core_sha256)))
    if phase == 'publication':
        saved_load_validate_publication(result, interval['jobs'], jobs, raw_result['readback'],xp2=xp2)
        phase_receipt = dict(jobs_unchanged=True, readback_unchanged=True)
    elif phase == 'player_view':
        phase_receipt = saved_load_validate_player_view(result, interval['jobs'], jobs, raw_result['readback'],**({'xp2':True} if xp2 else {}))
    elif phase == 'unit_commands':
        if city_action:
            if transition is None or transition['publication_count'] != previous_transition['publication_count']+1:
                raise ValueError('City command requires one authenticated publication')
            phase_receipt=saved_load_validate_city_controls(result,interval,jobs,core_sha256=core_sha256)
        elif result['action']['kind'] == 'found_city':
            if city_controls:
                if any(r['stage'] in _CITY_EFFECT_STAGES for r in interval['commands']):
                    raise ValueError('Foundation interval contains a city-control effect')
                interval=dict(interval,commands=[r for r in interval['commands']
                    if r['stage']!='native_player_view_published'])
            phase_receipt = saved_load_validate_unit_commands(result, interval, jobs,
                **({} if transition is None else dict(transition=transition)),
                **({} if core_sha256 is None else dict(core_sha256=core_sha256)))
        elif result['action']['kind'] in ('end_turn', 'force_end_turn', 'unready_turn'):
            if transition is None:
                raise ValueError('Turn request requires an explicit authenticated continuation boundary')
            phase_receipt = saved_load_validate_turn(result, interval, jobs, update=False,
                **({} if core_sha256 is None else dict(core_sha256=core_sha256)))
        elif result['action']['kind'] in ('world_select_unit','world_plot_click','world_deselect_unit'):
            if transition is None:
                raise ValueError('World input requires an explicit authenticated continuation boundary')
            phase_receipt = saved_load_validate_world_input(result, interval, jobs, core_sha256=core_sha256)
        elif result['action']['kind']=='unit_order':
            if transition is None:
                raise ValueError('Unit order requires an explicit authenticated continuation boundary')
            phase_receipt = saved_load_validate_unit_order(result, interval, jobs, core_sha256=core_sha256)
        elif result['action']['kind'] in ('queue_append','queue_remove','queue_swap'):
            if transition is None:
                raise ValueError('Queue edit requires an explicit authenticated continuation boundary')
            phase_receipt = saved_load_validate_production_queue(result, interval, jobs, core_sha256=core_sha256)
        elif result['action']['kind'] in ('production_placement','production_resume'):
            if transition is None:
                raise ValueError('Placement requires an explicit authenticated continuation boundary')
            phase_receipt = saved_load_validate_placement(result, interval, jobs, core_sha256=core_sha256)
        elif result['action']['kind']=='unit_attack':
            if transition is None:
                raise ValueError('Unit attack requires an authenticated continuation boundary')
            from review_unit_attacks import validate_native_attack
            phase_receipt=validate_native_attack(result,interval,jobs,
                transport=saved_load_validate_turn_transport,core_sha256=core_sha256)
        else:
            phase_receipt = saved_load_validate_choices(result, interval, jobs,
                **({} if transition is None else dict(transition=transition)),
                **({} if core_sha256 is None else dict(core_sha256=core_sha256)))
    elif phase == 'turn_update':
        phase_receipt = saved_load_validate_turn(result, interval, jobs, update=True,
            **({} if core_sha256 is None else dict(core_sha256=core_sha256)))
    elif phase == 'checkpoint':
        phase_receipt=saved_load_validate_checkpoint(result,interval,jobs,events,previous_transition,
            **({} if core_sha256 is None else dict(core_sha256=core_sha256)),
            **({} if reviewed_producers is None else dict(reviewed_producers=reviewed_producers)))
        transition=dict(previous_transition,protocol_sequence=interval['returned']['event']['protocol_sequence'])
    else:
        phase_receipt = saved_load_validate_lifetime(result, interval, jobs, events,xp2_loaded=xp2,
            **(dict(continuation=True) if session_supervision and xp2 else {}))
    receipt = dict(schema='civ6-host.'+('xp2' if xp2 else 'xp1')+'-'+phase+'-job-ledger-authenticated.v1',
        ledger_provenance_authenticated=True, first_line=interval['begin']['line'],
        last_line=interval['returned']['line'], interval_sha256=interval['interval_sha256'],
        interval_bytes=interval['interval_bytes'], stdout_sha256=interval['stdout_sha256'],
        stdout_lines=interval['stdout_lines'], job_export_record_count=len(interval['jobs']),
        phase_receipt=phase_receipt, public_runtime_admitted=False,
        final_jobs=result['jobs_unloaded'] if phase == 'lifetime' else result['jobs_after'],
        post_action_jobs=result['jobs_after'] if phase == 'unit_commands' else None)
    if transition is not None:
        receipt['continuation'] = transition
    return receipt


def saved_load_validate_publication(result, job_events, loaded_jobs, loaded, *, xp2=False):
    from civ6_host.runtime.saved_load_job_observer import require_quiescent
    from civ6_host.runtime.native.native_checkpoint_postload_jobs import _ledger_event
    if (any(result.get(k) is not True for k in ('post190_called', 'native_return_ignored'))
            or any(result.get(k) is not False for k in ('public_runtime_admitted',
                'public_player_observation', 'game_update_called', 'context_destroyed'))):
        raise ValueError('Publication receipt lacks its private native return')
    before, after, final = (result[k] for k in ('jobs_before', 'jobs_after', 'jobs_final'))
    for snapshot in (before, after, final):
        require_quiescent(snapshot)
    if (before != after or before != final
            or before.get('core_identity') != loaded_jobs.get('core_identity')
            or before.get('source_build') != loaded_jobs.get('source_build')
            or any(_ledger_event(row)[0] != 'noop' for row in job_events)):
        raise ValueError('Publication scheduler interval is not the same unchanged quiescent owner')
    expected = dict(current_game_turn=loaded['turn'], width=loaded['width'], height=loaded['height'],
        major_player_ids=list(range(2 if xp2 else 6)), scope='privileged diagnostic; no learner observation', game_update_called=False)
    if (result['readback'] != expected
            or result['cache_dimensions'] != [loaded['width'], loaded['height'], loaded['width']*loaded['height']]):
        raise ValueError('Publication readback or dimensions differ from the captured loaded game')


def saved_load_validate_player_view(result, job_events, loaded_jobs, loaded, *, xp2=False):
    from civ6_host.runtime.saved_load_job_observer import require_quiescent
    from civ6_host.runtime.native.native_checkpoint_postload_jobs import _ledger_event
    from civ6_host.runtime.native.native_player_observation import parse_player_observation
    from civ6_host.runtime.xp1_ui_binding import SOURCE
    if type(xp2) is not bool:raise ValueError('Exact player observation engine mode required')
    if xp2:
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        from civ6_host.runtime.xp2_ui_binding_source import SOURCE,UI_THUNK_RVA
    binding=result['binding']
    if (binding.get('native_ui_registration_returned') is not True
            or type(binding.get('outer_protected_status')) is not int or binding['outer_protected_status']!=0
            or binding.get('distinct_managed_children') is not True
            or binding.get('complete_registration_verified') is not False
            or binding.get('gameplay_api_copied') is not False or binding.get('source_sha256')!=SOURCE[1]
            or result.get('gameplay_visibility_unchanged') is not True
            or any(result.get(k) is not False for k in ('public_runtime_admitted',
                'complete_player_observation','visibility_parity_qualified','game_update_called','gameplay_api_copied'))):
        raise ValueError('Player observation lacks its separate native UI binding or overstates qualification')
    if xp2 and (result.get('core_sha256')!=XP2_CORE_SHA256
            or result.get('source_sha256')!=SOURCE[1]
            or binding.get('core_sha256')!=XP2_CORE_SHA256
            or binding.get('method_rva')!=hex(UI_THUNK_RVA)
            or result.get('player_id')!=loaded['player_id']
            or result.get('explored_memory_included') is not False):
        raise ValueError('XP2 player observation binding differs from its selected native source')
    before,after=result['jobs_before'],result['jobs_after']
    for snapshot in (before,after):require_quiescent(snapshot)
    if (before!=after or before.get('core_identity')!=loaded_jobs.get('core_identity')
            or before.get('source_build')!=loaded_jobs.get('source_build')
            or any(_ledger_event(row)[0]!='noop' for row in job_events)):
        raise ValueError('Player observation changed the native scheduler owner')
    observation=parse_player_observation(json.dumps(result['observation']),loaded['player_id'])
    if tuple(observation[k] for k in ('turn','width','height'))!=tuple(loaded[k] for k in ('turn','width','height')):
        raise ValueError('Player observation identifies another saved state')
    own_comparison=None
    if xp2:
        from civ6_host.runtime.native.native_official_postload import compare_public_own_fields
        own_comparison=compare_public_own_fields(observation,loaded)
    receipt=dict(jobs_unchanged=True,native_ui_observation_returned=True,
                player_id=observation['player_id'],plot_count=len(observation['plots']),
                own_units=len(observation['units']),own_cities=len(observation['cities']),
                complete_player_observation=False,visibility_parity_qualified=False)
    if xp2:receipt.update(core_sha256=XP2_CORE_SHA256,source_sha256=SOURCE[1],
        captured_own_readback_matched=True,compared=own_comparison,
        comparison_scope='same-save P0 own units, city count, gold, turn and dimensions')
    return receipt


def saved_load_validate_transition(result, interval, previous, *, update, core_sha256=None):
    """Join native transitions, not RPC calls (observe calls do not advance it)."""
    from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
    from civ6_host.runtime.native.native_player_observation import parse_player_observation
    from civ6_host.runtime.unit_operation_ui_profile import SOURCE as UNIT_SOURCE
    selected_unit_source=UNIT_SOURCE
    if core_sha256 is not None:selected_unit_source=saved_load_validate_unit_source(result['unit_source'],core_sha256)
    DiagnosticEpisodeIdentity(previous['episode_id'], previous['game_generation'])
    protocol_sequence = interval['begin']['event'].get('protocol_sequence')
    if (type(update) is not bool or type(protocol_sequence) is not int or protocol_sequence < 1
            or interval['returned']['event'].get('protocol_sequence') != protocol_sequence
            or type(previous['sequence']) is not int or previous['sequence'] < 0
            or type(result['sequence']) is not int or result['sequence'] != previous['sequence']+1
            or any(result[k] != previous[k] for k in ('episode_id','game_generation'))
            or result['observation_before'] != previous['observation']
            or result.get('game_update_called') is not update
            or any(result.get(k) is not False for k in ('public_runtime_admitted',
                'complete_action_space','same_save_official_transition_compared'))
            or result['unit_source']['source_sha256'] != selected_unit_source[1]):
        raise ValueError('Native continuation lost its exact identity, observation or internal sequence')
    before, after = result['observation_before'], result['observation_after']
    for observation in (before,after):
        if parse_player_observation(json.dumps(observation),before['player_id']) != observation:
            raise ValueError('Native continuation observation failed the shared player boundary')
    if (any(after[k] != before[k] for k in ('player_id','width','height'))
            or after['turn'] not in (before['turn'],before['turn']+1)):
        raise ValueError('Native continuation crossed an unqualified player/map/turn boundary')
    if (type(previous['publication_count']) is not int or previous['publication_count'] < 0
            or type(result['publication_count']) is not int
            or result['publication_count'] < previous['publication_count']):
        raise ValueError('Native publication count regressed or is not exact')
    refused = not update and result['action']['kind'] in ('end_turn','force_end_turn','unready_turn') and result['effect'].get('status')=='refused'
    delta = result['publication_count']-previous['publication_count']
    world=not update and result['action']['kind'] in ('world_select_unit','world_plot_click','world_deselect_unit')
    if world:
        receipt=result['effect'].get('receipt')
        if type(receipt) is not dict or type(receipt.get('archive_delivered')) is not bool:
            raise ValueError('World input lacks its explicit native delivery receipt')
        if delta != int(receipt['archive_delivered']):
            raise ValueError('World-input publication count differs from actual native delivery')
    elif not update and result['action']['kind'] in ('unit_order','queue_append','queue_remove','queue_swap','production_placement','production_resume','unit_attack'):
        if delta!=1:
            raise ValueError('Explicit order publication count differs from its single native delivery')
    elif (refused and delta != 0) or (not refused and delta < 1):
        raise ValueError('Native publication count disagrees with the transition receipt')
    return dict(episode_id=result['episode_id'],game_generation=result['game_generation'],
        sequence=result['sequence'],publication_count=result['publication_count'],
        observation=after,protocol_sequence=protocol_sequence)


def saved_load_validate_turn_transport(rows, player_id, *, core_sha256=None):
    """Replay captured FIFO bytes; an archive is never a network acknowledgement."""
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
    from civ6_host.runtime.native.native_game_turn_complete import decode_archive
    selected_core=XP1_CORE_SHA256
    if core_sha256 is not None:selected_core=saved_load_review_profile(core_sha256)['core_sha256']
    pending=[];received=None;draining=False;echo=None;delivered=[];echoes=[]
    for row in rows:
        stage=row['stage']
        if stage=='native_command_archive_queued':
            payload=bytes.fromhex(row['archive_hex'])
            if (not 0<len(payload)<=6784 or type(row['bytes']) is not int or row['bytes']!=len(payload)
                    or type(row['queue_count']) is not int or row['queue_count']!=len(pending)+1
                    or row.get('delivery_pending') is not True or row.get('action_applied') is not False):
                raise ValueError('Turn archive differs from the actual bounded pending FIFO')
            pending.append(row['archive_hex'])
        elif stage=='before_native_game_turn_complete_echo':
            if (echo is not None or received is not None or draining or len(pending)!=1
                    or row['archive_hex']!=pending[0] or row['player_id']!=player_id
                    or row.get('archive_fabricated') is not False
                    or decode_archive(bytes.fromhex(pending[0]),core_sha256=selected_core)['player_id']!=player_id):
                raise ValueError('Completion echo lacks its already-captured local-player archive')
            echo=pending[0]
        elif stage=='native_command_received_in_core_queue':
            if (received is not None or draining or not pending or row['archive_hex']!=pending[0]
                    or row.get('native_owned_copy') is not True or row.get('action_applied') is not False):
                raise ValueError('Turn native receive differs from the captured FIFO')
            received=pending.pop(0)
        elif stage=='before_native_command_queue_drain':
            if received is None or draining:raise ValueError('Turn drain lacks its unique native receive')
            draining=True
        elif stage=='native_command_queue_drained':
            if received is None or not draining or row.get('native_dispatcher_used') is not True:
                raise ValueError('Turn drain lacks its native dispatcher return')
            delivered.append(received);received=None;draining=False
        elif stage=='native_game_turn_complete_echo_verified':
            if (echo is None or pending or received is not None or draining or not delivered
                    or delivered[-1]!=echo or row['archive_hex']!=echo or row['player_id']!=player_id
                    or row.get('core_dispatcher_used') is not True
                    or row.get('processed_before_next_public_update') is not True):
                raise ValueError('Completion echo return differs from its actual native delivery')
            echoes.append(echo);echo=None
        elif stage=='before_native_game_update' and (pending or received is not None or draining or echo is not None):
            raise ValueError('Native update overlaps an unconsumed command or completion echo')
    if pending or received is not None or draining or echo is not None:
        raise ValueError('Native turn interval retains unfinished command work')
    return dict(delivered_archives=delivered,completion_echo_archives=echoes,network_ack_inferred=False)


def saved_load_validate_turn(result, interval, loaded_jobs, *, update, core_sha256=None):
    """Authenticate the shared submit/advance path without asserting network parity."""
    from civ6_host.contracts.network_turn import validate_turn_controls
    from civ6_host.runtime.xp1_continuation import validate_command
    from civ6_host.runtime.xp1_action_job_ledger import reconcile_action_jobs
    from civ6_host.runtime.xp1_turn_ui_profile import SOURCE as UI_SOURCE
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
    selected_core=XP1_CORE_SHA256;victory_execute_rva=0x465110;selected_ui_source=UI_SOURCE
    if core_sha256 is not None:
        selected=saved_load_validate_engine(loaded_jobs,core_sha256)
        saved_load_validate_engine(result['jobs_after'],core_sha256)
        selected_ui_source=selected['turn_ui_source'];selected_core=core_sha256
        victory_execute_rva=selected['job']['execute_rva']
    rows=interval['commands'];before=result['observation_before'];after=result['observation_after']
    if result['jobs_before']!=loaded_jobs or result.get('game_update_called') is not update:
        raise ValueError('Turn request/update lost its native scheduler boundary')
    transport=saved_load_validate_turn_transport(rows,before['player_id'],
        **({} if core_sha256 is None else dict(core_sha256=core_sha256)))
    stages=[row['stage'] for row in rows]
    def only(stage):
        matches=[r for r in rows if r['stage']==stage]
        if len(matches)!=1:raise ValueError('Expected one native turn marker: '+stage)
        return matches[0]
    request_stages=('xp1_turn_request_ui_revalidated','official_lan_turn_request_effect',
                    'official_lan_turn_request_submitted',
        'before_native_end_turn_request','native_end_turn_serialization_verified',
        'native_forced_end_turn_parameters_verified','before_native_unready_turn_request',
        'native_unready_turn_emission_observed')
    update_stages=('before_native_game_update','native_game_update_returned')
    if update:
        if result['action'] is not None or result['effect'] is not None or any(s in stages for s in request_stages):
            raise ValueError('Native poll fabricated a requested action or effect')
        started,returned=only(update_stages[0]),only(update_stages[1])
        if (stages.index(update_stages[0])>=stages.index(update_stages[1])
                or started.get('outer_slot')!='0x90' or started.get('game_slot')!='0x30'
                or returned.get('eligible_for_training') is not False
                or transport['delivered_archives']!=transport['completion_echo_archives']):
            raise ValueError('Poll lacks one explicit update or delivered a non-completion command')
        outcome=None
    else:
        action=result['action'];validate_command(action)
        if action['kind'] not in ('end_turn','force_end_turn','unready_turn') or any(s in stages for s in update_stages):
            raise ValueError('Turn request called update or has a foreign action kind')
        gate=only('xp1_turn_request_ui_revalidated');effect=result['effect']
        if (gate.get('action')!=action or gate.get('source_sha256')!=selected_ui_source[1]
                or gate.get('core_sha256')!=selected_core
                or set(effect)!={'status','reason','requested_action'} or effect['requested_action']!=action):
            raise ValueError('Turn request lacks its exact fresh UI gate or submit receipt')
        availability=gate['turn_availability'][action['kind']]
        if availability is not None and type(availability) is not bool:
            raise ValueError('Turn request gate is not exact Boolean/unknown')
        outcome=effect['status']
        if outcome=='refused':
            expected=('native_turn_ui_gate_unknown' if availability is None else
                      'native_turn_ui_gate_unavailable' if availability is False else 'native_unready_not_queued')
            if (effect['reason']!=expected or before!=after or transport['delivered_archives']
                    or any(s in stages for s in ('official_lan_turn_request_effect','official_lan_turn_request_submitted'))):
                raise ValueError('Refused turn request has an invented effect or reason')
            if availability is True:
                emission=only('native_unready_turn_emission_observed')
                if (action['kind']!='unready_turn' or emission.get('queued') is not False
                        or emission.get('status')!='not_queued' or emission.get('player_id')!=before['player_id']):
                    raise ValueError('Refused available turn request lacks native unready non-emission')
            elif any(s in stages for s in request_stages[1:]):
                raise ValueError('Unavailable UI request nevertheless executed native request code')
        elif outcome in ('completed','submitted'):
            submitted=outcome=='submitted'
            stage='official_lan_turn_request_submitted' if submitted else 'official_lan_turn_request_effect'
            other='official_lan_turn_request_effect' if submitted else 'official_lan_turn_request_submitted'
            native=only(stage)
            if (availability is not True or native['action']!=action or other in stages
                    or native['player_id']!=before['player_id'] or native.get('network_ack_inferred') is not False
                    or native.get('strategic_training_ready') is not False
                    or native.get('turn_advanced') is not (after['turn']>before['turn'])
                    or stages.index('xp1_turn_request_ui_revalidated')>=stages.index(stage)):
                raise ValueError('Turn request lacks an actual qualified native control receipt')
            if submitted:
                if (effect['reason']!='native_turn_controls_unchanged' or action!={'kind':'force_end_turn'}
                        or native['before']!=native['after'] or native['before']['active'] is not False):
                    raise ValueError('Submitted turn request must preserve its inactive public controls without claiming an effect')
            elif effect['reason'] is not None or native['before']==native['after']:
                raise ValueError('Completed turn request lacks an actual changed native control state')
            validate_turn_controls(native['before'],before['player_id'],before['turn'])
            validate_turn_controls(native['after'],after['player_id'],after['turn'])
            if action['kind']=='unready_turn':
                only('before_native_unready_turn_request')
                serialized=only('native_unready_turn_emission_observed')
                if (serialized.get('queued') is not True or serialized.get('status')!='queued'
                        or serialized.get('player_id')!=before['player_id']):
                    raise ValueError('Unready lacks its real native emission')
            else:
                only('before_native_end_turn_request')
                serialized=only('native_end_turn_serialization_verified')
                if serialized.get('player')!=before['player_id'] or serialized.get('native_parameter_object') is not True:
                    raise ValueError('EndTurn lacks its actual native parameters/serialization')
                if action['kind']=='force_end_turn':
                    forced=only('native_forced_end_turn_parameters_verified')
                    if (forced.get('player_id')!=before['player_id'] or forced.get('reason')!='UserForced'
                            or any(forced.get(k) is not True for k in ('native_string_setter_used',
                               'native_reason_converter_used','string_roundtrip_verified'))):
                        raise ValueError('Forced turn lacks the actual native UserForced parameter')
                elif 'native_forced_end_turn_parameters_verified' in stages:
                    raise ValueError('Normal EndTurn has forced parameters')
            if transport['delivered_archives'] != [serialized['archive_hex']]+transport['completion_echo_archives']:
                raise ValueError('Native turn effect differs from its exact delivered request/completion archives')
        else:
            raise ValueError('Unknown native turn submit outcome')
    jobs=reconcile_action_jobs(result['jobs_before'],result['jobs_after'],interval['jobs'],victory_execute_rva=victory_execute_rva)
    return dict(jobs=jobs,game_update_authenticated=update,turn_request_status=outcome,
        transport=transport,player_observation_refreshed=True,
        native_turn_advanced=after['turn']-before['turn'],network_ack_inferred=False,
        same_save_official_transition_compared=False)


def saved_load_validate_unit_commands(result, interval, loaded_jobs, *, transition=None, core_sha256=None):
    from civ6_host.runtime.xp1_continuation import validate_unit_command
    from civ6_host.runtime.unit_operation_ui_profile import SOURCE as UNIT_SOURCE
    from civ6_host.runtime.xp1_action_job_ledger import reconcile_action_jobs
    victory_execute_rva=0x465110;selected_unit_source=UNIT_SOURCE
    if core_sha256 is not None:
        selected=saved_load_validate_engine(loaded_jobs,core_sha256)
        saved_load_validate_engine(result['jobs_after'],core_sha256)
        selected_unit_source=saved_load_validate_unit_source(result['unit_source'],core_sha256)
        victory_execute_rva=selected['job']['execute_rva']
    action=result['action'];validate_unit_command(action)
    before,after=result['observation_before'],result['observation_after']
    from civ6_host.runtime.native.native_player_observation import parse_player_observation
    for observation in (before,after):
        if parse_player_observation(json.dumps(observation),before['player_id'])!=observation:
            raise ValueError('XP1 command observation failed the shared player boundary')
    effect=result['effect']
    expected={'player_id':before['player_id'],'consumed_unit_id':action['unit_id'],
              'city_id':effect['city_id'],'x':action['x'],'y':action['y'],'population':effect['population']}
    if (effect!=expected or result['jobs_before']!=loaded_jobs
            or (transition is None and (result['sequence']!=1 or result['publication_count']!=1))
            or result.get('public_runtime_admitted') is not False
            or result.get('complete_action_space') is not False or result.get('game_update_called') is not False
            or result['unit_source']['source_sha256']!=selected_unit_source[1]
            or any(after[k]!=before[k] for k in ('player_id','turn','width','height'))):
        raise ValueError('XP1 unit effect lost the exact initial observation or native source')
    old_units={u['id']:u for u in before['units']};new_units={u['id']:u for u in after['units']}
    old_cities={c['id']:c for c in before['cities']};new_cities={c['id']:c for c in after['cities']}
    if (action['unit_id'] not in old_units or set(new_units)!=set(old_units)-{action['unit_id']}
            or set(new_cities)!=set(old_cities)|{effect['city_id']} or effect['city_id'] in old_cities):
        raise ValueError('Foundation did not consume the selected unit/create a new observed city')
    city=new_cities[effect['city_id']]
    if any(city[k]!=effect[k] for k in ('x','y','population')):
        raise ValueError('Founded city differs from the refreshed public observation')
    rows=interval['commands']
    if transition is not None:
        rows=[r for r in rows if r['stage']!='native_processor_flags_observed']
    order=['native_found_city_candidate','native_command_archive_queued','native_command_received_in_core_queue',
           'before_native_command_queue_drain','native_command_queue_drained','native_found_city_effect_verified']
    if [r['stage'] for r in rows]!=order:
        raise ValueError('Unit command lacks its unique serialized/received/drained/effect chain')
    candidate,serialized,received,_,drained,verified=rows
    if (candidate['unit_id']!=action['unit_id'] or candidate['player_id']!=before['player_id']
            or (candidate['x'],candidate['y'])!=(action['x'],action['y'])
            or serialized['archive_hex']!=received['archive_hex']
            or len(bytes.fromhex(serialized['archive_hex']))!=serialized['bytes']
            or received.get('native_owned_copy') is not True or drained.get('native_dispatcher_used') is not True
            or any(verified[k]!=v for k,v in effect.items()) or verified.get('native_rules_used') is not True):
        raise ValueError('Serialized native command chain disagrees with the explicit effect')
    jobs=reconcile_action_jobs(result['jobs_before'],result['jobs_after'],interval['jobs'],victory_execute_rva=victory_execute_rva)
    return dict(jobs=jobs,explicit_unit_command_applied=True,player_observation_refreshed=True,
                archive_bytes=serialized['bytes'],same_save_official_transition_compared=False)


def saved_load_validate_choices(result, interval, loaded_jobs, *, transition=None, core_sha256=None):
    """Authenticate actual changed choices on the shared command/job stream."""
    from civ6_host.runtime.xp1_continuation import validate_command
    from civ6_host.runtime.xp1_action_job_ledger import reconcile_action_jobs
    from civ6_host.runtime.native.native_player_observation import parse_player_observation
    victory_execute_rva=0x465110
    if core_sha256 is not None:
        selected=saved_load_validate_engine(loaded_jobs,core_sha256)
        saved_load_validate_engine(result['jobs_after'],core_sha256)
        victory_execute_rva=selected['job']['execute_rva']
    action=result['action'];validate_command(action)
    if action['kind'] not in ('research','civic','production'):
        raise ValueError('No grouped native choice verifier for this family')
    before,after=result['observation_before'],result['observation_after']
    for observation in (before,after):
        if parse_player_observation(json.dumps(observation),before['player_id'])!=observation:
            raise ValueError('Choice observation failed the shared player boundary')
    seq=interval['begin']['event'].get('protocol_sequence')
    if (type(seq) is not int or interval['returned']['event'].get('protocol_sequence')!=seq
            or (transition is None and result['sequence']!=seq) or result['jobs_before']!=loaded_jobs
            or any(after[k]!=before[k] for k in ('player_id','turn','width','height'))
            or any(result.get(k) is not False for k in ('public_runtime_admitted',
                'complete_action_space','game_update_called','same_save_official_transition_compared'))):
        raise ValueError('Choice lost its native same-turn command boundary')
    transport_stages=('native_command_archive_queued','native_command_received_in_core_queue',
                      'before_native_command_queue_drain','native_command_queue_drained')
    transport=[r for r in interval['commands'] if r['stage'] in transport_stages]
    if [r['stage'] for r in transport]!=list(transport_stages):
        raise ValueError('Changed choice lacks exactly one native transport chain')
    serialized,received,_,drained=transport
    if (serialized['archive_hex']!=received['archive_hex']
            or len(bytes.fromhex(serialized['archive_hex']))!=serialized['bytes']
            or received.get('native_owned_copy') is not True or drained.get('native_dispatcher_used') is not True):
        raise ValueError('Choice serialization differs from native reception/delivery')
    if action['kind'] in ('research','civic'):
        expected_stage='native_player_research_effect_verified'
        rows=[r for r in interval['commands'] if r['stage']==expected_stage]
        if (len(rows)!=1 or rows[0]['kind']!=action['kind']
                or rows[0]['player_id']!=before['player_id'] or rows[0]['selected_hash']!=action['hash']
                or rows[0]['after']!=result['effect'] or rows[0].get('native_rules_used') is not True
                or result['effect']['confirmed'] is not True
                or result['effect']['observed_index']!=action['index']
                or result['effect']['current_game_turn']!=before['turn']):
            raise ValueError('Native research/civic effect differs from the explicit choice')
    else:
        rows=[r for r in interval['commands'] if r['stage']=='official_explicit_production_effect']
        if len(rows)!=1:raise ValueError('Production lacks its native queue effect')
        choice,prior,current=rows[0]['choice'],rows[0]['production_before'],rows[0]['production']
        if (choice['city_id']!=action['city_id'] or choice['player_id']!=before['player_id']
                or choice['current_game_turn']!=before['turn'] or choice['kind']!=action['category']
                or any(choice[k]!=action[k] for k in ('hash','index','item_type'))
                or current['city_id']!=action['city_id'] or prior['city_id']!=action['city_id']
                or current['owner_id']!=before['player_id']
                or current['current_production_hash'] & 0xffffffff!=action['hash']
                or current['item_index']!=action['index']
                or current['queue_size']!=max(1,prior['queue_size'])
                or current['kind']!={'unit':'U','building':'B','district':'D','project':'P'}[action['category']]
                or rows[0]['item_completed'] is not False):
            raise ValueError('Production effect differs from the requested native replacement')
    jobs=reconcile_action_jobs(result['jobs_before'],result['jobs_after'],interval['jobs'],victory_execute_rva=victory_execute_rva)
    return dict(jobs=jobs,explicit_choice_applied=True,kind=action['kind'],
        player_observation_refreshed=True,archive_bytes=serialized['bytes'],
        same_save_official_transition_compared=False)


def saved_load_validate_world_request(request, action, before, *, core_sha256=None):
    """Round-trip the retained request through the shared official Lua parser."""
    from civ6_host.runtime.native.native_world_click import parse_request_result
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
    if type(request) is not dict or request.get('status') not in ('request','noop','unsupported'):
        raise ValueError('World click lacks an admitted explicit native route result')
    for key,expected in (('player_id',before['player_id']),('turn',before['turn']),
            ('unit_id',action['unit_id']),('destination_plot_id',action['plot_id']),
            ('width',before['width']),('height',before['height'])):
        if type(request.get(key)) is not int or request[key]!=expected:
            raise ValueError('World-click request differs from its public identity or coordinates')
    fields=[request['status'],request['player_id'],request['turn'],request['unit_id'],
            request['destination_plot_id'],request['width'],request['height'],'-','-','-','-','-',
            request.get('source_sha256')]
    if request['status']=='request':
        if (request.get('operation_name')!='MOVE_TO' or type(request.get('operation')) is not int
                or type(request.get('parameters')) is not list):
            raise ValueError('World-click native request is not the selected MOVE_TO route')
        params=request['parameters']
        if any(type(p) is not list or len(p)!=3 or type(p[0]) is not str
               or type(p[1]) is not int or type(p[2]) is not int for p in params):
            raise ValueError('World-click parameter receipt is not exact')
        fields[7:10]=[request['operation_name'],request['operation'],
                      ';'.join('%s:%d=%d'%tuple(p) for p in params)]
    if type(fields[-1]) is not str or len(fields[-1])!=64:
        raise ValueError('World click lacks its official source hash')
    parsed=parse_request_result(','.join(map(str,fields)).encode('ascii'),before['player_id'],
        before['turn'],action['unit_id'],action['plot_id'],core_sha256=XP1_CORE_SHA256 if core_sha256 is None else core_sha256)
    if json.loads(json.dumps(parsed))!=request:
        raise ValueError('World-click receipt differs from the shared official parser')
    return request


def saved_load_validate_world_input(result, interval, loaded_jobs, *, core_sha256=None):
    """Join native world input, actual FIFO delivery and its public readback."""
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
    selected_core=XP1_CORE_SHA256;victory_execute_rva=0x465110
    if core_sha256 is not None:
        selected=saved_load_review_profile(core_sha256)
        selected_core=selected['core_sha256'];victory_execute_rva=selected['job']['execute_rva']
    from civ6_host.contracts.capability_world_input import validate_action
    from civ6_host.runtime.xp1_action_job_ledger import reconcile_action_jobs
    action=result['action'];before=result['observation_before'];after=result['observation_after']
    validate_action(action,width=before['width'],height=before['height'])
    if (result['jobs_before']!=loaded_jobs or result['game_update_called'] is not False
            or any(before[k]!=after[k] for k in ('player_id','turn','width','height'))):
        raise ValueError('World input lost its same-turn native boundary')
    effect=result['effect']
    if (type(effect) is not dict or set(effect)!={'status','refusal_code','observation','receipt'}
            or effect['observation']!=after):
        raise ValueError('World-input adapter effect lost its exact observation/receipt')
    receipt=effect['receipt'];rows=interval['commands']
    emitted=[r for r in rows if r['stage']=='official_world_input_result']
    fields={'action','request','archive_hex','archive_delivered','delegated_minor_war',
            'queued_destination_after','observation_before','observation_after',
            'base_observation_changed','action_dialogue_retained','automatic_choices_applied',
            'strategic_training_ready'}
    if (type(receipt) is not dict or set(receipt)!=fields or len(emitted)!=1
            or emitted[0]!={'stage':'official_world_input_result',**receipt}
            or receipt['action']!=action or receipt['observation_before']!=before
            or receipt['observation_after']!=after or receipt['base_observation_changed'] is not (before!=after)
            or type(receipt['archive_delivered']) is not bool
            or any(receipt[k] is not False for k in ('delegated_minor_war','action_dialogue_retained',
                       'automatic_choices_applied','strategic_training_ready'))):
        raise ValueError('World input differs from its actual shared native result event')
    transport_stages={'native_command_archive_queued','native_command_received_in_core_queue',
                      'before_native_command_queue_drain','native_command_queue_drained'}
    if any(r['stage'] not in transport_stages|{'official_world_input_result','native_processor_flags_observed'}
           for r in rows):
        raise ValueError('World-input interval contains a different command/update family')
    meaningful=[r for r in rows if r['stage']!='native_processor_flags_observed']
    if meaningful[-1] is not emitted[0]:
        raise ValueError('World-input result precedes its native transport completion')
    transport=saved_load_validate_turn_transport(rows,before['player_id'],core_sha256=core_sha256)
    request=receipt['request'];kind=action['kind']
    if kind=='world_plot_click':
        request=saved_load_validate_world_request(request,action,before,core_sha256=core_sha256)
        status=request['status']
        queued=receipt['queued_destination_after']
        present=any(u['id']==action['unit_id'] for u in after['units'])
        if present:
            if (type(queued) is not dict or set(queued)!={'unit_present','plot_id'}
                    or queued['unit_present'] is not True or queued['plot_id'] is not None
                    and (type(queued['plot_id']) is not int
                         or not 0<=queued['plot_id']<before['width']*before['height'])):
                raise ValueError('World-input own queued destination is not its native readback')
        elif queued is not None:
            raise ValueError('Disappeared own unit has a fabricated queued destination')
    else:
        status='selection'
        if request is not None or receipt['queued_destination_after'] is not None:
            raise ValueError('UI selection claimed a native click/query result')
    refused=status=='unsupported';delivered=status=='request'
    if (effect['status']!=('refused' if refused else 'completed')
            or effect['refusal_code']!=('native_world_input_branch_unqualified' if refused else None)
            or receipt['archive_delivered'] is not delivered or transport['completion_echo_archives']):
        raise ValueError('World-input status confuses unsupported input and a native request')
    if delivered:
        if (type(receipt['archive_hex']) is not str
                or transport['delivered_archives']!=[receipt['archive_hex']]):
            raise ValueError('World input lost its unique captured and delivered native archive')
    elif (receipt['archive_hex'] is not None or transport['delivered_archives']
            or result['jobs_before']!=result['jobs_after'] or before!=after):
        raise ValueError('UI-only/refused world input changed simulation or delivered a native command')
    jobs=reconcile_action_jobs(result['jobs_before'],result['jobs_after'],interval['jobs'],victory_execute_rva=victory_execute_rva)
    return dict(jobs=jobs,world_input_status=effect['status'],native_route=status,
        native_request_delivered=delivered,archive_hex=receipt['archive_hex'],
        queued_destination_after=receipt['queued_destination_after'],
        player_observation_refreshed=True,network_ack_inferred=False,
        same_save_official_transition_compared=False)


def saved_load_validate_unit_order(result, interval, loaded_jobs, *, core_sha256=None):
    """Authenticate the shared native rest/wake/cancel event and archive FIFO."""
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
    selected_core=XP1_CORE_SHA256;victory_execute_rva=0x465110
    if core_sha256 is not None:
        selected=saved_load_review_profile(core_sha256)
        selected_core=selected['core_sha256'];victory_execute_rva=selected['job']['execute_rva']
    from civ6_host.runtime.native.native_saved_unit_orders import validate_action, validate_catalog, CANCEL_NAME
    from civ6_host.runtime.xp1_unit_orders_profile import SOURCE as ORDER_SOURCE
    if selected_core==XP2_CORE_SHA256:
        from civ6_host.runtime.xp2_unit_orders_source import SOURCE as ORDER_SOURCE
    from civ6_host.runtime.xp1_action_job_ledger import reconcile_action_jobs
    action=result['action'];validate_action(action)
    before,after=result['observation_before'],result['observation_after'];effect=result['effect']
    if (result['jobs_before']!=loaded_jobs or result['game_update_called'] is not False
            or any(before[k]!=after[k] for k in ('player_id','turn','width','height'))
            or type(effect) is not dict or set(effect)!={'status','refusal_code','observation','receipt'}
            or effect['status']!='completed' or effect['refusal_code'] is not None or effect['observation']!=after):
        raise ValueError('Unit order lost its same-turn native effect boundary')
    receipt=effect['receipt'];rows=interval['commands']
    fields={'action','unit_before','unit_after','state_changed','observation_before','observation_after',
            'source_proof_sha256','native_archive_delivered','automatic_choices_applied','strategic_training_ready'}
    if action['item_type']==CANCEL_NAME:fields.add('cancel_source_proof_sha256')
    emitted=[r for r in rows if r['stage']=='official_explicit_unit_order_effect']
    if (type(receipt) is not dict or set(receipt)!=fields or len(emitted)!=1
            or emitted[0]!={'stage':'official_explicit_unit_order_effect',**receipt}
            or receipt['action']!=action or receipt['observation_before']!=before
            or receipt['observation_after']!=after or receipt['source_proof_sha256']!=ORDER_SOURCE[1]
            or action['item_type']==CANCEL_NAME and receipt['cancel_source_proof_sha256']!=ORDER_SOURCE[1]
            or receipt['native_archive_delivered'] is not True
            or receipt['automatic_choices_applied'] is not False or receipt['strategic_training_ready'] is not False
            or receipt['state_changed'] is not (receipt['unit_before']!=receipt['unit_after'])):
        raise ValueError('Unit order differs from its exact source-selected native result event')
    for key,observation in (('unit_before',before),('unit_after',after)):
        unit=receipt[key]
        validate_catalog(dict(player_id=before['player_id'],turn=before['turn'],units=[unit],offers=[]),
                         before['player_id'],before['turn'])
        if (unit['unit_id']!=action['unit_id']
                or len([u for u in observation['units'] if u['id']==action['unit_id']])!=1):
            raise ValueError('Unit-order effect names a foreign or missing own unit')
    actual=[r for r in rows if r['stage']!='native_processor_flags_observed']
    expected=['native_command_archive_queued','native_command_received_in_core_queue',
              'before_native_command_queue_drain','native_command_queue_drained','official_explicit_unit_order_effect']
    if [r['stage'] for r in actual]!=expected:
        raise ValueError('Unit order lacks its single actual native archive/delivery/effect interval')
    transport=saved_load_validate_turn_transport(rows,before['player_id'],core_sha256=core_sha256)
    if len(transport['delivered_archives'])!=1 or transport['completion_echo_archives']:
        raise ValueError('Unit order lost its one native delivered archive')
    jobs=reconcile_action_jobs(result['jobs_before'],result['jobs_after'],interval['jobs'],victory_execute_rva=victory_execute_rva)
    return dict(jobs=jobs,unit_order_status='completed',native_request_delivered=True,
        archive_hex=transport['delivered_archives'][0],unit_before=receipt['unit_before'],
        unit_after=receipt['unit_after'],state_changed=receipt['state_changed'],
        source_proof_sha256=ORDER_SOURCE[1],player_observation_refreshed=True,
        network_ack_inferred=False,same_save_official_transition_compared=False)


_CITY_EFFECT_STAGES = {
    'official_explicit_city_focus_effect1000',
    'official_explicit_city_citizen_effect',
}
_CITY_REVIEW_STAGES = _CITY_EFFECT_STAGES | {'native_player_view_published'}


def saved_load_validate_city_controls(result, interval, loaded_jobs, *, core_sha256):
    """Join each city gesture to the shared FIFO, publication and native readback."""
    from civ6_host.contracts.capability_city_controls import validate_action
    from civ6_host.runtime.expansion_city_controls_profile import SOURCE
    from civ6_host.runtime.native import native_saved_city_focus1000 as focus
    from civ6_host.runtime.native import native_saved_citizens as citizens
    from civ6_host.runtime.xp1_action_job_ledger import reconcile_action_jobs

    selected = saved_load_review_profile(core_sha256)
    if not selected['xp2']:
        raise ValueError('City evidence review requires XP2')
    action = validate_action(result['action'])
    is_focus = action['kind']=='city_focus'
    module = focus if is_focus else citizens
    key = 'focus' if is_focus else 'citizens'
    stage = ('official_explicit_city_focus_effect1000' if is_focus
             else 'official_explicit_city_citizen_effect')
    before, after = result['observation_before'], result['observation_after']
    effect = result['effect']
    if (result['jobs_before']!=loaded_jobs or result['game_update_called'] is not False
            or any(before[k]!=after[k] for k in ('player_id','turn','width','height'))
            or type(effect) is not dict or set(effect)!={'status','refusal_code','observation','receipt'}
            or effect['status']!='completed' or effect['refusal_code'] is not None
            or effect['observation']!=after):
        raise ValueError('City command lost its native same-turn effect boundary')
    receipt = effect['receipt']
    fields = {'action', key+'_before', key+'_after', 'observation_before', 'observation_after',
              'automatic_choices_applied','captured_ui_gate_source_selected','core_sha256',
              'diagnostic_ui_enabled','qualification','source_proof_sha256',
              'strategic_training_ready','ui_tutorial_gate_qualified'}
    fields |= ({'ordered_commands'} if is_focus else
               {'displayed_state_changed','native_assignment_reimplemented','native_commands_delivered'})
    rows = [r for r in interval['commands'] if r['stage']!='native_processor_flags_observed']
    emitted = [r for r in rows if r['stage'] in _CITY_EFFECT_STAGES]
    if (type(receipt) is not dict or set(receipt)!=fields
            or emitted!=[{'stage':stage,**receipt}]
            or receipt['source_proof_sha256']!=SOURCE[1] or receipt['core_sha256']!=core_sha256
            or receipt['captured_ui_gate_source_selected'] is not True
            or receipt['diagnostic_ui_enabled'] is not True
            or receipt['ui_tutorial_gate_qualified'] is not False
            or receipt['automatic_choices_applied'] is not False
            or receipt['strategic_training_ready'] is not False
            or receipt['qualification']!='source and fixture candidate; native expansion qualification required'
            or receipt['action']!=action or receipt['observation_before']!=before
            or receipt['observation_after']!=after):
        raise ValueError('City command differs from its source-selected native effect event')
    prior, current = receipt[key+'_before'], receipt[key+'_after']
    for catalog, observation in ((prior,before),(current,after)):
        module.validate_catalog(catalog,observation['player_id'],observation['turn'])
        if (catalog['city_id']!=action['city_id']
                or sum(c['id']==action['city_id'] for c in observation['cities'])!=1):
            raise ValueError('City command lost its own-city readback')
    if action not in module.actions(prior):
        raise ValueError('City command was absent from the revalidated native catalogue')
    if is_focus:
        requests, flags = focus.transition(action)
        expected = [dict(row) for row in prior['yields']]
        expected[focus.YIELDS.index(action['yield_type'])].update(favored=flags[0],disfavored=flags[1])
        if (receipt['ordered_commands']!=[dict(flags=f,data0=d) for f,d in requests]
                or current['yields']!=expected):
            raise ValueError('Focus command order or native flag readback differs')
        count = len(requests)
    else:
        if (type(receipt['native_commands_delivered']) is not int
                or receipt['native_commands_delivered']!=1
                or receipt['native_assignment_reimplemented'] is not False
                or receipt['displayed_state_changed'] is not (prior!=current)):
            raise ValueError('Citizen readback differs from its one native delivery')
        count = 1

    expected_stages = (['native_command_archive_queued']*count
        + ['native_command_received_in_core_queue','before_native_command_queue_drain',
           'native_command_queue_drained']*count + ['native_player_view_published',stage])
    if [r['stage'] for r in rows]!=expected_stages:
        raise ValueError('City effect lacks its exact ordered FIFO and publication')
    publication = rows[-2]
    if ((publication.get('width'),publication.get('height'),publication.get('plot_count'))
            != (after['width'],after['height'],after['width']*after['height'])
            or publication.get('action_applied') is not False):
        raise ValueError('City publication differs from its native map boundary')
    transport = saved_load_validate_turn_transport(rows,before['player_id'],core_sha256=core_sha256)
    archives = transport['delivered_archives']
    if (len(archives)!=count or transport['completion_echo_archives']
            or any(not raw.startswith('130a6b34') for raw in archives)):
        raise ValueError('City command lacks its captured CityCommand archives')
    jobs = reconcile_action_jobs(result['jobs_before'],result['jobs_after'],interval['jobs'],
                                 victory_execute_rva=selected['job']['execute_rva'])
    return dict(jobs=jobs,city_control_applied=True,kind=action['kind'],
        archives=archives,publication_count=1,catalogue_before=prior,catalogue_after=current)


def saved_load_validate_production_queue(result, interval, loaded_jobs, *, core_sha256=None):
    """Join the shared queue permutation, native effect and one archive FIFO."""
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
    selected_core=XP1_CORE_SHA256;victory_execute_rva=0x465110
    if core_sha256 is not None:
        selected=saved_load_review_profile(core_sha256)
        selected_core=selected['core_sha256'];victory_execute_rva=selected['job']['execute_rva']
    from civ6_host.contracts import production_queue as queues
    from civ6_host.runtime.xp1_production_queue_profile import SOURCE as QUEUE_SOURCE
    if selected_core==XP2_CORE_SHA256:
        from civ6_host.runtime.xp2_production_queue_source import SOURCE as QUEUE_SOURCE
    from civ6_host.runtime.xp1_action_job_ledger import reconcile_action_jobs
    action=result['action'];queues.validate_action(action)
    before,after=result['observation_before'],result['observation_after'];effect=result['effect']
    if (result['jobs_before']!=loaded_jobs or result['game_update_called'] is not False
            or any(before[k]!=after[k] for k in ('player_id','turn','width','height'))
            or type(effect) is not dict or set(effect)!={'status','refusal_code','observation','receipt'}
            or effect['status']!='completed' or effect['refusal_code'] is not None or effect['observation']!=after):
        raise ValueError('Queue edit lost its same-turn native effect boundary')
    receipt=effect['receipt'];rows=interval['commands']
    fields={'action','queue_before','queue_after','native_archive_delivered','automatic_choices_applied',
            'source_proof_sha256','public_source_proof_sha256','tutorial_gate_qualified','strategic_training_ready'}
    emitted=[r for r in rows if r['stage']=='official_explicit_production_queue_effect']
    if (type(receipt) is not dict or set(receipt)!=fields or len(emitted)!=1
            or emitted[0]!={'stage':'official_explicit_production_queue_effect',**receipt}
            or receipt['action']!=action or receipt['source_proof_sha256']!=QUEUE_SOURCE[1]
            or receipt['public_source_proof_sha256']!=QUEUE_SOURCE[1]
            or receipt['native_archive_delivered'] is not True or receipt['tutorial_gate_qualified'] is not True
            or receipt['automatic_choices_applied'] is not False or receipt['strategic_training_ready'] is not False):
        raise ValueError('Queue edit differs from its exact source-selected native result event')
    for key,observation in (('queue_before',before),('queue_after',after)):
        queue=receipt[key];queues.validate_catalog(queue,before['player_id'],before['turn'])
        if (queue.get('schema')!=queues.PUBLIC_SCHEMA or queue['enabled'] is not True or queue['city_id']!=action['city_id']
                or len([c for c in observation['cities'] if c['id']==action['city_id'] and c['owner']==before['player_id']])!=1):
            raise ValueError('Queue effect names an unavailable or foreign own-city queue')
    if action not in receipt['queue_before']['offers']:
        raise ValueError('Queue command was absent from its revalidated native offer')
    queues.check_effect(action,receipt['queue_before'],receipt['queue_after'])
    actual=[r for r in rows if r['stage']!='native_processor_flags_observed']
    expected=['native_command_archive_queued','native_command_received_in_core_queue',
              'before_native_command_queue_drain','native_command_queue_drained','official_explicit_production_queue_effect']
    if [r['stage'] for r in actual]!=expected:
        raise ValueError('Queue edit lacks its single actual native archive/delivery/effect interval')
    transport=saved_load_validate_turn_transport(rows,before['player_id'],core_sha256=core_sha256)
    if len(transport['delivered_archives'])!=1 or transport['completion_echo_archives']:
        raise ValueError('Queue edit lost its one native delivered archive')
    jobs=reconcile_action_jobs(result['jobs_before'],result['jobs_after'],interval['jobs'],victory_execute_rva=victory_execute_rva)
    return dict(jobs=jobs,production_queue_status='completed',native_request_delivered=True,
        archive_hex=transport['delivered_archives'][0],queue_before=receipt['queue_before'],
        queue_after=receipt['queue_after'],source_proof_sha256=QUEUE_SOURCE[1],
        public_source_proof_sha256=QUEUE_SOURCE[1],player_observation_refreshed=True,
        network_ack_inferred=False,same_save_official_transition_compared=False)


def saved_load_validate_placement(result, interval, loaded_jobs, *, core_sha256=None):
    """Review the shared native placement/resume path, never simulate a plot."""
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
    selected_core=XP1_CORE_SHA256;victory_execute_rva=0x465110
    if core_sha256 is not None:
        selected=saved_load_review_profile(core_sha256)
        selected_core=selected['core_sha256'];victory_execute_rva=selected['job']['execute_rva']
    from civ6_host.contracts import placement as placed
    from civ6_host.runtime.native.native_production_placement import parse_effect
    from civ6_host.runtime.native.native_saved_placement import action as public_action
    from civ6_host.runtime.native.native_session_resume import restore_placement_choice
    from civ6_host.runtime.xp1_production_placement_profile import SOURCE as PLACEMENT_SOURCE
    if selected_core==XP2_CORE_SHA256:
        from civ6_host.runtime.xp2_production_placement_source import SOURCE as PLACEMENT_SOURCE
    from civ6_host.runtime.xp1_action_job_ledger import reconcile_action_jobs
    action=result['action'];before,after=result['observation_before'],result['observation_after'];effect=result['effect']
    placed.validate_action(action,player_id=before['player_id'])
    if (result['jobs_before']!=loaded_jobs or result['game_update_called'] is not False
            or any(before[k]!=after[k] for k in ('player_id','turn','width','height'))
            or type(effect) is not dict or set(effect)!={'status','refusal_code','observation','receipt'}
            or effect['status']!='completed' or effect['refusal_code'] is not None or effect['observation']!=after):
        raise ValueError('Placement lost its same-turn native adapter boundary')
    receipt=effect['receipt'];resume=action['kind']=='production_resume'
    stage='official_explicit_production_resume_effect' if resume else 'official_explicit_placement_effect'
    fields={'action','choice','effect','observation_before','observation_after','automatic_choices_applied'}
    if resume:fields|={'production_before','production_after','progress_before','progress_after','placements_before','placements_after'}
    events=interval['commands'];emitted=[r for r in events if r['stage']==stage]
    if (type(receipt) is not dict or set(receipt)!=fields or len(emitted)!=1 or emitted[0]!={'stage':stage,**receipt}
            or receipt['action']!=action or receipt['observation_before']!=before or receipt['observation_after']!=after
            or receipt['automatic_choices_applied'] is not False):
        raise ValueError('Placement differs from its exact emitted native effect')
    choice=restore_placement_choice(receipt['choice'])
    if (choice['player_id']!=before['player_id'] or choice['current_game_turn']!=before['turn']
            or (choice['width'],choice['height'])!=(before['width'],before['height'])
            or public_action(choice['city_id'],choice,player_id=before['player_id'])!=action):
        raise ValueError('Placement choice differs from the player, map or selected action')
    native=receipt['effect']
    tokens=['placement-effect-v1',*[choice[k] for k in ('player_id','city_id','current_game_turn','kind','index','hash','mode','plot_id','x','y')],
            int(native['has_been_placed']),native['plot_type'],native['plot_owner']]
    if type(native['has_been_placed']) is not bool or parse_effect('|'.join(map(str,tokens)).encode('ascii'),choice)!=native:
        raise ValueError('Placement effect failed its shared native parser')
    production=[r for r in events if r['stage']=='official_explicit_production_effect']
    if len(production)!=1:raise ValueError('Placement lacks its unique native current-production effect')
    p=production[0];old,new=p['production_before'],p['production']
    if (p['choice']!=receipt['choice'] or p['item_completed'] is not False
            or old['city_id']!=action['city_id'] or new['city_id']!=action['city_id']
            or new['owner_id']!=before['player_id'] or new['queue_size']!=max(1,old['queue_size'])
            or new['item_index']!=action['index'] or new['current_production_hash'] & 0xffffffff!=action['hash']
            or new['kind']!={'district':'D','building':'B'}[action['category']]):
        raise ValueError('Placement current-production readback differs from the native choice')
    progress=[r for r in events if r['stage']=='official_explicit_placement_progress']
    for row in progress:
        summary=row['summary'];nr=row['native_receipt'];placed.validate_progress([summary],before['turn'],player_id=before['player_id'])
        if (set(row)!={'stage','summary','native_receipt','native_gameplay_mutated','source_proof_sha256'}
                or row['native_gameplay_mutated'] is not False or row['source_proof_sha256']!=PLACEMENT_SOURCE[1]
                or nr['player_id']!=before['player_id'] or nr['city_id']!=summary['city_id']
                or nr['turn']!=summary['observed_turn'] or nr['placement_turn']!=summary['placement_turn']
                or nr['item_index']!=summary['index'] or any(nr[k]!=summary[k] for k in ('plot_id','x','y'))
                or nr['plot_owner']!=before['player_id'] or nr['purchase_city_owner']!=before['player_id']
                or nr['purchase_city_id']!=summary['city_id']
                or nr['eligible_for_training'] is not False or nr['exposed_to_learner'] is not False
                or summary['exists'] is not (not nr.get('wonder_absent',False))
                or summary['complete'] is not nr['native_is_complete' if summary['category']=='district' else 'city_has_building']):
            raise ValueError('Tracked progress differs from its source-selected native plot/city readback')
    if resume:
        if (receipt['production_before']!=old or receipt['production_after']!=new
                or type(receipt['progress_before']) is not int or not 0<=receipt['progress_before']<=0x7fffffff
                or type(receipt['progress_after']) is not int or receipt['progress_before']!=receipt['progress_after']
                or new['progress']!=receipt['progress_after'] or receipt['placements_before']!=receipt['placements_after']):
            raise ValueError('Resumption lost retained production progress or tracked placement identity')
        for name in ('placements_before','placements_after'):
            placed.validate_progress(receipt[name],before['turn'],player_id=before['player_id'])
        first_archive=next(i for i,r in enumerate(events) if r['stage']=='native_command_archive_queued')
        first_production=events.index(p)
        snapshots=([r['summary'] for r in events[:first_archive] if r['stage']=='official_explicit_placement_progress'],
                   [r['summary'] for r in events[first_production+1:] if r['stage']=='official_explicit_placement_progress'])
        if snapshots!=(receipt['placements_before'],receipt['placements_after']):
            raise ValueError('Resumption progress snapshots lack their actual before/after reads')
    elif progress:
        raise ValueError('Fresh placement unexpectedly includes resumption progress reads')
    actual=[r for r in events if r['stage'] not in ('native_processor_flags_observed','official_explicit_placement_progress')]
    expected=['native_command_archive_queued','native_command_received_in_core_queue','before_native_command_queue_drain',
              'native_command_queue_drained','official_explicit_production_effect',stage]
    if [r['stage'] for r in actual]!=expected:raise ValueError('Placement lost its exact archive/production/effect ordering')
    transport=saved_load_validate_turn_transport(events,before['player_id'],core_sha256=core_sha256)
    if len(transport['delivered_archives'])!=1 or transport['completion_echo_archives']:
        raise ValueError('Placement lacks its one actually delivered native archive')
    jobs=reconcile_action_jobs(result['jobs_before'],result['jobs_after'],interval['jobs'],victory_execute_rva=victory_execute_rva)
    return dict(jobs=jobs,placement_status='completed',kind=action['kind'],native_request_delivered=True,
        source_proof_sha256=PLACEMENT_SOURCE[1],archive_hex=transport['delivered_archives'][0],effect=native,
        production_before=old,production_after=new,progress_before=receipt.get('progress_before'),
        progress_after=receipt.get('progress_after'),placements_before=receipt.get('placements_before'),
        placements_after=receipt.get('placements_after'),native_progress_reads=progress,
        network_ack_inferred=False,same_save_official_transition_compared=False)


def saved_load_validate_checkpoint(result, interval, loaded_jobs, events, previous, *, reviewed_producers=None,
                                   core_sha256=None):
    """Save is administrative: authenticate its native bytes without an action."""
    from civ6_host.runtime import network_checkpoint
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
    from civ6_host.runtime.xp1_bundle_inputs import XP1_LAN_PROFILE
    from civ6_host.runtime.xp1_action_job_ledger import reconcile_action_jobs
    if core_sha256 is None or core_sha256==XP1_CORE_SHA256:
        checkpoint_profile,checkpoint_core,victory_execute=XP1_LAN_PROFILE,XP1_CORE_SHA256,0x465110
    else:
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        from civ6_host.runtime.xp2_bundle_inputs import XP2_LAN_PROFILE
        if core_sha256!=XP2_CORE_SHA256:raise ValueError('Unknown checkpoint review engine')
        selected=saved_load_review_profile(core_sha256)
        checkpoint_profile,checkpoint_core=XP2_LAN_PROFILE,XP2_CORE_SHA256
        victory_execute=selected['job']['execute_rva']
    protocol=interval['begin']['event'].get('protocol_sequence')
    control=result['control_before']
    if (type(control) is not dict or set(control)!={'pending_count','sequence','consumed',
            'notification_counter','metadata_counter','scope','actions_admitted','timers_admitted',
            'candidate_command_transport_present','pending_command_count'}
            or any(type(control[k]) is not int or control[k]<0 for k in
                   ('pending_count','sequence','consumed','notification_counter','metadata_counter','pending_command_count'))
            or any(control[k]!=0 for k in ('pending_count','notification_counter','metadata_counter','pending_command_count'))
            or control['sequence']!=control['consumed'] or control['scope']!='saved owner services'
            or control['actions_admitted'] is not False or control['timers_admitted'] is not False
            or control['candidate_command_transport_present'] is not True):
        raise ValueError('Checkpoint lacks its actual idle saved-owner control snapshot')
    if (type(protocol) is not int or protocol<1 or interval['returned']['event'].get('protocol_sequence')!=protocol
            or any(result[k]!=previous[k] for k in ('episode_id','game_generation','sequence','publication_count'))
            or type(result['sequence']) is not int or type(result['publication_count']) is not int
            or result['observation_before']!=previous['observation']
            or result['observation_after']!=result['observation_before']
            or result['control_before']!=result['control_after']
            or result['jobs_before']!=loaded_jobs or result['jobs_after']!=result['jobs_before']
            or interval['commands']):
        raise ValueError('Checkpoint changed native continuation, public state, control or scheduler boundary')
    saved=result['save_result'];finalized=events.get('native_session_checkpoint_finalized')
    before=events.get('before_native_session_checkpoint');lines=events['_event_lines']
    if (type(saved) is not dict or finalized!={'stage':'native_session_checkpoint_finalized',**saved,'strategic_training_ready':False}
            or type(before) is not dict or before.get('turn')!=previous['observation']['turn']
            or before.get('raw_components_only') is not True or before.get('strategic_training_ready') is not False
            or not interval['begin']['line']<lines.get('before_native_session_checkpoint',0)
                   <lines.get('native_session_checkpoint_finalized',0)<interval['returned']['line']
            or type(saved.get('native_save_status')) is not int or saved['native_save_status']!=0
            or saved.get('stream_closed') is not True or saved.get('native_load_of_new_pair_validated') is not False
            or saved.get('controlled_stop_required') is not True):
        raise ValueError('Checkpoint lacks its completed native Save/closed-stream markers')
    manifest=network_checkpoint.manifest(saved['manifest'],
        **({} if reviewed_producers is None else dict(reviewed_producers=reviewed_producers)))
    if (manifest['input_profile']!=checkpoint_profile.name or manifest['core_sha256']!=checkpoint_core
            or manifest['observation']!=previous['observation']
            or manifest['components']!=saved['components'] or manifest['observed_game_turn']!=saved['observed_game_turn']
            or manifest['configuration_receipt']!=before['configuration']
            or manifest['jobs_before']!=result['jobs_before'] or manifest['jobs_after']!=result['jobs_after']
            or manifest['jobs_quiescent_unchanged'] is not True or manifest['full_civ6save_container'] is not False):
        raise ValueError('Native checkpoint manifest differs from its exact selected Save receipt')
    jobs=reconcile_action_jobs(result['jobs_before'],result['jobs_after'],interval['jobs'],victory_execute_rva=victory_execute)
    return dict(jobs=jobs,manifest_reference=saved['manifest'],components=saved['components'],
        observed_game_turn=saved['observed_game_turn'],native_save_status=0,stream_closed=True,
        public_state_unchanged=True,continuation_not_advanced=True,native_load_of_pair_claimed=False)


def saved_load_validate_lifetime(result, interval, loaded_jobs, events, *, xp2_raw=False, xp2_loaded=False,
                                 continuation=False):
    """Authenticate ordered native teardown, preserving the snapshot boundary."""
    from civ6_host.runtime.xp1_loaded_lifetime import validate_jobs_shutdown, SOURCE as LIFETIME_SOURCE
    from civ6_host.runtime.native.native_checkpoint_postload_jobs import _ledger_event
    if type(xp2_raw) is not bool or type(xp2_loaded) is not bool or xp2_raw and xp2_loaded:
        raise ValueError('Exact mutually exclusive lifetime mode required')
    if type(continuation) is not bool or continuation and not xp2_loaded:
        raise ValueError('XP2 continuation review requires its loaded lifetime mode')
    if continuation:
        from civ6_host.runtime.xp2_action_transport_source import SOURCE as COMMAND_SOURCE
        if (result.get('continuation_closed') is not True or result.get('command_transport_closed') is not True
                or result.get('command_source_sha256')!=COMMAND_SOURCE[1]
                or type(result.get('continuation_source_pin_count')) is not int
                or result['continuation_source_pin_count']<=0
                or result.get('postload_candidate_only') is not False):
            raise ValueError('XP2 continuation lacks its actual command owner cleanup receipt')
    source_reference=LIFETIME_SOURCE
    if xp2_raw or xp2_loaded:
        from civ6_host.runtime.xp2_loaded_lifetime_source import SOURCE as XP2_LIFETIME_SOURCE
        source_reference=XP2_LIFETIME_SOURCE
    true_flags = ('native_unload_called','native_destroy_called','context_destroyed',
                  'services_closed','configuration_closed','lua_closed',
                  'core_lock_closed','database_shutdown','unknown_host_callbacks_refused')
    steps=['loaded_notifications_consumed' if xp2_raw else 'native_cache_wrappers_released',
        'native_unload','native_destroy','shared_services_closed','native_performance_map_destroyed',
        'native_configuration_destroyed','native_lua_closed','native_core_lock_closed','database_shutdown']
    if 'ui_child_released' in result:
        ui_released=result['ui_child_released']
        if (type(ui_released) is not bool or xp2_raw and ui_released
                or result.get('ui_child_release_order')!=('after_native_destroy_before_game_child_and_runtime_close'
                    if ui_released else 'no_ui_child_owned')):
            raise ValueError('Loaded lifetime UI release ownership/order differs')
        if ui_released:steps[6:6]=['saved_ui_child_released','game_child_released']
    if (any(result.get(k) is not True for k in true_flags)
            or result.get('cache_wrappers_released') is not (not xp2_raw)
            or result.get('cleanup_inferred_from_process_exit') is not False
            or result.get('public_loaded_lifetime_admitted') is not False
            or result.get('source_sha256') != source_reference[1]
            or result.get('steps') != steps):
        raise ValueError('Loaded lifetime lacks a complete ordered native cleanup receipt')
    if xp2_raw and (result.get('raw_load_only') is not True or result.get('post160_called') is not False
            or result.get('cache_wrappers_present') is not False or result.get('jobs_before') != loaded_jobs):
        raise ValueError('XP2 raw cleanup differs from its observed Load boundary')
    options = result.get('performance_closed')
    if (type(options) is not dict or options.get('native_destructor_returned') is not True
            or options.get('guards_intact') is not True or options.get('outer_storage_freed_by_native') is not False):
        raise ValueError('Loaded lifetime lacks native Performance destruction')
    before, after = result['jobs_before'], result['jobs_unloaded']
    transition = validate_jobs_shutdown(before,after)
    if (transition != result.get('jobs_transition') or result.get('jobs_identical') is not (before==after)
            or before.get('core_identity') != loaded_jobs.get('core_identity')
            or before.get('source_build') != loaded_jobs.get('source_build')):
        raise ValueError('Loaded lifetime scheduler receipt differs from actual same-Core snapshots')
    required = ('before_xp1_loaded_wrapper_release','xp1_loaded_wrappers_released',
                'before_xp1_loaded_unload','xp1_loaded_unload_returned',
                'before_xp1_loaded_destroy','xp1_loaded_destroy_returned','xp1_loaded_lifetime_closed')
    if xp2_raw or xp2_loaded:
        required=tuple(key.replace('xp1_','xp2_',1) for key in required if not xp2_raw or key!='xp1_loaded_wrappers_released')
    lines = events['_event_lines']
    positions = [lines.get(k,0) for k in required]
    if (not all(k in events for k in required) or positions != sorted(set(positions))
            or not interval['begin']['line'] < positions[0] < positions[-1] < interval['returned']['line']):
        raise ValueError('Loaded lifetime native markers are missing or out of order')
    for key in required:
        if not key.endswith('loaded_wrappers_released') and events[key].get('source_sha256') != source_reference[1]:
            raise ValueError('Loaded lifetime event source differs')
    def marker(key):return key.replace('xp1_','xp2_',1) if xp2_raw or xp2_loaded else key
    wrappers = events.get(marker('xp1_loaded_wrappers_released'),{})
    unloaded = events[marker('xp1_loaded_unload_returned')]
    destroyed = events[marker('xp1_loaded_destroy_returned')]
    if (events[marker('before_xp1_loaded_wrapper_release')].get('jobs_before') != before
            or (not xp2_raw and (wrappers.get('owners') != ['prefix.cache_facades','publisher._facades','status.game']
                or wrappers.get('native_release_calls_completed') is not True
                or wrappers.get('unknown_status_after_release_refused') is not True))
            or any(unloaded.get(k) is not True for k in ('game_object_null','cache_service_null','rules_manager_null','void_return_ignored'))
            or unloaded.get('jobs_unloaded') != after or unloaded.get('jobs_transition') != transition
            or destroyed.get('void_return_ignored') is not True
            or destroyed.get('context_storage_read_after_destroy') is not False
            or destroyed.get('native_globals_detached') is not True
            or {k:v for k,v in events[marker('xp1_loaded_lifetime_closed')].items() if k!='stage'} != result):
        raise ValueError('Loaded lifetime markers disagree with native release/unload/Destroy receipt')
    if xp2_raw:
        loaded=events.get('xp2_loaded_notifications_consumed',{})
        unloaded_notifications=events.get('xp2_unloaded_notifications_consumed',{})
        if (not interval['begin']['line']<lines.get('xp2_loaded_notifications_consumed',0)<positions[0]
                or not lines['xp2_loaded_unload_returned']<lines.get('xp2_unloaded_notifications_consumed',0)<lines['before_xp2_loaded_destroy']
                or loaded.get('game_alive') is not True or loaded.get('post160_called') is not False
                or loaded.get('cache_wrappers_present') is not False
                or type(loaded.get('count')) is not int or loaded['count']<0
                or loaded['count']!=result.get('loaded_notifications_consumed')
                or type(unloaded_notifications.get('count')) is not int or unloaded_notifications['count']<0
                or unloaded_notifications['count']!=result.get('unloaded_notifications_consumed')
                or unloaded_notifications.get('cache_feedback_executed') is not False):
            raise ValueError('XP2 notification drains lack their ordered lifetime receipts')
    # Replay only the exact empty-list release operations implemented by the
    # source-bound C host. No post-Destroy context memory is read or inferred.
    occupied={slot['handle'] for slot in before['slots'] if slot['occupied']}
    freed=[];groups_destroyed=0;noop_count=0
    for line,row in zip(interval['job_lines'],interval['jobs'],strict=True):
        stage=row.get('stage');export=row.get('export');mutation=False
        if stage=='job_list_freed' and export=='EXP_JobManager_FreeJobList':
            if (set(row)!={'stage','export','handle','canonical_handle','queued_jobs'}
                    or type(row['handle']) is not int or not 1<=row['handle']<(1<<64)
                    or type(row['canonical_handle']) is not int
                    or row['canonical_handle']!=((row['handle']-1)&0xffffffff)+1
                    or row['canonical_handle'] not in occupied
                    or type(row['queued_jobs']) is not int or row['queued_jobs']!=0):
                raise ValueError('Native list release is not an existing empty canonical handle')
            occupied.remove(row['canonical_handle']);freed.append(row['canonical_handle']);mutation=True
        elif stage=='job_list_free_ignored' and export=='EXP_JobManager_FreeJobList':
            if set(row)!={'stage','export','handle','reason'} or type(row['handle']) is not int or not 1<=row['handle']<(1<<64):
                raise ValueError('Malformed ignored native list release')
            index=(row['handle']-1)&0xffffffff
            expected='out_of_range' if index>=64 else 'inactive' if index+1 not in occupied else None
            if expected is None or row['reason']!=expected:raise ValueError('Ignored native release disagrees with registry')
            noop_count+=1
        elif stage=='native_job_set_destroyed':
            if set(row)!={'stage','pending_jobs','profile'} or type(row['pending_jobs']) is not int or row['pending_jobs']!=0 or row['profile']!='diagnostic_serial_native_callbacks':
                raise ValueError('Malformed owned native job group destruction')
            groups_destroyed+=1;mutation=True
        elif stage=='empty_job_set_destroyed' and export=='EXP_JobManager_DestroyJobSet':
            if (set(row)!={'stage','export','first_argument_raw','member0','member8','contract'}
                    or type(row['first_argument_raw']) is not int or not 1<=row['first_argument_raw']<(1<<64)
                    or type(row['member0']) is not int or row['member0']!=0
                    or type(row['member8']) is not int or row['member8']!=0 or row['contract']!='two_null_members_only'):
                raise ValueError('Native empty group destruction is not its exact no-op contract')
            noop_count+=1
        else:
            if _ledger_event(row)[0]!='noop':raise ValueError('Loaded teardown created or submitted jobs')
            noop_count+=1
        if mutation and not positions[0]<line<lines[marker('xp1_loaded_unload_returned')]:
            raise ValueError('Scheduler mutation lies outside the observed pre-/post-unload snapshots')
    if (sorted(freed)!=transition['removed_empty_handles']
            or groups_destroyed!=transition['removed_owned_empty_groups']
            or occupied!={slot['handle'] for slot in after['slots'] if slot['occupied']}):
        raise ValueError('Native release ledger does not match emptied scheduler slots/groups')
    return dict(native_unload_authenticated=True,native_destroy_authenticated=True,
                cleanup_completed=True,removed_empty_handles=sorted(freed),removed_group_count=groups_destroyed,
                group_identity_limit='C destruction record reports count, not pointer; removed group identities come from snapshots',
                noop_records=noop_count,post_unload_mutations_observed=False,post_destroy_snapshot_taken=False,
                ledger_provenance_authenticated=True,public_loaded_lifetime_admitted=False)


def saved_load_validate_supervision(report, expected_pins, *, lifetime_seconds, xp2_raw=False, session=False,
                                   placement_preparation=False, core_sha256=None):
    unchanged = report.get('source_unchanged')
    if type(xp2_raw) is not bool or type(session) is not bool or session and xp2_raw:
        raise ValueError('Exact separate saved supervision mode required')
    if type(placement_preparation) is not bool or placement_preparation and (not session or xp2_raw):
        raise ValueError('Placement preparation requires explicit session supervision')
    if session and (report.get('exit_code')!=90 or report.get('normal_destroy_called') is not True):
        raise ValueError('Session review requires its actual completed client lifetime')
    if xp2_raw:
        if (type(lifetime_seconds) is not int or lifetime_seconds not in (120,180)
                or report.get('wall_limit_seconds')!=lifetime_seconds
                or report.get('memory_limit_bytes')!=768*1024*1024
                or report.get('status')!='passed' or report.get('exit_code')!=0
                or report.get('process_reaped') is not True or report.get('job_contained') is not True
                or report.get('game_executable_launched') is not False
                or report.get('error') is not None or type(unchanged) is not dict or not expected_pins
                or set(unchanged)!=set(expected_pins) or any(value is not True for value in unchanged.values())):
            raise ValueError('XP2 raw Load lacks complete pinned bounded supervision')
        return
    selected_xp2=(core_sha256 is not None and saved_load_review_profile(core_sha256)['xp2'])
    extended=placement_preparation or session and selected_xp2
    allowed=(45,60,120,300,420,600,900) if extended else (45,60,120,300,420)
    if session and selected_xp2 and not placement_preparation:allowed=allowed+(1800,)
    if (type(lifetime_seconds) is not int or lifetime_seconds not in allowed
            or report.get('reaped') is not True or report.get('job_assigned') is not True
            or report.get('exit_code') not in (78, 89, 90) or report.get('error') is not None
            or report.get('timed_out') is not False or report.get('timeout_seconds') != lifetime_seconds
            or report.get('memory_limit_bytes') != 512*1024*1024
            or report.get('stdout_limit_bytes') != 64*1024*1024
            or type(unchanged) is not dict or not expected_pins
            or set(unchanged) != set(expected_pins)
            or any(value is not True for value in unchanged.values())):
        raise ValueError('Native Load ledger lacks complete pinned bounded supervision')


def saved_load_reconcile_jobs(report, expected_pins, raw_result, interval, *, lifetime_seconds=45,
                             xp2_raw=False, core_sha256=None, session_supervision=False, placement_preparation=False):
    """Authenticate parent-owned evidence before the shared pure reconciliation."""
    if session_supervision and core_sha256 is None:
        raise ValueError('Session review requires an explicit Core identity')
    selected=None
    if core_sha256 is not None:
        selected=saved_load_review_profile(core_sha256)
        if xp2_raw and not selected['xp2']:raise ValueError('Conflicting saved review engine selectors')
    if placement_preparation and (selected is None or not selected['xp2']):
        raise ValueError('Placement preparation supervision requires selected XP2')
    saved_load_validate_supervision(report, expected_pins, lifetime_seconds=lifetime_seconds,
                                   xp2_raw=xp2_raw,session=session_supervision,placement_preparation=placement_preparation,core_sha256=core_sha256)
    receipt = raw_result['raw_load_receipt']
    begin, returned = interval['begin']['event'], interval['returned']['event']
    if (type(receipt.get('status')) is not int or receipt['status'] != 0
            or type(returned.get('status')) is not int or returned['status'] != receipt['status']
            or type(begin.get('game_bytes')) is not int or begin['game_bytes'] <= 0
            or begin['game_bytes'] != receipt.get('bytes_consumed')
            or returned.get('bytes_consumed') != receipt['bytes_consumed']
            or returned.get('validation_completed') is not False
            or interval['begin']['line'] >= interval['returned']['line']):
        raise ValueError('Native Load interval differs from its checked raw receipt')
    from civ6_host.runtime.saved_load_job_observer import reconcile_ledger
    if selected is not None:
        saved_load_validate_engine(receipt['jobs_structural_candidate'],core_sha256,allow_legacy_transition=True)
    reconciled = reconcile_ledger(receipt['jobs_structural_candidate'], interval['jobs'])
    return dict(schema='civ6-host.'+('xp2' if xp2_raw or selected and selected['xp2'] else 'xp1')+'-load-job-ledger-authenticated.v1',
                reconciliation=reconciled, ledger_provenance_authenticated=True,
                first_line=interval['begin']['line'], last_line=interval['returned']['line'],
                interval_sha256=interval['interval_sha256'], interval_bytes=interval['interval_bytes'],
                stdout_sha256=interval['stdout_sha256'], stdout_lines=interval['stdout_lines'],
                job_export_record_count=len(interval['jobs']), raw_receipt_modified=False,
                cache_interval_reconciled=False, public_runtime_admitted=False)


def saved_load_reconcile_post160(report, expected_pins, raw_result, result, events, load_ledger, *, lifetime_seconds,
                                xp2=False, core_sha256=None, session_supervision=False, placement_preparation=False):
    """Authenticate the separate post160 sequence without upgrading public admission."""
    from civ6_host.runtime.saved_load_job_observer import require_quiescent
    from civ6_host.runtime.native.native_checkpoint_postload_jobs import _ledger_event
    if type(xp2) is not bool:raise ValueError('Exact post160 engine mode required')
    if session_supervision and core_sha256 is None:
        raise ValueError('Session review requires an explicit Core identity')
    if core_sha256 is not None:
        selected=saved_load_review_profile(core_sha256)
        if xp2 and not selected['xp2']:raise ValueError('Conflicting saved review engine selectors')
        xp2=selected['xp2']
    if placement_preparation and (not xp2 or core_sha256 is None):
        raise ValueError('Placement preparation supervision requires selected XP2')
    saved_load_validate_supervision(report, expected_pins, lifetime_seconds=lifetime_seconds,
                                   xp2_raw=xp2 and not session_supervision,session=session_supervision,
                                   placement_preparation=placement_preparation,core_sha256=core_sha256)
    interval = events['post160_job_interval']
    returned = events.get('native_checkpoint_postload_160_returned')
    if (load_ledger.get('ledger_provenance_authenticated') is not True
            or load_ledger['stdout_sha256'] != interval['stdout_sha256']
            or load_ledger['last_line'] >= interval['begin']['line']
            or not isinstance(returned, dict) or returned.get('native_return', 0) is not None
            or returned.get('jobs_identical') is not True or returned.get('validation_completed') is not False
            or any(result.get(k) is not True for k in ('post160_called','call_returned',
                'immediate_jobs_unchanged','postreadback_jobs_unchanged','owners_retained'))
            or any(result.get(k) is not False for k in ('post190_called','game_update_called',
                'context_destroyed','full_exe_load_lifecycle_reproduced','reset_validated','continuation_validated','eligible_for_training'))):
        raise ValueError('Post160 lacks the complete same-transcript bounded native return')
    before, after = returned['jobs_before'], returned['jobs_after']
    require_quiescent(before); require_quiescent(after)
    if core_sha256 is not None:
        for snapshot in (before,after):saved_load_validate_engine(snapshot,core_sha256)
    loaded_jobs = raw_result['raw_load_receipt']['jobs_structural_candidate']
    if (before.get('core_identity') != loaded_jobs.get('core_identity')
            or before.get('source_build') != loaded_jobs.get('source_build')
            or before != after or any(_ledger_event(row)[0] != 'noop' for row in interval['jobs'])):
        raise ValueError('Post160 scheduler interval is not an unchanged quiescent sequence')
    readback, loaded = result['readback'], raw_result['readback']
    expected = dict(current_game_turn=loaded['turn'],width=loaded['width'],height=loaded['height'],
        major_player_ids=list(range(2 if xp2 else 6)),scope='privileged diagnostic; no learner observation',game_update_called=False)
    if readback != expected:
        raise ValueError('Post160 readback differs from the exact captured XP1 roster/map/turn')
    return dict(schema='civ6-host.'+('xp2' if xp2 else 'xp1')+'-post160-job-ledger-authenticated.v1',
        ledger_provenance_authenticated=True,first_line=interval['begin']['line'],
        last_line=interval['returned']['line'],interval_sha256=interval['interval_sha256'],
        interval_bytes=interval['interval_bytes'],stdout_sha256=interval['stdout_sha256'],
        stdout_lines=interval['stdout_lines'],job_export_record_count=len(interval['jobs']),
        jobs_unchanged=True,readback_unchanged=True,public_runtime_admitted=False,final_jobs=after)




def saved_load_result_file(run, event, name):
    if event is None:
        return None
    reference = event.get('receipt')
    path = Path(run)/name
    if (type(reference) is not dict or reference.get('path') != str(path)
            or reference.get('sha256') != digest(path.read_bytes())):
        raise ValueError('Saved Load result file differs from its worker receipt')
    return json.loads(path.read_bytes())


def saved_load_profile_capabilities(run, emit):
    """Opt-in instrumentation of two existing callbacks; no result substitution."""
    import cProfile
    import pstats
    from civ6_host.runtime.native.native_app_ownership import ClosedBaseOwnership
    original = ClosedBaseOwnership.status
    calls = 0
    def observed(owner, player, capability):
        nonlocal calls
        calls += 1
        sample = calls
        if sample not in (1, 10):
            return original(owner, player, capability)
        profile = cProfile.Profile()
        profile.enable()
        try:
            return original(owner, player, capability)
        finally:
            profile.disable()
            stats = pstats.Stats(profile)
            rows = [dict(file=key[0], line=key[1], function=key[2],
                         primitive_calls=value[0], calls=value[1],
                         total_seconds=value[2], cumulative_seconds=value[3])
                    for key, value in stats.stats.items()]
            rows.sort(key=lambda row: row['cumulative_seconds'], reverse=True)
            receipt = write_once(run/f'capability-profile-{sample}.json',
                dict(schema='civ6-host.xp1-capability-profile.v1', sample=sample,
                     total_seconds=stats.total_tt, rows=rows[:30],
                     diagnostic_instrumentation=True, production_throughput=False))
            emit('xp1_capability_profile', sample=sample, receipt=receipt)
    ClosedBaseOwnership.status = observed


def saved_load_worker(closure_path):
    """Qualify the shared saved owner; later phases require explicit requests."""
    from civ6_host.runtime.native.native_probe import Windows
    from civ6_host.runtime.native.native_checkpoint_stream import terminate_worker
    win = Windows()
    win.kernel.SetErrorMode(1 | 2 | 32768)
    if sys.stdin.buffer.readline(16) != b'go\n':
        terminate_worker(89)
    import time
    telemetry_started = time.perf_counter()
    telemetry_last = telemetry_started
    def emit(stage, **fields):
        nonlocal telemetry_last
        raw = json.dumps(dict(stage=stage, **fields), allow_nan=False, separators=(',', ':'))
        if len(raw.encode('utf-8')) + 1 > 1024*1024:
            raise ValueError('Saved Load event exceeds the shared line bound')
        now = time.perf_counter()
        if now - telemetry_last >= 1:
            print(json.dumps(dict(stage='xp1_saved_load_progress', native_stage=stage,
                                  worker_elapsed_seconds=now-telemetry_started),
                             separators=(',', ':')), flush=True)
            telemetry_last = now
        print(raw, flush=True)
    close_attempted = False
    close_result = None
    try:
        raw = Path(closure_path).read_bytes()
        if digest(raw) != os.environ.get(SAVED_LOAD_CLOSURE_ENV):
            raise ValueError('Saved Load private closure changed')
        closure = json.loads(raw)
        run = Path(closure_path).resolve().parent
        if not run.is_relative_to((resource_root()/'work').resolve()):
            raise ValueError('Saved Load output escaped private work')
        if (closure.get('schema') != 'civ6-host.xp1-saved-load-candidate.v1'
                or closure.get('input_profile') != 'xp1-lan'
                or closure.get('raw_only_candidate') is not True
                or type(closure.get('post160_candidate', False)) is not bool
                or type(closure.get('publish_cache_candidate', False)) is not bool
                or type(closure.get('close_loaded_candidate', False)) is not bool
                or type(closure.get('observe_player_candidate', False)) is not bool
                or type(closure.get('unit_commands_candidate', False)) is not bool
                or (closure.get('unit_commands_candidate', False)
                    and closure.get('observe_player_candidate') is not True)
                or (closure.get('observe_player_candidate', False)
                    and not(closure.get('publish_cache_candidate') is True and closure.get('close_loaded_candidate') is True))
                or ((closure.get('publish_cache_candidate', False) or closure.get('close_loaded_candidate', False))
                    and closure.get('post160_candidate') is not True)
                or type(closure.get('lifetime_seconds')) is not int
                or closure['lifetime_seconds'] not in (45, 60, 120)
                or closure.get('stdout_limit_bytes') != 64*1024*1024):
            raise ValueError('Unknown saved Load candidate closure')
        image_options = {}
        if 'execution_image' in closure:
            from civ6_host.runtime.execution_images import from_identity
            image_options = dict(execution_image=from_identity(closure['execution_image']),
                                 official_bundle=closure['official_bundle'])
        verify_installation(**({'audit_historical': False} if image_options else {}))
        for name, expected in closure['pins'].items():
            saved_load_pin({}, name, expected)
        if digest(Path(__file__).read_bytes()) != os.environ.get(PIN_ENV):
            raise ValueError('Saved Load qualifier changed')
        host = saved_load_build_pins({}, ui=closure.get('observe_player_candidate', False),
                                    **image_options)
        if Path(sys.executable).resolve() != host:
            raise ValueError('Saved Load requires its exact XP1 jobs executable')
        from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
        if os.environ.get('CIV6_HOST_PROFILE_XP1_CAPABILITY') == '1':
            saved_load_profile_capabilities(run, emit)
        saved = SavedLoadOwner.open(closure, emit, win)
        raw_result = saved.raw_result
        emit('xp1_saved_raw_load_observed', receipt=write_once(run/'raw-load-result.json', raw_result))
        cache_result = saved.populate_caches()
        emit('xp1_saved_cache_observed', receipt=write_once(run/'cache-result.json', cache_result))
        post_requested = closure.get('post160_candidate', False)
        if post_requested:
            emit('before_xp1_saved_post160_sequence', public_runtime_admitted=False)
            post_result = saved.postload()
            emit('xp1_saved_post160_sequence_returned',
                 receipt=write_once(run/'post160-result.json', post_result))
        publication = None
        publication_requested = closure.get('publish_cache_candidate', False)
        if publication_requested:
            emit('before_xp1_saved_cache_publication', public_runtime_admitted=False)
            publication_result = saved.publish()
            publication = saved.publication
            emit('xp1_saved_cache_publication_returned',
                 receipt=write_once(run/'publication-result.json', publication_result))
        close_requested = closure.get('close_loaded_candidate', False)
        if closure.get('observe_player_candidate', False):
            emit('before_xp1_saved_player_view', public_runtime_admitted=False)
            view_result = saved.observe_initial()
            emit('xp1_saved_player_view_returned',
                 receipt=write_once(run/'player-view-result.json',view_result))
        continuation = None
        if closure.get('unit_commands_candidate', False):
            emit('before_xp1_saved_unit_commands', public_runtime_admitted=False)
            continuation = saved.begin_commands()
            command_result = saved.execute(closure['unit_command'])
            emit('xp1_saved_unit_commands_returned',
                 receipt=write_once(run/'unit-commands-result.json', command_result))
        if close_requested:
            close_attempted = True
            emit('before_xp1_saved_loaded_close', completed_phase='unit_commands' if continuation is not None else 'publication' if publication is not None else 'post160',
                 public_runtime_admitted=False)
            close_result = saved.close()
            emit('xp1_saved_loaded_close_returned',
                 receipt=write_once(run/'loaded-lifetime-result.json', close_result))
        emit('xp1_saved_load_controlled_stop', normal_destroy_called=close_result is not None,
             post160_called=post_requested, publication_called=publication_requested,
             public_runtime_admitted=False, owners_retained=close_result is None)
        terminate_worker(90)
    except BaseException as exc:
        emit('xp1_saved_load_refused', error=repr(exc), cleanup_guessed=False,
             normal_destroy_called=None if close_attempted else False, public_runtime_admitted=False)
        terminate_worker(89)


def saved_load_supervisor(run, pins, closure_path, executable, environment, prepared_session, *, lifetime_seconds=45):
    """Reuse NativeSavedSession's bounded readers/watch/reaper, without reset()."""
    import threading
    import time
    from civ6_host.runtime.native.native_saved_session import MEMORY_LIMIT, MAX_STDERR
    if type(lifetime_seconds) is not int or lifetime_seconds not in (45, 60, 120):
        raise ValueError('Saved Load requires an explicit 45s, 60s or 120s bounded diagnostic')
    session = prepared_session
    session.run, session.pins = run, pins
    session.process = session.job = session.protocol = session.last = None
    session.error = session.stop_reason = None
    session.peak, session.samples = {}, 0
    session.close_context = 'xp1_saved_load_candidate_os_stop'
    session.stdout_native_records = []
    session.done, session.error_lock = threading.Event(), threading.Lock()
    session.threads, session.finished = [], False
    session.lifetime_seconds, session.stdout_limit_bytes = lifetime_seconds, 64*1024*1024
    session.command_log = (run/'commands.jsonl').open('xb')
    session.started = time.perf_counter()
    try:
        session._check_reset_resources('before_spawn')
        session.process = subprocess.Popen(
            [str(executable), '-B', str(Path(__file__).resolve()), '--stage', 'saved_load',
             '--saved-load-worker', str(closure_path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=REPO, env=environment,
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
        session.job = session.win.job(session.process, MEMORY_LIMIT)
        for target, args in (
                (session._read_stream, (session.process.stdout, 'events.jsonl', session.stdout_limit_bytes, False)),
                (session._read_stream, (session.process.stderr, 'stderr.txt', MAX_STDERR, False)),
                (session._watch, ())):
            thread = threading.Thread(target=target, args=args, daemon=True)
            session.threads.append(thread)
            thread.start()
        session._send(b'go\n')
        session.process.wait(timeout=lifetime_seconds+1)
    except BaseException as exc:
        session._fail('saved_load_supervision_failed', repr(exc))
    finally:
        session.reset_timings_seconds['reset_total_seconds'] = time.perf_counter()-session.reset_started
        session._finish()
    return session.report


def saved_load_main(argv):
    import argparse
    import threading
    import time
    import uuid
    if len(argv) == 2 and argv[0] == '--saved-load-worker':
        return saved_load_worker(argv[1])
    if argv and argv[0] == '--review-run':
        parser = argparse.ArgumentParser(description='Review retained saved Load without native execution')
        parser.add_argument('--review-run', required=True)
        parser.add_argument('--qualification-sha', required=True)
        parser.add_argument('--closure-sha', required=True)
        parser.add_argument('--sources-archive', required=True)
        return review_retained_saved_load(parser.parse_args(argv))
    parser = argparse.ArgumentParser(description='Bounded candidate XP1 raw Load and populated caches')
    parser.add_argument('--prepared-capture', required=True)
    parser.add_argument('--prepared-sha', required=True)
    parser.add_argument('--current-xp1', action='store_true',
                        help='Use the registered installed XP1 image for the private saved-game boundary')
    parser.add_argument('--postload160', action='store_true',
                        help='Continue the same loaded candidate through the existing native postload sequence')
    parser.add_argument('--publish-cache', action='store_true',
                        help='Refresh the completed loaded XP1 cache with the shared native publisher')
    parser.add_argument('--close-loaded', action='store_true',
                        help='Release owned wrappers, unload and destroy this candidate through native lifetime')
    parser.add_argument('--observe-player', action='store_true',
                        help='Read the shared player observation from a separate official XP1 UI child')
    parser.add_argument('--unit-command', type=json.loads,
                        help='One explicit candidate unit command as JSON; no automatic action selection')
    parser.add_argument('--lifetime-seconds', type=int, choices=(45, 60, 120), default=45,
                        help='Diagnostic worker bound; larger values isolate measured startup/Load duration, not production throughput')
    args = parser.parse_args(argv)
    if args.current_xp1 and args.unit_command is not None:
        parser.error('--current-xp1 currently supports the private saved-game view and teardown')
    if (args.publish_cache or args.close_loaded) and not args.postload160:
        parser.error('--publish-cache and --close-loaded require --postload160')
    if args.observe_player and not(args.publish_cache and args.close_loaded):
        parser.error('--observe-player requires --publish-cache and --close-loaded')
    if args.unit_command is not None and not args.observe_player:
        parser.error('--unit-command requires --observe-player')
    if args.unit_command is not None:
        from civ6_host.runtime.xp1_continuation import validate_unit_command
        validate_unit_command(args.unit_command)
    from civ6_host.runtime import xp1_saved_load
    from civ6_host.runtime.native.native_probe import Windows, prepare_init_fixture_copies
    from civ6_host.runtime.native.native_saved_session import NativeSavedSession
    from civ6_host.runtime.native.native_official_bundle import DATABASE_PROFILE, LOCALIZATION_HANDOFF_ENV
    from civ6_host.runtime.capture_admission import ENV as PREPARED_ENV, configure_prepared_closure
    from civ6_host.runtime.resource_resolution import configure_closure
    verify_installation(**({'audit_historical': False} if args.current_xp1 else {}))
    # Only reuse the shared resource/containment methods; reset() is Base-only.
    session = object.__new__(NativeSavedSession)
    session.owner_thread, session.win = threading.get_ident(), Windows()
    session.reset_started = time.perf_counter()
    session.reset_timings_seconds, session.reset_resource_samples = {}, []
    session._check_reset_resources('before_preflight')
    package = dict(path=str(Path(args.prepared_capture).resolve()), sha256=args.prepared_sha)
    if args.current_xp1:
        from civ6_host.runtime.capture_candidates import consume_input_handoff
        from civ6_host.runtime.execution_images import _XP1_PROFILE
        captured = consume_input_handoff('xp1-lan', package,
            official_bundle=xp1_saved_load.REFERENCE, execution_image=_XP1_PROFILE)
    else:
        captured = xp1_saved_load.consume_input_handoff(package)
    run = (resource_root()/'work/xp1-configuration/saved-load'/('run-'+uuid.uuid4().hex)).resolve()
    run.mkdir(parents=True, exist_ok=False)
    from civ6_host.runtime.xp1_session_inputs import prepare_sources, prepare_private_fixture
    pins, executable = prepare_sources(captured, package, postload160=args.postload160,
        publish_cache=args.publish_cache, close_loaded=args.close_loaded,
        observe_player=args.observe_player, unit_commands=args.unit_command is not None)
    saved_load_pin(pins, Path(__file__))
    session._check_reset_resources('after_preflight')
    fixture, isolation = prepare_private_fixture(run, captured, pins)
    closure = dict(schema='civ6-host.xp1-saved-load-candidate.v1', pins=pins,
                   fixture=str(fixture), fixture_isolation=isolation,
                   input_profile='xp1-lan', database_profile=DATABASE_PROFILE,
                   official_bundle=dict(path=captured.reference[0], sha256=captured.reference[1]),
                   initial_turn=captured.initial_turn, prepared_capture=package,
                   raw_only_candidate=True, post160_candidate=args.postload160,
                   publish_cache_candidate=args.publish_cache, close_loaded_candidate=args.close_loaded,
                   observe_player_candidate=args.observe_player,
                   unit_commands_candidate=args.unit_command is not None, unit_command=args.unit_command,
                   lifetime_seconds=args.lifetime_seconds, stdout_limit_bytes=64*1024*1024)
    if args.current_xp1:
        configure_prepared_closure(closure, captured)
    configure_closure(closure)
    closure_path = run/'closure.json'
    closure_receipt = write_once(closure_path, closure)
    # Pin the closure after serialization, outside its own recursive pin map.
    supervisor_pins = dict(pins)
    saved_load_pin(supervisor_pins, closure_path, closure_receipt['sha256'])
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.pop(LOCALIZATION_HANDOFF_ENV, None)
    env.update(PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1', CIV6RL_PYTHON_HOME=sys.base_prefix)
    env.update({PREPARED_ENV:json.dumps(package, sort_keys=True),
                PIN_ENV:digest(Path(__file__).read_bytes()),
                SAVED_LOAD_CLOSURE_ENV:closure_receipt['sha256']})
    env['PATH'] = sys.base_prefix+os.pathsep+env.get('PATH', '')
    report = saved_load_supervisor(run, supervisor_pins, closure_path, executable, env, session,
                                   lifetime_seconds=args.lifetime_seconds)
    result, success = evaluate_saved_load(run, report, supervisor_pins, args)
    result['receipt'] = write_once(run/'saved-load-qualification.json', result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if success else 2


def evaluate_saved_load(run, report, supervisor_pins, args):
    """Shared parent evaluator for a just-finished or retained native run."""
    raw_result = cache_result = ledger_receipt = None
    post_result = post_ledger = None
    post_error = None
    ledger_error = None
    parse_error = None
    event_count = 0
    events = {}
    try:
        event_count, events = saved_load_events(run/'events.jsonl')
        raw_result = saved_load_result_file(run, events.get('xp1_saved_raw_load_observed'), 'raw-load-result.json')
        cache_result = saved_load_result_file(run, events.get('xp1_saved_cache_observed'), 'cache-result.json')
        _, interval_events = saved_load_events(run/'events.jsonl', require_load_interval=True)
        events['load_job_interval'] = interval_events['load_job_interval']
    except (OSError, ValueError) as exc:
        parse_error = repr(exc)
    if parse_error is None and raw_result is not None:
        try:
            ledger_receipt = saved_load_reconcile_jobs(report, supervisor_pins, raw_result, events['load_job_interval'],
                                                      lifetime_seconds=args.lifetime_seconds)
        except (KeyError, TypeError, ValueError) as exc:
            ledger_error = repr(exc)
    if args.postload160:
        try:
            post_result = saved_load_result_file(run, events.get('xp1_saved_post160_sequence_returned'), 'post160-result.json')
            _, post_events = saved_load_events(run/'events.jsonl', require_post160_interval=True)
            if post_result is None or ledger_receipt is None:
                raise ValueError('Post160 lacks its completed receipt or authenticated prior Load')
            post_ledger = saved_load_reconcile_post160(report, supervisor_pins, raw_result, post_result,
                post_events, ledger_receipt, lifetime_seconds=args.lifetime_seconds)
        except (KeyError, OSError, TypeError, ValueError) as exc:
            post_error = repr(exc)
    continuation = {}
    previous_ledger = post_ledger
    for phase, requested, marker, filename in (
            ('publication', args.publish_cache, 'xp1_saved_cache_publication_returned', 'publication-result.json'),
            ('player_view', args.observe_player, 'xp1_saved_player_view_returned', 'player-view-result.json'),
            ('unit_commands', args.unit_command is not None, 'xp1_saved_unit_commands_returned', 'unit-commands-result.json'),
            ('lifetime', args.close_loaded, 'xp1_saved_loaded_close_returned', 'loaded-lifetime-result.json')):
        row = dict(requested=requested, result=None, ledger=None, error=None)
        continuation[phase] = row
        if not requested:
            continue
        try:
            row['result'] = saved_load_result_file(run, events.get(marker), filename)
            _, phase_events = saved_load_events(run/'events.jsonl', require_interval=phase)
            if row['result'] is None or previous_ledger is None:
                raise ValueError('Continuation lacks its own result or authenticated prior phase')
            row['ledger'] = saved_load_reconcile_later(report, supervisor_pins, raw_result, row['result'],
                phase_events, previous_ledger, phase=phase, lifetime_seconds=args.lifetime_seconds)
        except (KeyError, OSError, TypeError, ValueError) as exc:
            row['error'] = repr(exc)
        previous_ledger = row['ledger']
    close_evidence = continuation['lifetime']
    normal_destroy_called = (True if close_evidence['ledger'] is not None else
                             None if 'before_xp1_saved_loaded_close' in events else False)
    success = (report['exit_code'] == 90 and report['reaped'] and report['job_assigned']
               and report['error'] is None and all(report['source_unchanged'].values())
               and parse_error is None and ledger_receipt is not None
               and ledger_error is None and 'xp1_saved_load_controlled_stop' in events
               and 'xp1_saved_load_refused' not in events and raw_result is not None
               and cache_result is not None and cache_result.get('cache_facades_populated') is True
               and (not args.postload160 or (post_ledger is not None and post_error is None))
               and all(not row['requested'] or (row['ledger'] is not None and row['error'] is None)
                       for row in continuation.values()))
    success_status = ('candidate_loaded_unit_command_and_lifetime_observed' if args.unit_command is not None
                      else 'candidate_loaded_player_view_and_lifetime_observed' if args.observe_player
                      else 'candidate_loaded_cache_publication_and_lifetime_observed' if args.close_loaded and args.publish_cache
                      else 'candidate_loaded_post160_and_lifetime_observed' if args.close_loaded
                      else 'candidate_loaded_cache_publication_observed' if args.publish_cache
                      else 'candidate_raw_load_cache_and_post160_observed' if args.postload160
                      else 'candidate_raw_load_and_cache_observed')
    result = dict(stage='saved_load', status=success_status if success else 'failed_or_incomplete',
                  callback_profiling=os.environ.get('CIV6_HOST_PROFILE_XP1_CAPABILITY') == '1',
                  run_directory=str(run), saved_game_loaded=raw_result is not None and ledger_receipt is not None,
                  raw_load_observed=raw_result is not None,
                  native_failure=events.get('xp1_saved_load_refused') or events.get('unsupported_host_contract'),
                  raw_load=raw_result, cache_publication=cache_result,
                  post160_requested=args.postload160, post160=post_result,
                  post160_job_ledger=post_ledger, post160_error=post_error,
                  continuation=continuation,
                  load_job_ledger=ledger_receipt, load_job_ledger_error=ledger_error,
                  supervisor=report, stdout_event_count=event_count, stdout_parse_error=parse_error,
                  prepared_service_group_reused_as_load_evidence=False,
                  public_runtime_admitted=False,
                  post160_called=(True if 'native_checkpoint_postload_160_returned' in events else
                                  None if 'before_xp1_saved_post160_sequence' in events else False),
                  normal_destroy_called=normal_destroy_called,
                  normal_destroy_basis='authenticated native lifetime receipt; supervisor reports generic process reaping only',
                  strategic_training_ready=False)
    return result, success


def review_retained_saved_load(args):
    """Review a parent-only failure without rerunning or reinterpreting runtime code."""
    import zipfile
    run = Path(args.review_run).resolve()
    if not run.is_relative_to((resource_root()/'work').resolve()):
        raise ValueError('Retained saved Load is outside private work resources')
    original_bytes = (run/'saved-load-qualification.json').read_bytes()
    closure_bytes = (run/'closure.json').read_bytes()
    if digest(original_bytes) != args.qualification_sha or digest(closure_bytes) != args.closure_sha:
        raise ValueError('Retained qualification or closure differs from explicit input digests')
    original, closure = json.loads(original_bytes), json.loads(closure_bytes)
    report = json.loads((run/'supervisor.json').read_bytes())
    if (report != original['supervisor'] or original['status'] != 'failed_or_incomplete'
            or original['native_failure'] is not None or original['stdout_parse_error'] is not None
            or report['exit_code'] != 90 or original['run_directory'] != str(run)):
        raise ValueError('Retained failure is not a completed native run with a parent-only refusal')
    pins = dict(closure['pins'])
    pins[str(run/'closure.json')] = args.closure_sha
    tool = str(Path(__file__).resolve())
    changed = [path for path, sha in pins.items() if digest(Path(path).read_bytes()) != sha]
    if changed != [tool]:
        raise ValueError('Retained runtime/source closure changed beyond the parent qualifier')
    archive = Path(args.sources_archive).resolve()
    with zipfile.ZipFile(archive) as stored:
        executed = stored.read('tools/qualify_xp1_configuration.py')
    if digest(executed) != pins[tool]:
        raise ValueError('Archived executed qualifier differs from the native source closure')
    def nodes(source):
        tree = ast.parse(source)
        return [(getattr(node, 'name', None), ast.dump(node, include_attributes=False)) for node in tree.body]
    allowed = {'saved_load_reconcile_later', 'saved_load_reconcile_post160', 'saved_load_main',
               'evaluate_saved_load', 'review_retained_saved_load'}
    old, new = nodes(executed), nodes(Path(tool).read_bytes())
    if [row for row in old if row[0] not in allowed] != [row for row in new if row[0] not in allowed]:
        raise ValueError('Qualifier changed outside the reviewed parent-only functions')
    # Authenticate the same stdout before running the shared evaluator. The
    # retained Load ledger remains an immutable anchor, not a rewritten report.
    stdout_sha = digest((run/'events.jsonl').read_bytes())
    if stdout_sha != original['load_job_ledger']['stdout_sha256']:
        raise ValueError('Retained native transcript changed')
    options = SimpleNamespace(postload160=closure['post160_candidate'],
        publish_cache=closure['publish_cache_candidate'], observe_player=closure['observe_player_candidate'],
        unit_command=closure['unit_command'], close_loaded=closure['close_loaded_candidate'],
        lifetime_seconds=closure['lifetime_seconds'])
    result, success = evaluate_saved_load(run, report, pins, options)
    result['callback_profiling'] = original['callback_profiling']
    if not success:
        errors = {name: row['error'] for name, row in result['continuation'].items() if row['error']}
        raise ValueError('Retained evaluation remains incomplete: '+repr(errors))
    result['review'] = dict(classification='retained_execution_revalidated_after_parent_only_refusal',
        new_native_execution=False, original_qualification_sha256=args.qualification_sha,
        closure_sha256=args.closure_sha, stdout_sha256=stdout_sha,
        executed_qualifier_sha256=pins[tool], review_qualifier_sha256=digest(Path(tool).read_bytes()),
        executed_sources_archive=dict(path=str(archive), sha256=digest(archive.read_bytes())),
        changed_parent_functions=sorted(allowed), unchanged_native_source_pin_count=len(pins)-1,
        original_failure_preserved=True)
    result['receipt'] = write_once(run/'saved-load-qualification-reviewed.json', result)
    print(json.dumps(dict(status=result['status'], review=result['review'], receipt=result['receipt']), ensure_ascii=False))
    return 0


def review_retained_xp2_configuration(run_dir, supervisor_sha):
    """Apply new engine source proof to immutable old output, without a rerun."""
    from civ6_host.runtime.configuration_roundtrip import compare_provider_roundtrip
    from civ6_host.runtime.xp2_bundle_inputs import CONFIGURATION_SHA256, REFERENCE
    from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256
    from civ6_host.runtime.xp2_normalization_source import SOURCE
    parent = dict(path=str(resource_root()/'evidence/host-xp2-configuration-lifecycle.json'),
                  sha256='9a7c6cc386be4af81e2eaf5350898b06513d8cb22202d0443d230dcdadf397de')

    def pinned(reference):
        path = Path(reference['path'])
        if not path.is_file() or not 0 < path.stat().st_size <= 8*1024**2:
            raise ValueError('Retained XP2 review input is missing or oversized')
        raw = path.read_bytes()
        if digest(raw) != reference['sha256']:
            raise ValueError('Retained XP2 review input changed: ' + str(path))
        return raw

    verify_installation()
    evidence = json.loads(pinned(parent))
    native = evidence['native_xp2']
    run = Path(run_dir).resolve()
    if (Path(native['supervisor']['path']).parent.resolve() != run
            or native['supervisor']['sha256'] != supervisor_sha):
        raise ValueError('Review requires the exact retained XP2 native lifetime')
    supervisor = json.loads(pinned(native['supervisor']))
    group = json.loads(pinned(native['group']))
    for key in ('source_pins', 'source_archive', 'stdout'):
        pinned(native[key])
    if (supervisor['status'] != 'passed' or supervisor['exit_code'] != 0
            or supervisor['process_reaped'] is not True
            or supervisor['job_contained'] is not True
            or group['status'] != 'native_xp2_captured_initialization_and_destroy_passed'
            or group['core_sha256'] != XP2_CORE_SHA256
            or tuple(group['origin']) != REFERENCE
            or group['context_destroyed'] is not True
            or group['saved_game_loaded'] is not False):
        raise ValueError('Retained XP2 Init lifetime is not a completed witness')
    output = pinned(evidence['provider_comparison']['output'])
    input_path = REPO/'work/xp2-bundle-inputs/configuration.bin'
    input_ref = dict(path=str(input_path), sha256=CONFIGURATION_SHA256)
    before = pinned(input_ref)
    if (group['configuration_input_sha256'] != CONFIGURATION_SHA256
            or group['configuration_output_sha256'] != digest(output)
            or group['configuration_output_bytes'] != len(output)):
        raise ValueError('Retained provider streams differ from the native lifetime')
    comparison = compare_provider_roundtrip(before, output, core_sha256=XP2_CORE_SHA256)
    result = dict(schema='civ6-host.xp2-provider-equivalence-review.v1',
        status='retained_native_xp2_provider_representation_equivalence_qualified',
        previous_lifecycle_evidence=parent, historical_native=native,
        source_proof=dict(path=str(resource_root()/SOURCE[0]), sha256=SOURCE[1]),
        comparison=comparison, input=input_ref, output=evidence['provider_comparison']['output'],
        review_sources={str(path):digest(path.read_bytes()) for path in (
            Path(__file__), REPO/'src/civ6_host/runtime/configuration_roundtrip.py',
            REPO/'src/civ6_host/runtime/xp2_normalization_source.py',
            REPO/'src/civ6_host/runtime/native/official_configuration.py')},
        new_native_execution=False, producer_sources_substituted=False,
        saved_game_loaded=False, strategic_training_ready=False)
    result['receipt'] = write_once(run/'configuration-equivalence-review.json', result)
    print(json.dumps(dict(status=result['status'], comparison=comparison,
                          receipt=result['receipt'])), flush=True)
    return 0


from civ6_host.runtime.xp2_session_inputs import xp2_saved_load_source_dependencies


def evaluate_xp2_saved_load(run,sources,report):
    """Review a stopped raw Load/close worker; never promote failed execution."""
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
    from civ6_host.runtime.saved_load_job_observer import require_quiescent, XP2_SOURCE, XP2_HOST_COMPONENT_SHA
    from civ6_host.runtime.job_registry_snapshot import validate_empty_transition_data
    review=dict(schema='civ6-host.xp2-raw-load-close-review.v1',passed=False,
        status='refused',source_unchanged={},errors=[],reconciliations={},receipts={},
        phases={'load':'absent','lifetime':'absent'},public_session_admitted=False,
        postload_completed=False,strategic_training_ready=False,native_calls_during_review=False)
    run=Path(run).resolve();pins={}
    try:
        postload=sources.get('postload160',False);observe_player=sources.get('observe_player',False)
        if (type(postload) is not bool or type(observe_player) is not bool
                or observe_player and not postload):raise ValueError('Exact XP2 postload/observation request required')
        if observe_player:review['phases']['player_view']='absent'
        duration=180 if observe_player else 120
        if (sources.get('wall_limit_seconds',120)!=duration
                or sources.get('memory_limit_bytes',768*1024**2)!=768*1024**2):
            raise ValueError('XP2 executed bounds differ from the exact requested scope')
        if (type(sources) is not dict or sources.get('saved_load') is not True
                or not sources.get('runtime') or not sources.get('dependencies')):
            raise ValueError('XP2 review lacks its selected executed source closure')
        for mapping in (sources['runtime'],sources['dependencies'],
                {str(Path(__file__).resolve()):sources['qualifier']},
                {sources[k]['path']:sources[k]['sha256'] for k in ('native_host','native_build')}):
            for name,expected in mapping.items():
                path=Path(name)
                if not path.is_absolute() or (str(path) in pins and pins[str(path)]!=expected):
                    raise ValueError('Ambiguous executed source pin')
                pins[str(path)]=expected
        for name,expected in pins.items():
            try:review['source_unchanged'][name]=digest(Path(name).read_bytes())==expected
            except OSError:review['source_unchanged'][name]=False
        if any(value is not True for value in review['source_unchanged'].values()):
            raise ValueError('Executed sources changed after worker shutdown')
        if sources['dependencies']!=xp2_saved_load_source_dependencies(postload160=postload,observe_player=observe_player):
            raise ValueError('Executed dependency set differs from the selected XP2 source graph')
        if observe_player and sources['native_host']['sha256']!=XP2_UI_HOST[1]:
            raise ValueError('XP2 player observation lacks its exact UI host')
        if json.loads((run/'executed-source-pins.json').read_bytes())!=sources:
            raise ValueError('Recorded executed source closure differs')
        if digest((run/'executed-sources.zip').read_bytes())!=report.get('source_archive_sha256'):
            raise ValueError('Executed source archive changed')
        review['sources_authenticated_after_process']=report.get('process_reaped') is True
        supervised=dict(report,source_unchanged=review['source_unchanged'])
        saved_load_validate_supervision(supervised,pins,lifetime_seconds=duration,xp2_raw=True)
        count,events=saved_load_events(run/'stdout.jsonl',require_load_interval=True,
                                     stdout_limit_bytes=64*1024*1024)
        review['stdout_lines']=count
        raw=json.loads((run/'raw-load-result.json').read_bytes())
        lifetime=json.loads((run/'loaded-lifetime-result.json').read_bytes())
        group=json.loads((run/'xp2-saved-load-group.json').read_bytes())
        for name in ('raw-load-result.json','loaded-lifetime-result.json','xp2-saved-load-group.json'):
            path=run/name;review['receipts'][name]=dict(path=str(path),sha256=digest(path.read_bytes()))
        if report.get('completion_receipt')!=review['receipts']['xp2-saved-load-group.json']:
            raise ValueError('Supervisor completion reference differs')
        receipt=raw['receipt'];interval=events['load_job_interval']
        returned=interval['returned']['event'];before,after=returned['jobs_before'],returned['jobs_after']
        require_quiescent(before);require_quiescent(after)
        for key in ('core_identity','source_build','current_executable','host_sha256','owner_thread_id'):
            if before.get(key)!=after.get(key):raise ValueError('Load scheduler identity changed: '+key)
        core=after['core_identity'];build=after['source_build']
        if (core.get('profile')!=3 or core.get('sha256')!=XP2_CORE_SHA256
                or core.get('source_sha256')!=XP2_SOURCE[1]
                or core.get('host_component_sha')!=XP2_HOST_COMPONENT_SHA
                or build.get('host_sha256')!=sources['native_host']['sha256']
                or after['host_sha256']!=sources['native_host']['sha256']):
            raise ValueError('Scheduler snapshots are not this exact XP2 Core/host')
        candidate=dict(validate_empty_transition_data(before,after),
            schema='civ6_host.saved_load_empty_jobs_transition.v1',source_proof_sha256=XP2_SOURCE[1],
            source_build=build,core_identity=core,source_host_component_sha256=XP2_HOST_COMPONENT_SHA)
        if (receipt.get('jobs_structural_candidate')!=candidate
                or receipt.get('game_initialized')!=1 or type(receipt.get('game_initialized')) is not int
                or receipt.get('scheduler_ledger_reconciliation_pending') is not True
                or receipt.get('jobs_identical') is not (before==after)):
            raise ValueError('Raw Load receipt differs from its actual scheduler snapshots')
        observed=events.get('official_gamecore_load_observed',{})
        readback=observed.get('readback',{})
        comparison=readback.get('comparison',{})
        if (observed.get('result')!=receipt or readback.get('observed')!=raw.get('readback')
                or comparison.get('matched') is not True or comparison.get('compared')!=raw.get('readback')
                or readback.get('privileged_diagnostic') is not True or readback.get('learner_observation') is not False
                or readback.get('major_player_ids')!=[0,1] or readback.get('human_player_ids')!=[0]
                or readback.get('human_status_native_verified') is not True
                or raw.get('roster')!='1|44|26|0|1' or group.get('roster')!=raw['roster']
                or group.get('readback')!=raw.get('readback') or group.get('core_sha256')!=XP2_CORE_SHA256
                or any(group.get(k) is not True for k in ('game_load_called','saved_game_loaded','context_destroyed'))
                or raw.get('postload_completed') is not False
                or group.get('postload_completed') is not postload
                or group.get('player_observed',False) is not observe_player
                or any(value.get(k) is not False for value in (raw,group)
                       for k in ('public_session_admitted','strategic_training_ready'))):
            raise ValueError('Raw Load readback/roster/completion receipts disagree')
        review['reconciliations']['load']=saved_load_reconcile_jobs(supervised,pins,
            {'raw_load_receipt':receipt},interval,lifetime_seconds=duration,xp2_raw=True)
        review['phases']['load']='authenticated'
        if postload:
            review_xp2_postload_phases(run,supervised,pins,raw,group,review,observe_player=observe_player)
            return review
        _,close_events=saved_load_events(run/'stdout.jsonl',require_interval='xp2_raw_lifetime',
                                        stdout_limit_bytes=64*1024*1024)
        close_interval=close_events['xp2_raw_lifetime_job_interval'];lines=close_events['_event_lines']
        if (interval['stdout_sha256']!=close_interval['stdout_sha256']
                or not interval['returned']['line']<lines.get('official_gamecore_load_observed',0)<close_interval['begin']['line']
                or close_interval['begin']['event'].get('game_load_called') is not True
                or close_interval['returned']['event'].get('status')!=group.get('status')
                or group.get('status')!='native_xp2_captured_raw_load_readback_and_close_passed'):
            raise ValueError('Raw Load/close markers do not form one ordered transcript')
        closed=saved_load_validate_lifetime(lifetime,close_interval,after,close_events,xp2_raw=True)
        review['reconciliations']['lifetime']=dict(closed,
            stdout_sha256=close_interval['stdout_sha256'],interval_sha256=close_interval['interval_sha256'],
            first_line=close_interval['begin']['line'],last_line=close_interval['returned']['line'],
            job_export_record_count=len(close_interval['jobs']))
        review['phases']['lifetime']='authenticated'
        review.update(passed=True,status='authenticated_raw_load_readback_and_close')
    except (OSError,ValueError,KeyError,TypeError,RuntimeError) as exc:
        review['errors'].append(str(exc))
        for name,filename in (('load','raw-load-result.json'),('lifetime','loaded-lifetime-result.json'),('player_view','player-view-result.json')):
            if name not in review['phases']:continue
            if review['phases'][name]=='absent' and (run/filename).is_file():review['phases'][name]='refused'
    return review


def review_xp2_postload_phases(run,supervised,pins,raw,group,review,*,observe_player=False):
    """Join the existing stage receipts/ledgers on the same XP2 transcript."""
    if type(observe_player) is not bool:raise ValueError('Exact XP2 observation scope required')
    status=('native_xp2_captured_player_observation_and_close_passed' if observe_player
            else 'native_xp2_captured_postload_publication_and_close_passed')
    if group.get('status')!=status or group.get('player_observed',False) is not observe_player:
        raise ValueError('XP2 postload group lacks its exact completion marker')
    raw_shared=dict(raw_load_receipt=raw['receipt'],readback=raw['readback'])
    previous=review['reconciliations']['load']
    duration=180 if observe_player else 120
    markers={'post160':'xp1_saved_post160_sequence_returned',
             'publication':'xp1_saved_cache_publication_returned',
             'player_view':'xp1_saved_player_view_returned',
             'lifetime':'xp1_saved_loaded_close_returned'}
    filenames={'post160':'post160-result.json','publication':'publication-result.json',
               'player_view':'player-view-result.json','lifetime':'loaded-lifetime-result.json'}
    for phase in ('post160','publication',*(('player_view',) if observe_player else ()), 'lifetime'):
        _,events=saved_load_events(run/'stdout.jsonl',require_interval=phase,stdout_limit_bytes=64*1024*1024)
        value=saved_load_result_file(run,events.get(markers[phase]),filenames[phase])
        if value is None:raise ValueError('Missing XP2 stage receipt: '+phase)
        if phase=='player_view':
            from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
            from civ6_host.runtime.xp2_ui_binding_source import SOURCE as UI_SOURCE,UI_THUNK_RVA
            interval=events['player_view_job_interval'];lines=events['_event_lines']
            before_binding=events.get('before_xp1_ui_api_bind',{})
            returned_binding=events.get('xp1_ui_api_bind_returned',{})
            if (not interval['begin']['line']<lines.get('before_xp1_ui_api_bind',0)
                    <lines.get('xp1_ui_api_bind_returned',0)<interval['returned']['line']
                    or before_binding.get('core_sha256')!=XP2_CORE_SHA256
                    or before_binding.get('source_sha256')!=UI_SOURCE[1]
                    or before_binding.get('method_rva')!=hex(UI_THUNK_RVA)
                    or before_binding.get('native_host_sha256')!=XP2_UI_HOST[1]
                    or returned_binding.get('native_host_sha256')!=XP2_UI_HOST[1]
                    or type(returned_binding.get('profile_id')) is not int
                    or returned_binding['profile_id']!=2
                    or {k:v for k,v in returned_binding.items() if k!='stage'}!=value.get('binding')):
                raise ValueError('XP2 UI binding lacks its ordered exact native receipt')
        if phase=='lifetime':
            if not observe_player and 'before_xp1_saved_player_view' in events:
                raise ValueError('Unrequested XP2 player observation reached the native transcript')
            if observe_player and events['lifetime_job_interval']['begin']['event'].get('completed_phase')!='player_view':
                raise ValueError('XP2 loaded close does not follow its requested player observation')
            if value.get('ui_child_released',False) is not observe_player:
                raise ValueError('XP2 lifetime does not close the requested native UI child')
        if phase=='post160':
            cache=saved_load_result_file(run,events.get('xp1_saved_cache_observed'),'cache-result.json')
            if (type(cache) is not dict or cache.get('candidate_native_cache_only') is not True
                    or cache.get('public_cache_gate_enabled') is not False):
                raise ValueError('XP2 cache receipt crossed its private native boundary')
            previous=saved_load_reconcile_post160(supervised,pins,raw_shared,value,events,previous,lifetime_seconds=duration,xp2=True)
        else:
            previous=saved_load_reconcile_later(supervised,pins,raw_shared,value,events,previous,
                phase=phase,lifetime_seconds=duration,xp2=True)
        path=run/filenames[phase]
        review['receipts'][filenames[phase]]=dict(path=str(path),sha256=digest(path.read_bytes()))
        review['reconciliations'][phase]=previous;review['phases'][phase]='authenticated'
    _,events=saved_load_events(run/'stdout.jsonl',stdout_limit_bytes=64*1024*1024)
    done=events.get('xp2_saved_load_group_completed',{})
    if (done.get('status')!=group['status'] or events['_event_lines'].get('xp2_saved_load_group_completed',0)<=previous['last_line']):
        raise ValueError('XP2 completion does not follow authenticated loaded shutdown')
    review.update(passed=True,status='authenticated_load_player_observation_and_close' if observe_player
                  else 'authenticated_load_postload_publication_and_close',postload_completed=True)
    if observe_player:review['player_observed']=True


def xp2_configuration_main(argv):
    """Private captured-input stages sharing one bounded supervisor and bundle."""
    import ctypes as C
    import datetime
    import time
    import uuid
    import zipfile
    from civ6_host.runtime.windows_process import WindowsProcessRuntime
    saved_load = '--saved-load' in argv
    if saved_load:
        argv = list(argv)
        argv.remove('--saved-load')
    postload160='--postload160' in argv
    if postload160:
        argv=list(argv);argv.remove('--postload160')
        if not saved_load:raise ValueError('XP2 postload requires --saved-load')
    observe_player='--observe-player' in argv
    if observe_player:
        argv=list(argv);argv.remove('--observe-player')
        if not postload160:raise ValueError('XP2 observation requires --saved-load --postload160')
    limit,duration=(768*1024**2,180 if observe_player else 120) if saved_load else (512*1024**2,90)
    work_name = 'native-xp2-saved-load' if saved_load else 'native-xp2-configuration'
    if len(argv)==4 and argv[0]=='--review-run' and argv[2]=='--supervisor-sha':
        return review_retained_xp2_configuration(argv[1], argv[3])
    package = dict(path=str(resource_root()/'work/host-prepared-captures/xp2-gs-lan-rows-20261102/manifest.json'),
        sha256='6468bf13145fa712438bd276896273630789ca4afb6003d904b66a8aa29e2020')
    if len(argv)==2 and argv[0]=='--worker':
        run=Path(argv[1]).resolve()
        if not run.is_relative_to((resource_root()/'work'/work_name).resolve()):
            raise ValueError('XP2 qualifier output escaped its private root')
        if sys.stdin.readline().strip()!='CONTAINED':
            raise ValueError('XP2 qualifier needs the bounded supervisor handshake')
        from civ6_host.runtime import xp2_bundle_inputs as inputs
        from civ6_host.runtime.xp1_session_inputs import prepare_private_fixture
        from civ6_host.runtime.native import native_official_bundle as original
        from civ6_host.runtime.native.native_core_context_profiles import profile_for_core
        from civ6_host.runtime.native.native_checkpoint_provider import verify_source as provider_source
        from civ6_host.runtime.native.native_checkpoint_configuration_only import _NativeBackend
        from civ6_host.runtime.native.native_probe import Windows
        Windows().kernel.SetErrorMode(1 | 2 | 32768)
        verify_installation()
        expected=json.loads((run/'executed-source-pins.json').read_bytes())
        if (expected.get('saved_load',False) is not saved_load
                or expected.get('postload160',False) is not postload160
                or expected.get('observe_player',False) is not observe_player
                or expected.get('wall_limit_seconds',120 if saved_load else 90)!=duration
                or expected.get('memory_limit_bytes',limit)!=limit
                or Path(sys.executable).resolve()!=Path(expected['native_host']['path']).resolve()
                or installed_source_pins()!=expected['runtime'] or digest(Path(__file__).read_bytes())!=expected['qualifier']
                or digest(Path(expected['native_host']['path']).read_bytes())!=expected['native_host']['sha256']
                or digest(Path(expected['native_build']['path']).read_bytes())!=expected['native_build']['sha256']):
            raise ValueError('XP2 configuration executed sources differ from parent')
        if saved_load:
            for name, expected_sha in expected['dependencies'].items():
                if digest(Path(name).read_bytes())!=expected_sha:
                    raise ValueError('XP2 saved Load dependency changed before worker: '+name)
            if expected['dependencies']!=xp2_saved_load_source_dependencies(postload160=postload160,observe_player=observe_player):
                raise ValueError('XP2 worker dependency scope differs before loading Core')
        def emit(event_name,**fields):
            row=dict(stage=event_name,**fields) if saved_load else dict(event_name=event_name,fields=fields)
            print(json.dumps(row,ensure_ascii=True),flush=True)
        started=time.perf_counter()
        bundle=inputs.consume_input_handoff(package)
        fixture,isolation=prepare_private_fixture(run,bundle,{})
        original.validate_fixture(bundle,fixture)
        profile=profile_for_core(bundle.engine_path,mode='context')
        dll_dirs=[os.add_dll_directory(str(path)) for path in (profile.shared_dependency_directory,profile.core_path.parent)]
        core=C.WinDLL(str(profile.core_path))
        create=core.DllCreateGameContext
        create.argtypes,create.restype=([],C.c_void_p)
        if C.cast(create,C.c_void_p).value!=core._handle+profile.create_context_rva:
            raise ValueError('XP2 factory export differs')
        context=create()
        if not context:raise RuntimeError('XP2 context factory returned null')
        if saved_load:
            from civ6_host.runtime.native.native_official_load import OfficialLoadBackend, run_experiment
            from civ6_host.runtime.captured_saved_load import proofs_for_candidate
            from civ6_host.runtime.xp1_saved_load_composition import compose_saved_load_services
            from civ6_host.runtime.xp1_loaded_lifetime import close_raw_loaded
            backend=OfficialLoadBackend(core,int(context),fixture,profile.shared_dependency_directory,
                profile,proofs_for_candidate(profile.core_sha256),emit,candidate_bundle=bundle)
            backend._saved_dll_directories=dll_dirs
            if postload160:backend._xp2_postload_requested=True
            raw=run_experiment(backend,bundle.inputs,prepare_services=compose_saved_load_services)
            backend.raw_load_result=raw
            write_once(run/'raw-load-result.json',dict(receipt=raw,readback=backend.loaded_readback,
                roster=backend.loaded_roster.decode('ascii'),postload_completed=False,
                public_session_admitted=False,strategic_training_ready=False))
            if postload160:
                from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
                closure=dict(input_profile='xp2-lan',raw_only_candidate=True,
                    post160_candidate=True,publish_cache_candidate=True,close_loaded_candidate=True,
                    observe_player_candidate=observe_player,unit_commands_candidate=False)
                saved=SavedLoadOwner.from_loaded(backend,closure,emit)
                emit('xp1_saved_raw_load_observed',receipt=dict(path=str(run/'raw-load-result.json'),sha256=digest((run/'raw-load-result.json').read_bytes())))
                cache_result=saved.populate_caches()
                emit('xp1_saved_cache_observed',receipt=write_once(run/'cache-result.json',cache_result))
                emit('before_xp1_saved_post160_sequence',public_runtime_admitted=False)
                post_result=saved.postload()
                emit('xp1_saved_post160_sequence_returned',receipt=write_once(run/'post160-result.json',post_result))
                emit('before_xp1_saved_cache_publication',public_runtime_admitted=False)
                publication_result=saved.publish()
                emit('xp1_saved_cache_publication_returned',receipt=write_once(run/'publication-result.json',publication_result))
                if observe_player:
                    emit('before_xp1_saved_player_view',public_runtime_admitted=False)
                    view_result=saved.observe_initial()
                    emit('xp1_saved_player_view_returned',receipt=write_once(run/'player-view-result.json',view_result))
                emit('before_xp1_saved_loaded_close',completed_phase='player_view' if observe_player else 'publication',public_runtime_admitted=False)
                closed=saved.close()
                emit('xp1_saved_loaded_close_returned',receipt=write_once(run/'loaded-lifetime-result.json',closed))
            else:
                emit('before_xp2_raw_loaded_close',game_load_called=True)
                closed=close_raw_loaded(backend)
                write_once(run/'loaded-lifetime-result.json',closed)
            if installed_source_pins()!=expected['runtime']:
                raise ValueError('XP2 runtime changed during qualification')
            result=dict(status='native_xp2_captured_player_observation_and_close_passed' if observe_player else
                        'native_xp2_captured_postload_publication_and_close_passed' if postload160 else 'native_xp2_captured_raw_load_readback_and_close_passed',
                package=package,origin=bundle.reference,fixture=str(fixture),isolation=isolation,
                core_sha256=profile.core_sha256,readback=backend.loaded_readback,
                roster=backend.loaded_roster.decode('ascii'),context_destroyed=backend.destroyed,
                elapsed_seconds=time.perf_counter()-started,game_load_called=True,
                saved_game_loaded=True,postload_completed=postload160,public_session_admitted=False,
                strategic_training_ready=False)
            if observe_player:result['player_observed']=True
            write_once(run/'xp2-saved-load-group.json',result)
            emit('xp2_saved_load_group_completed',status=result['status'])
            return 0
        backend=_NativeBackend(core,int(context),fixture,profile.shared_dependency_directory,
            profile,provider_source(core_sha256=profile.core_sha256),emit)
        backend._saved_load_candidate=True
        backend.captured_bundle=bundle
        backend.state(False)
        backend.initialize()
        backend.state(True)
        backend.clone()
        restored=backend.restore(bundle.inputs.configuration,
            expected_sha256=inputs.CONFIGURATION_SHA256)
        output,serialized=backend.serialize()
        # The whole original and resulting wire are retained. A comparison is
        # evidence, never a reason to substitute/normalize an unprofiled format.
        (run/'configuration-output.bin').write_bytes(output)
        raw_equal=output==bundle.inputs.configuration
        emit('xp2_captured_configuration_roundtrip_observed',exact_bytes_equal=raw_equal,
            input_sha256=inputs.CONFIGURATION_SHA256,output_sha256=digest(output),
            output_bytes=len(output),restore=restored,serialize=serialized,
            comparison_only=True,game_load_called=False)
        backend.close_owner()
        backend.state(True)
        host=backend.host
        backend.destroy_context()
        backend.finish_database()
        from civ6_host.runtime.configuration_roundtrip import compare_provider_roundtrip
        comparison = compare_provider_roundtrip(bundle.inputs.configuration, output,
                                                core_sha256=profile.core_sha256)
        if installed_source_pins()!=expected['runtime']:
            raise ValueError('XP2 runtime changed during qualification')
        result=dict(status='native_xp2_captured_initialization_and_destroy_passed',
            package=package,origin=bundle.reference,fixture=str(fixture),isolation=isolation,
            core_sha256=profile.core_sha256,init=host.context_init_receipt,
            teardown=host.context_teardown_receipt,context_destroyed=backend.destroyed,
            configuration_exact_bytes_equal=raw_equal,configuration_input_sha256=inputs.CONFIGURATION_SHA256,
            configuration_output_sha256=digest(output),configuration_output_bytes=len(output),
            configuration_comparison=comparison,
            elapsed_seconds=time.perf_counter()-started,game_load_called=False,
            saved_game_loaded=False,strategic_training_ready=False)
        write_once(run/'xp2-configuration-group.json',result)
        emit('xp2_configuration_group_completed',status=result['status'])
        return 0
    if argv:raise ValueError('XP2 stage uses fixed configuration limits; no arbitrary native CLI')
    runtime=WindowsProcessRuntime()
    run=resource_root()/'work'/work_name/(
        'run-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:12])
    run.mkdir(parents=True)
    verify_installation()
    executable=(resource_root()/XP2_UI_HOST[0] if observe_player else
                REPO/'work/xp2-service-composition/build-jobs-01/civ6rl-native-python.exe'
                if saved_load else Path(CONTEXT_HOST[0]))
    if observe_player and digest(executable.read_bytes())!=XP2_UI_HOST[1]:
        raise ValueError('XP2 observation requires its exact registered UI host')
    if not saved_load and digest(executable.read_bytes())!=CONTEXT_HOST[1]:
        raise ValueError('Qualified native Python platform host differs')
    native_build=executable.with_name('build.json')
    build=json.loads(native_build.read_bytes())
    executable_sha=digest(executable.read_bytes())
    if saved_load:
        from civ6_host.runtime.source_build_identity import verify_source_build
        from civ6_host.runtime.saved_load_job_observer import XP2_HOST_COMPONENT_SHA
        required_components={'gamecore_python_host.c':XP2_HOST_COMPONENT_SHA}
        if observe_player:
            from civ6_host.runtime.xp2_ui_binding_source import UI_COMPONENT_SHA
            required_components['script_core_ui_binding_profiles.inc']=UI_COMPONENT_SHA
        verify_source_build(executable,required_components=required_components)
    if build['executable']['sha256']!=executable_sha:
        raise ValueError('Native platform host build identity differs')
    sources=dict(runtime=installed_source_pins(),qualifier=digest(Path(__file__).read_bytes()),
        saved_load=saved_load,postload160=postload160,native_host=dict(path=str(executable),sha256=executable_sha),
        native_build=dict(path=str(native_build),sha256=digest(native_build.read_bytes())))
    if observe_player:sources.update(observe_player=True,wall_limit_seconds=duration,memory_limit_bytes=limit)
    if saved_load:
        sources['dependencies']=xp2_saved_load_source_dependencies(postload160=postload160,observe_player=observe_player)
    write_once(run/'executed-source-pins.json',sources)
    with zipfile.ZipFile(run/'executed-sources.zip','x',compression=zipfile.ZIP_DEFLATED)as archive:
        for name,sha in sources['runtime'].items():
            path=Path(name)
            if digest(path.read_bytes())!=sha:raise ValueError('XP2 source changed before archive')
            archive.write(path,path.relative_to(REPO).as_posix())
        archive.write(__file__,'invocation/qualify_xp1_configuration.py')
    available=runtime.available()
    if available['physical_available_bytes']<limit+256*1024**2:
        raise RuntimeError('Insufficient available memory for bounded XP2 configuration stage')
    report=dict(status='starting',run_directory=str(run),memory_limit_bytes=limit,
        wall_limit_seconds=duration,game_executable_launched=False,saved_game_loaded=False,
        source_archive_sha256=digest((run/'executed-sources.zip').read_bytes()))
    process=job=None
    started=time.perf_counter();peaks={}
    try:
        with (run/'stdout.jsonl').open('xb')as stdout,(run/'stderr.txt').open('xb')as stderr:
            process=subprocess.Popen([str(executable),__file__,'--engine','xp2',
                                      *(['--saved-load'] if saved_load else []),
                                      *(['--postload160'] if postload160 else []),
                                      *(['--observe-player'] if observe_player else []),'--worker',str(run)],
                cwd=REPO,env=dict(os.environ,PYTHONIOENCODING='utf8',
                    CIV6RL_PYTHON_HOME=sys.base_prefix,PATH=sys.base_prefix+os.pathsep+os.environ.get('PATH','')),
                stdin=subprocess.PIPE,
                stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
            job=runtime.job(process,limit)
            report.update(pid=process.pid,job_contained=True)
            process.stdin.write(b'CONTAINED\n');process.stdin.flush();process.stdin.close()
            while process.poll()is None:
                if time.perf_counter()-started>duration:
                    runtime.terminate_job(job,91);report['status']='timeout';break
                try:
                    for key,value in runtime.memory(int(process._handle)).items():
                        peaks[key]=max(peaks.get(key,0),value)
                except OSError:pass
                if (run/'stdout.jsonl').stat().st_size>(64 if saved_load else 4)*1024**2:
                    runtime.terminate_job(job,92);report['status']='telemetry_limit';break
                time.sleep(.05)
            process.wait(timeout=10)
            if report['status']=='starting':report['status']='passed'if process.returncode==0 else'failed'
            report.update(exit_code=process.returncode,process_reaped=True)
    finally:
        if process is not None and process.poll()is None:
            if job is not None:runtime.terminate_job(job,93)
            else:process.terminate()
            process.wait(timeout=10)
        if job is not None:runtime.close_job(job)
        report.update(elapsed_seconds=time.perf_counter()-started,memory_peaks=peaks)
        if saved_load:
            completed=run/'xp2-saved-load-group.json'
            report.update(requested_stage='saved_load_player_observation_close' if observe_player else
                          'saved_load_postload_publication_close' if postload160 else 'saved_load_readback_close',
                          postload_completed=False,public_session_admitted=False)
            if report['status']=='passed':
                if not completed.is_file():
                    report['status']='missing_completion_receipt'
                else:
                    group=json.loads(completed.read_bytes())
                    if (group.get('saved_game_loaded') is not True
                            or group.get('context_destroyed') is not True
                            or group.get('public_session_admitted') is not False):
                        report['status']='invalid_completion_receipt'
                    else:
                        report.update(saved_game_loaded=True,
                            postload_completed=postload160,
                            completion_receipt=dict(path=str(completed),sha256=digest(completed.read_bytes())))
            try:
                report['source_and_ledger_review']=evaluate_xp2_saved_load(run,sources,report)
                if report['status']=='passed' and report['source_and_ledger_review'].get('passed') is not True:
                    report['status']='source_or_ledger_review_failed'
                if observe_player:
                    report['player_observed']=(report['status']=='passed'
                        and report['source_and_ledger_review'].get('player_observed') is True)
            except BaseException as exc:
                report['source_and_ledger_review_error']=repr(exc)
                if report['status']=='passed':report['status']='source_or_ledger_review_failed'
        write_once(run/'supervisor.json',report)
    summary=dict(report)
    if saved_load and 'source_and_ledger_review' in summary:
        review=summary.pop('source_and_ledger_review')
        summary['review']={key:review.get(key) for key in ('passed','status','errors','phases')}
    print(json.dumps(summary))
    return 0 if report['status']=='passed'else 2


def main():
    if sys.argv[1:3]==['--engine','xp2']:
        try:
            return xp2_configuration_main(sys.argv[3:])
        except BaseException as exc:
            if '--worker' not in sys.argv[3:]:
                raise
            # A native owner may be partly initialized. Retain the refusal,
            # then let the OS reclaim the isolated process; never run guessed
            # DLL cleanup or Python finalizers over an uncertain live Game.
            import traceback
            traceback.print_exc()
            print(json.dumps(dict(stage='xp2_worker_refused',error=repr(exc),
                cleanup_guessed=False,normal_destroy_validated=False)),flush=True)
            from civ6_host.runtime.native.native_checkpoint_stream import terminate_worker
            terminate_worker(89)
    if '--stage' in sys.argv[1:]:
        index = sys.argv.index('--stage')
        os.environ[STAGE_ENV] = sys.argv[index+1]
        del sys.argv[index:index+2]
    stage = selected_stage()
    worker='--worker' in sys.argv[1:]
    if not worker:
        wire_flag='--script-wire-paths' in sys.argv[1:]
        if wire_flag:
            sys.argv.remove('--script-wire-paths')
        os.environ[WIRE_ENV]='1' if wire_flag else '0'
    selected_wire_mode()
    if stage == 'saved_load':
        return saved_load_main(sys.argv[1:])
    if '--review-run' in sys.argv[1:]:
        if stage!='scripts' or len(sys.argv)!=5 or sys.argv[1]!='--review-run' or sys.argv[3]!='--supervisor-sha':
            raise ValueError('Review requires scripts stage, retained run and explicit supervisor digest')
        return review_retained_script_run(sys.argv[2],sys.argv[4])
    reference, reference_path = load_reference()
    if stage=='a0':
        # This grouped codec qualification produces two receipts per case on
        # top of the existing lifecycle. Preserve the byte/time/memory limits;
        # the old 256-entry Init ledger is too small for this complete group.
        if reference.MAX_EVENTS!=256:raise ValueError('Retained lifecycle event bound changed')
        reference.MAX_EVENTS=512
    verify_installation()
    pins, fingerprint = source_state()
    worker = '--worker' in sys.argv[1:]
    expected = os.environ.get(PIN_ENV) if worker else fingerprint
    if expected != fingerprint:
        raise ValueError('Actual configuration runtime/hook differs from supervisor source fingerprint')
    original_verify = reference.verify_source_closure
    def verify(*args,**kwargs):
        value = original_verify(*args,**kwargs)
        if source_state()[1] != expected:
            raise ValueError('Configuration runtime/hook changed during qualification')
        return dict(value, configuration_runtime_fingerprint=expected,
                    executed_configuration_hook=str(Path(__file__).resolve()),
                    explicit_source_pin_migration=SOURCE_MIGRATION,
                    helper_host_parent_before=HELPER_HOST_PARENT)
    reference.verify_source_closure = verify
    if worker:
        index = sys.argv.index('--output-root')
        run_dir = Path(sys.argv[index+1]).resolve()
        if not run_dir.is_relative_to((resource_root()/'work').resolve()):
            raise ValueError('Qualification output is outside private work resources')
        use_common_lifecycle(reference)
        return reference.main(sys.argv[1:])

    if sys.argv[1:]:
        raise ValueError('Qualification uses the retained fixed 45s/512MiB/2048MiB limits')
    real_popen = subprocess.Popen
    def launch(command,**kwargs):
        if len(command)<3 or Path(command[1]).resolve()!=reference_path.resolve() or command[2]!='--worker':
            raise ValueError('Unexpected child launch from retained supervisor')
        command = list(command)
        command[1] = str(Path(__file__).resolve())
        kwargs['env'] = dict(kwargs['env'], **{PIN_ENV:expected, STAGE_ENV:stage,
                                              WIRE_ENV:'1' if selected_wire_mode() else '0'})
        return real_popen(command,**kwargs)
    subprocess.Popen = launch
    try:
        report = reference._supervise(SimpleNamespace(timeout_seconds=45,memory_mib=512,reserve_mib=2048))
    finally:
        subprocess.Popen = real_popen
    run_dir = Path(report['run_directory'])
    group_path = run_dir/(stage+'-group.json')
    group = json.loads(group_path.read_text(encoding='utf-8')) if group_path.is_file() else None
    success = report['status']=='completed_diagnostic' and group is not None and group.get('status')==f'native_{stage}_group_passed'
    result = {'status':f'native_{stage}_group_passed' if success else 'failed_or_incomplete',
              'stage':stage,
              'scope':f'shared product XP1 {stage} lifecycle on retained candidate DBs, not a saved game',
              'shared_backend_executed':True,
              'reference_runner_sha256':REFERENCE[1],'actual_runtime_fingerprint':expected,
              'diagnostic_event_limit':reference.MAX_EVENTS,
              'explicit_source_pin_migration':SOURCE_MIGRATION,
              'helper_host_parent_before':HELPER_HOST_PARENT,
              'retained_supervisor_status':report['status'],'run_directory':str(run_dir),
              'exit_code':report['exit_code'],'elapsed_seconds':report['elapsed_seconds'],
              'reaped':report['reaped'],'job_object_assigned':report['job_object_assigned'],
              'group':group,'saved_game_loaded':False,'strategic_training_ready':False,
              'worker_report': report.get('worker_report')}
    result['receipt'] = write_once(run_dir/(stage+'-qualification.json'),result)
    print(json.dumps(result,ensure_ascii=False))
    return 0 if success else 2


if __name__=='__main__':
    raise SystemExit(main())
