"""Scoped recursive GameEvents transport for the exact BBG capture."""
import ctypes as C
import hashlib

from .configuration_profiles import _source
from .native.native_script_arguments import HKSArgument, pack_arguments
from .native.native_script_runtime import NativeScriptRuntime
from .profile_script_binding import _current_executable
from .source_build_identity import (XP2_HOST_COMPONENT_SHA, verify_source_build,
    xp2_component_requirements, CURRENT_HAVOK_BUILD_PROFILE, CURRENT_STRINGS_BUILD_PROFILE)
from . import xp2_bbg_inputs as bbg

SOURCE = ('evidence/host-bbg751-first-turn-native-prefix.json',
          'fc170bad317d1f9c3956827d8d56c48323883243a83fe64efa1c71495912bdba')
COMPONENT = ('script_bbg_nested_game_events.inc',
             'ca5c13aa5d426131329bed5d9e7cfd5e5a05b922a8b9d22b0c3080dfe4a6ef0b')
WINDOWS = {
    'outer_OnGameTurnStarted': '0x5aa76d',
    'inner_UnitCreated': '0x5a871e',
    'aux60_shared_dispatch': '0x244e8',
    'lua_gameplay_mutation_call': '0x6c69a0',
}


def runtime_type(backend):
    """Verify the exact build and producer windows before enabling recursion."""
    from .xp2_bbg_property_table import BUILD_PROFILE
    executable = _current_executable()
    build = verify_source_build(executable, required_components=xp2_component_requirements(
        executable, {'gamecore_python_host.c': XP2_HOST_COMPONENT_SHA}))
    if build['profile'] not in (BUILD_PROFILE, CURRENT_HAVOK_BUILD_PROFILE, CURRENT_STRINGS_BUILD_PROFILE):
        raise ValueError('BBG runtime requires its registered native profile')
    if COMPONENT[0] not in build['sources']:
        return NativeScriptRuntime
    if build['sources'].get(COMPONENT[0]) != COMPONENT[1]:
        raise ValueError('BBG nested event dispatcher source differs')
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.bbg751-first-turn-native-prefix.v1'
            or proof['core_sha256'] != backend.load_abi.core_sha256
            or not bbg.is_reference(backend.captured_bundle.reference)):
        raise ValueError('BBG nested GameEvents source is for another engine or capture')
    windows = proof['nested_callback']['core_windows']
    for name, start in WINDOWS.items():
        window = windows[name]
        raw = b''.join(bytes.fromhex(row['bytes']) for row in window['instructions'])
        if (window['start'] != start or len(raw) != int(window['end'], 16) - int(start, 16)
                or hashlib.sha256(raw).hexdigest() != window['sha256']
                or backend.runtime.read(backend.core._handle + int(start, 16), len(raw)) != raw):
            raise ValueError('BBG nested GameEvents producer differs: ' + name)
    return BBGNestedScriptRuntime


class BBGNestedScriptRuntime(NativeScriptRuntime):
    def dispatch_game_event_result(self, name, arguments, *, method, output_initial=0):
        depth_before = self.lua['gettop'](self.root)
        if not depth_before:
            return super().dispatch_game_event_result(
                name, arguments, method=method, output_initial=output_initial)
        self.registry._check()
        if (method not in ('Call', 'TestAll') or type(output_initial) is not int
                or not 0 <= output_initial <= 255 or type(name) is not bytes
                or not name or len(name) > 255 or not name.isascii() or b'\x00' in name):
            raise ValueError('Unverified nested GameEvents request')
        packed = pack_arguments(arguments)
        valid, output = C.c_uint8(), C.c_uint8(output_initial)
        dispatch = self.host.LAB_BBGGameEventsDispatchNestedTypedResult
        dispatch.argtypes = [C.c_void_p, C.c_char_p, C.POINTER(HKSArgument), C.c_size_t,
                             C.c_uint, C.POINTER(C.c_uint8), C.POINTER(C.c_uint8)]
        dispatch.restype = C.c_int
        status = dispatch(self.root, name, packed, len(packed), int(method == 'TestAll'),
                          C.byref(valid), C.byref(output))
        # The ordinary error helper empties the root. Here the caller owns
        # the existing frame, including on a protected-call failure.
        if self.lua['gettop'](self.root) != depth_before:
            raise RuntimeError('Nested GameEvents changed the parent stack depth')
        if status:
            raise RuntimeError(f'Nested GameEvents {name!r} refused with native status {status}')
        self.emit('native_bbg_nested_gameevent_dispatched', event_name=name.decode('ascii'),
                  method=method, argument_count=len(packed), root_stack_depth=depth_before,
                  result_non_nil=bool(valid.value), protected_call_success=True)
        return bool(valid.value), output.value
