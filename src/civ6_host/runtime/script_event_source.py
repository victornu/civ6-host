"""XP1 caller ABI for the shared synchronous event service; not Load admission."""
from __future__ import annotations

import struct

from .configuration_profiles import _source, XP1_CORE_SHA256

SOURCE = ('work/host-extensions/script-events-static/script-events-xp1-source-v1.json',
          '1d842ea09dda97ace1c9bd01e8abfe864079cab28ffc195e0279ee595337611b')
FUNCTIONS = ('call_dispatch','test_all_dispatch','set_host_thunk','set_host_globals')


def source():
    proof = _source(SOURCE)
    contract = proof['contract']
    if (proof['schema'] != 'civ6_host.xp1_script_events_static.v1'
            or proof['native_execution'] is not False
            or proof['images']['xp1']['sha256'] != XP1_CORE_SHA256
            or contract['aux_global_rva'] != '0x9f2648'
            or contract['synchronization_service_global_rva'] != '0x9f2640'
            or contract['xp1_call_dispatch_rva'] != '0x20cd0'
            or contract['xp1_test_all_dispatch_rva'] != '0x20df0'
            or contract['post_prepare_witness']['explicit_official_wrapper_diagnostic_supported'] is not True):
        raise ValueError('Script-event source contract differs')
    for reference in proof['references'].values():
        # Includes original host implementations and EXE evidence. The current
        # extracted implementation is pinned separately by the runtime closure.
        from .paths import resource_root
        import hashlib
        path=resource_root()/reference['path']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=reference['sha256']:
            raise ValueError('Script-event source dependency differs: '+reference['path'])
    return proof


def verify_xp1(base, read, *, host_pointer, auxiliary_pointer):
    if any(type(x) is not int or not 0<x<(1<<63) for x in (base,host_pointer,auxiliary_pointer)):
        raise ValueError('Invalid script-event module or interface address')
    proof = source()
    for name in FUNCTIONS:
        body=proof['functions']['xp1'][name]
        for fragment in body.get('fragments',[body]):
            for instruction in fragment['instructions']:
                raw=bytes.fromhex(instruction['bytes'])
                address=base+int(instruction['va'],16)-0x180000000
                if read(address,len(raw))!=raw:
                    raise ValueError('XP1 script-event code differs: '+name)
    for offset,pointer in ((0x9F2640,host_pointer),(0x9F2648,auxiliary_pointer)):
        if read(base+offset,8)!=struct.pack('<Q',pointer):
            raise ValueError('XP1 script-event installed host global differs')
    return {'source_sha256':SOURCE[1],'core_sha256':XP1_CORE_SHA256,
            'native_calls_made':False,'saved_game_load_admitted':False}
