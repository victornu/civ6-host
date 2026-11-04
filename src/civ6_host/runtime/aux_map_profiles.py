"""Source-bound map layout selection, independent of saved-game admission."""
from __future__ import annotations

from dataclasses import dataclass
import struct

from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256, _source, _body

SOURCE = ('work/host-extensions/aux-map-static/aux-map-xp1-source-v1.json',
          '434937bad85bc216bf97a1d20ca00341baab7174fd4ad04caf9353efaa123f16')


@dataclass(frozen=True)
class MapABI:
    core_sha256: str
    vtable_rva: int
    slots: tuple
    name_getter_rva: int
    source_sha256: str


_BASE = MapABI(BASE_CORE_SHA256,0x81CFA0,
    ((8,0x2DE850),(0x60,0x745D00),(0x70,0x745E10),(0x1D8,0x67370)),
    0x74E850,'8aedcab5c742d8b142e760e76ce6d079296d7ad12ec80cf045f89091c7e4dfb1')
_XP1 = MapABI(XP1_CORE_SHA256,0x93F590,
    ((8,0x351540),(0x60,0x845540),(0x70,0x845650),(0x1D8,0x7FCAA0)),
    0x84A340,SOURCE[1])


def source():
    proof = _source(SOURCE)
    contract = proof['contract']
    slots = dict(_XP1.slots) | {0x18:_XP1.name_getter_rva}
    layout = {'map_kind':2,'map_header_bytes':84,'name_resolver_offset':32,
        'sentinel_offset':48,'begin_offset':56,'root_offset':64,'count_offset':80,
        'count_bytes':4,'node_read_bytes':64,'node_right_offset':0,'node_left_offset':8,
        'node_parent_offset':16,'node_key_offset':32,'node_variant_offset':40,
        'variant_bytes':24,'variant_tag_offset':0,'variant_tag_bytes':2,
        'variant_payload_offset':8,'variant_size_offset':16,'variant_flags_offset':20,
        'variant_pointer_bit':1<<29,'list_begin_offset':40,'list_end_offset':48,
        'list_variant_stride':24}
    if (proof['native_execution'] is not False
            or proof['images']['base']['sha256'] != BASE_CORE_SHA256
            or proof['images']['xp1']['sha256'] != XP1_CORE_SHA256
            or int(contract['vtable_rva'],16) != _XP1.vtable_rva
            or {int(k,16):int(v,16) for k,v in contract['slots'].items()} != slots
            or dict(contract['layout']) != layout
            or int(contract['name_getter_rva'],16) != _XP1.name_getter_rva):
        raise ValueError('XP1 native map source/profile differs')
    return proof


def profile_for_sha(core_sha256):
    if core_sha256 == BASE_CORE_SHA256:
        return _BASE
    if core_sha256 == XP1_CORE_SHA256:
        source()
        return _XP1
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_aux_map_profile import profile
        return profile()
    raise ValueError('Native map engine layout is not admitted')


def verify_live(profile, base, read):
    if type(profile) is MapABI and profile.core_sha256==XP2_CORE_SHA256:
        from .xp2_aux_map_profile import verify_live as verify_xp2
        return verify_xp2(profile,base,read)
    if profile is _BASE:
        return  # Existing V1 decoder retains its own identity/slot checks.
    if profile is not _XP1 or type(base) is not int or not 0 < base < (1<<63):
        raise ValueError('Expected the canonical XP1 native map profile')
    for name, body in source()['functions']['xp1'].items():
        for fragment in _body(body)['fragments']:
            for instruction in fragment['instructions']:
                raw = bytes.fromhex(instruction['bytes'])
                address = base + int(instruction['va'],16) - 0x180000000
                if read(address,len(raw)) != raw:
                    raise ValueError('XP1 native map code differs: '+name)
    for offset, rva in (*profile.slots,(0x18,profile.name_getter_rva)):
        if read(base+profile.vtable_rva+offset,8) != struct.pack('<Q',base+rva):
            raise ValueError('XP1 native map dispatch differs')


def prepared_game_properties(base, read):
    """Borrow the source-verified services map; never allocate a stand-in."""
    verify_live(_XP1,base,read)
    services, = struct.unpack('<Q',read(base+0x9F2628,8))
    if not 0 < services < (1<<63)-0x210:
        raise ValueError('XP1 services owner is not prepared')
    pointer = services + 0x1B8
    if read(pointer,8) != struct.pack('<Q',base+_XP1.vtable_rva):
        raise ValueError('XP1 Game.GetProperties map is not initialized')
    return pointer
