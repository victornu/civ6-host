"""Initial diplomacy queries and explicit requests on the retained XP2 owner."""
from contextlib import nullcontext
from copy import deepcopy

from civ6_host.contracts import diplomacy_overview as contract
from .configuration_profiles import XP2_CORE_SHA256
from . import xp2_diplomacy_overview_source as ui
from . import xp2_initial_query_source as queries
from . import xp2_initial_statement_factory as factories
from . import xp2_diplomatic_relationships as relationships
from . import xp2_city_state_peace as peace
from . import xp2_major_deals as deals
from . import xp2_deal_draft as draft
from . import xp2_deal_peace as treaty


def source_dependencies(*, execution_image, stock=False):
    from .xp2_diplomacy_display_source import source_dependencies as display_dependencies
    from .xp2_statement_source import source_dependencies as statement_dependencies
    from .xp2_world_configuration import source_dependencies as configuration_dependencies
    pins = {}
    common = (
        ui.source_dependencies(execution_image=execution_image, stock=stock),
        queries.source_dependencies(execution_image=execution_image),
        factories.source_dependencies(execution_image=execution_image),
        display_dependencies(execution_image=execution_image),
        statement_dependencies(execution_image=execution_image),
        relationships.source_dependencies(ui._load_profile()['official_files']['xp2_view']['path']),
        configuration_dependencies(),
        deals.source_dependencies(execution_image=execution_image, stock=stock),
        draft.source_dependencies(execution_image=execution_image),
        treaty.dependencies(execution_image),
        peace.source_dependencies(stock=stock),
    )
    for group in common:
        for path, digest in group.items():
            if path in pins and pins[path] != digest:
                raise ValueError("Initial diplomacy source closure has conflicting pins")
            pins[path] = digest
    return pins


def require_stock_capture(reference):
    from .xp2_bundle_inputs import REFERENCE
    from .native.native_official_bundle import normalize_reference
    if type(reference) is tuple and len(reference) == 2:
        reference = dict(zip(('path', 'sha256'), reference))
    if normalize_reference(reference) != REFERENCE:
        raise ValueError('Initial stock diplomacy requires the registered unmodded Gathering Storm capture')


def _bind(saved, *, active):
    from .xp1_saved_load_owner import SavedLoadOwner
    from . import xp2_bbg_inputs
    if type(saved) is not SavedLoadOwner:
        raise TypeError("Initial diplomacy requires the retained saved owner")
    if active:
        saved._check_active()
    else:
        saved._check_query()
    b, p = saved.backend, saved.prefix
    stock = getattr(saved, "standard_trade", False) is True
    if stock:
        require_stock_capture(b.captured_bundle.reference)
    if (getattr(saved, "diplomacy_overview_diagnostic", False) is not True
            or (not stock and (getattr(saved, "governors_diagnostic", False) is not True
                or not xp2_bbg_inputs.is_reference(saved.inputs.official_bundle)))
            or getattr(saved, "war_source_sha256", None) is None
            or b.load_abi.core_sha256 != XP2_CORE_SHA256
            or getattr(saved, "_xp2_diplomacy", None) is not None
            or p.deferred_events.pending_diplomacy_statements
            or saved.continuation.world_input_prompts.get(saved.continuation.observation["player_id"]) is not None):
        raise ValueError("Initial diplomacy has an unqualified owner or another pending modal")
    image = getattr(b.core, "_civ6_host_execution_image", None)
    lifetime = b.core, p
    if getattr(saved, "_xp2_initial_diplomacy_lifetime", None) != lifetime:
        from .xp2_diplomacy_display_source import verify_live
        verify_live(b.core._handle, b.runtime.read, execution_image=image)
        queries.verify_live(b.core._handle, b.runtime.read, execution_image=image)
        factories.verify_image(b.core._handle, b.runtime.read, execution_image=image)
        from .network_dialogue import attach_database
        attach_database(b)
        saved._xp2_initial_diplomacy_lifetime = lifetime
    return b, p, image, stock


def _configuration(b, p, pid):
    from .native.native_diplomacy_configuration import read
    raw = p.runtime.evaluate_text(p.ui_child,
        b"local n=DiplomacyInitiatorTypes.HUMAN\n"
        b"assert(type(n)=='number' and n%1==0,'Missing native diplomacy enum')\nreturn tostring(n)",
        b"@xp2_initial_diplomacy_initiator", capacity=64)
    if type(raw) is not bytes or len(raw) > 12:
        raise ValueError("Invalid native XP2 initial diplomacy initiator")
    initiator = int(raw)
    if not -(1 << 31) <= initiator < (1 << 32):
        raise ValueError("Initial diplomacy initiator exceeds its native ABI")
    players = read(b, {"fields": {"FromPlayer": pid, "Initiator": initiator}},
                   core_sha256=XP2_CORE_SHA256)
    return dict(initiator=initiator, players=players, paused=queries.read_pause(b))


def catalogue(saved, observation, *, active=False, sequence=None, public_relationships=False):
    b, p, image, stock = _bind(saved, active=active)
    pid, turn = observation["player_id"], observation["turn"]
    if (pid, turn) != (saved.continuation.observation["player_id"],
                       saved.continuation.observation["turn"]):
        raise ValueError("Initial diplomacy query has a foreign player or turn")
    verification = getattr(saved, "_xp2_initial_war_verification", None)
    if verification is not None:
        from .xp2_world_war import _read_state
        request_pid, target, request_turn = verification
        if request_pid != pid:
            raise ValueError("Initial-war readback changed player perspective")
        state = _read_state(p, pid, turn, target)
        if state["at_war"] is not True:
            raise RuntimeError("Initial war request has no native at-war state after the dialogue")
        saved.emit("native_xp2_initial_war_effect_verified", player_id=pid,
                   turn=turn, request_turn=request_turn, target_player_id=target,
                   native_war_state=state, game_update_called=False)
        del saved._xp2_initial_war_verification
    configuration = _configuration(b, p, pid)
    raw = p.runtime.evaluate_text(p.ui_child,
        ui.source(pid, turn, configuration=configuration, execution_image=image),
        b"@xp2_initial_diplomacy_overview", capacity=262144)
    value = ui.parse(raw, pid, turn)
    if stock or public_relationships:
        value = relationships.read(p, value)
        lifetime = b.core, p
        if getattr(saved, '_xp2_major_deals_lifetime', None) != lifetime:
            deals.verify_live(b.core._handle, b.runtime.read, execution_image=image)
            saved._xp2_major_deals_lifetime = lifetime
        if stock:
            value = deals.read_stock_negotiation(p, value)
            value = dict(value, schema=contract.STOCK_CITY_STATE_PEACE_SCHEMA,
                         city_state_peace=peace.panel(p, pid, turn))
            contract.validate(value, pid, turn)
        else:
            value = dict(value, schema=contract.CITY_STATE_PEACE_SCHEMA,
                         city_state_peace=peace.panel(p, pid, turn))
            value = deals.read(p, value, draft=True, open_borders=True, demand=True, major_peace=True)
    saved._xp2_initial_diplomacy_catalogue = deepcopy(value)
    saved.emit("native_xp2_initial_diplomacy_overview",
        episode_id=saved.continuation.identity.episode_id,
        game_generation=saved.continuation.identity.game_generation,
        sequence=sequence, player_id=pid, turn=turn,
        transient_command_revalidation=active,
        source_sha256=ui.PROFILE_SHA256, overview=deepcopy(value),
        native_gameplay_mutated=False)
    return value


def initiate(saved, action, observation):
    """Requery availability, dispatch official Lua, and deliver its native archive."""
    from .a0_diplomacy_statement import require_receiver
    from .native.native_diplomacy_choices import deliver_statement_request
    contract.validate_action(action)
    b, p, image, stock = _bind(saved, active=True)
    making_peace = action['choice'] == contract.MAKE_PEACE
    demand = action['choice'] == contract.OPEN_DEMAND
    opening_deal = action['choice'] == contract.OPEN_DEAL or demand or making_peace
    current = catalogue(saved, observation, active=True, public_relationships=opening_deal)
    target = action['target_player_id']
    if (making_peace and current['schema'] in contract.CITY_STATE_SCHEMAS
            and not any(row['player_id'] == target for row in current['targets'])):
        return peace.apply(saved, b, p, action, current)
    choices = contract.candidates(current) if opening_deal or stock else ui.candidates(current)
    if action not in choices:
        return dict(status="refused", refusal_code="native_diplomacy_availability_changed",
                    requested_action=action, pending_statement_retained=False)
    if not require_receiver(saved):
        return dict(status="refused", refusal_code="xp2_initial_diplomacy_receiver_unqualified",
                    requested_action=action, pending_statement_retained=False)
    if p.actions.pending:
        raise RuntimeError("Initial diplomacy overlaps a native command")
    pid, turn = observation["player_id"], observation["turn"]
    if opening_deal:
        name = 'MAKE_DEMAND' if demand else 'MAKE_DEAL'
        factory = draft.verify_request(saved, image, demand=demand)
        if making_peace:
            treaty.verify(b.core._handle, b.runtime.read, image)
    else:
        name = ui.REQUEST_STATEMENT_TYPES[action['choice']]
        factory = factories.verify_request(b.core._handle, b.runtime.read, name,
                                           execution_image=image)
    war_request = name.startswith("DECLARE_") and name != "DECLARE_FRIEND"
    war_before = None
    if war_request:
        from .xp2_world_war import _read_state
        war_before = _read_state(p, pid, turn, action["target_player_id"])
    configuration = _configuration(b, p, pid)
    request_options = {'deal_draft': True} if opening_deal else {}
    scope = (draft.statement_scope(saved.continuation, pid, action['target_player_id'], demand=demand)
             if opening_deal else nullcontext())
    with scope:
        raw = p.runtime.evaluate_text(p.ui_child,
            ui.request_source(pid, turn, action["target_player_id"], action["choice"],
                              configuration=configuration, execution_image=image, **request_options),
            b"@xp2_initial_diplomacy_request", capacity=64)
        if raw == b"requested" and factory["expected_registration"] is True:
            deliver_statement_request(p.actions)
            p.deferred_events.drain()
            p.view_publisher.publish()
    if raw == b"not_requested":
        if p.actions.pending or p.deferred_events.pending_diplomacy_statements:
            raise RuntimeError("Native RequestSession refused but produced pending work")
        saved.emit("native_xp2_initial_diplomacy_request_refused", action=deepcopy(action),
                   factory=factory, native_request_invoked=True,
                   native_request_returned=False, game_update_called=False,
                   native_war_state_before=war_before)
        return dict(status="refused", refusal_code="native_session_request_returned_false",
                    requested_action=action, pending_statement_retained=False)
    if raw != b"requested" or factory["expected_registration"] is not True:
        raise RuntimeError("Initial diplomacy returned an unqualified request receipt")
    ledger = p.deferred_events.pending_diplomacy_statements
    if len(ledger) > 1:
        raise RuntimeError("Initial diplomacy produced multiple unqualified pending statements")
    pending = bool(ledger)
    if opening_deal:
        if not pending:
            raise RuntimeError('Native deal request produced no statement')
        fields = ledger[0]['fields']
        if (fields['StatementType'] != factory['statement_hash']
                or {fields['FromPlayer'], fields['ToPlayer']} != {pid, target}):
            raise RuntimeError('Native deal request produced a different statement')
        saved._xp2_requested_deal = (pid, target, turn)
        if demand:
            saved._xp2_demand = True
        if making_peace:
            saved._xp2_major_peace = True
    war_after = None
    if war_request and not pending:
        war_after = _read_state(p, pid, turn, action["target_player_id"])
        if war_after["at_war"] is not True:
            raise RuntimeError("Delivered initial war request has no native at-war state")
    elif war_request:
        # A live dialogue can block strategic commands. Verify through the
        # existing ready-state reader once the caller explicitly closes it.
        saved._xp2_initial_war_verification = (pid, action["target_player_id"], turn)
    saved.emit("native_xp2_initial_diplomacy_request_delivered", action=deepcopy(action),
        factory=factory, request_delivered=True, pending_statement=pending,
        automatic_response=False, game_update_called=False,
        native_war_state_before=war_before, native_war_state_after=war_after,
        gameplay_effect_verified=war_after is not None)
    return dict(status="completed", refusal_code=None, requested_action=action,
                pending_statement_retained=pending, native_request_delivered=True)
