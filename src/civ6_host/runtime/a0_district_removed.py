"""Expansion district-removal query lease, reusing the retained EXE record codec.

An actual NULL player/item is a native branch, never a fallback. Presentation
payload padding on that branch is admitted only by the codec's explicit empty
receiver policy. This module does not make a loaded session playable.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes as C
import struct
from types import MappingProxyType

from .configuration_profiles import _source,_body,XP1_CORE_SHA256,XP2_CORE_SHA256
from .a0_family_source import A0FamilyProfile,_path,verify_pinned_files,verify_extracted_sources
from .native import native_event_fdf12323 as codec

SOURCE=('work/host-extensions/xp1-district-removed-static/xp1-district-removed-source-v1.json',
        '2b9a17b99ddc13ba3a83cfc5f46a07df8e91c630b83d0234854cdd099f98530f')
ENTRIES={'get_player':0x4bd1a0,'release_player':0x4c6a80,'player_collection':0x4c6f90,
 'release_collection':0x4c8f50,'collection_index':0x4c8f70,'release_item':0x4c2f30,
 'item_variant':0x4c2f70,'item_raw':0x4baaf0}
TABLES={'outer':(0x8a8df0,((0xb8,0x4bd1a0),)),
 'player':(0x8aa2c8,((8,0x4c6a80),(0x130,0x4c6f90))),
 'collection':(0x8aa720,((8,0x4c8f50),(0x10,0x4c8f70))),
 'item':(0x8a9948,((8,0x4c2f30),(0x20,0x4baaf0),(0x30,0x4c2f70)))}
PROFILE=dict(normalizer_transform_present=False,per_thread_hook_present=False,
             writer_metadata_callback_present=False,padding_policy='headless-zero-uninitialized-stack')


def source(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_district_removed_source import source as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown district query engine')
    p=_source(SOURCE)
    tables={k:(v[0],tuple(tuple(r) for r in v[1])) for k,v in p['profile']['tables'].items()}
    if (p['schema']!='civ6_host.xp1_district_removed.static.v1'
            or p['images']['xp1']['sha256']!=XP1_CORE_SHA256
            or p['images']['exe']['sha256']!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or (p['profile']['kind'],p['profile']['record_type'],p['profile']['record_size'])!=(codec.EVENT_KIND,0xa0,128)
            or dict(p['profile']['entries'])!=ENTRIES or tables!=TABLES
            or p['validation']['instruction_bytes_match_pinned_images'] is not True
            or p['validation']['native_execution'] is not False
            or p['profile']['preexisting_cache_owners_required'] is not False
            or p['profile']['receiver_payload_read_under_empty_profile'] is not False):
        raise ValueError('XP1 district-removal source/profile differs')
    for ref in p['references'].values():_source((ref['path'],ref['sha256']))
    codec.verify_source_evidence()
    return p


def source_dependencies(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_district_removed_source import source_dependencies as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown district query engine')
    p=source();refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),*p['references'].values(),*p['source_pins'].values()]
    return {str(_path(r['path'])):r['sha256'] for r in refs}


def event_profile(core_sha256=XP1_CORE_SHA256):
    p=source(core_sha256);verify_pinned_files(source_dependencies(core_sha256));verify_extracted_sources(p['source_pins'].values())
    from .native.native_deferred_empty_profile import _ROWS
    row=_ROWS[0xa0]
    if row['handler_va']!='0x1400d9af0' or set(row['record_sizes'])!={128}:
        raise ValueError('DistrictRemoved empty receiver differs')
    return A0FamilyProfile(MappingProxyType({codec.EVENT_KIND:frozenset((0xa0,))}),
                           MappingProxyType({0xa0:128}),_binding(core_sha256)[2][1])


def _binding(core_sha256):
    if core_sha256==XP1_CORE_SHA256:return ENTRIES,TABLES,SOURCE
    if core_sha256==XP2_CORE_SHA256:
        from . import xp2_district_removed_source as selected
        return selected.ENTRIES,selected.TABLES,selected.SOURCE
    raise ValueError('Unknown district query engine')


def verify_live(base,context,read,*,core_sha256):
    _,tables,ref=_binding(core_sha256);p=source(core_sha256)
    for name,body in p['bodies' if core_sha256==XP2_CORE_SHA256 else 'functions'].items():
        for f in _body(body)['fragments']:
            for row in f['instructions']:
                raw=bytes.fromhex(row['bytes'])
                if read(base+int(row['va'],16)-0x180000000,len(raw))!=raw:
                    raise ValueError('District query native body differs: '+name)
    for table,slots in tables.values():
        for slot,target in slots:
            if read(base+table+slot,8)!=struct.pack('<Q',base+target):
                raise ValueError('District query virtual target differs')
    _check(read,base,context,'outer',tables=tables)
    return dict(source_sha256=ref[1],native_queries_executed=False)


def _check(read,base,pointer,label,*,tables=TABLES):
    if type(pointer) is not int or pointer<=0:raise ValueError('Missing district query '+label+' facade')
    table,slots=tables[label]
    if read(pointer,8)!=struct.pack('<Q',base+table):raise ValueError('Unknown district query '+label+' facade')
    for slot,target in slots:
        if read(base+table+slot,8)!=struct.pack('<Q',base+target):
            raise ValueError('Unknown district query '+label+' method')
    if label!='outer':
        raw=read(pointer+8,20)
        if type(raw) is not bytes or len(raw)!=20:raise ValueError('Incomplete district wrapper')
        live,cache,count=struct.unpack('<QQI',raw)
        if not live or cache or count!=1:raise ValueError('District query requires a live uniquely retained '+label)


def _api(base,native_api,*,entries=ENTRIES):
    signatures={'get_player':(C.c_void_p,(C.c_void_p,C.c_int32)),
      'release_player':(None,(C.c_void_p,)),'player_collection':(C.c_void_p,(C.c_void_p,)),
      'release_collection':(None,(C.c_void_p,)),'collection_index':(C.c_void_p,(C.c_void_p,C.c_uint32)),
      'release_item':(None,(C.c_void_p,)),'item_variant':(C.c_void_p,(C.c_void_p,C.c_void_p)),
      'item_raw':(C.c_uint32,(C.c_void_p,))}
    if native_api is not None:
        if type(native_api) is not dict or set(native_api)!=set(signatures) or any(not callable(f) for f in native_api.values()):
            raise ValueError('District query test seam requires eight exact operations')
        return native_api
    return {name:C.WINFUNCTYPE(result,*args)(base+entries[name]) for name,(result,args) in signatures.items()}


@contextmanager
def record_lease(sequence,core,context,fields,*,read,empty_receiver_state,query_diagnostic,native_api=None,core_sha256=XP1_CORE_SHA256):
    codec._profile(sequence,fields,**PROFILE)
    if type(query_diagnostic) is not dict:raise ValueError('District query diagnostic must be explicit')
    base=int(core._handle)
    if base<=0:raise ValueError('Missing district query core')
    entries,tables,ref=_binding(core_sha256)
    _check(read,base,context,'outer',tables=tables);api=_api(base,native_api,entries=entries)
    def encode(values):
        record=codec.encode_record(sequence,fields,values,**PROFILE,empty_receiver_state=empty_receiver_state,
                                   missing_item_policy='zero-unread-item-DWORD')
        query_diagnostic.update(item_present=values.item_present,read_skipped_reason=values.read_skipped_reason,
            native_item_queries_executed=values.item_present,native_player_query_executed=True,
            native_null_result_observed=not values.item_present,
            raw_dword_origin='native-query' if values.item_present else 'uninitialized-stack-zero-unread-policy',
            source_sha256=ref[1])
        return record
    def missing(reason):return encode(codec.NativeValues(bytes.fromhex('ffff0000ffffffff'),0,False,reason))
    item=0;checked=False
    try:
        player=api['get_player'](context,fields.owner)
        if not player:
            yield missing('player-null');return
        _check(read,base,player,'player',tables=tables)
        try:
            collection=api['player_collection'](player)
            _check(read,base,collection,'collection',tables=tables)
            try:item=api['collection_index'](collection,fields.item_id)
            finally:api['release_collection'](collection)
        finally:api['release_player'](player)
        if not item:
            yield missing('item-null');return
        _check(read,base,item,'item',tables=tables);checked=True
        variant=codec.shared._out8(api['item_variant'],item)
        raw=api['item_raw'](item)
        yield encode(codec.NativeValues(variant,raw))
    finally:
        if checked:api['release_item'](item)


def dispatch(owner,kind,raw_fields):
    if kind!=codec.EVENT_KIND:raise ValueError('Unknown DistrictRemoved event kind')
    if len(owner.pending)>=owner.limit:raise RuntimeError('Native deferred queue bound exceeded')
    fields=codec.decode_fields(raw_fields,owner.read);diagnostic={}
    with record_lease(owner._sequence+1,owner.deferred.core,owner.deferred.context,fields,
            read=owner.read,empty_receiver_state=owner.empty_receiver_state,query_diagnostic=diagnostic,
            core_sha256=owner.deferred.cache_core_sha256) as record:
        owner._enqueue(record)
    owner.emit('native_deferred_host_event_enqueued',dispatch_kind=hex(kind),queue_type='0xa0',
        record_hex=record.hex(),owner=fields.owner,item_id=fields.item_id,pending_count=len(owner.pending),
        **diagnostic,retained_item_released=diagnostic['item_present'],
        retained_sources_live_at_enqueue=diagnostic['item_present'],unspecified_padding_policy='zero',
        consumer_validated=False,eligible_for_training=False,native_dispatch_return=0)
    return 0
