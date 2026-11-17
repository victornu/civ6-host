"""Omit external Game History storage on the verified XP2 victory listener path."""

import ctypes as C
import hashlib
from pathlib import Path

from .a0_family_source import _path
from .a0_policy_unlock_current import CURRENT_CORE_SHA256, CURRENT_EXE_SHA256, _require_image
from .configuration_profiles import _source
from .resource_resolution import resolve_path


SOURCE = ('evidence/host-xp2-victory-history-slot28-source.json',
          '75e904411ce910c366e154f09769561ab666ef26f84a9b5b2aea5bffa08723e3')
ACHIEVEMENT_SOURCE = ('evidence/host-xp2-victory-achievement-listener-source.json',
                      '424c184b199b3e0cc065cd6ad2a682c3f6908c59fb512c52a0f5702a2b8407ab')
SLOT = 0x28
HOST_GLOBAL_RVA = 0xb8aa80
CALLER_PREFIX = ('0x24bc69', '0xfc253', '0x25583f')
CORE_MODULE = 'GameCore_XP2_FinalRelease.dll'


def source():
    proof = _source(SOURCE)
    contract = proof['contract']
    if (proof['schema'] != 'civ6-host.xp2-victory-history-slot28-source.v1'
            or proof['images']['core']['sha256'] != CURRENT_CORE_SHA256
            or proof['images']['exe']['sha256'] != CURRENT_EXE_SHA256
            or (contract['slot'], contract['host_global_rva'], contract['native_return_prefix'],
                contract['return_abi'], contract['null_branch_rva'])
            != (SLOT, HOST_GLOBAL_RVA, CALLER_PREFIX, 'nullable-pointer', 0x24cbf4)
            or contract['native_result_already_written'] is not True
            or contract['team_victory_emits_after_the_listener'] is not True
            or contract['history_success_synthesized'] is not False
            or contract['engine_victory_synthesized'] is not False):
        raise ValueError('XP2 victory history source contract differs')
    return proof


def source_dependencies(execution_image):
    _require_image(execution_image)
    proof = source()
    achievement_source()
    pins = {str(_path(path).resolve()): digest for path, digest in (SOURCE, ACHIEVEMENT_SOURCE)}
    pins.update({str(Path(resolve_path(ref['path'])).resolve()): ref['sha256']
                 for ref in proof['images'].values()})
    return pins


def verify_live(core, read, *, host_pointer):
    _require_image(core._civ6_host_execution_image)
    for span in (*source()['core_spans'].values(), *achievement_source()['live_spans']):
        raw = read(core._handle + span['rva'], span['bytes'])
        if type(raw) is not bytes or len(raw) != span['bytes'] or hashlib.sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('XP2 victory history live caller differs')
    if read(core._handle + HOST_GLOBAL_RVA, 8) != host_pointer.to_bytes(8, 'little'):
        raise ValueError('XP2 victory history live host owner differs')


def require_caller(frames):
    returns = tuple(frame['rva'] for frame in frames if frame['module'] == CORE_MODULE)
    if returns[:len(CALLER_PREFIX)] != CALLER_PREFIX:
        raise ValueError('Unqualified caller of XP2 Game History service')


def achievement_source():
    proof = _source(ACHIEVEMENT_SOURCE)
    routes = tuple(row['return_prefix'] for row in proof['return_routes'])
    flow = proof['dataflow']
    if (proof['schema'] != 'civ6-host.xp2-victory-slot20-group-source.v1'
            or proof['core']['sha256'] != CURRENT_CORE_SHA256 or proof['dependency']['sha256'] != SOURCE[1]
            or len(routes) != 21 or len(set(routes)) != 21
            or any(len(route) != 5 or route[0] != '0x17f098' or route[-2:] != CALLER_PREFIX[-2:]
                   for route in routes)
            or proof['observed']['return_prefix'] not in routes
            or flow['platform_success_synthesized'] is not False
            or flow['gameplay_result_already_written'] is not True):
        raise ValueError('XP2 victory achievement listener source contract differs')
    return proof


def select_achievement_source(returns, execution_image):
    if len(returns) < 5 or returns[0] != '0x17f098' or returns[3:5] != CALLER_PREFIX[-2:]:
        return None
    _require_image(execution_image)
    if any(returns[:5] == row['return_prefix'] for row in achievement_source()['return_routes']):
        return ACHIEVEMENT_SOURCE[1]
    return None


def install(backend):
    from .native.native_absent_achievements import capture_stack
    from .xp1_continuation import SavedContinuation
    from .xp2_turn_source import require_prepared_owner

    backend.check_thread()
    require_prepared_owner(backend)
    host, core, runtime = backend.host, backend.core, backend.runtime
    image = core._civ6_host_execution_image
    _require_image(image)
    if (backend.stage != 'prepared' or backend.prefix is not None or not backend.busy
            or backend.destroyed or backend.poisoned or hasattr(backend, '_xp2_victory_history')):
        raise ValueError('XP2 victory history requires its exclusive prepared owner')
    previous = host._slot_bindings.get((C.addressof(host.vtable), SLOT))
    if (previous is None or previous[0] != host.vtable[SLOT // 8]
            or getattr(previous[1], '_native_unavailable', None) != ('host', SLOT)):
        raise ValueError('XP2 Game History slot has a different owner')
    verify_live(core, runtime.read, host_pointer=host.pointer)

    def absent_history(this):
        backend.check_thread()
        host._check(this)
        continuation = getattr(backend, '_xp1_continuation', None)
        if (backend.host is not host or backend.core is not core or backend.runtime is not runtime
                or core._civ6_host_execution_image is not image or backend.destroyed or backend.poisoned
                or type(continuation) is not SavedContinuation or continuation.owner is not backend):
            raise ValueError('XP2 victory history active owner differs')
        continuation.check(active=True)
        require_caller(capture_stack())
        backend.emit('xp2_native_victory_history_sink_absent', slot=hex(SLOT),
                     source_proof_sha256=SOURCE[1], engine_result_already_written=True,
                     history_record_written=False, native_null_branch_used=True)
        return None

    host._bind(host.vtable, SLOT, C.c_void_p, [C.c_void_p], absent_history)
    backend._xp2_victory_history = (host, absent_history)
