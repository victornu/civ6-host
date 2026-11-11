"""Source and loaded-image boundary for XP1's application control inputs."""
from __future__ import annotations

import hashlib
import struct
from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256,_source,_body,configuration_abi

SOURCE=('work/host-extensions/controller-load-static/controller-load-xp1-source-v1.json',
        '8a56266b7b6fc07e4a46e203072429aa09ccb13aef34d992bc0970873b0ca309')
REACTIVATION_SOURCE=('evidence/host-xp1-ranged-production-slot68-frontier.json',
                     'ed0a9abfe29160532166248ca1f65d28706d81f1600586ec152bd8deed94bf0a')
XP2_REACTIVATION_SOURCE=('evidence/host-xp2-reinforced-turn-reactivation-source.json',
                         'e8a138eeebd87bba4897c464f4f480f86e672f108e69e416e127114104719738')


def source():
    proof=_source(SOURCE)
    from .native.native_controller_code import SOURCE_SHA,EXE_SHA
    if (proof['schema']!='civ6_host.controller_load_xp1.static.v1'
            or proof['images']['xp1']['sha256']!=XP1_CORE_SHA256
            or proof['images']['exe']['sha256']!=EXE_SHA
            or proof['references']['native_controller']['sha256']!=SOURCE_SHA
            or proof['validation']['all_instruction_bytes_match_pinned_images'] is not True
            or proof['validation']['native_execution'] is not False):
        raise ValueError('XP1 control input source identity differs')
    d0=proof['profile']['d0'];controller=proof['profile']['controller120']
    if (d0['slot']!='0xd0' or d0['return']!='uint32' or int(d0['caller_rva'],16)!=0x558370
            or tuple(d0['host_policy_domain'])!=(-1,64)
            or controller['slot']!='0x120' or controller['return']!='uint8 AL'
            or int(controller['caller_rva'],16)!=0x533B0
            or controller['requires_shared_turn_state'] is not True
            or int(proof['profile']['host_global_rva'],16)!=0x9F2640):
        raise ValueError('XP1 control input ABI differs')
    for ref in proof['references'].values():_source((ref['path'],ref['sha256']))
    return proof


def body(name):
    proof=source();route=proof['profile']['live_body_sources'][name]
    if route['kind']=='local_body':
        value=proof
        for key in route['selector']:value=value[key]
        return _body(value)
    if route['kind']!='referenced_body':raise ValueError('Unknown control body source')
    row=proof['referenced_bodies'][route['key']];ref=proof['references'][row['reference']]
    value=_source((ref['path'],ref['sha256']))
    for key in row['selector']:value=value[key]
    value=_body(value)
    raw=b''.join(bytes.fromhex(i['bytes']) for f in value['fragments'] for i in f['instructions'])
    if hashlib.sha256(raw).hexdigest()!=row['instruction_bytes_sha256']:
        raise ValueError('Control input referenced body differs')
    return value


def verify_xp1(base,context,read,*,host_pointer):
    def exact(addr,size):
        raw=read(addr,size)
        if type(raw) is not bytes or len(raw)!=size:raise ValueError('Incomplete control input memory read')
        return raw
    for name in ('local_player_update','controller_query'):
        for fragment in body(name)['fragments']:
            for instruction in fragment['instructions']:
                raw=bytes.fromhex(instruction['bytes'])
                if exact(base+int(instruction['va'],16)-0x180000000,len(raw))!=raw:
                    raise ValueError('XP1 control caller instructions differ: '+name)
    q=lambda addr:struct.unpack('<Q',exact(addr,8))[0]
    abi=configuration_abi(XP1_CORE_SHA256).load
    if (q(context)!=base+abi.outer_vtable_rva or q(base+0x9F2640)!=host_pointer
            or not q(context+8) or q(context+8)!=q(base+0x9F2620)):
        raise ValueError('XP1 control callback owner/context differs')
    return {'source_sha256':SOURCE[1],'caller_bodies_verified':True,
        'local_identity_inferred':False,'native_callers_invoked':False,'saved_game_load_admitted':False}


def source_pins():
    from .paths import resource_root
    from .resource_resolution import resolve_path
    proof=source();refs=[{'path':SOURCE[0],'sha256':SOURCE[1]},*proof['references'].values()]
    return {str(resolve_path(resource_root()/r['path'])):r['sha256'] for r in refs}


def reactivation_profile(core):
    from .execution_images import _PROFILE, _XP1_PROFILE

    image=getattr(core,'_civ6_host_execution_image',None)
    return image if image is _XP1_PROFILE or image is _PROFILE else None


def reactivation_source(execution_image=None):
    from .execution_images import _PROFILE, _XP1_PROFILE
    from .native.native_host_turn_reactivation import PROOF_SHA256, verify_source

    if execution_image is _PROFILE:
        from .xp2_cache_source import SOURCE as getter_source
        selected=_PROFILE
        reference=XP2_REACTIVATION_SOURCE
        schema='civ6-host.xp2-reinforced-turn-reactivation-source.v1'
        getter_key='retained_xp2_game_getter'
        call,test='0x5c9a7','0x5c9aa'
    elif execution_image is None or execution_image is _XP1_PROFILE:
        from .retained_game_source import SOURCE as getter_source
        selected=_XP1_PROFILE
        reference=REACTIVATION_SOURCE
        schema='civ6-host.xp1-ranged-production-slot68-frontier.v1'
        getter_key='retained_xp1_game_getter'
        call,test='0x538b7','0x538ba'
    else:
        raise ValueError('Reactivation requires a source-qualified installed expansion')
    proof=_source(reference)
    row=proof['source']
    getter=row[getter_key]
    caller=row['core_spans']['caller']['instructions']
    instructions={i['rva']:i['bytes'] for i in caller}
    if (proof['schema']!=schema
            or (proof['native_refusal']['interface'],proof['native_refusal']['slot'])!=('host','0x68')
            or row['core']['sha256']!=selected.image_sha256
            or (row['exe_vtable_rva'],row['slot_target_rva'])!=('0xfc89d0','0x1c88b0')
            or row['base_host_contract']['sha256']!=PROOF_SHA256
            or (getter['path'],getter['sha256'])!=getter_source
            or instructions.get(call)!='ff5068' or instructions.get(test)!='84c0'):
        raise ValueError('Installed expansion reactivation contract differs')
    if selected is _PROFILE:
        from .retained_game_source import getter_abi
        shared=row['xp1_same_exe_contract']
        if ((shared['path'],shared['sha256'])!=REACTIVATION_SOURCE
                or row['exe']!=reactivation_source(_XP1_PROFILE)['exe']
                or row['host_global_rva']!='0xb8aa80'
                or row['core_spans']['retained_getter']['sha256']!=getter_abi(XP2_CORE_SHA256).getter_sha256):
            raise ValueError('Installed XP2 shared reactivation service differs')
    verify_source()
    _source(getter_source)
    return row


def verify_reactivation(core,read):
    from .execution_images import _PROFILE

    image=reactivation_profile(core)
    if image is None:
        raise ValueError('Reactivation requires a source-qualified installed expansion')
    row=reactivation_source(image)
    for instruction in row['core_spans']['caller']['instructions']:
        expected=bytes.fromhex(instruction['bytes'])
        actual=read(core._handle+int(instruction['rva'],16),len(expected))
        if type(actual) is not bytes or actual!=expected:
            raise ValueError('Installed expansion reactivation caller differs')
    return (XP2_REACTIVATION_SOURCE if image is _PROFILE else REACTIVATION_SOURCE)[1]


def reactivation_source_pins(execution_image=None):
    from .execution_images import _PROFILE
    from .paths import resource_root

    row=reactivation_source(execution_image)
    if execution_image is _PROFILE:
        reference=XP2_REACTIVATION_SOURCE
        refs=(row['base_host_contract'],row['retained_xp2_game_getter'],row['xp1_same_exe_contract'])
    else:
        reference=REACTIVATION_SOURCE
        refs=(row['base_host_contract'],row['retained_xp1_game_getter'])
    return {resource_root()/reference[0]:reference[1],
            row['exe']['path']:row['exe']['sha256'],
            **{resource_root()/ref['path']:ref['sha256'] for ref in refs}}
