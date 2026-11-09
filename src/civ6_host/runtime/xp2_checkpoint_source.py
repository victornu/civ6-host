"""Exact XP2 Save source for the existing owner/stream; no runtime admission.

This selects existing native serializers. It supplies no substitute bytes,
callbacks, rule state, scheduler, or saved-Load implementation.
"""
from collections.abc import Mapping
import hashlib
from pathlib import Path
import struct

from .configuration_profiles import XP2_CORE_SHA256, _source

SOURCE=('work/host-extensions/xp2-checkpoint-preparation-static/source-profile-v1.json',
        '3f84973236fda9d3c022d140d21ca081d1f5104565de238ac9c9f6aab148150f')
SUPPLEMENT=('work/host-extensions/xp2-checkpoint-preparation-static/dependency-supplement-v1.json',
            '4d216b3bf954eeb43e803fbb7468aae74a1969cbf35dd5821f924ff91cf3bd8f')
RULES=('work/host-extensions/xp2-checkpoint-preparation-static/rules-delegate-supplement-v1.json',
       'e6074e9882595d9dfb8aaad7f5c71129d7329bccdf42d9ab21e0998f812c2ef5')
EXE_SHA256='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
BASE=0x180000000


def _rows(body):
    result=[]
    for fragment in body['fragments']:
        for value in fragment['instructions']:
            row=dict(value)
            row['va']=row['va'] if 'va' in row else hex(BASE+int(row['rva'],16))
            if not bytes.fromhex(row['bytes']):raise ValueError('Empty XP2 Save instruction')
            result.append(row)
    if not result or sum(len(bytes.fromhex(r['bytes'])) for r in result)!=body['total_length']:
        raise ValueError('Incomplete XP2 Save source body')
    return result


def verify_source(core_sha256=XP2_CORE_SHA256):
    if core_sha256!=XP2_CORE_SHA256:raise ValueError('Exact XP2 checkpoint source required')
    p,s,r=(_source(ref) for ref in (SOURCE,SUPPLEMENT,RULES))
    if (p['schema']!='civ6-host.xp2-checkpoint.static.v1'
            or p['image']['sha256']!=core_sha256 or p['exe']['sha256']!=EXE_SHA256
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['validation']['all_instruction_bytes_match_image'] is not True
            or p['tables']['outer']!={'rva':'0xa101e8','slots':{'0x38':0x590660,'0x168':0x5916e0,'0x170':0x5906e0}}
            or p['tables']['inner']!={'rva':'0xa44f70','slots':{'0x70':0x463b0,'0x78':0x472c0,'0xc0':0x462a0}}
            or s['schema']!='civ6-host.xp2-checkpoint.dependencies.v1'
            or s['image']['sha256']!=core_sha256 or s['source']['sha256']!=SOURCE[1]
            or r['schema']!='civ6-host.xp2-checkpoint.rules-delegate.v1'
            or r['image']['sha256']!=core_sha256 or r['previous']['sha256']!=SUPPLEMENT[1]
            or r['global_rva']!='0xb8e298' or r['vtable_rva']!='0x9f31f0'
            or r['slots']!={'0x18':0x37ae80,'0x40':0x37b3c0}
            or any(v['native_execution'] is not False or v['process_memory_read'] is not False for v in (s,r))):
        raise ValueError('XP2 checkpoint source identity or interface changed')
    for proof in (p,s,r):
        for body in proof['bodies'].values():_rows(body)
    for reference in p['references']:_source((reference['path'],reference['sha256']))
    parent=_source((p['slot_authority']['source'],p['slot_authority']['source_sha256']))
    if (parent['images']['exe']['sha256']!=EXE_SHA256
            or parent['slot_contracts']['writer_plus28']['abi']!=
                'Win64: RCX=this, RDX=const source bytes, R8=byte_length uint64; returns int32 status in EAX'):
        raise ValueError('XP2 Save lost independent EXE writer/caller authority')
    if not any(i['va']=='0x14016d42f' and i['text']=='call qword ptr [rax + 0x168]'
               for body in parent['functions'].values() for f in body.get('fragments',(body,))
               for i in f.get('instructions',())):
        raise ValueError('XP2 Save lost the actual EXE outer-slot caller')
    return p,s,r


def _exact(read,address,size):
    if type(address) is not int or address<0x10000 or address>(1<<47)-size or size<=0:
        raise ValueError('Invalid XP2 Save memory range')
    raw=read(address,size)
    if type(raw) is not bytes or len(raw)!=size:raise ValueError('Incomplete XP2 Save source read')
    return raw


def bind_source(session,read,*,core_sha256):
    p,s,r=verify_source(core_sha256)
    from .saved_load_services import SavedLoadServices
    if (type(session) is not SavedLoadServices or session.backend.prefix is not session
            or session.backend.core is not session.core or session.backend.context!=session.context
            or session.backend.load_abi.core_sha256!=core_sha256):
        raise ValueError('XP2 Save requires its actual captured service owner')
    session.backend.check_thread();session.check()
    base=session.core._handle
    q=lambda address:struct.unpack('<Q',_exact(read,address,8))[0]
    if q(session.context)!=base+0xa101e8:raise ValueError('Foreign XP2 Save context')
    inner=q(session.context+8)
    if not inner or q(inner)!=base+0xa44f70:raise ValueError('Foreign XP2 Save inner owner')
    for proof in (p,s,r):
        for body in proof['bodies'].values():
            for row in _rows(body):
                raw=bytes.fromhex(row['bytes'])
                if _exact(read,base+int(row['va'],16)-BASE,len(raw))!=raw:
                    raise ValueError('Live XP2 Save source body differs')
    for vt,slots in ((0xa101e8,p['tables']['outer']['slots']),
                     (0xa44f70,{**p['tables']['inner']['slots'],**s['tables']['inner_parameters']['slots']}),
                     (0x9c1240,s['tables']['rules_singleton']['slots']),
                     (0xa45e48,s['tables']['registered_notifications']['slots']),
                     (0x9f31f0,r['slots'])):
        for slot,target in slots.items():
            if q(base+vt+int(slot,16))!=base+target:raise ValueError('XP2 Save virtual target differs')
    for row in s['data']:
        raw=bytes.fromhex(row['raw_hex'])
        if _exact(read,base+int(row['rva'],16),len(raw))!=raw:
            raise ValueError('XP2 Save native version literal differs')
    # These are native objects selected by source producers, not host callbacks
    # inferred from their slot numbers. Never allocate or repair them here.
    native_owners={}
    for global_rva,vt in ((0xb8b298,0x9c1240),(0xb8e298,0x9f31f0)):
        instance=q(base+global_rva)
        if not instance or q(instance)!=base+vt:raise ValueError('XP2 Save native rules owner differs')
        native_owners[hex(global_rva)]=instance
    game=q(base+0xb8aa68)
    if not game or game!=q(inner+0x60):
        raise ValueError('XP2 Save native registry belongs to another Game')
    begin,end=q(game+8),q(game+0x10)
    index=struct.unpack('<I',_exact(read,base+0xb60cd0,4))[0]
    if not begin or end<begin or (end-begin)%0x120 or index>=(end-begin)//0x120:
        raise ValueError('XP2 Save notification registry item is absent or malformed')
    notification=q(begin+index*0x120)
    if not notification or q(notification)!=base+0xa45e48:
        raise ValueError('XP2 Save registry item is not the native Notifications owner')
    identity=dict(xp2_rules=native_owners['0xb8b298'],xp2_rules_delegate=native_owners['0xb8e298'],
        xp2_notification_registry=game,xp2_notification_begin=begin,xp2_notification_end=end,
        xp2_notification_index=index,xp2_notifications=notification,
        xp2_rules_scalar=struct.unpack('<I',_exact(read,native_owners['0xb8e298']+8,4))[0])
    return {'core_functions':{'save_outer':{'instructions':_rows(p['bodies']['outer_save'])},
                              'inner_save':{'instructions':_rows(p['bodies']['inner_save'])}},
            'native_owner_identity':identity}


def source_dependencies(*, execution_image=None):
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .xp2_configuration_profile import source_dependencies as configuration
    from .xp2_normalization_source import source_dependencies as normalization
    from .action_transport_profiles import source_dependencies as transport
    from .saved_load_job_observer import XP2_SOURCE
    from .xp2_cache_source import source_dependencies as cache
    p,s,r=verify_source();pins={};provenance_images=[]
    def add(reference):
        path=resolve_path(resource_root()/reference['path']).resolve(strict=True)
        digest=reference['sha256']
        if str(path) in pins:
            if pins[str(path)]!=digest:raise ValueError('Conflicting XP2 checkpoint source dependency')
            return
        if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('XP2 checkpoint dependency changed')
        pins[str(path)]=digest
    for ref in (SOURCE,SUPPLEMENT,RULES,XP2_SOURCE):add(dict(path=ref[0],sha256=ref[1]))
    for proof in (p,s,r):
        for name in ('image','exe','extractor','capture_script','source','previous'):
            if name not in proof:
                continue
            ref=proof[name]
            if execution_image is not None and name in ('image','exe'):
                if 'path' in ref and 'sha256' in ref:
                    provenance_images.append(ref)
                continue
            add(ref)
        for row in proof.get('references',()):add(row)
    for group in (configuration(),normalization(),
                  transport(core_sha256=XP2_CORE_SHA256,execution_image=execution_image),cache()):
        for path,digest in group.items():add(dict(path=path,sha256=digest))
    if execution_image is not None:
        from .runtime_source_dependencies import materialize_runtime_source_pins
        pins=materialize_runtime_source_pins(
            pins,execution_image=execution_image,provenance_images=provenance_images)
        from .a0_family_source import verify_pinned_files
        verify_pinned_files(pins)
    return pins
