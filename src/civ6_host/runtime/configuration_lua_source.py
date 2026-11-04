"""Source/live-code join for XP1 official configuration GetValue callbacks."""
from __future__ import annotations

import struct

from .configuration_profiles import _source, _body, BASE_CORE_SHA256, XP1_CORE_SHA256

SOURCE = ('work/host-extensions/configuration-lua-static/configuration-lua-source-v1.json',
          'ed99dfbdf39f2c0bdee91a487c74068eba738bd27b2fd539424735da27d2b88a')


def source():
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6_host.configuration_lua_static.v1'
            or proof['native_execution'] is not False
            or proof['images']['base']['sha256'] != BASE_CORE_SHA256
            or proof['images']['xp1']['sha256'] != XP1_CORE_SHA256
            or proof['contract']['aux_slot'] != '0xa0'
            or proof['contract']['get_value']['utf16_before_callback'] is not False
            or proof['contract']['tag6_exact_conversion']['maximum_payload_bytes'] != 1023
            or proof['contract']['player_configuration']['generic_GetValue_registered'] is not False):
        raise ValueError('Configuration Lua source contract differs')
    return proof


def verify_xp1(base, read):
    if type(base) is not int or not 0 < base < (1 << 63):
        raise ValueError('Invalid XP1 configuration Lua module address')
    proof = source()
    for name, value in proof['functions']['xp1'].items():
        for fragment in _body(value)['fragments']:
            for instruction in fragment['instructions']:
                raw = bytes.fromhex(instruction['bytes'])
                address = base + int(instruction['va'],16) - 0x180000000
                if read(address,len(raw)) != raw:
                    raise ValueError('XP1 configuration Lua code differs: '+name)
    if read(base+0x93F590+0x60,8) != struct.pack('<Q',base+0x845540):
        raise ValueError('XP1 configuration GetValue provider slot differs')
    return {'source_sha256':SOURCE[1], 'core_sha256':XP1_CORE_SHA256,
            'native_calls_made':False, 'saved_game_load_admitted':False}
