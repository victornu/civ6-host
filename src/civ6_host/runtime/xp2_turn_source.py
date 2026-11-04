"""Exact XP2 turn primitives and HOST58/60/78 consumers, without loop admission.

The shared EXE services and native parameter/queue algorithms are unchanged.
Completion feedback delivers an already emitted archive only in its real guard
phase; this profile never writes readiness or manufactures a completion event.
"""
import hashlib
from pathlib import Path
import struct

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source
from .xp1_turn_profile import TurnProfile

SOURCE = ('work/host-extensions/xp2-turn-static/source-profile-v1.json',
          '881497bd2c43ff51233b89cd6e7a97f8aa5173eb129b5de07e49569c49cac854')
ABI = TurnProfile(XP2_CORE_SHA256, 0x590880, 0x590830,
    '81240b8b202b5b7b2b3ec3c90827a0cf08cec98d7751bba849dccb1e0879dcce',
    0x99E4B0, 0x99E5D0, 0xABF080, 0x99F5C0,
    0x9A4F60, 0x9A4FE0, 0xABF918, 0x9A5D50,
    0x9A6E40, 0x9A7080, 0x6061F0, 0xB8AB20,
    'XP2 Core035F70 returns whileB8AB21 is set')
FORCED_BODY_GUARDS = (
    (0x9A6E40, 138, '243b799dd9998593e48d36363e43b676b7548dd1f6e40c842d5714acd65453fc'),
    (0x6061F0, 81, 'aaef66bebcdd88c2538dab97659dba9237c5bc1a961cc62c59f68253716df51d'))


def source():
    from .native.native_host_thread_gate import PROFILE, PROOF_SHA
    p = _source(SOURCE)
    expected = {k: v for k, v in vars(ABI).items()
                if k not in ('core_sha256', 'completion_guard_description')}
    if (p['schema'] != 'civ6-host.xp2-turn-services.source.v1'
            or p['native_execution'] is not False
            or p['image']['sha256'] != XP2_CORE_SHA256
            or p['comparison_image']['sha256'] != XP1_CORE_SHA256
            or dict(p['abi']) != expected
            or tuple(tuple(r) for r in p['forced_body_guards']) != FORCED_BODY_GUARDS
            or p['contract']['completion_echo_flags'] != (1, 1, 0, 0)
            or p['contract']['completion_ignore_byte_rva'] != 0xB8AB21
            or p['contract']['completion_message'] != 0x1BDB4F5C
            or p['contract']['echo_requires_real_pending_archive'] is not True
            or p['contract']['echo_requires_exact_player'] is not True
            or p['contract']['readiness_writes'] is not False
            or p['contract']['turn_loop_admitted'] is not False
            or p['thread']['explicit_host_profile'] != PROFILE
            or p['thread']['shared_exe_source']['sha256'] != PROOF_SHA
            or p['thread']['slot58_only_after_owner_thread'] is not True
            or p['thread']['active_controller_returns_false_before_core_work'] is not True
            or p['thread']['non_owner_thread_skips_slot58_and_continues_core'] is not True):
        raise ValueError('XP2 turn/service source contract differs')
    if any(p['comparisons'][name]['normalized_equal'] is not True for name in p['equal_primitives']):
        raise ValueError('XP2 shared turn primitive differs')
    if any(p['comparisons'][name]['normalized_equal'] is not True for name in
           ('request_dispatch', 'thread_consumer', 'thread_caller', 'thread_caller_overload')):
        raise ValueError('XP2 turn dispatcher/controller flow differs')
    for body in (*p['functions'].values(), *p['complete_xp1_comparators'].values()):
        if body['all_conditional_targets_captured'] is not True:
            raise ValueError('XP2 turn source contains an incomplete body')
        for f in body['fragments']:
            raw = bytes.fromhex(f['raw_hex'])
            if len(raw) != f['length'] or hashlib.sha256(raw).hexdigest() != f['sha256']:
                raise ValueError('XP2 turn source body identity differs')
    def rows(name):
        return {int(r['rva'], 16): r for f in p['functions'][name]['fragments'] for r in f['instructions']}
    thread = rows('thread_consumer')
    if (thread[0x59C20]['bytes'] != 'ff5060' or thread[0x59C2D]['bytes'] != 'ff5058'
            or thread[0x59C13]['rip_targets'] != ('0x180b8aa80',)
            or any(thread[r]['bytes'] != '84c0' for r in (0x59C23, 0x59C30))
            or rows('completion_guard')[0x4AB90]['rip_targets'] != ('0x180b8ab21',)):
        raise ValueError('XP2 native Boolean consumer differs')
    slot = p['slot78']
    if (slot['call_rvas'] != (0x49DBE, 0x49E02)
            or slot['key_values'] != (0x4FC6296A, 0x715C87D1)
            or slot['abi'] != 'uint32 __fastcall(void *host, uint32 key)'
            or dict(slot['callback']) != dict(rva=0x9744B0, body_hex='33c0c3', result=0,
                reads_receiver=False, reads_key=False, side_effects=False, caller_reads_result=False)
            or any(rows('slot78_consumer')[r]['bytes'] != 'ff5078' for r in slot['call_rvas'])):
        raise ValueError('XP2 HOST78 consumer differs')
    shared = _source((slot['shared_exe_source']['path'], slot['shared_exe_source']['sha256']))
    if (shared['slot_bytes'] != 'b044974001000000'
            or ''.join(r['bytes'] for r in shared['callback']['instructions']) != '33c0c3'):
        raise ValueError('Shared EXE HOST78 source differs')
    return p


def source_dependencies():
    from .paths import resource_root
    from .provenance import installed_host_source_reference
    from .resource_resolution import resolve_path
    p = source()
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), *p['references'],
            p['image'], p['comparison_image']]
    pins = {}
    for row in refs:
        installed = installed_host_source_reference(row['path'])
        path = (installed or resolve_path(resource_root() / row['path'])).resolve()
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != row['sha256']:
                raise ValueError('XP2 turn/service dependency differs: ' + str(path))
        if 'bytes' in row and path.stat().st_size != row['bytes']:
            raise ValueError('XP2 turn/service dependency extent differs')
        pins[str(path)] = row['sha256']
    return pins


def verify_live(base, read, *, family, context=None, host_pointer=None):
    from .xp2_action_transport_source import _equal
    if type(base) is not int or not 0 < base < (1 << 47) - 0x1000000 or not callable(read):
        raise ValueError('XP2 turn/service requires an exact live module and reader')
    p = source()
    if family == 'turn':
        if type(context) is not int or context <= 0:
            raise ValueError('XP2 turn transport requires its outer context')
        _equal(read, context, struct.pack('<Q', base + 0xA101E8), 'turn outer interface')
        names = tuple(n for n in p['functions'] if not n.startswith(('thread_', 'slot78_')))
        for vt, slots in p['tables'].values():
            for slot, target in slots.items():
                _equal(read, base + vt + int(slot), struct.pack('<Q', base + target), 'turn vtable slot')
    elif family in ('thread', 'slot78'):
        if type(host_pointer) is not int or not 0 < host_pointer < (1 << 47):
            raise ValueError('XP2 turn service requires the actual host owner')
        _equal(read, base + 0xB8AA80, struct.pack('<Q', host_pointer), 'turn host owner')
        names = tuple(n for n in p['functions'] if n.startswith(family + '_'))
    else:
        raise ValueError('Unknown XP2 turn/service family')
    spans = 0
    for name in names:
        for f in p['functions'][name]['fragments']:
            raw = bytes.fromhex(f['raw_hex'])
            _equal(read, base + int(f['start_rva'], 16), raw, 'turn/service body ' + name)
            spans += (len(raw) + 4095) // 4096
    return spans


def require_prepared_owner(backend):
    """Authenticate the XP2 owner before mutating either shared host service."""
    from .native.native_official_load import OfficialLoadBackend
    from .native.native_host import DiagnosticHost
    if (not isinstance(backend, OfficialLoadBackend) or not isinstance(backend.host, DiagnosticHost)
            or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or backend.configuration_abi.core_sha256 != XP2_CORE_SHA256
            or backend.runtime.read is None):
        raise ValueError('XP2 turn service requires its actual saved configuration owner')
    with Path(backend.core._name).open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != XP2_CORE_SHA256:
            raise ValueError('XP2 turn service binary differs')
    from .xp2_action_transport_source import _equal
    _equal(backend.runtime.read, backend.context, struct.pack('<Q', backend.core._handle + 0xA101E8),
           'turn service outer owner')
