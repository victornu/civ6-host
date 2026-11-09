"""Initial diplomacy queries and explicit requests on the retained XP2 owner."""
from copy import deepcopy

from .configuration_profiles import XP2_CORE_SHA256
from . import xp2_diplomacy_overview_source as ui
from . import xp2_initial_query_source as queries
from . import xp2_initial_statement_factory as factories


def source_dependencies(*, execution_image):
    from .xp2_diplomacy_display_source import source_dependencies as display_dependencies
    from .xp2_statement_source import source_dependencies as statement_dependencies
    from .xp2_world_configuration import source_dependencies as configuration_dependencies
    pins = {}
    for group in (ui.source_dependencies(execution_image=execution_image),
                  queries.source_dependencies(execution_image=execution_image),
                  factories.source_dependencies(execution_image=execution_image),
                  display_dependencies(execution_image=execution_image),
                  statement_dependencies(execution_image=execution_image),
                  configuration_dependencies()):
        for path, digest in group.items():
            if path in pins and pins[path] != digest:
                raise ValueError("Initial diplomacy source closure has conflicting pins")
            pins[path] = digest
    return pins


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
    if (getattr(saved, "diplomacy_overview_diagnostic", False) is not True
            or getattr(saved, "governors_diagnostic", False) is not True
            or getattr(saved, "war_source_sha256", None) is None
            or b.load_abi.core_sha256 != XP2_CORE_SHA256
            or not xp2_bbg_inputs.is_reference(saved.inputs.official_bundle)
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
    return b, p, image


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


def catalogue(saved, observation, *, active=False, sequence=None):
    b, p, image = _bind(saved, active=active)
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
    from civ6_host.contracts.diplomacy_overview import validate_action
    from .a0_diplomacy_statement import require_receiver
    from .native.native_diplomacy_choices import deliver_statement_request
    validate_action(action)
    b, p, image = _bind(saved, active=True)
    current = catalogue(saved, observation, active=True)
    if action not in ui.candidates(current):
        return dict(status="refused", refusal_code="native_diplomacy_availability_changed",
                    requested_action=action, pending_statement_retained=False)
    if not require_receiver(saved):
        return dict(status="refused", refusal_code="xp2_initial_diplomacy_receiver_unqualified",
                    requested_action=action, pending_statement_retained=False)
    if p.actions.pending:
        raise RuntimeError("Initial diplomacy overlaps a native command")
    pid, turn = observation["player_id"], observation["turn"]
    name = ui.REQUEST_STATEMENT_TYPES[action["choice"]]
    factory = factories.verify_request(b.core._handle, b.runtime.read, name,
                                       execution_image=image)
    war_request = name.startswith("DECLARE_") and name != "DECLARE_FRIEND"
    war_before = None
    if war_request:
        from .xp2_world_war import _read_state
        war_before = _read_state(p, pid, turn, action["target_player_id"])
    configuration = _configuration(b, p, pid)
    raw = p.runtime.evaluate_text(p.ui_child,
        ui.request_source(pid, turn, action["target_player_id"], action["choice"],
                          configuration=configuration, execution_image=image),
        b"@xp2_initial_diplomacy_request", capacity=64)
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
    deliver_statement_request(p.actions)
    p.deferred_events.drain()
    p.view_publisher.publish()
    ledger = p.deferred_events.pending_diplomacy_statements
    if len(ledger) > 1:
        raise RuntimeError("Initial diplomacy produced multiple unqualified pending statements")
    pending = bool(ledger)
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
