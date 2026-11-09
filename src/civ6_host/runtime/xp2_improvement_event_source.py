"""Exact XP2 ImprovementChanged/RouteChanged source for the shared transport.

The established EXE queries, releases and FIFO records remain required. Empty
receivers do not establish transitive query purity and do not admit omission.
"""
from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
from types import MappingProxyType

from .configuration_profiles import XP2_CORE_SHA256, _source

SOURCE = ('work/host-extensions/xp2-improvement-events-static/source-profile-v1.json',
          'bcd17fdc8df4162ed1a4f858b8a408b24078d6e9b9d2fc6827a9dfc2b7d35092')
IMPROVEMENT_CHANGED, ROUTE_CHANGED = 0x30ae2a3d, 0x7b65ff2e
KINDS = MappingProxyType({IMPROVEMENT_CHANGED: 0x90, ROUTE_CHANGED: 0x99})
CALLBACKS = MappingProxyType({IMPROVEMENT_CHANGED: 0x148fc0, ROUTE_CHANGED: 0x152710})
SIZES = MappingProxyType({0x90: 144, 0x99: 128})
POLICY = 'shared-native-query-and-fifo'
_EXE = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
_SHAPES = {IMPROVEMENT_CHANGED: {0xa1e5a149: 3, 0x8c468e3c: 0},
           ROUTE_CHANGED: {0xa1e5a149: 3, 0x8c468e3c: 0, 0xd6fcf3e4: 2, 0xa1fbc372: 2}}
_SITES = (
    (IMPROVEMENT_CHANGED,0x110990,0x110a9b,'mov rbx, qword ptr [rsp + 0x60]'),
    (IMPROVEMENT_CHANGED,0x25cfa0,0x25d1b4,'movsx eax, word ptr [rdi + 0x28]'),
    (IMPROVEMENT_CHANGED,0x376310,0x3764bc,'mov rbp, qword ptr [rsp + 0x50]'),
    (ROUTE_CHANGED,0x360060,0x3602cb,'test bpl, bpl'),
    (ROUTE_CHANGED,0x361570,0x3615f9,'add rsp, 0x30'),
    (ROUTE_CHANGED,0x38d2d0,0x38d65e,'add rsi, 4'),
    (ROUTE_CHANGED,0x390a70,0x390be8,'add r15, 4'),
    (ROUTE_CHANGED,0x3931c0,0x393354,'mov ecx, dword ptr [rbp + 0xd8]'),
)


def _texts(p, name):
    capture = p['functions'][name]['capture']
    base = 0x180000000 if name.startswith('core_') else 0x140000000
    return {int(r['rva'],16) if 'rva' in r else int(r['va'],16)-base:r['text']
            for f in capture.get('fragments',(capture,)) for r in f['instructions']}


def _verify(p):
    from .xp2_turn_event_profile import fragments
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    if (p['schema'] != 'civ6-host.xp2-improvement-route.source.v1'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['images']['core']['sha256'] != XP2_CORE_SHA256
            or p['images']['exe']['sha256'] != _EXE
            or set(p['families']) != {hex(k) for k in KINDS}
            or p['contract']['policy'] != POLICY or p['contract']['omission_admitted'] is not False
            or p['contract']['native_queries_and_releases_preserved'] is not True
            or p['contract']['synthetic_query_outputs'] is not False
            or p['contract']['core_internal_dispatch_before_host'] is not True
            or p['contract']['normalizer_return'] != 0):
        raise ValueError('XP2 improvement/route source contract changed')
    for body in p['functions'].values():
        raw = b''.join(raw for _,raw in fragments(body))
        if (len(raw) != body['bytes'] or hashlib.sha256(raw).hexdigest() != body['sha256']
                or body['complete_unwind_or_leaf'] is not True
                or body['capture']['boundary_method'] != 'complete-runtime-function-chained-unwind-root-v2'):
            raise ValueError('XP2 improvement/route complete source bytes changed')
    expected = {
        IMPROVEMENT_CHANGED: (0x5faa50,0x1477a0,0x133d80),
        ROUTE_CHANGED: (0x5fac20,0x147cc0,0x134a50),
    }
    for kind,(builder,query,writer) in expected.items():
        family = p['families'][hex(kind)]
        if (EXE_EVENT_CALLBACKS.get(kind) != CALLBACKS[kind]
                or family['callback_rva'] != hex(CALLBACKS[kind])
                or (family['builder_rva'],family['query_rva'],family['writer_rva']) !=
                    (hex(builder),hex(query),hex(writer))
                or (family['record_type'],family['record_size']) != (KINDS[kind],SIZES[KINDS[kind]])
                or {int(k,16):v for k,v in family['fields'].items()} != _SHAPES[kind]):
            raise ValueError('XP2 improvement/route registration or field mapping changed')
        callback = set(_texts(p,'exe_'+hex(CALLBACKS[kind])).values())
        if not {'call '+hex(0x140000000+query),'call '+hex(0x140000000+writer)} <= callback:
            raise ValueError('XP2 improvement/route EXE query/writer join changed')
        writer_text = set(_texts(p,'exe_'+hex(writer)).values())
        if not {'mov dword ptr [rbx], '+hex(SIZES[KINDS[kind]]),
                'mov dword ptr [rbx + 4], '+hex(KINDS[kind])} <= writer_text:
            raise ValueError('XP2 improvement/route FIFO writer identity changed')
    # Match the actual producer call, each key assignment, constructor write and
    # every disabled/cleanup branch; fixture-selected tags are not evidence.
    required = {
      'core_0x5faa50': {
        0x5faa91:'mov edx, 0xa1e5a149',0x5faa96:'call 0x1809a0000',
        0x5faaad:'xor r8d, r8d',0x5faabb:'mov edx, 0x8c468e3c',
        0x5faac0:'mov dword ptr [rsp + 0x20], 8',0x5faab0:'mov dword ptr [rsp + 0x28], 1',
        0x5faaa5:'mov dword ptr [rsp + 0x30], 0x1000000',0x5faac8:'call qword ptr [rax + 0xb0]',
        0x5faada:'call 0x18007c670',0x5faaf5:'call qword ptr [rax + 0xa0]',
        0x5fab00:'mov ebx, eax',0x5fab02:'call 0x18099e5d0',0x5fab07:'mov eax, ebx',
        0x5fab12:'or eax, 0xffffffff',0x5fab1d:'ret'},
      'core_0x5fac20': {
        0x5fac71:'mov edx, 0xa1e5a149',0x5fac76:'call 0x1809a0000',
        0x5fac8d:'xor r8d, r8d',0x5fac9b:'mov edx, 0x8c468e3c',
        0x5faca0:'mov dword ptr [rsp + 0x20], 8',0x5fac90:'mov dword ptr [rsp + 0x28], 1',
        0x5fac85:'mov dword ptr [rsp + 0x30], 0x1000000',0x5faca8:'call qword ptr [rax + 0xb0]',
        0x5facb6:'mov edx, 0xd6fcf3e4',0x5facbb:'call 0x18099fee0',
        0x5facc8:'mov edx, 0xa1fbc372',0x5faccd:'call 0x18099fee0',
        0x5facde:'call 0x18007c670',0x5facf9:'call qword ptr [rax + 0xa0]',
        0x5fad04:'mov ebx, eax',0x5fad06:'call 0x18099e5d0',0x5fad0b:'mov eax, ebx',
        0x5fad0f:'or eax, 0xffffffff',0x5fad26:'ret'},
      'core_0x9a0000': {0x9a0079:'mov dword ptr [rbx], 3',0x9a008f:'mov dword ptr [rsp + 0x30], 3'},
      'core_0x99fee0': {0x99ff59:'mov dword ptr [rbx], 2',0x99ff6f:'mov dword ptr [rsp + 0x30], 2'},
      'exe_0x1ca2d0': {0x1ca7bd:'call 0x1401445f0',0x1ca7ca:'xor eax, eax'},
    }
    for name,instructions in required.items():
        actual = _texts(p,name)
        if any(actual.get(address) != text for address,text in instructions.items()):
            raise ValueError('XP2 improvement/route typed producer/order changed: '+name)
    sites = {(r['kind'],r['producer_rva'],r['call_rva'],r['return_consumed']) for r in p['callsites']}
    if sites != {(hex(k),hex(p),hex(c),False) for k,p,c,_ in _SITES}:
        raise ValueError('XP2 improvement/route caller membership changed')
    for kind,producer,call,following in _SITES:
        text = _texts(p,'core_'+hex(producer))
        if (text.get(call) != 'call '+hex(0x180000000+expected[kind][0])
                or text.get(call+5) != following):
            raise ValueError('XP2 improvement/route caller return usage changed')
    if set(p['receiver_rows']) != {'0x90','0x99'}:
        raise ValueError('XP2 improvement/route receiver membership changed')
    for record,ctor,handler in ((0x90,0xcee60,0xd94f0),(0x99,0xcf520,0xd9850)):
        row = p['receiver_rows'][hex(record)]
        if (row['row_va'] != hex(0x1412c68b0+record*48) or row['record_size'] != SIZES[record]
                or row['constructor_rva'] != hex(ctor) or row['handler_rva'] != hex(handler)
                or [t for t in _texts(p,'exe_'+hex(handler)).values() if t.startswith('call ')] !=
                    ['call 0x14098a780','call 0x1400dc0d0','call 0x14098a7b0']):
            raise ValueError('XP2 improvement/route empty receiver changed')
    return p


@lru_cache(maxsize=1)
def source():
    from .native import native_event_30ae2a3d as improvement, native_event_7b65ff2e as route
    p = _verify(_source(SOURCE))
    improvement.verify_source_evidence()
    route.verify_source_evidence()
    return p


verify_source = source


def source_dependencies(*, execution_image=None):
    from .a0_family_source import verify_pinned_files
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .turn_unit_event_profile import source_dependencies as query_dependencies
    p = source()
    pins = query_dependencies(core_sha256=XP2_CORE_SHA256, execution_image=execution_image)
    image_refs = tuple(p['images'].values())
    refs = [dict(path=SOURCE[0],sha256=SOURCE[1]),p['generator'],*p['references'].values()]
    if execution_image is None:
        refs.extend(image_refs)
    for ref in refs:
        path = str(resolve_path(resource_root()/ref['path']).resolve())
        if path in pins and pins[path] != ref['sha256']:
            raise ValueError('XP2 improvement/route source dependency conflict')
        pins[path] = ref['sha256']
    if execution_image is not None:
        from .runtime_source_dependencies import materialize_runtime_source_pins
        pins = materialize_runtime_source_pins(
            pins, execution_image=execution_image, provenance_images=image_refs)
    verify_pinned_files(pins)
    return pins


def core_fragments():
    from .xp2_turn_event_profile import fragments
    for body in source()['functions'].values():
        if body['image'] == 'xp2':
            for address,raw in fragments(body):
                yield address-0x180000000,raw


def verify_live(base,read):
    count = 0
    for rva,raw in core_fragments():
        for offset in range(0,len(raw),4096):
            expected = raw[offset:offset+4096]
            actual = read(base+rva+offset,len(expected))
            if type(actual) is not bytes or actual != expected:
                raise ValueError('XP2 improvement/route live producer source changed')
            count += 1
    return count


@dataclass(frozen=True)
class VerifiedSource:
    owner: object
    core: object
    base: int
    proof_sha256: str
    instructions: int


def bind_owner(owner,core,read,*,execution_image=None):
    from .turn_unit_event_profile import bind_owner as bind_queries
    from .foundation_facade_profiles import verify_xp1_once
    from .paths import resource_root
    owner.check_thread()
    if (owner.core is not core or owner.load_abi.core_sha256 != XP2_CORE_SHA256
            or type(core._handle) is not int or core._handle <= 0):
        raise ValueError('XP2 improvement/route source owner mismatch')
    old = getattr(owner,'_xp2_improvement_change_source',None)
    if old is not None and (type(old) is not VerifiedSource or old.owner is not owner
            or old.core is not core or old.base != core._handle or old.proof_sha256 != SOURCE[1]):
        raise ValueError('XP2 improvement/route source lifetime changed')
    if execution_image is None:
        execution_image = getattr(core, '_civ6_host_execution_image', None)
    source_dependencies(execution_image=execution_image)
    bind_queries(owner,core,read)
    verify_xp1_once(core,core._handle,read,resource_root(),core_sha256=XP2_CORE_SHA256)
    count = verify_live(core._handle,read)
    if old is None:
        old = VerifiedSource(owner,core,core._handle,SOURCE[1],count)
        owner._xp2_improvement_change_source = old
    return old


@lru_cache(maxsize=1)
def _event_profile():
    from .a0_family_source import A0FamilyProfile
    from .native.native_deferred_empty_profile import resolve_empty_receiver_row
    source()
    for record,size in SIZES.items():
        row = resolve_empty_receiver_row(record)
        if row is None or set(row['record_sizes']) != {size}:
            raise ValueError('XP2 improvement/route receiver shape changed')
    return A0FamilyProfile(MappingProxyType({k:frozenset((r,)) for k,r in KINDS.items()}),SIZES,SOURCE[1])


def event_profile(*, execution_image=None):
    if execution_image is not None:
        from .execution_images import identity
        identity(execution_image)
    return _event_profile()


def decode_fields(kind,fields,read):
    """The same EXE typed decoder; this copies the borrowed position now."""
    import struct
    from .native import native_event_30ae2a3d as improvement, native_event_7b65ff2e as route
    source()
    if (type(kind) is not int or kind not in KINDS or type(fields) is not dict
            or set(fields) != set(_SHAPES[kind])
            or any(type(k) is not int or type(raw) is not bytes or len(raw) != 24
                   or struct.unpack_from('<H',raw)[0] != _SHAPES[kind][k]
                   for k,raw in fields.items())):
        raise ValueError('XP2 improvement/route input shape is not source qualified')
    return (improvement if kind == IMPROVEMENT_CHANGED else route).decode_fields(fields,read)


def encode_record(kind,sequence,fields,native_values,**guard_options):
    """Retain exact EXE payload, metadata, padding and empty receiver guards."""
    from .native import native_event_30ae2a3d as improvement, native_event_7b65ff2e as route
    source()
    if type(kind) is not int or kind not in KINDS:
        raise ValueError('Unqualified XP2 improvement/route kind')
    return (improvement if kind == IMPROVEMENT_CHANGED else route).encode_record(
        sequence,fields,native_values,**guard_options)


__all__ = ['SOURCE','KINDS','CALLBACKS','SIZES','POLICY','IMPROVEMENT_CHANGED','ROUTE_CHANGED',
           'source','verify_source','source_dependencies','core_fragments','verify_live','bind_owner',
           'event_profile','VerifiedSource','decode_fields','encode_record']
