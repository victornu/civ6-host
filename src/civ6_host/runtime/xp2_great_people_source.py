"""Exact stock and BBG source selection for installed Gathering Storm Great People."""
from hashlib import sha256

from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP2_CORE_SHA256, _source
from .execution_images import _PROFILE
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp2_bbg_inputs import REFERENCE
from .xp2_bundle_inputs import REFERENCE as STOCK_REFERENCE


SOURCE = (
    'evidence/host-xp2-bbg-great-people-binding-source.json',
    'd1323d0d84ee4b252d9c2a0501ca44e846ae73adee918e403397a60698a351fc',
)
OPERATION_SOURCE = (
    'evidence/host-xp2-bbg-great-people-operation-source.json',
    '448df270d4dea2b63be9caa8b11eeb09b46fceb979e62660dad9ee8d03fed566',
)
STOCK_SOURCE = (
    'evidence/host-xp2-stock-great-people-source.json',
    '30e01273a5374f29ab30a747651f6f5b48b07e59b3073328e7f25f96397d96d8',
)
_STOCK_UI = ('popup', 'economy_extension', 'congress_extension', 'expansion_manifest', 'capabilities')


def _identity(row):
    return row['path'], row['sha256']


def supports(reference, image):
    return image is _PROFILE and type(reference) is tuple and reference in (REFERENCE, STOCK_REFERENCE)


def _stock_proof(shared):
    from .xp2_bundle_inputs import CONFIGURATION_SHA256, SELECTED_PATHS

    stock = _source(STOCK_SOURCE)
    rules = stock['gameplay_contract']
    if (stock['schema'] != 'civ6-host.xp2-stock-great-people.static.v1'
            or stock['image_sha256'] != _PROFILE.image_sha256
            or _identity(stock['capture']) != STOCK_REFERENCE
            or _identity(stock['shared_reader']) != SOURCE
            or _identity(stock['shared_operations']) != OPERATION_SOURCE
            or stock['configuration']['sha256'] != CONFIGURATION_SHA256
            or stock['selected_gameplay_paths'] != SELECTED_PATHS
            or set(stock['ui_sources']) != set(_STOCK_UI)
            or any(_identity(stock['ui_sources'][key]) != _identity(shared['ui_sources'][key])
                   for key in _STOCK_UI)
            or rules['bbg_hidden_class_present'] is not False
            or rules['foreign_class_joins'] != 0 or rules['class_unit_joins'] != rules['class_count']
            or stock['scope_checks']['official_popup_chain_preserved'] is not True
            or stock['scope_checks']['collector_ui_has_no_great_people_replacement'] is not True
            or stock['scope_checks']['congress_read_only_preserved'] is not True
            or stock['native_execution'] is not False or stock['native_command_qualified'] is not False):
        raise ValueError('Stock Gathering Storm Great People source differs')
    return stock


def operation_source(reference):
    if reference == STOCK_REFERENCE:
        return STOCK_SOURCE
    if reference == REFERENCE:
        return OPERATION_SOURCE
    raise ValueError('Unknown Gathering Storm Great People command capture')


def require_source(image, *, reference):
    if not supports(reference, image):
        raise ValueError('Gathering Storm Great People require the exact Boston BBG or stock capture and image')
    proof = _source(SOURCE)
    captured = proof['capture']
    installed = proof['image']
    if (proof['schema'] != 'civ6-host.xp2-bbg751-great-people-bindings.static.v1'
            or _identity(captured) != REFERENCE
            or (installed['profile'], installed['sha256']) != (image.id, image.image_sha256)
            or proof['native_actions_admitted'] is not False
            or proof['guards']['hidden_class_present_in_exact_rules'] is not False
            or proof['guards']['official_popup_read_only_in_congress'] is not True
            or len(proof['bindings']) != 15
            or set(proof['timeline_fields']) != {'Individual', 'Class', 'Era', 'Cost', 'Claimant', 'TurnGranted'}):
        raise ValueError('Gathering Storm Great People source differs')
    if reference == STOCK_REFERENCE:
        _stock_proof(proof)
    return proof


def require_actions(image, *, reference):
    require_source(image, reference=reference)
    proof = _source(OPERATION_SOURCE)
    expected = {
        'recruit_great_person': (0xe8e854ba, (0x385fc342,)),
        'patronize_great_person': (0xebdeb9f6, (0x385fc342, 0x2b8aba02)),
        'reject_great_person': (0x05ace248, (0x385fc342,)),
    }
    if (proof['schema'] != 'civ6-host.xp2-bbg-great-people-operations.static.v1'
            or _identity(proof['reader_source']) != SOURCE
            or _identity(proof['capture']) != REFERENCE
            or proof['image']['sha256'] != image.image_sha256
            or proof['native_command_qualified'] is not False
            or proof['requires_native_can_start'] is not True
            or proof['requires_published_human_offer'] is not True
            or {key: (op['operation'], tuple(op['params'])) for key, op in proof['operations'].items()} != expected
            or proof['archive_construction']['message'] != 0xc45de12f
            or proof['archive_construction']['flags_without_insert_mode'] != 2):
        raise ValueError('Gathering Storm Great Person operation source differs')
    return proof


def source_dependencies(image, *, reference, include_actions=False):
    proof = require_source(image, reference=reference)
    rows = (dict(path=SOURCE[0], sha256=SOURCE[1]), proof['image'])
    if reference == STOCK_REFERENCE:
        bound = _stock_proof(proof)
        rows += (dict(path=STOCK_SOURCE[0], sha256=STOCK_SOURCE[1]), bound['capture'],
                 bound['producer'], bound['configuration'], bound['database'], bound['capture_bridge'],
                 *bound['ui_sources'].values())
    else:
        rows += (proof['capture'], proof['gameplay'], *proof['ui_sources'].values())
    if include_actions:
        commands = require_actions(image, reference=reference)
        rows += (dict(path=OPERATION_SOURCE[0], sha256=OPERATION_SOURCE[1]),
                 commands['player_operation_source'])
    pins = {}
    for row in rows:
        path = str(resolve_path(resource_root() / row['path']).resolve(strict=True))
        if pins.setdefault(path, row['sha256']) != row['sha256']:
            raise ValueError('Conflicting Gathering Storm Great People source pins')
    verify_pinned_files(pins)
    return pins


def verify_live(base, read, *, image, reference):
    proof = require_source(image, reference=reference)
    for row in proof['bindings'].values():
        name = row['name'].encode('ascii') + b'\0'
        if read(base + row['name_rva'], len(name)) != name:
            raise ValueError('Live Great People registration literal differs')
    for name, row in proof['timeline_fields'].items():
        literal = name.encode('ascii') + b'\0'
        if read(base + row['rva'], len(literal)) != literal:
            raise ValueError('Live Great People timeline literal differs')
    spans = [span for row in proof['bindings'].values() for span in (row['registration'], *row['bodies'])]
    spans.extend(proof['timeline_reifier'])
    _verify_spans(base, read, spans)


def _verify_spans(base, read, spans):
    for span in spans:
        rva, length = span['rva'], span['bytes']
        raw = read(base + rva, length)
        if not 0 < length <= 4096 or len(raw) != length or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError(f'Live Gathering Storm Great People binding differs at {rva:#x}')


def bind(saved, *, borrowed_player=None):
    if borrowed_player is None:
        saved._check_query()
    else:
        from .xp1_session_view import _borrowed_xp2_reference

        _borrowed_xp2_reference(saved, borrowed_player)
    backend, prefix = saved.backend, saved.prefix
    core = backend.core
    if (getattr(saved, 'xp2_great_people', False) is not True
            or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or prefix.actions.pending or prefix.deferred_events.pending):
        raise ValueError('Gathering Storm Great People require their selected reader and drained queues')
    lifetime = (core, prefix)
    if getattr(saved, '_xp2_great_people_query_lifetime', None) != lifetime:
        verify_live(core._handle, backend.runtime.read,
                    image=getattr(core, '_civ6_host_execution_image', None),
                    reference=backend.captured_bundle.reference)
        saved._xp2_great_people_query_lifetime = lifetime


def verify_actions_live(base, read, *, image, reference):
    commands = require_actions(image, reference=reference)
    reader = require_source(image, reference=reference)
    definitions = reader['operation_enums']
    for name, row in definitions.items():
        literal = name.encode('ascii') + b'\0'
        if read(base + row['literal_rva'], len(literal)) != literal:
            raise ValueError('Live Gathering Storm Great Person operation selector differs')
    _verify_spans(base, read, (*commands['spans'].values(),
                              *(row['registration'] for row in definitions.values())))


def bind_actions(saved):
    saved._check_active()
    backend, prefix = saved.backend, saved.prefix
    core = backend.core
    lifetime = (core, prefix)
    if (getattr(saved, 'xp2_great_people_actions', False) is not True
            or getattr(saved, '_xp2_great_people_query_lifetime', None) != lifetime
            or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or prefix.actions.pending or prefix.deferred_events.pending):
        raise ValueError('Gathering Storm Great Person actions require their published reader and drained queues')
    prefix.actions.require_empty_native_queue()
    if getattr(saved, '_xp2_great_people_actions_lifetime', None) != lifetime:
        verify_actions_live(core._handle, backend.runtime.read,
            image=getattr(core, '_civ6_host_execution_image', None),
            reference=backend.captured_bundle.reference)
        saved._xp2_great_people_actions_lifetime = lifetime
