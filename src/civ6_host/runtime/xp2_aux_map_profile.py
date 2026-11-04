"""XP2 metadata for the existing read-only A8 map decoder.

Source and live-byte checks are not a native XP2 session qualification. The
shared decoder retains its type, ownership, depth, size and stability refusals.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import struct

from .aux_map_profiles import MapABI
from .configuration_profiles import _source
from .native.native_source_cache import load_pinned_json
from .paths import resource_root
from .resource_resolution import resolve_path
from .saved_load_profiles import XP2_CORE_SHA256

SOURCE=('work/host-extensions/xp2-aux-map/source-profile-v1.json',
        '2d4ffa1483df9142a430f26ad4742ad656b79bc494defb36a5209d016272b177')
_PROFILE=MapABI(XP2_CORE_SHA256,0xabf080,
    ((8,0x404190),(0x60,0x99f5c0),(0x70,0x99f6d0),(0x1d8,0x84e260)),0x989d0,SOURCE[1])
_LAYOUT=dict(map_kind=2,map_header_bytes=84,name_resolver_offset=32,
    sentinel_offset=48,begin_offset=56,root_offset=64,count_offset=80,count_bytes=4,
    node_read_bytes=64,node_right_offset=0,node_left_offset=8,node_parent_offset=16,
    node_key_offset=32,node_variant_offset=40,variant_bytes=24,variant_tag_offset=0,
    variant_tag_bytes=2,variant_payload_offset=8,variant_size_offset=16,
    variant_flags_offset=20,variant_pointer_bit=1<<29,
    list_begin_offset=40,list_end_offset=48,list_variant_stride=24,
    nested_map_tag=10,nested_map_flags=0x05000000,list_tag=11,list_flags=0x11000000)


def _require(condition,message):
    if not condition:raise ValueError(message)


def source():
    proof=_source(SOURCE)
    _require(proof['schema']=='civ6-host.xp2-aux-map-source.v1'
             and proof['native_execution'] is False
             and proof['core_sha256']==XP2_CORE_SHA256
             and proof['vtable_rva']==_PROFILE.vtable_rva
             and proof['name_getter_rva']==_PROFILE.name_getter_rva
             and dict(proof['layout'])==_LAYOUT,
             'XP2 map source/layout differs')
    slots=tuple((row['slot'],row['target_rva']) for row in proof['slots'])
    _require(slots==(*_PROFILE.slots,(0x18,_PROFILE.name_getter_rva)),
             'XP2 map source dispatch differs')
    bodies=proof['bodies']
    _require(0<len(bodies)<=64,'Invalid XP2 map body inventory')
    for body in bodies:
        raw=bytes.fromhex(body['raw_hex'])
        _require(type(body['rva']) is int and 0<body['rva']<0x1000000
                 and type(body['bytes']) is int and 0<body['bytes']==len(raw)<=1024*1024
                 and hashlib.sha256(raw).hexdigest()==body['sha256'],
                 'XP2 map source body differs')
    _require({target for _,target in slots}.issubset({body['rva'] for body in bodies}),
             'XP2 map source lacks a required complete reader body')
    root=resource_root()
    for row in proof['references']:
        relative=Path(row['path'])
        _require(not relative.is_absolute() and not relative.drive and '..' not in relative.parts,
                 'XP2 map source reference is not relative')
        path=resolve_path(root/relative).resolve(strict=True)
        _require(path.is_relative_to(root) and 0<row['bytes']<=16*1024*1024
                 and path.stat().st_size==row['bytes'],'XP2 map source reference left its bounds')
        # Immutable JSON only: reuse the existing metadata-aware digest cache.
        # Live map data is never cached here.
        load_pinned_json(path,row['sha256'])
    return proof


def profile():
    source()
    return _PROFILE


def verify_live(selected,base,read):
    _require(selected is _PROFILE and type(base) is int and 0<base<(1<<47)-0x1000000
             and callable(read),'Expected canonical XP2 map profile and checked reader')
    proof=source()
    for body in proof['bodies']:
        raw=read(base+body['rva'],body['bytes'])
        _require(type(raw) is bytes and raw==bytes.fromhex(body['raw_hex']),
                 'XP2 native map code differs: '+body['name'])
    for slot,target in (*selected.slots,(0x18,selected.name_getter_rva)):
        _require(read(base+selected.vtable_rva+slot,8)==struct.pack('<Q',base+target),
                 'XP2 native map dispatch differs')


def source_dependencies():
    proof=source()
    return {str(resolve_path(resource_root()/name).resolve()):sha for name,sha in
            (SOURCE,*[(row['path'],row['sha256']) for row in proof['references']])}
