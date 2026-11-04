"""Exact XP2 bindings for the shared DistrictRemoved query and record lease."""
import hashlib
from .configuration_profiles import _source,XP2_CORE_SHA256

SOURCE=('work/host-extensions/xp2-district-removed-static/source-profile-v1.json',
        'a6b0bbf07a87acc794b381874613395d9356a4f0f636abbf4dadd57eac535e8f')
ENTRIES=dict(get_player=0x590360,release_player=0x59c8c0,player_collection=0x59cdd0,
    release_collection=0x59ed80,collection_index=0x59edb0,release_item=0x596570,
    item_variant=0x5965b0,item_raw=0x58da90)
TABLES=dict(outer=(0xa101e8,((0xb8,ENTRIES['get_player']),)),
    player=(0xa11a80,((8,ENTRIES['release_player']),(0x130,ENTRIES['player_collection']))),
    collection=(0xa11ed8,((8,ENTRIES['release_collection']),(0x10,ENTRIES['collection_index']))),
    item=(0xa10d98,((8,ENTRIES['release_item']),(0x20,ENTRIES['item_raw']),(0x30,ENTRIES['item_variant']))))


def source():
    from .native import native_event_fdf12323 as codec
    p=_source(SOURCE);c=p['profile']
    tables={k:(v[0],tuple(tuple(row) for row in v[1])) for k,v in c['tables'].items()}
    if (p['schema']!='civ6-host.xp2-district-removed.source.v1'
            or p['native_execution'] is not False or p['core_sha256']!=XP2_CORE_SHA256
            or p['exe_sha256']!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or dict(c['entries'])!=ENTRIES or tables!=TABLES
            or (c['kind'],c['record_type'],c['record_size'])!=(codec.EVENT_KIND,0xa0,128)
            or (c['wrapper_size'],c['live_offset'],c['cache_offset'],c['refcount_offset'])!=(32,8,16,24)
            or (c['game_unload_rva'],c['unload_flag_clear_rva'],c['player_teardown_call_rva'])!=(0x63e160,0x63e182,0x63e262)
            or c['native_null_not_substituted'] is not True
            or c['preexisting_cache_owners_required'] is not False
            or c['receiver_payload_read_under_empty_profile'] is not False
            or c['cache_only_wrappers_refused'] is not True
            or c['null_collection_refused'] is not True
            or c['only_district_removed_admitted'] is not True):
        raise ValueError('XP2 district-removal source/ownership differs')
    # Capture native differences explicitly: Player+6E8, larger teardown
    # allocations, and additional engine-internal producer work after HOST A0.
    same={'get_player','release_player','release_collection','collection_index','release_item',
          'item_variant','item_raw','generic_emitter','descriptor','game_initialized',
          'player_constructor','collection_constructor','item_constructor','item_city_id','item_city_owner'}
    if {name for name,row in p['comparisons'].items() if row['normalized_instructions_equal']}!=same:
        raise ValueError('XP2 district comparison inventory differs')
    instructions={}
    for name,b in p['bodies'].items():
        parts=[]
        for f in b['fragments']:
            raw=bytes.fromhex(f['raw_hex']);parts.append(raw)
            if (len(raw)!=f['length'] or hashlib.sha256(raw).hexdigest()!=f['sha256']
                    or ''.join(i['bytes'] for i in f['instructions'])!=raw.hex()):
                raise ValueError('XP2 district fragment differs: '+name)
            instructions.update({i['rva']:i['text'] for i in f['instructions']})
        raw=b''.join(parts)
        if (raw.hex()!=b['raw_hex'] or hashlib.sha256(raw).hexdigest()!=b['sha256']
                or b['all_conditional_targets_captured'] is not True
                or b['boundary_method'] not in ('complete-runtime-function-chained-unwind-root-v2',
                                               'complete-reachable-leaf-cfg-v1')):
            raise ValueError('XP2 district complete body differs: '+name)
    if any(instructions.get(rva)!=text for rva,text in p['instruction_guards'].items()):
        raise ValueError('XP2 district producer/Unload instruction join differs')
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    codec.verify_source_evidence()
    return p


def source_dependencies():
    from .a0_family_source import _path,verify_pinned_files
    p=source();refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),*p['references'],*p['source_pins'].values(),
        *(p[k] for k in ('generator','boundary_helper','extractor','witness')),
        p['retained_xp1_interval']['events'],p['retained_xp1_interval']['qualification']]
    pins={str(_path(r['path'])):r['sha256'] for r in refs};verify_pinned_files(pins)
    return pins
