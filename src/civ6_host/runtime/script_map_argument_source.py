"""Native event-map ownership and recursive A8 conversion source boundary."""
import hashlib
import struct

from .configuration_profiles import _source, _body, BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE=('work/host-extensions/script-map-argument-static/script-map-argument-source-v1.json',
        '87c26e72896a0dad150a24a7c6a92f45f1e58f18a4f66d97bff9c9073b68f9c4')


def source():
    proof=_source(SOURCE)
    owner=proof['contract']['xp1_native_owner']
    if (proof['schema']!='civ6_host.script_map_argument_static.v1'
            or proof['images']['xp1']['sha256']!=XP1_CORE_SHA256
            or proof['native_execution'] is not False
            or owner['source_kind']!=2 or owner['storage_size']!=0x58
            or owner['existing_assign_rva']!='0x84b5d0'
            or owner['destructor_rva']!='0x844580'):
        raise ValueError('Map argument source contract differs')
    for value in proof['references'].values():
        if hashlib.sha256(resolve_path(resource_root()/value['path']).read_bytes()).hexdigest()!=value['sha256']:
            raise ValueError('Map argument source dependency differs: '+value['path'])
    return proof


def source_for_core(core_sha256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_aux_map_profile import source as xp2_source
        return xp2_source()
    if core_sha256 in (BASE_CORE_SHA256,XP1_CORE_SHA256):
        return source()
    raise ValueError('Unknown nested-map source engine')


def verify_xp2(base,read):
    from .xp2_aux_map_profile import profile,verify_live,SOURCE as xp2_source
    verify_live(profile(),base,read)
    return dict(source_sha256=xp2_source[1],core_sha256=XP2_CORE_SHA256,native_execution=False)


def live_bodies(proof):
    bodies=dict(proof['functions']['xp1'])
    references={}
    ref=proof['references']['aux_maps']
    aux=_source((ref['path'],ref['sha256']))
    bodies['source_kind_getter']=aux['functions']['xp1']['map_kind']
    for name,row in proof['referenced_bodies'].items():
        if row['image']!='xp1':continue
        ref=proof['references'][row['reference']]
        if row['reference'] not in references:
            references[row['reference']]=_source((ref['path'],ref['sha256']))
        body=references[row['reference']]
        for key in row['selector']:body=body[key]
        bodies[name]=body
    return bodies


def verify_xp1(base,read):
    if type(base) is not int or not 0<base<(1<<63):raise ValueError('Invalid map argument module')
    proof=source()
    for name,body in live_bodies(proof).items():
        for fragment in _body(body)['fragments']:
            for instruction in fragment['instructions']:
                raw=bytes.fromhex(instruction['bytes'])
                if read(base+int(instruction['va'],16)-0x180000000,len(raw))!=raw:
                    raise ValueError('Native map argument code differs: '+name)
    owner=proof['contract']['xp1_native_owner'];vtable=base+int(owner['source_vtable_rva'],16)
    for slot,target in owner['required_slots'].items():
        if read(vtable+int(slot,16),8)!=struct.pack('<Q',base+int(target,16)):
            raise ValueError('Native map argument provider slot differs')
    return {'source_sha256':SOURCE[1],'core_sha256':XP1_CORE_SHA256,'native_execution':False}
