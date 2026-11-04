"""XP2 random-event producer family, on the existing EXE notification FIFO.

This is a source/lifetime boundary, not a replacement climate simulation.
Raw copied events remain administrative: visibility is not inferred here.
"""
from functools import lru_cache
import hashlib
from types import MappingProxyType

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source

SOURCE = ('work/host-extensions/xp2-turn-event-family/source-profile-v1.json',
          '21180213a91f5292da14fac2cf37ecb21a76bdd26a75b7ecccc7921b355aa844')
SCOPE_SOURCE = ('work/host-extensions/xp2-weather-dispatch-scope/source-index-v1.json',
                '0169262d1780f479ff9c6b79d6c416ef3951134919d928ef7282666e92961f54')
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
STORM_KIND = 0x13b135e4
DESCRIPTOR53_KIND = 0x07f2abd3
FAVOR_KIND = 0x68e7d3da
CALLBACKS = {STORM_KIND: 0x1532a0, 0x2bea7bcb: 0x142d30,
             0xd109a8fc: 0x14d550, 0xe869c8ff: 0x14d290,
             DESCRIPTOR53_KIND: 0x145650, FAVOR_KIND: 0x146600}
RECORDS = {STORM_KIND: frozenset((0x138,)), 0x2bea7bcb: frozenset((0x145,)),
           0xd109a8fc: frozenset((0x135,)), 0xe869c8ff: frozenset((0x136, 0x137)),
           DESCRIPTOR53_KIND: frozenset((0x13b,)), FAVOR_KIND: frozenset((0x142,))}
SIZES = {0x138: 128, 0x145: 96, 0x135: 112, 0x136: 112, 0x137: 112, 0x13b: 112,
         0x142: 96}


def fragments(body):
    capture = body['capture']
    for fragment in capture.get('fragments', (capture,)):
        rows = fragment['instructions']
        raw = b''.join(bytes.fromhex(row['bytes']) for row in rows)
        core_fragment = 'start_rva' in fragment
        digest = fragment['sha256'] if core_fragment else fragment['raw_sha256']
        start = (0x180000000 + int(fragment['start_rva'], 16) if core_fragment
                 else int(fragment['start_va'], 16))
        if core_fragment and (fragment['raw_hex'] != raw.hex()
                or 'start_va' in fragment and int(fragment['start_va'], 16) != start):
            raise ValueError('XP2 climate fragment image or bytes changed')
        if (len(raw) != fragment['length']
                or hashlib.sha256(raw).hexdigest() != digest):
            raise ValueError('XP2 climate retained instruction bytes changed')
        cursor = start
        for row in rows:
            va = 0x180000000 + int(row['rva'], 16) if core_fragment else int(row['va'], 16)
            if va != cursor:
                raise ValueError('XP2 climate source instruction boundary changed')
            cursor += len(bytes.fromhex(row['bytes']))
        if ('end_va_exclusive' in fragment and cursor != int(fragment['end_va_exclusive'], 16)
                or 'end_rva_exclusive' in fragment and cursor != 0x180000000 + int(fragment['end_rva_exclusive'], 16)):
            raise ValueError('XP2 climate retained fragment is truncated')
        yield start, raw


@lru_cache(maxsize=1)
def source():
    p = _source(SOURCE)
    if (p['images']['xp2']['sha256'] != XP2_CORE_SHA256
            or p['images']['exe']['sha256'] != EXE_SHA256
            or p['native_execution'] is not False
            or p['validation']['all_captured_instruction_bytes_match_pinned_images'] is not True
            or p['validation']['complete_unwind_bodies'] is not True):
        raise ValueError('XP2 climate producer source identity changed')
    for body in p['functions'].values():
        raw = b''.join(raw for _, raw in fragments(body))
        if hashlib.sha256(raw).hexdigest() != body['sha256']:
            raise ValueError('XP2 climate source body digest changed')
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    if any(EXE_EVENT_CALLBACKS.get(kind) != callback for kind, callback in CALLBACKS.items()):
        raise ValueError('XP2 climate EXE registration differs')
    return p


def source_dependencies(*, core_sha256=XP2_CORE_SHA256):
    if core_sha256 == XP1_CORE_SHA256:
        return {}
    if core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Unqualified climate producer engine')
    source()
    from .a0_family_source import _path, verify_pinned_files
    from . import xp2_turn_event_records as records
    from . import xp2_weather_position as position
    from . import xp2_storm_query as query
    from . import xp2_descriptor53_query as drought
    from . import xp2_favor_event_profile as favor
    from . import xp2_weather_lifecycle as lifecycle
    pins = {str(_path(SOURCE[0]).resolve()): SOURCE[1]}
    scope_source()
    records.terrain_source()
    records.terrain_occurred_source()
    records.terrain_short_source()
    for path, digest in (records.TERRAIN_SOURCE, records.TERRAIN_NORMALIZER,
                         records.TERRAIN_OCCURRED_SOURCE, records.TERRAIN_SHORT_SOURCE):
        pins[str(_path(path).resolve())] = digest
    pins[str(_path(SCOPE_SOURCE[0]).resolve())] = SCOPE_SOURCE[1]
    for module in (records, position, query, drought, favor, lifecycle):
        for path, digest in module.source_dependencies().items():
            if path in pins and pins[path] != digest:
                raise ValueError('XP2 climate source dependency conflict')
            pins[path] = digest
    verify_pinned_files(pins)
    return pins


def scope_source():
    """Join legacy producers and the separately proved presentation omissions.

    This is a routing index. Per-kind producer/codec guards remain authoritative;
    the legacy source is never reinterpreted as covering the new lifecycle.
    """
    from . import xp2_weather_lifecycle as lifecycle
    p = _source(SCOPE_SOURCE)
    if (p['schema'] != 'civ6-host.xp2-weather-dispatch-scope.v1'
            or p['native_execution'] is not False or p['core_sha256'] != XP2_CORE_SHA256
            or dict(p['existing_source']) != dict(path=SOURCE[0], sha256=SOURCE[1])
            or dict(p['lifecycle_source']) != dict(path=lifecycle.SOURCE[0], sha256=lifecycle.SOURCE[1])
            or set(p['kinds']) != {hex(k) for k in set(RECORDS) | lifecycle.KINDS}):
        raise ValueError('XP2 weather dispatch source index changed')
    for kind in set(RECORDS) | lifecycle.KINDS:
        row = p['kinds'][hex(kind)]
        omitted = kind in lifecycle.KINDS
        if (set(row) != {'source_sha256', 'record_types', 'policy'}
                or row['source_sha256'] != (lifecycle.SOURCE[1] if omitted else SOURCE[1])
                or tuple(row['record_types']) != (() if omitted else tuple(sorted(RECORDS[kind])))
                or row['policy'] != (lifecycle.POLICY if omitted else 'existing-source-qualified-producer')):
            raise ValueError('XP2 weather dispatch kind policy changed')
    return p


def event_profile(*, core_sha256):
    if core_sha256 != XP2_CORE_SHA256:
        raise ValueError('XP2 climate family requires its exact engine')
    source_dependencies()
    from .a0_family_source import A0FamilyProfile
    from .native.native_deferred_empty_profile import resolve_empty_receiver_row
    from . import xp2_turn_event_records as records
    sizes = {**SIZES, records.TERRAIN_RECORD: 112}
    for record, size in sizes.items():
        row = resolve_empty_receiver_row(record)
        if row is None or row['record_sizes'] != {size}:
            raise ValueError('XP2 climate empty receiver is not source qualified')
    from .xp2_weather_lifecycle import KINDS
    mapping = dict(RECORDS)
    mapping[records.TERRAIN_KIND] = frozenset((records.TERRAIN_RECORD,))
    mapping.update((kind, frozenset()) for kind in KINDS)
    return A0FamilyProfile(MappingProxyType(mapping), MappingProxyType(sizes), SCOPE_SOURCE[1])


def bind_owner(backend, core, read):
    backend.check_thread()
    if backend.core is not core or backend.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('XP2 climate producer owner mismatch')
    for body in source()['functions'].values():
        if body['image'] != 'xp2':
            continue
        for va, raw in fragments(body):
            # Keep the checked reader's per-read bound even for long producers.
            for offset in range(0, len(raw), 4096):
                chunk = raw[offset:offset + 4096]
                if read(core._handle + va - 0x180000000 + offset, len(chunk)) != chunk:
                    raise ValueError('XP2 climate live producer bytes changed')
    from .xp2_favor_event_profile import bind_owner as bind_favor
    bind_favor(backend, core, read)
    from .xp2_weather_lifecycle import bind_owner as bind_lifecycle
    bind_lifecycle(backend, core, read)
    from .xp2_turn_event_records import terrain_core_fragments
    for rva, raw in terrain_core_fragments():
        if read(core._handle + rva, len(raw)) != raw:
            raise ValueError('XP2 terrain notification live producer changed')
    return SOURCE[1]
