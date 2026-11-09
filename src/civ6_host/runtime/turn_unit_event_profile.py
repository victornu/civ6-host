"""Engine-selected Unit/Improvement notification ABI, not gameplay admission.

The algorithms remain the shared EXE codecs. These snapshots feed the verified
empty presentation receivers; they are not player observations or agent inputs.
"""
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256, _source

SOURCE = ('work/host-extensions/xp1-turn-units-static/turn-units-source-v1.json',
          'c4c0eccf1e2ee3beba92c5eeb96c06d8060d26de5ad077bf1206390df2fb7bcd')
KINDS = {0xb8515a41: 28, 0xc50d66d6: 25, 0x6e7ef927: 24,
         0xa625c726: 148, 0xe5b20b82: 143}
SIZES = {28: 160, 25: 112, 24: 128, 148: 144, 143: 144}
TABLES = {
 'outer': (0x8a8df0, {0x90:0x4bcfe0,0xa8:0x4bd140,0xb8:0x4bd1a0,0x100:0x4bcf80}),
 'player': (0x8aa2c8, {8:0x4c6a80,0x18:0x4c7010,0x28:0x4c7150,0x110:0x4c74b0}),
 'units': (0x8aab38, {8:0x4ca430,0x10:0x4ca450}),
 'unit': (0x8ab0f8, {0x10:0x4cc400,0x28:0x4cc6c0,0x50:0x4cc590,0x58:0x4cc4f0,0x88:0x4cc7d0,0xb8:0x4cc470}),
 'data': (0x8a92e0, {8:0x4be7c0,0x260:0x4c2160,0x308:0x4c1e60,0x368:0x4c2a40}),
 'game': (0x8a9a88, {8:0x4c3790,0x128:0x4c3b30}),
 'map': (0x8aa088, {8:0x4c5930,0x40:0x4c5f50}),
 'plot': (0x8aacd8, {8:0x4cb070,0x30:0x4cb110,0x60:0x4cb340,0xc0:0x4cb590,0xc8:0x4cb760,0xe0:0x4cb720,0x178:0x4cb090,0x180:0x4cb0f0}),
 'component': (0x8613e8, {8:0x13fb0,0x10:0x14070,0x18:0x14030,0x30:0x13fd0}),
}
OPERATIONS = {
 'get_player':('outer',0xb8), 'release_player':('player',8),
 'player_units':('player',0x110), 'release_units':('units',8),
 'units_index':('units',0x10), 'release_unit':('unit',0x10),
 'unit_snapshot':('unit',0xb8), 'outer_map':('outer',0xa8),
 'get_plot':('map',0x40), 'release_map':('map',8),
 'release_plot':('plot',8), 'plot_component':('plot',0x60),
 'release_component':('component',8), 'snapshot180':('plot',0x180),
 'snapshot178':('plot',0x178), 'component10':('component',0x10),
 'component18':('component',0x18), 'component30':('component',0x30),
 'plot30':('plot',0x30), 'plotc8':('plot',0xc8),
 'plotc0':('plot',0xc0), 'plote0':('plot',0xe0),
 'get_game':('outer',0x90), 'get_local_team':('game',0x128),
 'release_game':('game',8),
}


@lru_cache(maxsize=2)
def verify_source(*, core_sha256=XP1_CORE_SHA256):
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_turn_notification_source import source
        return source()
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Unqualified Unit/Improvement engine')
    p = _source(SOURCE)
    if (p['schema'] != 'civ6_host.xp1_turn_units.static.v1'
            or p['image']['sha256'] != XP1_CORE_SHA256
            or p['native_execution'] is not False
            or p['validation']['instruction_bytes_match_image'] is not True
            or p['validation']['kind_count'] != 5):
        raise ValueError('XP1 turn Unit source identity changed')
    actual = {name:(row[0], {int(s):v for s,v in row[1].items()})
              for name,row in p['tables'].items()}
    if actual != TABLES:
        raise ValueError('XP1 turn Unit facade ABI changed')
    if ({int(k):tuple(v) for k,v in p['kind_to_record_types'].items()}
            != {k:(v,) for k,v in KINDS.items()}
            or {int(k):v for k,v in p['record_type_to_size'].items()} != SIZES):
        raise ValueError('XP1 turn Unit record membership changed')
    snap = p['unit_snapshot']
    if dict(snap) != dict(method_rva=0x4cc470,target_rva=0xab250,live_pointer_offset=8,
            bytes=184,string_offset=16,scalar_offset=28,string_empty=0x839d30,
            string_assign=0x8399e0,string_free=0x836b10,free_iat=0x85d678):
        raise ValueError('XP1 Unit snapshot/FString layout changed')
    checks = {
      '0x4cc470': ('mov rcx, qword ptr [rcx + 8]', 'jmp 0x1800ab250'),
      '0xab250': ('mov dword ptr [rdx + 0x1c], eax', 'lea rcx, [rbx + 0x10]', 'jmp 0x1808399e0'),
      '0x13f90': ('mov qword ptr [rcx + 8], rdx', 'mov dword ptr [rcx + 0x10], 1'),
      '0x14070': ('jne 0x180042570',), '0x14030': ('jne 0x180042550',),
      '0x13fd0': ('jne 0x1800424b0',),
    }
    for key, expected in checks.items():
        texts = {r['text'] for r in p['functions'][key]['instructions']}
        if not set(expected) <= texts:
            raise ValueError('XP1 Unit implementation seam changed: '+key)
    for reference in p['references']:
        _source((reference['path'], reference['sha256']))
    return p


def source_reference(*, core_sha256=XP1_CORE_SHA256):
    verify_source(core_sha256=core_sha256)
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_turn_notification_source import SOURCE as selected
        return selected
    return SOURCE


def _tables(core_sha256):
    p=verify_source(core_sha256=core_sha256)
    if core_sha256 == XP1_CORE_SHA256:return TABLES
    return {name:(row[0], {int(s):v for s,v in row[1].items()})
            for name,row in p['tables'].items()}


def select_tables(core_sha256, retained):
    """Retain the exact subset and iterable shape requested by a shared body."""
    if core_sha256 == BASE_CORE_SHA256:
        return retained
    tables = _tables(core_sha256)
    selected = {}
    for name, (_, slots) in retained.items():
        table, available = tables[name]
        keys = slots if isinstance(slots, dict) else [s for s,_ in slots]
        values = {s:available[s] for s in keys}
        selected[name] = (table, values if isinstance(slots, dict) else tuple(values.items()))
    return selected


def select_specs(core_sha256, retained):
    if core_sha256 == BASE_CORE_SHA256:
        return retained
    tables = _tables(core_sha256)
    selected = {}
    for name, (_, result, arguments) in retained.items():
        if name in ('string_empty', 'string_free'):
            rva = verify_source(core_sha256=core_sha256)['unit_snapshot'][name]
        else:
            table, slot = OPERATIONS[name]
            rva = tables[table][1][slot]
        selected[name] = (rva, result, arguments)
    return selected


def unit_live_offset(core_sha256):
    if core_sha256 == BASE_CORE_SHA256:
        return 16
    return verify_source(core_sha256=core_sha256)['unit_snapshot']['live_pointer_offset']


def read_application_mode(application, core_sha256, candidate_backend=None):
    from .native.native_app_ownership import read_application_mode as shared
    if core_sha256 == BASE_CORE_SHA256:
        if candidate_backend is not None:
            raise ValueError('Base mode cannot borrow an expansion owner')
        return shared(application)
    if (core_sha256 not in (XP1_CORE_SHA256, XP2_CORE_SHA256) or candidate_backend is None
            or candidate_backend.owner is not application
            or candidate_backend.load_abi.core_sha256 != core_sha256):
        raise ValueError('Expansion mode needs its exact application backend')
    return shared(application, candidate_backend=candidate_backend)


def source_dependencies(*, core_sha256=XP1_CORE_SHA256, execution_image=None):
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_turn_notification_source import source_dependencies as selected
        from .foundation_facade_profiles import source_dependencies as facade_dependencies
        from .application_mirror_profiles import civilization_source_dependencies
        from .xp1_load_capability import source_dependencies as capability_dependencies
        from .xp1_visibility_cache_gate import source_dependencies as cache_dependencies
        from .xp2_turn_notification_source import source as turn_source
        image=turn_source()['image']
        if execution_image is not None:
            from pathlib import Path
            if (str(Path(image['path']).resolve())!=str(Path(execution_image.path).resolve())
                    or image['sha256']!=execution_image.reference_core_sha256):
                raise ValueError('XP2 turn-unit provenance differs from the selected execution/reference pair')
        pins=selected()
        for extra in (facade_dependencies(core_sha256=core_sha256,
                      execution_image=execution_image),
                      civilization_source_dependencies(core_sha256),
                      capability_dependencies(core_sha256),
                      cache_dependencies(core_sha256=core_sha256,
                      **({'execution_image':execution_image} if execution_image is not None else {}))):
            if execution_image is not None:
                from .runtime_source_dependencies import materialize_runtime_source_pins
                extra=materialize_runtime_source_pins(extra,execution_image=execution_image,
                    provenance_images=(image,))
            for path,sha in extra.items():
                if path in pins and pins[path]!=sha:raise ValueError('Conflicting turn notification dependency')
                pins[path]=sha
        if execution_image is not None:
            from .runtime_source_dependencies import materialize_runtime_source_pins
            pins=materialize_runtime_source_pins(pins,execution_image=execution_image,
                provenance_images=(image,))
            from .a0_family_source import verify_pinned_files
            verify_pinned_files(pins)
        return pins
    if execution_image is not None:
        raise ValueError('Selected execution image requires the XP2 turn-unit ABI')
    verify_source(core_sha256=core_sha256)
    from .a0_family_source import _path
    p = verify_source()
    refs = [dict(path=SOURCE[0],sha256=SOURCE[1]), *p['references'], *p['source_modules']]
    pins = {str(_path(r['path'])):r['sha256'] for r in refs}
    from .foundation_event_profile import source_dependencies as foundation_dependencies
    pins.update(foundation_dependencies())
    # Retain the already-qualified configuration/mode provider and its closure.
    from .xp1_load_capability import SOURCE as MODE, CALLER, CONVERGENCE
    for path, sha in (MODE, CALLER, CONVERGENCE):
        _source((path,sha)); pins[str(_path(path))] = sha
    return pins


def event_profile(*, core_sha256=XP1_CORE_SHA256, execution_image=None):
    from .a0_family_source import A0FamilyProfile, verify_pinned_files, verify_extracted_sources
    from .native.native_deferred_empty_profile import _ROWS
    p = verify_source(core_sha256=core_sha256)
    verify_pinned_files(source_dependencies(core_sha256=core_sha256,
        execution_image=execution_image))
    verify_extracted_sources(p['source_modules'])
    for kind,size in SIZES.items():
        actual = _ROWS[kind]; expected = p['receiver_rows'][str(kind)]
        if (set(actual['record_sizes']) != {size}
                or any(actual[k] != expected[k] for k in expected)):
            raise ValueError('XP1 turn Unit empty receiver changed')
    return A0FamilyProfile(MappingProxyType({k:frozenset((v,)) for k,v in KINDS.items()}),
                           MappingProxyType(SIZES), source_reference(core_sha256=core_sha256)[1])


def verify_live(base, read, *, core_sha256=XP1_CORE_SHA256):
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_turn_notification_source import verify_live as selected
        return selected(base,read)["verified_fragments"]
    verify_source(core_sha256=core_sha256)
    from .xp1_status_profiles import _instruction_spans
    p = verify_source(); spans = _instruction_spans(p)
    for rva, raw in spans:
        if read(base+rva,len(raw)) != raw:
            raise ValueError('XP1 Unit instruction bytes changed at '+hex(rva))
    for table,slots in TABLES.values():
        for slot,target in slots.items():
            if read(base+table+slot,8) != (base+target).to_bytes(8,'little'):
                raise ValueError('XP1 Unit vtable slot changed')
    return len(spans)


@dataclass(frozen=True)
class VerifiedTurnUnitSource:
    owner: object
    core: object
    base: int
    source_sha256: str
    instruction_read_spans: int


def bind_owner(owner, core, read):
    owner.check_thread()
    if (owner.core is not core or owner.load_abi.core_sha256 not in (XP1_CORE_SHA256, XP2_CORE_SHA256)
            or type(core._handle) is not int or core._handle <= 0):
        raise ValueError('XP1 turn Unit source owner mismatch')
    core_sha256=owner.load_abi.core_sha256
    selected_source=source_reference(core_sha256=core_sha256)
    existing = getattr(owner, '_xp1_turn_unit_source_receipt', None)
    if existing is not None:
        if (type(existing) is not VerifiedTurnUnitSource or existing.owner is not owner
                or existing.core is not core or existing.base != core._handle
                or existing.source_sha256 != selected_source[1]):
            raise ValueError('XP1 turn Unit source receipt changed lifetime')
        return existing
    receipt = VerifiedTurnUnitSource(owner,core,core._handle,selected_source[1],verify_live(core._handle,read,core_sha256=core_sha256))
    owner._xp1_turn_unit_source_receipt = receipt
    return receipt
