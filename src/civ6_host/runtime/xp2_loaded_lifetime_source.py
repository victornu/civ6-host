"""Source selection for the private XP2 raw-Load shutdown boundary."""
import hashlib
from .configuration_profiles import XP2_CORE_SHA256, _source

SOURCE=('work/host-extensions/xp2-loaded-lifecycle/raw-lifetime-source-v1.json',
        '357e08175d71d9d01b0788b6d8fee692055d0f10e48289737ca1f347f173485d')
SLOTS={'0xa101e8+0x48':'0x591860','0xa44f70+0x58':'0x46a10',
    '0xa44f70+0x10':'0x470b0','0xa44f70+0x0':'0x45960',
    '0xa45160+0x0':'0x750630','0xa45160+0x48':'0x502e0'}

def fragments(p):
    for name,b in p['bodies'].items():
        parts=[]
        for f in b['fragments']:
            raw=bytes.fromhex(f['raw_hex']);parts.append(raw)
            if (len(raw)!=f['length'] or hashlib.sha256(raw).hexdigest()!=f['sha256']
                    or ''.join(r['bytes'] for r in f['instructions'])!=raw.hex()):
                raise ValueError('XP2 lifetime source fragment differs: '+name)
            yield name,int(f['start_rva'],16),raw
        raw=b''.join(parts)
        if (len(raw)!=b['bytes'] or raw.hex()!=b['raw_hex']
                or hashlib.sha256(raw).hexdigest()!=b['sha256']
                or b['all_conditional_targets_captured'] is not True
                or b['boundary_method'] not in ('complete-runtime-function-chained-unwind-root-v2',
                                               'complete-reachable-leaf-cfg-v1')):
            raise ValueError('XP2 lifetime complete source body differs: '+name)

def source():
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp2-raw-loaded-lifetime.source.v1'
            or p['native_execution'] is not False or p['core_sha256']!=XP2_CORE_SHA256
            or dict(p['slots'])!=SLOTS):
        raise ValueError('XP2 lifetime source identity differs')
    c=p['contract']
    if (c['unload_target_rva']!=0x591860 or c['inner_unload_rva']!=0x46a10
            or c['game_deleting_destructor_rva']!=0x750630 or c['game_destructor_rva']!=0x63ba90
            or c['clear_script_contexts_rva']!=0x5fe1c0
            or tuple(c['unloaded_inner_zero_offsets'])!=(0x60,0x1a68)
            or tuple(c['unloaded_zero_global_rvas'])!=(0xb8aa68,0xb8aa70,0xb8b298,0xb90710)
            or tuple(c['destroyed_zero_global_rvas'])!=(0xb8aa80,0xb8aa88,0xb8aa90,0xb8aa68,0xb8aa70,0xb90710)
            or not c['raw_load_only'] or not c['unload_before_destroy']
            or c['post160_called'] is not False or c['cache_wrappers_present'] is not False
            or c['public_loaded_lifetime_admitted'] is not False):
        raise ValueError('XP2 raw lifetime contract differs')
    list(fragments(p))
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    for name in ('generator','boundary_helper','extractor'):
        ref=p[name];actual=resolve_path(resource_root()/ref['path'])
        if hashlib.sha256(actual.read_bytes()).hexdigest()!=ref['sha256']:
            raise ValueError('XP2 lifetime capture dependency differs')
    return p

def verify_live(b):
    from .xp1_loaded_lifetime import _q
    p=source();base=b.core._handle;read=b.runtime.read
    for name,rva,raw in fragments(p):
        if read(base+rva,len(raw))!=raw:raise ValueError('XP2 lifetime code differs: '+name)
    for key,target in p['slots'].items():
        vt,slot=(int(x,16) for x in key.split('+'))
        if _q(read,base+vt+slot)!=base+int(target,16):
            raise ValueError('XP2 lifetime native dispatch differs')
    return p


def postload_source_dependencies():
    """Close the retained raw teardown source over exact postload owners."""
    from .xp1_loaded_lifetime import source_dependencies
    from .xp2_postload_aux90_source import source_dependencies as aux90_dependencies
    from .xp2_postload_source import source_dependencies as post160_dependencies
    from .xp2_cache_source import source_dependencies as cache_dependencies
    from .loaded_cache_publication import source_dependencies as loaded_cache_dependencies
    pins = source_dependencies(XP2_CORE_SHA256)
    for group in (aux90_dependencies(), post160_dependencies(), cache_dependencies(),
                  loaded_cache_dependencies(core_sha256=XP2_CORE_SHA256)):
        for path, digest in group.items():
            previous = pins.get(path)
            if previous is not None and previous != digest:
                raise ValueError('Conflicting XP2 postload lifetime source pin: ' + path)
            pins[path] = digest
    return pins


def verify_postload_live(backend):
    """Recheck shared XP2 teardown plus source-selected populated-cache code."""
    lifetime_proof = verify_live(backend)
    from .xp2_postload_source import source as post160_source, verify_live as verify_post160_live
    post160 = post160_source()
    verify_post160_live(backend.core._handle, backend.runtime.read, post160,
                        core_sha256=XP2_CORE_SHA256)
    from .xp2_cache_source import source as cache_source, verify_live as verify_cache_live
    cache = cache_source()
    verify_cache_live(backend.core._handle, backend.runtime.read, cache)
    from .loaded_cache_profiles import loaded_cache_abi,verify_live as verify_loaded_cache_live
    cache_abi=loaded_cache_abi(XP2_CORE_SHA256)
    loaded_cache=verify_loaded_cache_live(backend.core._handle,backend.runtime.read,
        core_sha256=XP2_CORE_SHA256)
    dependencies = postload_source_dependencies()
    return dict(contract=lifetime_proof['contract'],
        raw_lifetime=lifetime_proof, post160=post160, cache=cache,
        loaded_cache_abi=cache_abi, loaded_cache=loaded_cache,
        source_dependencies=dependencies, native_calls_made=False,
        saved_load_admitted=False)
