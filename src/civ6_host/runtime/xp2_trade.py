"""Saved-load adapter for the native trade catalogues.

The route and origin algorithms, Lua sources and native validators remain in
the established official-source adapters. This module binds them to one saved
continuation and its command/FIFO/publication lifecycle.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from struct import pack

from civ6_host.contracts import trade

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from .xp1_world_input import _owner

_ACCESSORS = ('work/trade-common-client/xp2-current-trade-accessors.json',
              '2c858af05f78ce1763c163995cfbacd5c2a1175b11073e8ca7dc0a69b34edd0f')
FIELDS = {'make_trade_route': 'trade_routes', 'change_trade_origin': 'trade_origins'}


def borrowed_enabled(saved, requested=None):
    enabled = (getattr(saved, 'standard_trade', False) is True
               or getattr(saved, 'trade_diagnostic', False) is True)
    if requested is None:
        return enabled
    if type(requested) is not bool or (requested and not enabled):
        raise ValueError('Borrowed trade requires the admitted Gathering Storm trade option')
    return requested


def validate_action(action, catalogue):
    if type(catalogue) is not dict:
        raise ValueError('Trade action requires its published native catalogue')
    width, height = catalogue['width'], catalogue['height']
    if action['kind'] == 'make_trade_route':
        trade.validate_route_action(action, width, height)
    else:
        trade.validate_origin_action(action, width, height)


def source_dependencies(*, execution_image=None):
    """Return exact static dependencies for the currently installed XP2 image."""
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .execution_images import ExecutionImageProfile
    if (type(execution_image) is not ExecutionImageProfile
            or execution_image.image_sha256 != '4de40abf7c739f53c1f3f825863ace84dc220e5a42d87620e56fceaf3fbd4dc8'):
        raise ValueError('XP2 trade accessors are pinned only for the current execution image')
    root = resource_root()
    accessor_path = resolve_path(root / _ACCESSORS[0]).resolve()
    accessor_bytes = accessor_path.read_bytes()
    if hashlib.sha256(accessor_bytes).hexdigest() != _ACCESSORS[1]:
        raise ValueError('Current XP2 trade accessor bytes changed')
    accessors = json.loads(accessor_bytes)
    if (accessors.get('schema') != 'civ6-host.xp2-current-trade-accessors.static.v1'
            or accessors.get('current_core', {}).get('sha256') != execution_image.image_sha256
            or accessors.get('binding_count') != 20
            or len(accessors.get('bindings', {})) != 20):
        raise ValueError('Current XP2 trade accessor profile is unknown')
    from .native import native_saved_trade as routes
    from .native import native_saved_trade_origin as origins
    route_proof, origin_proof = routes.verify_source(), origins.verify_source()
    pins = {str(accessor_path): _ACCESSORS[1]}
    refs = [
        (root / 'work/trade-route967/source.json',
         '0b7a086925f2a18ee3f9c98c443ea55617c59ca85a1271b98dcbc2fbba67869f'),
        (root / 'work/trade-origin968/source.json',
         '16441e00438e3a95a369ba365743f8acf961750ae36cbf653ac8cce18ccff84f'),
        (root / 'work/trade-common-client/xp2-current-trade-registration.json',
         'cdd63fa9e758eb02170ebc7d35a48c9ef7b2fa4e49ae330d64ff2061d79b6f43'),
    ]
    for proof in (route_proof, origin_proof):
        for row in proof['official_ui'].values():
            path = Path(resolve_path(row['path'])).resolve()
            refs.append((path, row['sha256']))
    refs.append((Path(routes.ROOT / route_proof['official_helper']['path']).resolve(),
                 route_proof['official_helper']['sha256']))
    for raw_path, expected in refs:
        path = Path(resolve_path(raw_path)).resolve()
        actual_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_sha256 != expected:
            raise ValueError('XP2 trade source dependency changed: ' + str(path)
                             + ' expected=' + expected + ' actual=' + actual_sha256)
        pins[str(path)] = expected
    return pins


def standard_source_dependencies(reference, *, core_sha256, execution_image):
    from .capture_admission import STOCK_XP2_READER_REVALIDATION
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .xp2_world_congress_source import SOURCE as congress_source
    from .xp2_trade_overview import stock_source_dependencies
    from .source_verification import file_sha256
    deps = stock_source_dependencies(reference, core_sha256=core_sha256, execution_image=execution_image)
    deps.update(source_dependencies(execution_image=execution_image))
    path = Path(__file__).resolve()
    deps[str(path)] = file_sha256(path)
    for path, digest in (STOCK_XP2_READER_REVALIDATION, congress_source):
        deps[str(resolve_path(resource_root() / path).resolve())] = digest
    return deps


@dataclass(frozen=True)
class _Catalogue:
    saved: object
    backend: object
    continuation: object
    prefix: object
    identity: object
    sequence: int
    observation: dict
    routes: dict
    origins: dict
    bbg_display: bool


def _bbg_display(saved, backend):
    selected = getattr(saved, 'trade_overview_ui_selected', False)
    if selected is False:
        return False
    from .xp2_trade_overview import supports
    image = getattr(backend.core, '_civ6_host_execution_image', None)
    if selected is not True or not supports(backend.captured_bundle.reference, image):
        raise ValueError('Trade chooser requires its captured BBG display profile')
    return True


def _current(saved, catalogue, *, active):
    b, c, p, identity = _owner(saved, active=active)
    if (type(catalogue) is not _Catalogue or catalogue.saved is not saved
            or catalogue.backend is not b or catalogue.continuation is not c
            or catalogue.prefix is not p or catalogue.identity is not identity
            or catalogue.sequence != c.sequence or catalogue.observation != c.observation
            or getattr(c, '_xp2_trade_catalogue', None) is not catalogue
            or getattr(c, 'explicit_trade_routes', None) != catalogue.routes
            or getattr(c, 'explicit_trade_origins', None) != catalogue.origins
            or catalogue.bbg_display is not _bbg_display(saved, b)):
        raise ValueError('XP2 trade catalogue is stale or foreign')
    return b, c, p, identity


def catalogue(saved, observation, *, include_origins=True):
    """Read routes and the explicitly admitted origin reader on this observation."""
    if type(include_origins) is not bool:
        raise ValueError('Trade origin reader selection must be Boolean')
    from .execution_images import ExecutionImageProfile
    b, c, p, identity = _owner(saved, active=False)
    if type(observation) is not dict or observation != c.observation:
        raise ValueError('Trade catalogue requires the current observation')
    image = getattr(b.core, '_civ6_host_execution_image', None)
    if b.load_abi.core_sha256 == XP1_CORE_SHA256:
        from .xp1_trade_source import supports
        if (getattr(saved, 'xp1_trade', False) is not True or not include_origins
                or not supports(b.captured_bundle.reference, image)):
            raise ValueError('Rise and Fall trade requires its exact stock route and origin readers')
    else:
        if b.load_abi.core_sha256 != XP2_CORE_SHA256 or type(image) is not ExecutionImageProfile:
            raise ValueError('Trade requires a supported expansion execution image')
        source_dependencies(execution_image=image)
    c._xp2_trade_catalogue = None
    c.explicit_trade_routes = c.explicit_trade_origins = None
    before, sequence = deepcopy(observation), c.sequence
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    bbg_display = _bbg_display(saved, b)
    route_state, origin_state = _read_native(p, before, bbg_display, include_origins)
    actual = _owner(saved, active=False)
    if (any(x is not y for x, y in zip(actual, (b, c, p, identity)))
            or c.sequence != sequence or c.observation != before):
        raise ValueError('Trade catalogue crossed its owner or observation revision')
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    record = _Catalogue(saved, b, c, p, identity, sequence, before,
                        deepcopy(route_state), deepcopy(origin_state), bbg_display)
    c.explicit_trade_routes = deepcopy(route_state)
    c.explicit_trade_origins = deepcopy(origin_state)
    c._xp2_trade_catalogue = record
    return {'trade_routes': deepcopy(route_state), 'trade_origins': deepcopy(origin_state)}


def _read_native(prefix, observation, bbg_display, include_origins):
    from .native import native_saved_trade as routes
    from .native import native_saved_trade_origin as origins

    pid, turn = observation['player_id'], observation['turn']
    route_state = routes.catalog(prefix, turn, player_id=pid, bbg_display=bbg_display)
    origin_state = origins.catalog(prefix, turn, player_id=pid) if include_origins else None
    routes.compare_own(route_state, observation)
    if origin_state is not None:
        origins.compare_own(origin_state, observation)
    return route_state, origin_state


def _borrowed_record(saved, observation, *, include_origins):
    from .xp1_session_view import _borrowed_xp2_reference

    _borrowed_xp2_reference(saved, observation['player_id'])
    b, c, p, identity = _owner(saved, active=True)
    image = getattr(b.core, '_civ6_host_execution_image', None)
    source_dependencies(execution_image=image)
    sequence = c.sequence
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    display = _bbg_display(saved, b)
    routes, origins = _read_native(p, observation, display, include_origins)
    if (any(a is not b for a, b in zip(_owner(saved, active=True), (b, c, p, identity)))
            or c.sequence != sequence):
        raise RuntimeError('Borrowed trade crossed its native decision boundary')
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    return _Catalogue(saved, b, c, p, identity, sequence, observation, routes, origins, display)


def read_borrowed(saved, observation, *, ready, strategic_allowed):
    if not ready:
        return dict(trade_routes=None, trade_origins=None)
    record = _borrowed_record(saved, observation, include_origins=strategic_allowed)
    return dict(trade_routes=record.routes, trade_origins=record.origins)


def apply_borrowed(saved, action, observation, *, expected, enabled, ready, strategic_allowed):
    refusal = dict(status='refused', requested_action=action)
    is_route = action['kind'] == 'make_trade_route'
    if not enabled or not ready or (not is_route and not strategic_allowed):
        return dict(refusal, reason='native_trade_acting_boundary_unavailable'), None
    record = _borrowed_record(saved, observation, include_origins=strategic_allowed)
    current = record.routes if is_route else record.origins
    if current != expected:
        return dict(refusal, reason='native_trade_choice_changed'), None
    actions = trade.route_actions(current) if is_route else trade.origin_actions(current)
    if action not in actions:
        return dict(refusal, reason='native_trade_choice_unavailable'), None
    effect = _apply(saved, action, record, borrowed=True)
    return dict(status='completed', reason=None, requested_action=action), effect['observation']


def verify_borrowed_archive(payload, player_id, action):
    """Check the native UnitOperation serializer before delivery."""
    head = (0x8c0f3f36, player_id, 1, action['unit_id'])
    if action['kind'] == 'make_trade_route':
        expected = pack('<IHH12I', *head, 18, 0xffffffff, 0, 1, 0,
                        action['x0'], action['y0'], action['x1'], action['y1'], 0xffffffff, 0)
    elif action['kind'] == 'change_trade_origin':
        expected = pack('<IHH9I', *head, 51, 0xffffffff, 0, 1, action['x'], action['y'], 0, 0)
    else:
        raise ValueError('Unsupported borrowed trade archive')
    if type(payload) is not bytes or payload != expected:
        raise RuntimeError('Trade archive differs from the native sender, unit or destination')


def apply(saved, action, before):
    """Submit one offered trade command, flush script feedback, then verify readback."""
    _, c, _, _ = _owner(saved, active=True)
    record = getattr(c, '_xp2_trade_catalogue', None)
    _, c, _, _ = _current(saved, record, active=True)
    if before != record.observation:
        raise ValueError('Trade action was not offered at this observation')
    return _apply(saved, action, record)


def _apply(saved, action, record, *, borrowed=False):
    from .native import native_saved_trade as routes
    from .native import native_saved_trade_origin as origins
    from .native.native_player_observation import observe_player

    b, c, p, before = record.backend, record.continuation, record.prefix, record.observation
    flag = 'xp1_trade' if b.load_abi.core_sha256 == XP1_CORE_SHA256 else 'standard_trade'
    standard = getattr(saved, flag, False) is True
    if standard and c.trade_feedback is not None:
        raise ValueError('Standard trade cannot use the BBG feedback owner')
    kind = action.get('kind') if type(action) is dict else None
    if kind == 'make_trade_route':
        module, state = routes, record.routes
        field = 'explicit_trade_routes'
        expected_stage = 'official_explicit_trade_effect'
    elif kind == 'change_trade_origin':
        module, state = origins, record.origins
        field = 'explicit_trade_origins'
        expected_stage = 'official_explicit_trade_origin_effect'
    else:
        raise ValueError('Unsupported XP2 trade action')
    if (not borrowed and getattr(c, field) != state) or state is None or action not in module.actions(state):
        raise ValueError('Trade action was not offered by the current native catalogue')
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    count = c.publication_count
    player_id, turn = before['player_id'], before['turn']
    if kind == 'make_trade_route':
        request = routes.request_source(action, state, bbg_display=record.bbg_display)
    else:
        request = origins.request_source(action, state)
    raw = p.runtime.evaluate_text(p.ui_child, request,
        b'@xp2_trade_route_request' if kind == 'make_trade_route' else b'@xp2_trade_origin_request')
    if raw != b'submitted' or len(p.actions.pending) != 1:
        raise RuntimeError('Native trade request did not enqueue exactly one action')
    if borrowed:
        verify_borrowed_archive(p.actions.pending[0], player_id, action)
    archive_sha256 = hashlib.sha256(p.actions.pending[0]).hexdigest()
    p.actions.deliver_one()
    p.deferred_events.drain_empty_receivers()
    # BBG can schedule route feedback in script callbacks. Consume that real
    # effect before publishing or taking the post-action observation.
    feedback = None if standard else c.flush_trade_feedback()
    if p.deferred_events.pending:
        raise RuntimeError('Trade feedback left deferred native events unconsumed')
    p.view_publisher.publish()
    c.transport.require_empty_native_queue()
    b.control(empty=True)
    after = observe_player(p.runtime, p.ui_child, player_id)
    if (after['player_id'], after['turn']) != (player_id, turn):
        raise RuntimeError('Trade effect crossed the native player or turn')
    refreshed_routes, refreshed_origins = _read_native(
        p, after, record.bbg_display, record.origins is not None)
    if kind == 'make_trade_route':
        expected = {key: action[key] for key in ('unit_id', 'origin_owner', 'origin_city',
                                                  'destination_owner', 'destination_city')}
        effect_seen = (not any(r['unit_id'] == action['unit_id'] for r in record.routes['active_routes'])
                       and refreshed_routes['active_routes'].count(expected) == 1)
    else:
        unit = next((u for u in after['units'] if u['id'] == action['unit_id']), None)
        effect_seen = bool(unit and unit['owner'] == player_id
                           and (unit['x'], unit['y']) == (action['x'], action['y']))
    if not effect_seen:
        raise RuntimeError('Native trade command effect is absent from readback')
    if c.publication_count != count + 1:
        raise RuntimeError('Trade command publication count did not advance once')
    receipt = {'stage': expected_stage, 'action': deepcopy(action),
               'native_archive_sha256': archive_sha256,
               'source_proof_sha256': module.PROOF_SHA,
               'native_archive_delivered': True, 'native_effect_readback': True,
               'automatic_choices_applied': False,
               'trade_feedback': deepcopy(feedback),
               'trade_routes_after': refreshed_routes,
               'trade_origins_after': refreshed_origins}
    if not borrowed:
        c._xp2_trade_catalogue = None
        c.explicit_trade_routes = c.explicit_trade_origins = None
    saved.emit(expected_stage, action=deepcopy(action), observation_before=deepcopy(before),
               observation_after=deepcopy(after), catalogue_routes_before=deepcopy(record.routes),
               catalogue_origins_before=deepcopy(record.origins),
               catalogue_routes_after=deepcopy(refreshed_routes),
               catalogue_origins_after=deepcopy(refreshed_origins),
               native_archive_sha256=archive_sha256, source_proof_sha256=module.PROOF_SHA,
               automatic_choices_applied=False, trade_feedback=deepcopy(feedback))
    return dict(status='completed', refusal_code=None, observation=deepcopy(after), receipt=receipt)
