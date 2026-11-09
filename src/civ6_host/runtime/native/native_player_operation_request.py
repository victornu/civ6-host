"""Native public player-operation request with owned scalar parameter storage.

This constructs native vector parameters; it never fabricates an archive or
treats a request return as evidence of a committed gameplay operation.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
from pathlib import Path
import struct
from civ6_host.runtime.native.native_setup import local_reader
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PINNED_EVIDENCE_SHA256 = 'e04deeffcd31ca8e0125ca595d998ad575acd149ecad00b0605820ee27a32468'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_player_operation_request.py')))).resolve().parents[1] / 'evidence/native-player-operation-request' / f'{PINNED_EVIDENCE_SHA256}.json'
_METHODS = {'parameter_ctor': (7649392, C.c_void_p, (C.c_void_p,)), 'parameter_dtor': (7649520, None, (C.c_void_p,)), 'set_u32': (7654928, C.c_void_p, (C.c_void_p, C.c_uint32, C.c_uint32)), 'lookup': (7652848, C.c_void_p, (C.c_void_p, C.c_uint32)), 'reason_ctor': (7621504, C.c_void_p, (C.c_void_p,)), 'reason_dtor': (7621792, None, (C.c_void_p,)), 'can_start': (4381024, C.c_uint8, (C.c_void_p, C.c_int32, C.c_uint32, C.c_void_p, C.c_uint8, C.c_void_p)), 'request': (4387408, None, (C.c_void_p, C.c_int32, C.c_uint32, C.c_void_p))}

def verify_source_evidence(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        from civ6_host.runtime.xp1_research_profile import verify_source as verify_selected_source
        return verify_selected_source(core_sha256)
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    if proof.get('schema') != 'civ6rl.native_player_operation_request.static.v1' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or (proof['ui_registration']['callback_va'] != '0x1401ae320') or (proof['vtables']['parameters']['va'] != '0x18081d838'):
        raise RuntimeError('Native player-operation request source identity changed')

class _GuardedStorage:

    def __init__(self, size, name):
        self.size, self.name = (size, name)
        self.storage = C.create_string_buffer(size + 32)
        self.address = C.addressof(self.storage) + 16
        C.memset(self.address - 16, 165, 16)
        C.memset(self.address + size, 165, 16)

    def check(self):
        if C.string_at(self.address - 16, 16) != b'\xa5' * 16 or C.string_at(self.address + self.size, 16) != b'\xa5' * 16:
            raise RuntimeError(f'Native {self.name} exceeded source-sized storage')

def request_player_operation(core, context, player, operation, parameters, *, read=None, native_api=None, submit=True, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', allow_empty=False, congress_permit=None):
    """Run native CanStart and, when true, submit the identical scalar map.

    ``allow_empty`` is restricted to the source-qualified XP2 UNLOCK_POLICIES
    operation, whose official UI submits an empty table. An internal sealed
    Congress permit additionally admits its exact source-described empty maps
    and direct requests without CanStart. Other callers retain their contract.

    ``parameters`` is an insertion-ordered dictionary of one to eight uint32
    keys and values obtained by the caller from the intended native Lua API.
    Values must be DWORD bit patterns of actual signed32 Lua integers; other
    Lua numeric representations can take the source floating-point branch.
    This helper does not infer operation/key meanings. It admits the source
    player-index domain 0..63, passes test_visible=False, and supplies an owned native
    reason map. The returned request_invoked flag means only the void public
    call returned; the caller must observe and deliver its native archive and
    independently inspect the resulting gameplay state.
    """
    from civ6_host.runtime.xp1_research_profile import player_operation_abi
    abi = player_operation_abi(core_sha256, _METHODS)
    verify_source_evidence(core_sha256=core_sha256)
    if type(submit) is not bool:
        raise ValueError('Exact player-operation submission mode required')
    if type(player) is not int or not 0 <= player < 64:
        raise ValueError('Player-operation player ID must be an exact integer in 0..63')
    if type(operation) is not int or not 0 <= operation <= 4294967295:
        raise ValueError('Player operation must be a uint32 native value')
    if type(allow_empty) is not bool:
        raise ValueError('Empty player-operation parameters require explicit qualification')
    congress_name = None
    if congress_permit is not None:
        from civ6_host.runtime.xp2_world_congress_source import authorize_request
        congress_name = authorize_request(congress_permit, core, context, player, operation,
            parameters, core_sha256=core_sha256, submit=submit, allow_empty=allow_empty)
    elif allow_empty:
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        from civ6_host.runtime.xp2_policy_controls_source import UNLOCK_POLICIES, source
        if core_sha256 != XP2_CORE_SHA256 or operation != UNLOCK_POLICIES:
            raise ValueError('Unqualified empty player-operation map')
        source()
    if not isinstance(parameters, dict) or not (0 if allow_empty else 1) <= len(parameters) <= 8 or any((type(k) is not int or type(v) is not int or (not 0 <= k <= 4294967295) or (not 0 <= v <= 4294967295) for k, v in parameters.items())):
        raise ValueError('Player-operation parameters require one to eight uint32 pairs')
    parameters = dict(parameters)
    base = getattr(core, '_handle', None)
    if type(base) is not int or base <= 0 or type(context) is not int or (context <= 0):
        raise ValueError('Player operation requires live relocated Core/context')
    read = read or local_reader()
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        from civ6_host.runtime.xp1_research_profile import verify_live
        image=getattr(core,'_civ6_host_execution_image',None)
        verify_live(base, read, core_sha256=core_sha256,
                    **({'execution_image':image} if image is not None else {}))

    def u64(address):
        raw = read(address, 8)
        if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 8:
            raise ValueError('Incomplete native player-operation pointer read')
        return struct.unpack('<Q', raw)[0]
    if u64(context) != base + abi.outer:
        raise ValueError('Unexpected player-operation outer interface')
    for vt, offset, target in abi.slots:
        if u64(base + vt + offset) != base + target:
            raise ValueError('Unexpected public player-operation/parameter method')
    if native_api is None:
        native_api = {name: C.WINFUNCTYPE(restype, *args)(base + rva) for name, (rva, restype, args) in abi.methods.items()}
    elif not isinstance(native_api, dict) or set(native_api) != set(abi.methods) or (not all((callable(value) for value in native_api.values()))):
        raise ValueError('Player-operation test API must supply the complete source contract')
    params = _GuardedStorage(72, 'vector parameter map')
    reasons = _GuardedStorage(96, 'reason map')
    params_live = reasons_live = False

    def check():
        params.check()
        reasons.check()

    def verify_values():
        for key, expected in parameters.items():
            pointer = native_api['lookup'](params.address, key)
            check()
            if not pointer:
                raise RuntimeError('Native vector parameter was not stored')
            raw = read(pointer, 24)
            if not isinstance(raw, (bytes, bytearray, memoryview)) or len(raw) != 24 or struct.unpack_from('<H', raw)[0] != 2 or (struct.unpack_from('<I', raw, 8)[0] != expected) or (struct.unpack_from('<Q', raw, 16)[0] != 0):
                raise RuntimeError('Native vector parameter differs from its DWORD input')
    try:
        result = native_api['parameter_ctor'](params.address)
        params_live = True
        check()
        if result != params.address or u64(params.address) != base + abi.parameters:
            raise RuntimeError('Native vector parameter constructor identity differs')
        if read(params.address + 8, 24) != bytes(24) or read(params.address + 40, 24) != bytes(24):
            raise RuntimeError('New native vector parameter map is not empty')
        for key, value in parameters.items():
            if native_api['lookup'](params.address, key):
                raise RuntimeError('New native vector parameter key already exists')
            check()
            pointer = native_api['set_u32'](params.address, key, value)
            check()
            if not pointer:
                raise RuntimeError('Native vector DWORD setter returned null')
        verify_values()
        result = native_api['reason_ctor'](reasons.address)
        reasons_live = True
        check()
        if result != reasons.address or u64(reasons.address) != base + abi.reasons:
            raise RuntimeError('Native reason-map constructor identity differs')
        # These source-bound UI requests do not call CanStart. The native
        # request still applies its own requested-player active-state guard.
        allowed = (True if congress_name is not None else
                   native_api['can_start'](context, player, operation, params.address, False, reasons.address))
        check()
        if type(allowed) not in (bool, int) or allowed not in (0, 1):
            raise RuntimeError('Native CanStartPlayerOperation returned a noncanonical Boolean')
        verify_values()
        if allowed and submit:
            native_api['request'](context, player, operation, params.address)
            check()
        receipt = {'player_id': player, 'operation': operation, 'can_start': bool(allowed), 'request_invoked': bool(allowed and submit), 'request_return_interpreted': False, 'parameter_count': len(parameters), 'native_parameter_vtable_rva': hex(abi.parameters), 'test_visible': False, 'native_reason_map': True, 'archive_fabricated': False, 'gameplay_outcome_verified': False, 'eligible_for_training': False, 'source_sha256': abi.source_sha256}
        if congress_name is not None:
            receipt.update(can_start=None, native_can_start_called=False,
                           source_qualified_request_only=congress_name)
        return receipt
    finally:
        try:
            if reasons_live:
                native_api['reason_dtor'](reasons.address)
        finally:
            try:
                if params_live:
                    native_api['parameter_dtor'](params.address)
            finally:
                check()
