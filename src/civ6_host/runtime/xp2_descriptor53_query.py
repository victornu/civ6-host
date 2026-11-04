"""Exact 07F2ABD3/descriptor53 query selection on the shared XP2 lifetime.

EXE145650 emits record13B through125710. Its helper146B30 queries only the
service+140 DWORD vector and converts each index through F1C00. It does not
perform Storm's additional +110 query and is not an alias of record138.
"""
from __future__ import annotations

import struct

from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import _source
from .saved_load_profiles import XP2_CORE_SHA256
from .xp2_storm_query import StormQueryResult, _query_objects

SOURCE = ('work/host-extensions/xp2-descriptor53-query/source-profile-v1.json',
          '36b6a8fee37f3361a5b51f04e337c889d2b8aea12bea4c8aa2f7d4cc98b40d4e')
SERVICE_LIST_SLOT = 0x140
SERVICE_LIST_RVA = 0x5980E0
EVENT_KIND = 0x07F2ABD3


def _rows(body):
    return body.get('instructions') or [row for fragment in body['fragments']
                                       for row in fragment['instructions']]


def source():
    from .xp2_storm_query import SERVICE_IID
    p = _source(SOURCE)
    if (p.get('schema') != 'civ6-host.xp2-descriptor53-query.static.v1'
            or p.get('images') != dict(core_sha256=XP2_CORE_SHA256,
                exe_sha256='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63')
            or p.get('native_execution') is not False
            or p.get('process_memory_read') is not False
            or p['service'] != dict(iid_hex=SERVICE_IID.hex(), iid_exe_rva='0xfbf4b0',
                wrapper_table_rva=0xA110F0, slot=SERVICE_LIST_SLOT,
                target_rva=SERVICE_LIST_RVA,
                slot_preferred_bytes=struct.pack('<Q', 0x180000000+SERVICE_LIST_RVA).hex(),
                abi='ignored_RAX(ptr,request_key8*,vector24*)', element_bytes=4,
                query_pair_called=False)):
        raise ValueError('Descriptor53 native source selection differs')
    for key, expected in dict(event_kind=EVENT_KIND, descriptor_type=0x53,
            callback_rva=0x145650, helper_rva=0x146B30, writer_rva=0x125710,
            record_type=0x13B, record_size=112, metadata_flag=4).items():
        if p['selection'].get(key) != expected:
            raise ValueError('Descriptor53 callback/writer contract differs')
    helper = {row['va']: row['text'] for row in _rows(p['exe_functions']['0x146b30'])}
    writer = {row['va']: row['text'] for row in _rows(p['exe_functions']['0x125710'])}
    if (helper.get('0x140146bd7') != 'call qword ptr [rax + 0x140]'
            or helper.get('0x140146caa') != 'call 0x1400f1c00'
            or any('[rax + 0x110]' in row for row in helper.values())
            or writer.get('0x1401257b8') != 'mov dword ptr [rbx + 4], 0x13b'
            or writer.get('0x1401257b2') != 'mov dword ptr [rbx], 0x70'):
        raise ValueError('Descriptor53 EXE selected getter or record differs')
    for ref in p['references'].values():
        _source((ref['path'], ref['sha256']))
    return p


def source_dependencies():
    from .xp2_storm_query import source_dependencies as shared_dependencies
    pins = shared_dependencies()
    p = source()
    for row in [dict(path=SOURCE[0],sha256=SOURCE[1]), p['generator'],
                *p['references'].values()]:
        path = str(_path(row['path']).resolve())
        if path in pins and pins[path] != row['sha256']:
            raise ValueError('Descriptor53 source dependency conflict')
        pins[path] = row['sha256']
    verify_pinned_files(pins)
    return pins


def verify_live(base, read):
    """Verify the new getter even when shared Storm source was already checked."""
    from .xp2_storm_query import _read_exact
    if type(base) is not int or base <= 0 or not callable(read):
        raise ValueError('Descriptor53 query requires a relocated Core and checked reader')
    p = source()
    checked = set()
    for function in p['functions'].values():
        for body in [function['body']] + [tail['body'] for tail in function['out_of_line_tail_jumps']]:
            for row in _rows(body):
                rva = int(row['rva'],16)
                raw = bytes.fromhex(row['bytes'])
                if _read_exact(read,base+rva,len(raw),'descriptor53 getter') != raw:
                    raise ValueError('Descriptor53 native getter bytes differ')
                checked.add(rva)
    target = struct.pack('<Q',base+SERVICE_LIST_RVA)
    if _read_exact(read,base+0xA110F0+SERVICE_LIST_SLOT,8,'descriptor53 slot') != target:
        raise ValueError('Descriptor53 native getter slot differs')
    return dict(source_sha256=SOURCE[1], checked_instructions=len(checked),
                native_calls_invoked=False)


def query_descriptor53_objects(core, context, request_key, *, read=None,
        native_calls=None, index_to_position=None,
        core_sha256=XP2_CORE_SHA256) -> StormQueryResult:
    """Return copied list/positions; ``position`` is always None (no +110).

    Reuses Game/wrapper/vector ownership from the Storm query. The exact native
    seam has get_game, release_game, get_service, query_values, release_service,
    and free_vector, with the same signatures as that adapter. The descriptor
    must be FFFF/53/id. Empty returned arrays do not define a record13B count or
    pointer; the record owner must refuse that undefined branch explicitly.
    """
    if (type(request_key) is not bytes or len(request_key) != 8
            or request_key[:4] != struct.pack('<HH',0xFFFF,0x53)):
        raise ValueError('Descriptor53 query requires the source FFFF/53/id key')
    return _query_objects(core,context,request_key,read=read,native_calls=native_calls,
        index_to_position=index_to_position,core_sha256=core_sha256,family='descriptor53')


__all__ = ['EVENT_KIND','SOURCE','query_descriptor53_objects','source',
           'source_dependencies','verify_live']
