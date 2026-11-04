"""Source-bound configuration ownership and stream ABIs, independent of Load admission.

Expansion configuration operations use official constructors/codecs and retained
ownership layouts. Selecting an owner ABI does not admit an expansion game to
the saved-game host or enable its initialization pipeline.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .paths import resource_root
from .resource_resolution import resolve_path
from .saved_load_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256, profile_for_sha
from .native.native_source_cache import load_pinned_json

OWNERSHIP_SOURCE = ('work/host-extensions/provider-ownership-static/provider-ownership-source.json',
                    '089ba8ff3b852f1279d4d20dd4145eac9d610d057b53bcaab54c3a8ad96406f6')
LIVE_SOURCE = ('work/host-extensions/provider-ownership-static/xp1-live-bodies-v2.json',
               '83ca1ddea5c93c8e1e4d6dfc0ec8807c0b0e18e1c7409682b2e2a5c5b611a7f0')
COPY_SOURCE = ('work/host-extensions/configuration-copy-static/xp1-b-to-a-copy-source-v1.json',
               '169268e489a9f11fe6ac08d9da2126b646aa1817d4da5d6ae0dd861eedbc1ce2')


@dataclass(frozen=True)
class ConfigurationABI:
    core_sha256: str
    vtable_rva: int
    constructor_rva: int
    destructor_rva: int
    assign_rva: int
    lookup_rva: int
    copy_rva: int
    uint_setter_rva: int
    root_key_rva: int
    map_key_rva: int
    player_key_table_rva: int
    initialized_getter_rva: int
    preparation: tuple
    codec_slots: tuple
    application_proof_sha256: str
    codec_proof_sha256: str

    @property
    def load(self):
        return profile_for_sha(self.core_sha256)


_BASE = ConfigurationABI(
    BASE_CORE_SHA256, 0x81CFA0, 0x744B80, 0x744CA0, 0x74BA50, 0x745CB0,
    0x7450A0, 0x7465A0, 0x8BCC58, 0x8BCD08, 0x8BCD50, 0x42E3A0,
    ((0x140, 0x42F390), (0x148, 0x42F350), (0x150, 0x42F310)),
    ((0x1E8, 0x7502D0), (0x1F0, 0x746210), (0x1F8, 0x750140), (0x200, 0x7501E0),
     (0x20, 0x74E850), (0x138, 0x7474F0), (0x160, 0x744F90), (0x1D8, 0x067370)),
    '8eb66f0839535c4ffc107674463a8d7b3bf1584abf2ef6d51461cdee5244dc73',
    '3d5ef65d87185b09b2925e2c0f61f7181d993b3f25e2e55cc3fbcc3c08a817a7')
_XP1 = ConfigurationABI(
    XP1_CORE_SHA256, 0x93F590, 0x844460, 0x844580, 0x84B5D0, 0x8454F0,
    0x844950, 0x845E90, 0x9F3D20, 0x9F3DD0, 0x9F3E20, 0x4BD4A0,
    ((0x140, 0x4BE490), (0x148, 0x4BE450), (0x150, 0x4BE410)),
    ((0x1E8, 0x84FD80), (0x1F0, 0x845B00), (0x1F8, 0x84FBF0), (0x200, 0x84FC90),
     (0x20, 0x84A340), (0x138, 0x846DF0), (0x160, 0x844870), (0x1D8, 0x7FCAA0)),
    LIVE_SOURCE[1], LIVE_SOURCE[1])


def configuration_abi(core_sha256):
    if core_sha256 == BASE_CORE_SHA256:
        return _BASE
    if core_sha256 == XP1_CORE_SHA256:
        return _XP1
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_configuration_profile import candidate_abi
        return candidate_abi(core_sha256)
    raise ValueError('Unknown GameCore configuration ABI')


def require_owner_profile(profile):
    if profile is not _BASE and profile is not _XP1:
        from .xp2_configuration_profile import _ABI, verify_source
        if profile is not _ABI:
            raise ValueError('Expected the canonical configuration ownership ABI')
        verify_source()
    if profile is _XP1:
        _xp1_sources()
    return profile


def _source(reference):
    path = resolve_path(resource_root() / reference[0])
    if not path.is_file() or not 0 < path.stat().st_size <= 8 * 1024 * 1024:
        raise ValueError('Missing or oversized configuration source')
    return load_pinned_json(path, reference[1])


def _body(value):
    value = value.get('body', value)
    fragments = value.get('fragments') or [value]
    if any(not f.get('instructions') for f in fragments):
        raise ValueError('Configuration source has only a digest or partial instruction summary')
    actual = sum(len(bytes.fromhex(i['bytes'])) for f in fragments for i in f['instructions'])
    expected = value.get('total_length', value.get('length'))
    if expected is not None and actual != expected:
        raise ValueError('Configuration instruction coverage differs from complete body length')
    return {'fragments': _copy(fragments)}


def _copy(value):
    """Materialize the source cache's frozen mappings without modifying them."""
    if isinstance(value, Mapping):
        return {k:_copy(v) for k,v in value.items()}
    if isinstance(value, (list,tuple)):
        return [_copy(v) for v in value]
    return value


def _xp1_sources():
    ownership = _source(OWNERSHIP_SOURCE)
    live = _source(LIVE_SOURCE)
    if ownership.get('native_execution') is not False or live.get('native_execution') is not False:
        raise ValueError('Configuration source classification changed')
    p = ownership['profiles']['xp1']
    if p['image']['sha256'] != XP1_CORE_SHA256 or live['image']['sha256'] != XP1_CORE_SHA256:
        raise ValueError('Configuration source engine identity changed')
    c, layout = p['contract'], p['application_layout']
    expected = {
        'provider_storage_bytes':0x58, 'setup_offset':0xD80, 'game_offset':0x88,
        'descriptor_offset':0x80, 'records_begin_offset':0x90, 'records_inline_offset':0xB8,
        'map_descriptor_offset':0xC28, 'normalized_map_offset':0xC30,
        'record_stride':0x20, 'player_key_stride':0x44, 'record_count':64,
        'submap_count':66, 'owned_map_flags':0x05000000,
    }
    integer = lambda value: int(value, 16) if type(value) is str else value
    if any(integer(layout.get(k)) != v for k,v in expected.items()):
        raise ValueError('XP1 configuration layout differs from the shared owner algorithm')
    for field,key in (('vtable_rva','provider_vtable_rva'),('constructor_rva','constructor_rva'),
                      ('destructor_rva','destructor_rva'),('root_key_rva','root_key_rva'),
                      ('map_key_rva','map_key_rva'),('player_key_table_rva','player_key_table_rva'),
                      ('initialized_getter_rva','outer_init_getter_rva')):
        if integer(c[key]) != getattr(_XP1,field):
            raise ValueError('XP1 configuration address changed: '+field)
    for slot,target in (*_XP1.codec_slots,(0x58,_XP1.lookup_rva),(0x178,_XP1.copy_rva),
                         (0x1D0,_XP1.assign_rva),(0x130,_XP1.uint_setter_rva)):
        if integer(c['slots'][hex(slot)]) != target:
            raise ValueError('XP1 provider virtual slot changed')
    if any(integer(c['outer_slots'][hex(slot)]) != target for slot,target in _XP1.preparation):
        raise ValueError('XP1 context preparation targets changed')
    dependencies = {k:_source((v['path'],v['sha256'])) for k,v in ownership['source_refs'].items()}
    keys = c['player_key_hashes']
    if keys != dependencies['base_ownership_proof']['player_keys'] or len(keys) != 64:
        raise ValueError('XP1 shared PLAYER names/hashes lost their source join')
    for value in live['functions'].values():
        _body(value)
    return ownership, live, dependencies


def application_source(core_sha256):
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_configuration_profile import application_source as source
        return source(core_sha256)
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('No expansion configuration owner source for this engine')
    ownership, live, deps = _xp1_sources()
    capture = deps['xp1_application_capture']['live_bodies']
    aliases = {'provider_constructor':'constructor','provider_base_constructor':'base_constructor',
               'provider_destructor':'destructor','provider_assign':'assign','provider_copy':'copy',
               'variant_clone_construct':'variant_clone_construct','variant_clone_assign':'variant_clone_assign',
               'variant_release':'variant_release'}
    functions = {name:_body(capture[source]) for name,source in aliases.items()}
    functions['lookup'] = _body(deps['xp1_player_capture']['live_bodies']['lookup'])
    extra = {name:_body(body) for name,body in live['functions'].items() if name.startswith('outer_slot_')}
    functions.update(extra)
    return {'core_functions':functions,'additional_live_names':tuple(extra),
            'player_keys':_copy(ownership['profiles']['xp1']['contract']['player_key_hashes']),
            'source_sha256':LIVE_SOURCE[1]}


def codec_source(core_sha256):
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_configuration_profile import codec_source as source
        return source(core_sha256)
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('No expansion configuration codec source for this engine')
    ownership, live, _ = _xp1_sources()
    return {'images':{'core':_copy(ownership['profiles']['xp1']['image'])},
            'captures':{'core':{name:_body(body) for name,body in live['functions'].items()
                                if name.startswith('provider_slot_')}},
            'source_sha256':LIVE_SOURCE[1]}


def context_copy_source(profile):
    """XP1 +120 copies/reindexes configuration; it is not NewGame or Load."""
    if profile is profile_for_sha(XP2_CORE_SHA256):
        from .xp2_configuration_profile import context_copy_source as source
        return source(profile)
    if profile is not _XP1.load:
        raise ValueError('Expansion configuration copy requires the exact XP1 ABI')
    proof = _source(COPY_SOURCE)
    if (proof['native_execution'] is not False
            or proof['images']['xp1']['sha256'] != XP1_CORE_SHA256
            or int(proof['dispatch']['xp1']['outer_vtable_rva'],16) != profile.outer_vtable_rva
            or int(proof['dispatch']['xp1']['wrapper_rva'],16) != profile.copy_rva
            or int(proof['game_initialized_getter']['rva'],16) != profile.game_initialized_rva):
        raise ValueError('XP1 copy source/profile identity differs')
    effects = proof['xp1_copy_and_relink_effects']
    if (effects['provider_assign']['dispatch_slot'] != '0x1D0'
            or int(effects['provider_assign']['target_rva'],16) != _XP1.assign_rva
            or effects['player_records']['count'] != 64
            or effects['player_records']['stride'] != '0x20'
            or effects['map_root_descriptor']['value_address'] != 'setup+0xC30'):
        raise ValueError('XP1 copy/reindex contract differs')
    for path, reference in proof['source_files'].items():
        _source((path,reference['sha256']))
    # Every body is checked in the loaded module. The accessor is explicitly a
    # bounded reachable CFG, not claimed as a complete pdata function extent.
    return {name:_body(body) for name,body in proof['functions']['xp1'].items()}


def verify_context_copy(profile, base, read):
    functions = context_copy_source(profile)
    if type(base) is not int or not 0 < base < (1 << 63):
        raise ValueError('Invalid configuration-copy module address')
    for name,body in functions.items():
        for fragment in body['fragments']:
            for instruction in fragment['instructions']:
                data = bytes.fromhex(instruction['bytes'])
                address = base + int(instruction['va'],16) - 0x180000000
                if read(address,len(data)) != data:
                    raise ValueError('XP1 configuration-copy live code differs: '+name)
    source_sha256=COPY_SOURCE[1]
    if profile is profile_for_sha(XP2_CORE_SHA256):
        from .xp2_configuration_profile import COPY_SOURCE as xp2_source
        source_sha256=xp2_source[1]
    return {'source_sha256':source_sha256, 'native_call_made':False,
            'game_load_admitted':False}
