"""Source-bound membership of the shared foundation notification family."""
from functools import lru_cache
import hashlib
from types import MappingProxyType
from .a0_family_source import (A0FamilyProfile, _path, verify_pinned_files,
                               verify_extracted_sources)
from .configuration_profiles import _source, XP1_CORE_SHA256
from .saved_load_profiles import XP2_CORE_SHA256

SOURCE = ('work/host-extensions/xp1-foundation-events-static/foundation-events-source-v1.json',
          '57e0f8d5dae2926327304d9efef742454b249d4b0949e389d8e0ffb1e655d0ed')
CODEC_DEPENDENCIES = ('work/host-extensions/xp1-foundation-events-static/foundation-codec-dependencies-v1.json',
                      '1c4d0a55631b6eba9337d85b714d160ef05043e9b2325c9f0b836fe91e9f2202')
PLOT_SOURCE = ('work/host-extensions/xp1-foundation-events-static/foundation-plot-notifications-source-v1.json',
               '4e8c9bfc4e2f0c73bdbaa10b47ca3b2743bcc462dfc946991ba14a9bc1208a82')


EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
PROJECT_KIND = 0x3182bc8e
PROJECT_RECORDS = MappingProxyType({96: 112, 99: 128, 100: 128})
PROJECT_SOURCE = ('work/host-extensions/xp2-game-history-static/turn30-project-completion-source.json',
                  '30e6ef4c84689dae86e47dced8b2b5f3e7f64e98bccefe5b6ca636b670fdb190')


def _rows(body):
    return [row for fragment in body['fragments'] for row in fragment['instructions']]


@lru_cache(maxsize=1)
def project_source():
    from .native import native_event_3182bc8e_project as shared
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS

    proof = _source(PROJECT_SOURCE)
    common = shared.verify_source_evidence()
    bodies = proof['bodies']
    callback = bodies['exe:141b90']
    actual = hashlib.sha256(b''.join(bytes.fromhex(row['bytes']) for row in _rows(callback)))
    caller = {row['text'] for row in _rows(bodies['xp2:102071'])}
    if (proof['images'] != {'xp2': XP2_CORE_SHA256, 'exe': EXE_SHA256}
            or proof['native_execution'] is not False
            or EXE_EVENT_CALLBACKS.get(PROJECT_KIND) != 0x141b00
            or actual.hexdigest() != common['captures']['callback']['code_sha256']
            or not {'mov qword ptr [rsp + 0x30], 0x3182bc8e', 'call 0x1805fbb20'} <= caller):
        raise ValueError('XP2 project completion source changed')
    return proof


def project_core_fragments():
    for key, body in project_source()['bodies'].items():
        if key.startswith('xp2:'):
            for fragment in body['fragments']:
                yield (int(fragment['start_va'], 16) - 0x180000000,
                       b''.join(bytes.fromhex(row['bytes']) for row in fragment['instructions']))


def verify_project_live(core_base, read):
    for rva, raw in project_core_fragments():
        for offset in range(0, len(raw), 4096):
            chunk = raw[offset:offset + 4096]
            if read(core_base + rva + offset, len(chunk)) != chunk:
                raise ValueError('XP2 project completion producer live bytes changed')


PILLAGE_SOURCE = (
    'evidence/host-xp2-turn36-building-pillage-refusal.json',
    '4d9079ae16cd631c5f3b52c69293ea0660f8a09979dea3b68e800f4fa1a1bac1',
)


@lru_cache(maxsize=2)
def pillage_source(execution_image=None):
    from .native import native_event_e660_building_pillaged as codec

    proof = _source(PILLAGE_SOURCE)
    codec.verify_source_evidence(execution_image=execution_image)
    if (proof['schema'] != 'civ6-host.xp2-turn36-building-pillage-refusal.v1'
            or proof['core_sha256'] != XP2_CORE_SHA256
            or proof['refusal_headers']['dispatch_kind'] != hex(codec.EVENT_KIND)
            or set(proof['core_producer']) != {'0x5fb580', '0x10eafe'}
            or not any(row['text'] == 'call 0x1805fb580'
                       for row in proof['core_producer']['0x10eafe']['instructions'])):
        raise ValueError('XP2 building-pillage producer changed')
    return proof


def verify_pillage_live(core_base, read, *, execution_image=None):
    for rva, body in pillage_source(execution_image=execution_image)['core_producer'].items():
        raw = bytes.fromhex(body['raw_hex'])
        if (hashlib.sha256(raw).hexdigest() != body['sha256']
                or read(core_base + int(rva, 16), len(raw)) != raw):
            raise ValueError('XP2 building-pillage live producer changed')


def plot_source():
    p = _source(PLOT_SOURCE)
    if (p['schema'] != 'civ6_host.xp1_foundation_plot_notifications.static.v1'
            or dict(p['kind_to_record_types']) != {'2274153042': (118,), '424708295': (138,)}
            or dict(p['record_type_to_size']) != {'118': 128, '138': 96}):
        raise ValueError('Foundation Plot notification membership changed')
    return p


def source():
    p = _source(SOURCE)
    v = p['validation']
    if (p['schema'] != 'civ6_host.xp1_foundation_events.static.v1'
            or p['images']['xp1_core_sha256'] != XP1_CORE_SHA256
            or v['native_execution'] is not False or v['source_hashes_checked'] is not True
            or v['all_retained_records_validated'] is not True
            or v['kind_count'] != 17 or v['record_type_count'] != 18
            or len(p['kind_to_record_types']) != 17
            or len(p['record_type_to_size']) != 18):
        raise ValueError('Foundation callback source contract changed')
    return p


def source_dependencies(*,core_sha256=XP1_CORE_SHA256,execution_image=None):
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
        raise ValueError('Unknown foundation event engine')
    if execution_image is not None and core_sha256!=XP2_CORE_SHA256:
        raise ValueError('Selected execution image requires the XP2 foundation source')
    p = source()
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), *p['references'], *p['source_modules']]
    closure = _source(CODEC_DEPENDENCIES)
    # Superset dependencies preserve their identities, not admission. In
    # particular building pillage requires a separate engine-specific producer
    # proof and is still refused by the XP1 adapter.
    refs.extend([dict(path=CODEC_DEPENDENCIES[0], sha256=CODEC_DEPENDENCIES[1]),
                 *closure['references'], *closure['source_modules']])
    plot = plot_source()
    refs.extend([dict(path=PLOT_SOURCE[0], sha256=PLOT_SOURCE[1]),
                 *plot['references'], *plot['source_modules']])
    from .foundation_facade_profiles import SOURCE as FACADE_SOURCE, source as facade_source
    from .paths import resource_root
    if core_sha256==XP1_CORE_SHA256:
        facade_source(resource_root())
        refs.append(dict(path=FACADE_SOURCE[0], sha256=FACADE_SOURCE[1]))
    pins = {}
    for ref in refs:
        path = str(_path(ref['path']))
        if path in pins and pins[path] != ref['sha256']:
            raise ValueError('Conflicting foundation dependency identity')
        pins[path] = ref['sha256']
    from .foundation_facade_profiles import source_dependencies as facade_dependencies
    from .xp1_visibility_cache_gate import source_dependencies as gate_dependencies
    selected={}
    if core_sha256==XP2_CORE_SHA256:
        selected.update(facade_dependencies(core_sha256=core_sha256))
        from .native import native_event_3182bc8e as initial, native_event_3182bc8e_project as project
        project_source()
        pillage_source(execution_image=execution_image)
        from .native.native_event_e660_building_pillaged import source_dependencies as pillage_dependencies
        from .xp2_wonder_completion import source_dependencies as wonder_dependencies
        for path, digest in (PILLAGE_SOURCE, PROJECT_SOURCE):
            selected[str(_path(path).resolve())] = digest
        for path, digest in (*pillage_dependencies(execution_image=execution_image).items(), *wonder_dependencies().items()):
            if path in selected and selected[path] != digest:
                raise ValueError('Conflicting foundation extended-event dependency')
            selected[path] = digest
        for codec in (initial, project):
            path, sha = str(codec._PROOF.resolve()), codec.PINNED_EVIDENCE_SHA256
            if path in selected and selected[path] != sha:
                raise ValueError('Conflicting foundation project dependency')
            selected[path] = sha
    for path, sha in selected.items():
        if path in pins and pins[path] != sha:
            raise ValueError('Conflicting foundation facade identity')
        pins[path]=sha
    for path, sha in gate_dependencies(core_sha256=core_sha256).items():
        if path in pins and pins[path] != sha:
            raise ValueError('Conflicting foundation cache identity')
        pins[path] = sha
    from .application_mirror_profiles import civilization_source_dependencies
    for path, sha in civilization_source_dependencies(core_sha256).items():
        if path in pins and pins[path] != sha:
            raise ValueError('Conflicting civilization getter source identity')
        pins[path] = sha
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_wmd_fallout_visibility import source_dependencies as wmd_dependencies
        for path, sha in wmd_dependencies().items():
            if path in pins and pins[path]!=sha:
                raise ValueError('Conflicting XP2 WMD visibility dependency')
            pins[path]=sha
    if execution_image is not None:
        from .runtime_source_dependencies import materialize_runtime_source_pins
        pins=materialize_runtime_source_pins(pins,execution_image=execution_image)
    verify_pinned_files(pins)
    return pins


def event_profile(*,core_sha256=XP1_CORE_SHA256,execution_image=None):
    if core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
        raise ValueError('Unknown foundation event engine')
    if execution_image is not None and core_sha256!=XP2_CORE_SHA256:
        raise ValueError('Selected execution image requires the XP2 foundation event profile')
    p = source()
    plot = plot_source()
    if core_sha256==XP2_CORE_SHA256:
        if p['images']['exe_sha256']!=EXE_SHA256:
            raise ValueError('Foundation host/receiver EXE profile differs')
        # Membership belongs to the shared EXE receiver and host dispatcher.
        # XP1 Core producer bytes are retained source context only; they do not
        # establish that these notifications occur in XP2.
        from .xp2_turn_notification_source import source as xp2_event_source
        current=xp2_event_source()
        if set(map(int,current['kind_to_record_types'])) & set(map(int,p['kind_to_record_types'])):
            raise ValueError('XP2 notification families overlap foundation dispatch membership')
        source_dependencies(core_sha256=core_sha256,execution_image=execution_image)
    else:
        source_dependencies(core_sha256=core_sha256)
    verify_extracted_sources((*p['source_modules'], *plot['source_modules']))
    from .native.native_deferred_empty_profile import _ROWS
    available_rows = _ROWS
    mapping = {int(k): frozenset(v) for k, v in p['kind_to_record_types'].items()}
    sizes = {int(k): v for k, v in p['record_type_to_size'].items()}
    if set(p['kind_to_record_types']) & set(plot['kind_to_record_types']):
        raise ValueError('Foundation Plot supplement overlaps another producer')
    mapping.update({int(k): frozenset(v) for k, v in plot['kind_to_record_types'].items()})
    sizes.update({int(k): v for k, v in plot['record_type_to_size'].items()})
    receiver_rows = dict(p['receiver_rows'])
    receiver_rows.update(plot['receiver_rows'])
    if core_sha256==XP2_CORE_SHA256:
        from . import xp2_wmd_fallout_visibility as wmd
        from .native.native_deferred_empty_profile import resolve_empty_receiver_row
        if wmd.KIND in mapping or wmd.RECORD_TYPE in sizes:
            raise ValueError('XP2 WMD visibility overlaps a foundation event')
        row=resolve_empty_receiver_row(wmd.RECORD_TYPE)
        if row!=wmd.receiver_row():
            raise ValueError('XP2 WMD visibility receiver differs from dispatch')
        mapping[wmd.KIND]=frozenset((wmd.RECORD_TYPE,))
        sizes[wmd.RECORD_TYPE]=wmd.RECORD_SIZE
        receiver_rows[str(wmd.RECORD_TYPE)]=row
        available_rows={**_ROWS,wmd.RECORD_TYPE:row}
        if mapping.get(PROJECT_KIND) != frozenset((96,)) or sizes.get(96) != PROJECT_RECORDS[96]:
            raise ValueError('Unexpected existing project completion ownership')
        for record in (99, 100):
            row = resolve_empty_receiver_row(record)
            if record in sizes or row is None or row['record_sizes'] != {PROJECT_RECORDS[record]}:
                raise ValueError('XP2 project completion receiver differs')
            available_rows[record] = receiver_rows[str(record)] = row
            sizes[record] = PROJECT_RECORDS[record]
        mapping[PROJECT_KIND] = frozenset(PROJECT_RECORDS)
        from .native import native_event_e660_building_pillaged as pillage
        row = resolve_empty_receiver_row(pillage.RECORD_TYPE)
        if (mapping.get(pillage.EVENT_KIND) != frozenset((166, 169))
                or pillage.RECORD_TYPE in sizes or row is None
                or row['event_name'] != 'GameCoreEvent::BuildingPillaged'
                or row['record_sizes'] != {pillage.RECORD_SIZE}):
            raise ValueError('XP2 building-pillage receiver differs')
        mapping[pillage.EVENT_KIND] |= frozenset((pillage.RECORD_TYPE,))
        sizes[pillage.RECORD_TYPE] = pillage.RECORD_SIZE
        available_rows[pillage.RECORD_TYPE] = receiver_rows[str(pillage.RECORD_TYPE)] = row
        from .native.native_event_e66012a7_wonder import RECORD_SIZE, RECORD_TYPES
        from .xp2_wonder_completion import KIND, source as wonder_source
        wonder_source()
        for record_type in RECORD_TYPES:
            row = resolve_empty_receiver_row(record_type)
            if record_type in sizes or row is None or row['record_sizes'] != {RECORD_SIZE}:
                raise ValueError('XP2 wonder completion receiver differs')
            available_rows[record_type] = receiver_rows[str(record_type)] = row
            sizes[record_type] = RECORD_SIZE
        mapping[KIND] |= frozenset(RECORD_TYPES)
    if set().union(*mapping.values()) != set(sizes):
        raise ValueError('Foundation record membership differs')
    for kind, size in sizes.items():
        row = available_rows[kind]
        expected = receiver_rows[str(kind)]
        if (row['record_sizes'] != {size}
                or any(row[k] != expected[k] for k in ('event_name', 'handler_va', 'handler_body_sha256'))):
            raise ValueError('Foundation empty receiver contract differs')
    return A0FamilyProfile(MappingProxyType(mapping), MappingProxyType(sizes), PLOT_SOURCE[1])
