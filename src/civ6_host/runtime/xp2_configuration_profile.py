"""Static XP2 configuration metadata for the existing native owner algorithms.

This module does not allocate a provider, initialize Core or admit saved Load.
The common owner/codec selectors reuse this ABI; saved Load remains refused.
Its MAP_ROOT value pointer and embedded sentinel provider are separate owners.
"""
import hashlib
import struct
from types import MappingProxyType
import zlib

from .configuration_profiles import ConfigurationABI, _source, _body, _copy
from .saved_load_profiles import XP2_CORE_SHA256
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE=('work/host-extensions/xp2-configuration-static/xp2_configuration_source_v1.json',
        '46ddfc453e1bf0d9de7cd5509173ebad3e25cf4d208906e08701d2ab790e8387')
INITIALIZED_SOURCE=('work/host-extensions/active-list-source/source.json',
        '404cc80b6ebb63a2e95a692a85152ce4df9cebcfc4cd4a90602b4423c5708dc6')
COPY_SOURCE=('work/host-extensions/xp2-configuration-copy-static/xp2-configuration-copy-source-v1.json',
        '884114e402319b773c5922baef55f5ea8439a1c2a7cda48e849805a6a82fb8c5')
_ABI=ConfigurationABI(XP2_CORE_SHA256,0xabf080,0x99e4b0,0x99e5d0,0x99e6c0,
    0x99f570,0x99e9d0,0x99fee0,0xb8c400,0xb8c4b0,0xb8c500,0x590660,
    ((0x140,0x591660),(0x148,0x591620),(0x150,0x5915e0)),
    ((0x1e8,0x9a9a40),(0x1f0,0x99fb50),(0x1f8,0x9a98b0),(0x200,0x9a9950),
     (0x20,0x989d0),(0x138,0x9a0d30),(0x160,0x99e8f0),(0x1d8,0x84e260)),
    SOURCE[1],SOURCE[1])
_LAYOUT=MappingProxyType(dict(provider_storage_bytes=0x58,setup_offset=0xd80,
    descriptor_offset=0x80,game_value_offset=0x88,records_begin_offset=0x90,
    records_end_offset=0x98,records_capacity_offset=0xa0,records_inline_pointer_offset=0xb0,
    records_inline_offset=0xb8,record_count=64,record_stride=0x20,records_inline_bytes=0x800,
    record_index_offset=0,record_provider_offset=8,record_value_offset=0x10,record_owner_offset=0x18,
    sentinel_record_offset=0x8b8,map_descriptor_offset=0xc28,map_value_offset=0xc30,
    embedded_provider_offset=0xc38,provider_owned_flag_offset=0xc90,player_key_stride=0x44,
    map_script_key_rva=0xb8c4c8,owned_map_flags=0x05000000))
_ENTRIES=MappingProxyType(dict(inner_constructor=0x454d0,inner_destructor=0x45630,
    setup_external_constructor=0x163f60,setup_default_constructor=0x164050,
    setup_destructor=0x164120,record_vector_insert=0x164550,record_default_constructor=0x169b80,
    map_descriptor_default_constructor=0x602980,outer_initialized_getter=0x590660,
    outer_slot_140=0x591660,outer_slot_148=0x591620,outer_slot_150=0x5915e0))


def _prior(proof):
    return {name:_source((ref['path'],ref['sha256'])) for name,ref in proof['prior_sources'].items()}


def _fragments(body):
    """Preserve the older CFG extent classification instead of inventing a body."""
    if 'blocks' in body:
        if (body['reachable_graph_complete_within_bounds'] is not True
                or body['full_function_body_proven'] is not False or body['unresolved_edges']):
            raise ValueError('XP2 bounded lookup/accessor CFG is not closed')
        return {'fragments':[_copy(v) for _,v in sorted(body['blocks'].items(),key=lambda p:int(p[0],16))],
                'boundary_method':'retained-bounded-reachable-CFG', 'full_function_body_proven':False}
    return _body(body)


def _all_bodies(proof,prior):
    bodies={name:_fragments(value['body']) for name,value in proof['functions'].items()}
    for name,ref in proof['retained_body_refs'].items():
        value=prior[ref['source']]
        for key in ref['keys']:value=value[key]
        bodies[name]=_fragments(value)
    return bodies


def _same_typed(value, expected):
    """Source offsets/counts must be integers, never equal-valued bool/float."""
    if isinstance(expected, (tuple,list)):
        return (isinstance(value, (tuple,list)) and len(value)==len(expected)
                and all(_same_typed(a,b) for a,b in zip(value,expected)))
    return type(value) is type(expected) and value==expected


def _initialized_source():
    source=_source(INITIALIZED_SOURCE)
    p=source['profiles'][XP2_CORE_SHA256]
    if (source['schema']!='civ6-host.expansion-active-list-source.v1'
            or source['native_execution'] is not False or source['saved_game_loaded'] is not False
            or p['image']['sha256']!=XP2_CORE_SHA256):
        raise ValueError('XP2 initialized getter source identity changed')
    body=_body(p['functions']['0x180046290'])
    rows=[(i['va'],i['text']) for f in body['fragments'] for i in f['instructions']]
    if rows!=[('0x180046290','movzx eax, byte ptr [rcx + 0x40]'),('0x180046294','ret')]:
        raise ValueError('XP2 initialized getter dependency changed')
    return source,body


def verify_source(core_sha256=XP2_CORE_SHA256):
    if type(core_sha256) is not str or core_sha256!=XP2_CORE_SHA256:
        raise ValueError('Expected exact XP2 configuration source selection')
    p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp2-configuration-source.v1'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['image']['sha256']!=XP2_CORE_SHA256 or p['image']['image_base']!=0x180000000
            or set(p['layout'])!=set(_LAYOUT)
            or any(not _same_typed(p['layout'][k],v) for k,v in _LAYOUT.items())
            or set(p['functions'])!=set(_ENTRIES)
            or any(not _same_typed(p['functions'][k]['rva'],v) for k,v in _ENTRIES.items())
            or dict(p['validation'])!={'new_function_count':12,'exact_semantic_guard_count':39,
                'all_new_instruction_bytes_match_pinned_image':True,'all_selected_slots_match_pinned_image':True}):
        raise ValueError('XP2 configuration source/layout contract changed')
    abi=p['abi']
    expected_names=set(_ABI.__dataclass_fields__)-{'application_proof_sha256','codec_proof_sha256'}
    if set(abi)!=expected_names:
        raise ValueError('XP2 configuration ABI fields changed')
    for name in expected_names:
        value=abi[name]
        if not _same_typed(value,getattr(_ABI,name)):
            raise ValueError('XP2 configuration ABI changed: '+name)
    prior=_prior(p)
    for name in ('owner','lookup','keys','records','initializers'):
        if prior[name]['native_execution'] is not False or prior[name]['image']['sha256']!=core_sha256:
            raise ValueError('Historical XP2 configuration source identity changed')
    keys=prior['keys']['globals'];map_key=prior['map']['map_root_key'];records=prior['records']['derived_layout']
    if (keys['game_root_key_hash_rva'].lower()!=hex(_ABI.root_key_rva)
            or keys['player_key_hash_table_rva'].lower()!=hex(_ABI.player_key_table_rva)
            or keys['player_key_count']!=64 or keys['player_key_stride_bytes']!=0x44
            or keys['map_script_key_hash_rva'].lower()!=hex(_LAYOUT['map_script_key_rva'])
            or map_key['global_rvas']['xp2'].lower()!=hex(_ABI.map_key_rva)
            or map_key['hash_helper_normalized_shapes_equal_base_xp1_xp2'] is not True
            or map_key['crc_loop_raw_bytes_equal_base_xp1_xp2'] is not True
            or map_key['raw_hash'].lower()!='0x7dd11279'
            or records['map_root_descriptor']['result_value_offset'].lower()!='0xc30'
            or records['normalized_map_candidate']['offset'].lower()!='0xc38'):
        raise ValueError('XP2 keys, MAP_ROOT and embedded provider source joins differ')
    player_keys=p['player_keys']
    if len(player_keys)!=64:raise ValueError('XP2 PLAYER key family is incomplete')
    for index,row in enumerate(player_keys):
        name='PLAYER_'+str(index)
        expected={'index':index,'name':name,'hash':zlib.crc32(name.encode('ascii'))^0xffffffff}
        if set(row)!=set(expected) or any(not _same_typed(row[k],v) for k,v in expected.items()):
            raise ValueError('XP2 PLAYER key differs from the source-shared CRC/name')
    bodies=_all_bodies(p,prior)
    for name,guards in p['semantic_guards'].items():
        rows={i['va']:i['text'] for f in bodies[name]['fragments'] for i in f['instructions']}
        if any(rows.get(va)!=text for va,text in guards.items()):
            raise ValueError('XP2 storage/lifetime semantic guard differs: '+name)
    initialized_rows={i['va']:i['text'] for f in bodies['outer_initialized_getter']['fragments']
                      for i in f['instructions']}
    if initialized_rows.get('0x18059066d')!='call 0x180046290':
        raise ValueError('XP2 initialized getter no longer calls the profiled dependency')
    _initialized_source()
    return p


def candidate_abi(core_sha256=XP2_CORE_SHA256):
    """Canonical configuration owner ABI; not an XP2 saved-Load admission."""
    verify_source(core_sha256)
    return _ABI


def configuration_layout(core_sha256=XP2_CORE_SHA256):
    verify_source(core_sha256)
    return _LAYOUT


def application_source(core_sha256=XP2_CORE_SHA256):
    """Same source dictionary consumed by native_application_configuration."""
    p=verify_source(core_sha256);prior=_prior(p);bodies=_all_bodies(p,prior)
    aliases={'provider_constructor':'provider_constructor','provider_base_constructor':'provider_base_constructor',
        'provider_destructor':'provider_non_deleting_destructor','provider_assign':'provider_assign',
        'provider_copy':'provider_copy','variant_clone_construct':'variant_clone_construct',
        'variant_clone_assign':'variant_clone_assign','variant_release':'variant_release'}
    functions={name:bodies['owner.'+target] for name,target in aliases.items()}
    functions['lookup']=bodies['lookup.xp2_provider_lookup_slot_58']
    extra=tuple(k for k in p['functions'] if k.startswith('outer_'))
    functions.update({name:bodies[name] for name in extra})
    functions['inner_initialized_getter']=_initialized_source()[1]
    extra+=('inner_initialized_getter',)
    return dict(core_functions=functions,additional_live_names=extra,player_keys=_copy(p['player_keys']),
                source_sha256=SOURCE[1],game_load_admitted=False)


def codec_source(core_sha256=XP2_CORE_SHA256):
    """Selected codec guards, matching the existing shared codec-source shape."""
    p=verify_source(core_sha256);bodies=_all_bodies(p,_prior(p))
    names={0x1e8:'codec_read',0x1f0:'codec_write',0x1f8:'codec_dependency_0x1f8',
        0x200:'codec_dependency_0x200',0x20:'allocator_getter',0x138:'dependency_0x138',
        0x160:'provider_clear',0x1d8:'dependency_0x1d8'}
    return dict(images={'core':_copy(p['image'])},captures={'core':{
        'provider_slot_'+hex(slot):bodies['owner.'+name] for slot,name in names.items()}},
        source_sha256=SOURCE[1],game_load_admitted=False)


def _copy_document():
    proof=_source(COPY_SOURCE)
    expected=dict(outer_vtable_rva=0xa101e8,outer_slot=0x120,wrapper_rva=0x591740,
        inner_copy_rva=0x469d0,setup_offset=0xd80,provider_assign_slot=0x1d0,
        provider_assign_rva=0x99e6c0,record_count=64,record_stride=0x20,
        map_value_offset=0xc30,embedded_provider_offset=0xc38,game_initialized_rva=0x63da20,
        calling_convention='Windows x64',arguments=['outer pointer RCX','source provider B pointer RDX'],
        return_value='void, not interpreted')
    if (proof['schema']!='civ6-host.xp2-configuration-copy-source.v1'
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or proof['image']['sha256']!=XP2_CORE_SHA256
            or set(proof['abi'])!=set(expected)
            or any(not _same_typed(proof['abi'][k],v) for k,v in expected.items())
            or proof['validation']['all_instruction_bytes_match_pinned_image'] is not True):
        raise ValueError('XP2 configuration copy source/ABI differs')
    return proof


def context_copy_source(profile):
    """Bodies for the shared Load owner's +120 copy, not admission to Load."""
    if profile is not _ABI.load:
        raise ValueError('XP2 configuration copy requires its canonical saved-Load profile')
    verify_source()
    proof=_copy_document()
    refs={name:_source((ref['path'],ref['sha256'])) for name,ref in proof['source_refs'].items()}
    bodies={name:_fragments(body) for name,body in proof['functions'].items()}
    for name,ref in proof['function_refs'].items():
        value=refs[ref['source']]
        for key in ref['keys']:value=value[key]
        bodies[name]=_fragments(value)
    for name,guards in proof['semantic_guards'].items():
        rows={i['va']:i['text'] for f in bodies[name]['fragments'] for i in f['instructions']}
        if any(rows.get(va)!=text for va,text in guards.items()):
            raise ValueError('XP2 native copy/relink semantic guard differs: '+name)
    if len(bodies)!=14 or set(proof['functions'])!={'ensure_game_root'}:
        raise ValueError('XP2 copy/relink source closure changed')
    return bodies


def source_dependencies():
    """Pin every directly consumed source and the supplement's capture script."""
    p=verify_source();pins={}
    copy=_copy_document();context_copy_source(_ABI.load)
    initialized,_=_initialized_source()
    for ref in ({'path':SOURCE[0],'sha256':SOURCE[1]},*p['prior_sources'].values(),p['capture_script'],
                {'path':INITIALIZED_SOURCE[0],'sha256':INITIALIZED_SOURCE[1]},*initialized['source_refs'],
                {'path':COPY_SOURCE[0],'sha256':COPY_SOURCE[1]},*copy['source_refs'].values(),copy['capture_script']):
        path=resolve_path(resource_root()/ref['path']).resolve()
        with path.open('rb') as stream:actual=hashlib.file_digest(stream,'sha256').hexdigest()
        if actual!=ref['sha256']:raise ValueError('XP2 configuration source changed: '+str(path))
        if str(path) in pins and pins[str(path)]!=actual:raise ValueError('XP2 configuration source pin conflict')
        pins[str(path)]=actual
    return pins


def verify_live(core_base,read):
    """Optional pure-read code/slot guard; never constructs or invokes a provider."""
    if type(core_base) is not int or not 0<core_base<(1<<63) or not callable(read):
        raise ValueError('Exact XP2 module/read binding required')
    p=verify_source();bodies=_all_bodies(p,_prior(p));count=0
    bodies['inner_initialized_getter']=_initialized_source()[1]
    for name,body in bodies.items():
        for fragment in body['fragments']:
            for row in fragment['instructions']:
                raw=bytes.fromhex(row['bytes']);rva=int(row['va'],16)-0x180000000
                if not raw or not 0<=rva<0x1000000 or bytes(read(core_base+rva,len(raw)))!=raw:
                    raise ValueError('XP2 configuration instruction mismatch: '+name)
                count+=1
    for row in p['slots']:
        if bytes(read(core_base+row['table_rva']+row['offset'],8))!=struct.pack('<Q',core_base+row['target_rva']):
            raise ValueError('XP2 configuration virtual slot mismatch')
    return dict(core_sha256=XP2_CORE_SHA256,source_sha256=SOURCE[1],instruction_guards=count,
                native_execution=False,game_load_admitted=False)
