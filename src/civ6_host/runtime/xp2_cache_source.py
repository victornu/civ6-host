"""Exact XP2 cache source selection; no public or native-run admission."""
from __future__ import annotations
import hashlib
import struct
from .configuration_profiles import _source
from .saved_load_profiles import XP2_CORE_SHA256

SOURCE=('work/host-extensions/xp2-cache-services/source-profile-v1.json','b8beb461d61621747584a93ea5cb118d31c3b049daf4d951c516d375b984f660')

def source():
    p=_source(SOURCE)
    if (p['schema']!='civ6_host.xp2_cache_services.static.v1'
            or p['image']['sha256']!=XP2_CORE_SHA256
            or p['profile']['core_sha256']!=XP2_CORE_SHA256
            or p['profile']['full_refresh_admitted'] is not False
            or p['validation']['instruction_bytes_match'] is not True
            or p['validation']['native_execution'] is not False
            or p['validation']['public_admission'] is not False):
        raise ValueError('XP2 cache source identity differs')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    for row in p['references'].values():
        path=resolve_path(resource_root()/row['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('XP2 cache source dependency differs: '+row['path'])
    return p

def source_dependencies():
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p=source();rows=[dict(path=SOURCE[0],sha256=SOURCE[1]),*p['references'].values()]
    from .xp2_preload_source import source_pins as preload_dependencies
    # The same exact event-map guards/dispatcher are reused, including all
    # referenced source captures, rather than treating an outer hash as closure.
    result=preload_dependencies()
    result.update({str(resolve_path(resource_root()/r['path']).resolve()):r['sha256'] for r in rows})
    return result

def bodies(proof=None):
    p=source() if proof is None else proof
    for name,fn in p['functions'].items():
        yield name,fn['body']
        for index,tail in enumerate(fn['out_of_line_tail_jumps']):
            yield name+':tail:'+str(index),tail['body']

def verify_live(base,read,proof=None):
    p=source()
    if proof is not None and proof!=p:raise ValueError('Foreign XP2 cache source proof')
    for name,body in bodies(p):
        for f in body['fragments']:
            for row in f['instructions']:
                raw=bytes.fromhex(row['bytes'])
                rva=int(row['rva'],16) if 'rva' in row else int(row['va'],16)-0x180000000
                if read(base+rva,len(raw))!=raw:raise ValueError('XP2 cache instructions differ: '+name)
    for row in p['slots']:
        if read(base+row['vtable_rva']+row['slot'],8)!=struct.pack('<Q',base+row['target_rva']):
            raise ValueError('XP2 cache virtual target differs: '+row['name'])
    return p
