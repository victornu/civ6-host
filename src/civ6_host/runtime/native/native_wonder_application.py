"""Preserve the E660 wonder controller effects with real native getter calls."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from contextlib import contextmanager
import ctypes as C
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PINNED_EVIDENCE_SHA256 = '5b18c4d82e3a1aa28f0b51da723703357b2563c38240f0a8462af54c6936d6a5'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_wonder_application.py')))).resolve().parents[1] / 'evidence/native-e660-ui-effects' / f'{PINNED_EVIDENCE_SHA256}.json'
_CORE_SHA = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
_BRANCH_SHA = '9f27a38ba65bbbbcc456d6c929304f76c7766c4941438a23540370aa794f3c33'
_BRANCH_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_wonder_application.py')))).resolve().parents[1] / 'evidence/native-e660-wonder-branch' / f'{_BRANCH_SHA}.json'

def verify_source_evidence(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    if core_sha256 != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        if core_sha256 != XP2_CORE_SHA256:
            raise ValueError('Unqualified natural-wonder source engine')
        from civ6_host.runtime.xp2_natural_wonder_source import source
        return source()
    proof = load_pinned_json(_PROOF, PINNED_EVIDENCE_SHA256)
    branch = load_pinned_json(_BRANCH_PROOF, _BRANCH_SHA)
    from civ6_host.runtime.native.native_retained_game_getter import verify_source_evidence as verify_retained
    verify_retained()
    if proof.get('schema') != 'civ6.native-e660-ui-effects.static.v1' or proof['images']['core']['sha256'] != _CORE_SHA or proof['images']['exe']['sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof['comparison_helper']['body_sha256'] != 'e1571a5d102187be6ac36bd527978c35cd6732d0ec580ba024feb7a4cc251a6e') or (proof['feature_flag_setter']['body_sha256'] != '1aa215bc0a1096ff21401e01f6852c0c11bc4e86174ee7fc1bdb6b0bfd98cf6c') or (proof['core_read_path']['game_facade_vtable']['slot_c8_target'] != '0x180435130') or (proof['core_read_path']['slot_c8_tail_leaf']['raw_sha256'] != 'f3d4c22a04548d4f2cba9577d8e6539dc7e4f924198bc8cd2c1c55a04e330247') or (branch.get('schema') != 'civ6rl.native_e660_wonder_branch.static.v1') or (branch['images']['core_sha256'] != _CORE_SHA) or (branch['validation']['all_captured_instruction_bytes_reverified'] is not True) or (branch['callback_guards']['0x14014041b'] != 'call 0x140151d70') or (branch['callback_guards']['0x140140429'] != 'call 0x1401b9c30'):
        raise RuntimeError('Wonder application effect source changed')
    return proof

def _signed(value):
    if type(value) is not int or not -(1 << 31) <= value < 1 << 31:
        raise ValueError('Wonder application getter requires a signed DWORD')
    return value

@contextmanager
def native_game_comparison_value(core, context, read, *, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Borrow outer+90/Game+C8 until the source comparison/effects finish."""
    if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        abi = dict(outer_table=7987232, get_game=4382432, game_table=7990488, release_game=4409168, read_value=4411696, bodies=((4411696, bytes.fromhex('e9bbdfc1ff')), (340208, bytes.fromhex('8b051a8e8600c3'))))
    else:
        verify_source_evidence(core_sha256=core_sha256)
        from civ6_host.runtime.xp2_natural_wonder_source import comparison_abi
        abi = comparison_abi()
    verify_source_evidence(core_sha256=core_sha256)
    base = int(core._handle)

    def qword(address):
        raw = read(address, 8)
        if type(raw) is not bytes or len(raw) != 8:
            raise ValueError('Wonder application requires an exact native qword')
        return struct.unpack('<Q', raw)[0]

    def check(pointer, table, slots):
        if not pointer or qword(pointer) != base + table:
            raise ValueError('Wonder application native facade identity changed')
        for offset, target in slots:
            if qword(base + table + offset) != base + target:
                raise ValueError('Wonder application native virtual slot changed')
    check(context, abi['outer_table'], ((144, abi['get_game']),))
    for rva, expected in abi['bodies']:
        if read(base + rva, len(expected)) != expected:
            raise ValueError('Wonder application native getter code changed')
    if native_api is None:
        api = {'get_game': C.WINFUNCTYPE(C.c_void_p, C.c_void_p)(base + abi['get_game']), 'read_value': C.WINFUNCTYPE(C.c_int32, C.c_void_p)(base + abi['read_value']), 'release_game': C.WINFUNCTYPE(None, C.c_void_p)(base + abi['release_game'])}
    else:
        api = native_api
        if type(api) is not dict or set(api) != {'get_game', 'read_value', 'release_game'} or any((not callable(fn) for fn in api.values())):
            raise ValueError('Wonder application native seam is incomplete')
    game = api['get_game'](context)
    if not game:
        yield None
        return
    validated = False
    try:
        check(game, abi['game_table'], ((8, abi['release_game']), (200, abi['read_value'])))
        validated = True
        yield _signed(api['read_value'](game))
    finally:
        if validated:
            api['release_game'](game)

def apply_wonder_application_effects(core, context, read, turn_state, retained_getter, *, native_api=None, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    """Apply 151D70 then the independent 1B9C30(1), between AE and AF.

    This shares the existing state read by native host+120. The full EXE
    controller scheduler remains outside this narrow callback contract.
    """
    verify_source_evidence(core_sha256=core_sha256)
    if getattr(turn_state, 'controller_initialized', None) is not True or type(getattr(turn_state, 'controller_byte_0d', None)) is not int or (not 0 <= turn_state.controller_byte_0d <= 255) or (type(getattr(turn_state, 'service_flags', None)) is not int) or (not 0 <= turn_state.service_flags <= 255) or (not callable(retained_getter)):
        raise ValueError('Wonder effect requires initialized shared controller/UI state')
    before = (turn_state.controller_byte_0d, turn_state.service_flags)
    retained = None
    with native_game_comparison_value(core, context, read, native_api=native_api, core_sha256=core_sha256) as value:
        matched = False
        if value is not None:
            retained = _signed(retained_getter())
            matched = value == retained
            if matched:
                turn_state.controller_byte_0d = 1
                turn_state.service_flags |= 64
    turn_state.service_flags |= 64
    return dict(game_value=value, retained_game_value=retained, comparison_matched=matched, controller_before=before[0], flags_before=before[1], controller_after=turn_state.controller_byte_0d, flags_after=turn_state.service_flags, native_gameplay_written=False, shared_host_slot120_state=True, original_exe_scheduler_reproduced=False)
