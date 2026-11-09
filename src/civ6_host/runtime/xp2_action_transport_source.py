"""Exact XP2 bindings for the shared archive transport and native Lua requests.

This selects native code and owners. It does not admit a session, create an
archive, replace operation legality, or qualify arbitrary Update callbacks.
"""
import hashlib
import json
from pathlib import Path

from .configuration_profiles import XP2_CORE_SHA256
from .action_transport_profiles import ActionTransportProfile

SOURCE = ('work/host-extensions/xp2-action-transport/source-profile-v1.json',
          '33e31b96dfd8f751b81479565216aa1cb68295e607c6cfd2947638621ee30ef4')
HOST_COMPONENT_SHA = '268a43bc7e06b383adfa13d2c084d2d7966ca8ffc9782044a0103ca36967f4f7'
CALLBACKS = {'CanStartOperation': 0x6C0390, 'RequestOperation': 0x6C3150}
ABI = ActionTransportProfile(XP2_CORE_SHA256, 0xB8AB20, 0x5901A0, 0x596DD0,
    0xA10EE8, 0x5979B0, 0xABFF20, 0x9AA080, 0xB8A9E8, 0x9A9EC0,
    0x9A9F80, 0xABFEC0, 0x590810, 0x590790, 0xB8AA19)


def _root(root):
    if root is None:
        from .paths import resource_root
        root = resource_root()
    return Path(root).resolve()


def _pinned(root, relative, expected):
    path = (root / relative).resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError('XP2 action source left its private root')
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('XP2 action source identity changed: ' + str(path))
    return path, raw


def source(root=None):
    profile, _ = _profile_and_pins(_root(root))
    return profile


def _profile_and_pins(root):
    profile_path, raw = _pinned(root, *SOURCE)
    pins = {str(profile_path): SOURCE[1]}
    p = json.loads(raw)
    expected = {k: v for k, v in vars(ABI).items() if k != 'core_sha256'}
    if (p['schema'] != 'civ6-host.xp2-action-transport.source.v1'
            or p['native_execution'] is not False
            or p['image']['sha256'] != XP2_CORE_SHA256
            or p['transport'] != expected or p['unit']['callbacks'] != CALLBACKS
            or p['owners'] != dict(outer_vtable_rva=0xA101E8,
                host_global_rva=0xB8AA80, aux_global_rva=0xB8AA88,
                unit_manager_global_rva=0xB6BD50, unit_manager_vtable_rva=0xA37348)
            or p['unit']['cached_unit_owner_offset'] != 0xEC
            or p['unit']['cached_unit_id_offset'] != 0xD0
            or p['unit']['request_lua_return_count'] != 0
            or p['log']['wrapper_rva'] != 0x9918E0
            or p['log']['getter_cache_rva'] != 0xB90648
            or p['log']['host_component_sha256'] != HOST_COMPONENT_SHA
            or p['log']['callback_return_consulted'] is not False
            or p['log']['c_change_required'] is not False):
        raise ValueError('XP2 action ABI/source contract changed')
    from .source_build_identity import SOURCE_BUILDS, verify_source_build
    from .xp2_session_inputs import XP2_UI_HOST
    from .xp2_ui_binding_source import UI_COMPONENT_SHA
    historical_build = SOURCE_BUILDS[XP2_UI_HOST[1]]['reference']
    for row in p['references']:
        reference = (row['path'], row['sha256'])
        if reference == historical_build:
            build = verify_source_build(root / XP2_UI_HOST[0], required_components={
                'gamecore_python_host.c': HOST_COMPONENT_SHA,
                'script_core_ui_binding_profiles.inc': UI_COMPONENT_SHA})
            for name, expected_sha in build['build_dependencies'].items():
                from .resource_resolution import resolve_path
                pins[str(resolve_path(root / name))] = expected_sha
            continue
        path, raw = _pinned(root, *reference)
        if len(raw) != row['bytes']:
            raise ValueError('XP2 action reference extent changed')
        pins[str(path)] = row['sha256']
    for body in p['functions'].values():
        if body['all_conditional_targets_captured'] is not True:
            raise ValueError('Incomplete XP2 action body')
        for f in body['fragments']:
            raw = bytes.fromhex(f['raw_hex'])
            if len(raw) != f['length'] or hashlib.sha256(raw).hexdigest() != f['sha256']:
                raise ValueError('XP2 action source body changed')
    return p, pins


def source_dependencies(root=None, *, execution_image=None):
    root = _root(root)
    p, pins = _profile_and_pins(root)
    image = Path(p['image']['path']).resolve()
    if str(image) != p['image']['path']:
        raise ValueError('XP2 action image path is not canonical')
    pins[str(image)] = XP2_CORE_SHA256
    from .execution_images import runtime_source_pins
    pins = runtime_source_pins(pins, execution_image=execution_image)
    expected_image_sha256 = pins[str(image)]
    if hashlib.sha256(image.read_bytes()).hexdigest() != expected_image_sha256:
        if execution_image is None:
            raise ValueError('XP2 action image changed')
        raise ValueError('XP2 action image differs from its explicit source/runtime pin')
    return pins


def _read(read, address, size):
    if (type(address) is not int or type(size) is not int or not 0 < size <= 4096
            or not 0 < address < (1 << 47) - size):
        raise ValueError('Invalid XP2 action memory range')
    raw = read(address, size)
    if type(raw) is not bytes or len(raw) != size:
        raise ValueError('Incomplete XP2 action memory read')
    return raw


def _equal(read, address, expected, label):
    for offset in range(0, len(expected), 4096):
        chunk = expected[offset:offset + 4096]
        if _read(read, address + offset, len(chunk)) != chunk:
            raise ValueError('XP2 action live ' + label + ' differs')


def verify_live(base, read, *, family, context=None, root=None):
    if type(base) is not int or not 0 < base < (1 << 47) - 0x1000000 or not callable(read):
        raise ValueError('XP2 action needs an exact module/reader')
    p = source(root)
    if family not in ('transport', 'unit', 'log'):
        raise ValueError('Unknown XP2 action source family')
    # Include the reviewed ownership helpers, not just the outer thunk.
    selected = (p['functions'].values() if family == 'transport'
                else (p['functions'][name] for name in p['families'][family]))
    count = 0
    for body in selected:
        for f in body['fragments']:
            _equal(read, base + int(f['start_rva'], 16), bytes.fromhex(f['raw_hex']), body['name'])
            count += 1
    for row in p['slots']:
        _equal(read, base + row['vtable_rva'] + row['slot'],
               (base + row['target_rva']).to_bytes(8, 'little'), 'slot')
    table = p['message_vtable']
    _equal(read, base + table['rva'], b''.join((base + r).to_bytes(8, 'little')
           for r in table['entries']), 'message vtable')
    for rva, row in p['literals'].items():
        _equal(read, base + int(rva, 16), bytes.fromhex(row['raw_hex']), 'literal')
    if context is not None:
        _equal(read, context, (base + p['owners']['outer_vtable_rva']).to_bytes(8, 'little'), 'context')
    return dict(core_sha256=XP2_CORE_SHA256, source_sha256=SOURCE[1],
                callbacks=dict(CALLBACKS) if family == 'unit' else {},
                instruction_spans_verified=count, native_request_invoked=False,
                native_callback_installed=False, actions_admitted=False)


def verify_owners(base, context, read, *, host_pointer, auxiliary_pointer):
    proof = source()
    for address, rva, label in ((host_pointer, proof['owners']['host_global_rva'], 'host owner'),
            (auxiliary_pointer, proof['owners']['aux_global_rva'], 'auxiliary owner')):
        if type(address) is not int or address <= 0:
            raise ValueError('XP2 action has no ' + label)
        _equal(read, base + rva, address.to_bytes(8, 'little'), label)
    _equal(read, context, (base + proof['owners']['outer_vtable_rva']).to_bytes(8, 'little'), 'context')


def verify_host_build():
    from .profile_script_binding import _current_executable
    from .source_build_identity import verify_source_build, xp2_component_requirements
    executable = _current_executable()
    return verify_source_build(executable, required_components=xp2_component_requirements(
        executable, {'gamecore_python_host.c': HOST_COMPONENT_SHA}))


def verify_log_binding(core, read, recorder):
    """Join the native lazy getter to this executable and retained callback."""
    import ctypes as C
    from .native.native_events import NativeEventRecorder
    if type(recorder) is not NativeEventRecorder or NativeEventRecorder._installed is not recorder:
        raise ValueError('XP2 log event requires its actual installed recorder')
    build = verify_host_build()
    module = recorder.kernel.GetModuleHandleW(None)
    getter = recorder.kernel.GetProcAddress(module, b'EXP_GetLogEventCallback')
    cached = int.from_bytes(_read(read, core._handle + 0xB90648, 8), 'little')
    if not getter or cached not in (0, getter):
        raise ValueError('XP2 log event cached getter has a foreign executable owner')
    callback = C.CFUNCTYPE(C.c_void_p)(getter)()
    if callback != C.cast(recorder.callback, C.c_void_p).value:
        raise ValueError('XP2 log event getter does not return its retained callback')
    return dict(getter_address=getter, cached_getter_address=cached, callback_address=callback,
                executable_module=module, source_sha256=SOURCE[1], source_build=build)
