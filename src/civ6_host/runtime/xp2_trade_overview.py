"""Publish the trade overview for selected captured BBG profiles."""
from hashlib import sha256
from pathlib import Path
from struct import unpack_from

from civ6_host.contracts import trade_overview
from .execution_images import ExecutionImageProfile
from .paths import resource_root
from .resource_resolution import resolve_path
from .native import native_trade_overview as native
from .native.native_source_cache import load_pinned_json
from .xp1_world_input import _owner

_ORIGIN = ('work/official-capture/bbg751-world-A-ui/manifest.json',
           '0438263e3e78b78233153afe0bc4e1ace6ac8e315aed21e4507f738bae8b285d')
_SOURCE = ('work/official-capture/bbg751-world-A-trade-ui-association/source.json',
           '66b81882c8430970f0b0abe8094c6d2d10dc01f21bb71bfaba2b4e84ccfa2b9f')
_CHOOSER = ('work/official-capture/bbg751-world-A-trade-ui-association/trade-chooser-source-delta.json',
            '5fec623c1188fda4d05bef51b5e4ae4936f76547dca574b2e2b6364bada9c8ef')
_CORRELATED = ('work/official-capture/xp2-bbg751-correlated-20261104/recovered-exact-inputs.json',
               '6bdcd32192781f3f92d26ee4632ce2539ccf2a95baa6b25d34f4616f26b1805a')
_CORRELATED_SOURCE = ('work/official-capture/bbg751-world-A-trade-ui-association/correlated-trade-ui-source.json',
                      'ef2d68a5bea067289924b3b80bffc6526d4e651b09e87458737afd4cdf5b64e4')
_CORE = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
_CIVIC_SOURCE = ('work/trade-common-client/xp2-current-trade-civic-hook-source.json',
                 '978c203c768504b9a631bb83224c3c612d418d127c56809d59a2ff31fee9f508')


def _civic_source():
    path = resolve_path(resource_root() / _CIVIC_SOURCE[0]).resolve()
    proof = load_pinned_json(path, _CIVIC_SOURCE[1])
    if (proof['schema'] != 'civ6-host.xp2-current-trade-civic-hook-source.v1'
            or proof['image']['sha256'] != _CORE or proof['abi'] != dict(kind=0x87667464,
                record_type=192, record_size=96, sequence_offset=80, player_offset=84, civic_offset=88)):
        raise ValueError('Trade civic hook source differs')
    return path, proof


def supports(reference, execution_image):
    return (reference in (_ORIGIN, _CORRELATED) and type(execution_image) is ExecutionImageProfile
            and execution_image.image_sha256 == _CORE)


def source_dependencies(reference, execution_image):
    if not supports(reference, execution_image):
        raise ValueError('Trade overview has no selected UI for this captured bundle and image')
    root = resource_root()
    path = resolve_path(root / _SOURCE[0]).resolve()
    proof = load_pinned_json(path, _SOURCE[1])
    chooser_path = resolve_path(root / _CHOOSER[0]).resolve()
    chooser = load_pinned_json(chooser_path, _CHOOSER[1])
    if (proof['schema'] != 'civ6-host.xp2-bbg751-world-a-trade-ui-association.v1'
            or proof['same_captured_lua_file_object'] is not True
            or (proof['official_manifest']['path'], proof['official_manifest']['sha256']) != _ORIGIN
            or proof['engine']['gamecore_sha256'] != execution_image.image_sha256):
        raise ValueError('Trade overview UI association differs from the selected input')
    if (chooser['schema'] != 'civ6-host.xp2-bbg-world-a-trade-chooser-source-delta.v1'
            or chooser['association']['sha256'] != _SOURCE[1]
            or chooser['official_selection']['same_world_a_lua_file'] is not True):
        raise ValueError('Trade chooser does not share the selected BBG display source')

    paths = {str(path): _SOURCE[1], str(chooser_path): _CHOOSER[1]}
    files = [proof['official_manifest'], *proof['selection_before_after'], *proof['hook_sources'],
             *(row['snapshot'] for row in proof['evidence'].values()),
             chooser['stock_chooser'], chooser['bbg_chooser']]
    if reference == _CORRELATED:
        correlated_path = resolve_path(root / _CORRELATED_SOURCE[0]).resolve()
        correlated = load_pinned_json(correlated_path, _CORRELATED_SOURCE[1])
        manifest = correlated['official_manifest']
        if (correlated['schema'] != 'civ6-host.xp2-bbg-correlated-trade-ui-source.v1'
                or (manifest['path'], manifest['sha256']) != reference
                or correlated['headless_core_sha256'] != execution_image.image_sha256
                or correlated['trade_ui_criteria_match'] is not True
                or correlated['no_competing_trade_ui_component'] is not True
                or correlated['selected_overview'] != 'ui/replacements/tradeoverview_bbg.lua'):
            raise ValueError('Correlated trade UI selection differs from the selected input')
        paths[str(correlated_path)] = _CORRELATED_SOURCE[1]
        files.extend((manifest, correlated['retained_witness'],
                      *correlated['selection_sources'], *correlated['installed_sources']))
    for row in files:
        paths[str(resolve_path(root / Path(row['path'])).resolve())] = row['sha256']
    from .source_verification import file_sha256
    for pinned, digest in paths.items():
        if file_sha256(Path(pinned)) != digest:
            raise ValueError('Trade overview UI association source changed: ' + pinned)
    paths.update(native.source_dependencies())
    path, _ = _civic_source()
    paths[str(path)] = _CIVIC_SOURCE[1]
    from . import xp2_trade
    from .native import native_saved_trade
    for source in (__file__, native.__file__, xp2_trade.__file__, native_saved_trade.__file__):
        paths[str(Path(source).resolve())] = file_sha256(Path(source))
    return paths


def stock_source_dependencies(reference, *, core_sha256, execution_image=None):
    """Require an exact stock capture and its selected UI source closure."""
    from civ6_host.contracts.trade_overview import STOCK_PROFILE
    from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
    from .source_verification import file_sha256

    if core_sha256 == XP1_CORE_SHA256 and execution_image is None:
        from .xp1_saved_load import REFERENCE
        expansion = 'Expansion1'
    elif (core_sha256 == XP2_CORE_SHA256 and type(execution_image) is ExecutionImageProfile
            and execution_image.image_sha256 == _CORE
            and execution_image.reference_core_sha256 == XP2_CORE_SHA256):
        from .xp2_bundle_inputs import REFERENCE
        expansion = 'Expansion2'
    else:
        raise ValueError('Unknown execution image for the standard trade overview')
    if reference != REFERENCE:
        raise ValueError('Standard trade overview requires its exact stock capture')

    root = resource_root()
    proof = native.stock_capture_source()
    stock = proof['candidates'][expansion]
    capture = stock['capture']
    if ((capture['path'], capture['sha256']) != reference
            or stock['native_core_capture_sha256'] != core_sha256
            or stock['no_selected_trade_lua_override'] is not True
            or stock['trade_view_capability_defined'] is not True):
        raise ValueError('Stock trade selection differs from the native input')

    pins = native.source_dependencies(STOCK_PROFILE)
    for row in (capture, stock['database'], stock['panel_context'], *stock['hooks'],
                *stock['selection'], *proof['retained_registry_snapshots']):
        file = resolve_path(root / Path(row['path'])).resolve()
        if file_sha256(file) != row['sha256']:
            raise ValueError('Stock trade UI association source changed: ' + str(file))
        pins[str(file)] = row['sha256']
    for source in (__file__, native.__file__):
        file = Path(source).resolve()
        pins[str(file)] = file_sha256(file)
    if expansion == 'Expansion2':
        path, _ = _civic_source()
        pins[str(path)] = _CIVIC_SOURCE[1]
    return pins


def bind_civic_hook(saved):
    """Bind the local UI capacity check to the verified CivicCompleted FIFO."""
    backend, continuation, prefix = saved.backend, saved.continuation, saved.prefix
    image = getattr(backend.core, '_civ6_host_execution_image', None)
    if type(image) is not ExecutionImageProfile or image.image_sha256 != _CORE:
        return
    continuation.check(active=False)
    owner = prefix.event_arguments.consumer
    events, runtime, child = prefix.deferred_events, prefix.runtime, prefix.ui_child
    if (owner.deferred is not events or events.core is not backend.core or events.pending
            or getattr(owner, 'trade_overview_civic_receiver', None) is not None):
        raise ValueError('Trade civic hook requires one live deferred receiver')
    _, proof = _civic_source()
    for name, span in proof['core_bodies'].items():
        raw = backend.runtime.read(backend.core._handle + span['rva'], span['bytes'])
        if type(raw) is not bytes or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live trade civic hook source changed: ' + name)

    def completed(record, sequence):
        if (len(record) != 96 or unpack_from('<II', record, 4) != (192, sequence)
                or not events._draining_empty_receivers or events.consumed_count != sequence
                or prefix.ui_child is not child or prefix.runtime is not runtime
                or saved.backend is not backend or saved.prefix is not prefix
                or prefix.event_arguments.consumer is not owner):
            raise ValueError('Trade civic hook crossed the owned notification')
        payload_sequence, player_id, civic_index = unpack_from('<IiI', record, 80)
        if payload_sequence != sequence:
            raise ValueError('Trade civic hook payload sequence differs')
        last_turn, unlocked = getattr(saved, '_trade_overview_unlock', (None, False))
        if player_id != 0 or unlocked:
            return
        backend.check_thread()
        produced = events._sequence
        raw = runtime.evaluate_text(child, native.CIVIC_CAPACITY_LUA, b'@trade_civic_capacity', capacity=64)
        turn, capacity = native.parse_civic_capacity(raw)
        if events.consumed_count != sequence or events._sequence != produced:
            raise RuntimeError('Trade civic capacity query changed the native FIFO')
        saved._trade_overview_unlock = (last_turn, capacity > 0)
        saved.emit('native_trade_overview_civic_checked', turn=turn, player_id=player_id,
                   civic_index=civic_index, deferred_sequence=sequence, capacity=capacity,
                   unlocked=capacity > 0, source_sha256=_CIVIC_SOURCE[1])

    owner.trade_overview_civic_receiver = completed


def read(saved, observation, decisions):
    owner = _owner(saved, active=False)
    b, c, _, _ = owner
    image = getattr(b.core, '_civ6_host_execution_image', None)
    if (getattr(saved, 'trade_overview_ui_selected', False) is not True
            or not supports(b.captured_bundle.reference, image)
            or observation != c.observation or observation['player_id'] != 0):
        raise ValueError('Trade overview requires its captured local player and current view')
    if decisions['trade_routes'] is None:
        return None, 'waiting_or_closed'
    if decisions['world_congress']['in_session']:
        return None, 'ui_boundary_unavailable'
    return _read(saved, owner, observation, decisions['sequence'], trade_overview.PROFILE)


def read_stock(saved, observation, sequence):
    from .xp2_bundle_inputs import REFERENCE
    owner = _owner(saved, active=False)
    b, c, _, _ = owner
    if (getattr(saved, 'standard_trade', False) is not True
            or b.captured_bundle.reference != REFERENCE
            or observation != c.observation or observation['player_id'] != 0):
        raise ValueError('Standard trade overview requires the captured local view')
    return _read(saved, owner, observation, sequence, trade_overview.STOCK_PROFILE)


def _read(saved, owner, observation, sequence, profile):
    from .native.native_locale_arguments import attach
    b, c, p, identity = owner
    turn = observation['turn']
    revision = c.sequence
    last_turn, unlocked = getattr(saved, '_trade_overview_unlock', (None, False))
    if last_turn is not None and last_turn > turn:
        raise ValueError('Trade overview turn moved backwards within its native owner')
    # The CivicCompleted receiver can latch the panel between these checks.
    # A mid-turn positive capacity alone is insufficient evidence.
    unlock_check = last_turn != turn
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    attach(p)
    source = native.source(0, turn, sequence, check_capacity=unlock_check, unlocked=unlocked, profile=profile)
    raw = p.runtime.evaluate_text(p.ui_child, source, b'@player_trade_overview', capacity=native.LIMIT + 1)
    panel, status = native.parse(raw, 0, turn, sequence, profile=profile)
    actual = _owner(saved, active=False)
    if (any(left is not right for left, right in zip(actual, (b, c, p, identity)))
            or c.sequence != revision or c.observation != observation):
        raise ValueError('Trade overview crossed its native owner or observation revision')
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    saved._trade_overview_unlock = (turn, unlocked or status == 'available')
    return panel, status
