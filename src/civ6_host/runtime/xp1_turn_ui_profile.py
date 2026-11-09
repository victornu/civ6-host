"""Human turn decisions on the exact retained XP1 LAN capture.

The official XP1 UI getters remain native. Only the inherited ActionPanel's
decision tree and fixed, witnessed user preferences are projected here. This
does not supply an elapsed clock, UI.CanEndTurn fallback, or a turn scheduler.
"""
from dataclasses import dataclass
import hashlib

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source, _body

SOURCE = ('work/host-extensions/xp1-turn-ui-static/human-turn-gates-v1.json',
          'e575e2d142bfaee2fadf6e01637e244b572ef2373902380d2bdeebb43be2d70a')
CALLBACKS = {
    'NotificationManager.GetFirstEndTurnBlocking': 0x600de0,
    'NotificationManager.GetAllEndTurnBlocking': 0x600bc0,
    'NotificationManager.FindEndTurnBlocking': 0x600a60,
    'NotificationManager.FindType': 0x600b10,
    'Notification.IsDismissed': 0x5ffdb0,
    'PlayerUnits.GetFirstReadyUnit': 0x5d2980,
    'PlayerCities.GetFirstRangedAttackCity': 0x5c6c10,
    'Player.GetUnits': 0x5c5d70,
    'Player.GetCities': 0x5c51b0,
    'Game.IsAllowTacticalCommands': 0x5b8610,
}
XP2_SOURCE=('work/host-extensions/xp2-turn-ui-static/source-profile-v1.json',
            'fb72fd41eea181d3c2e3f50f94de037c6c42a42984b4ef943ede9177f1dad562')
XP2_CALLBACKS={
    'NotificationManager.GetFirstEndTurnBlocking':0x6e7c90,
    'NotificationManager.GetAllEndTurnBlocking':0x6e7a70,
    'NotificationManager.FindEndTurnBlocking':0x6e7910,
    'NotificationManager.FindType':0x6e79c0,
    'Notification.IsDismissed':0x6e6c60,
    'PlayerUnits.GetFirstReadyUnit':0x6b6f00,
    'PlayerCities.GetFirstRangedAttackCity':0x6ab190,
    'Player.GetUnits':0x6aa300,'Player.GetCities':0x6a9740,
    'Game.IsAllowTacticalCommands':0x69ccc0}


def source_reference(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP1_CORE_SHA256:return SOURCE
    if core_sha256==XP2_CORE_SHA256:return XP2_SOURCE
    raise ValueError('Unknown human turn engine')


def verify_source(core_sha256=XP1_CORE_SHA256):
    selected=source_reference(core_sha256)
    callbacks=XP2_CALLBACKS if core_sha256==XP2_CORE_SHA256 else CALLBACKS
    schema=('civ6-host.xp2-human-turn-gates.source.v1' if core_sha256==XP2_CORE_SHA256
            else 'civ6_host.xp1_human_turn_gates.static.v1')
    proof = _source(selected)
    if (proof['schema'] != schema
            or proof['image']['sha256'] != core_sha256
            or proof['native_execution'] is not False
            or proof['validation']['exact_name_callback_pairs_verified'] != 10
            or proof['validation']['all_instruction_bytes_match_pinned_image'] is not True
            or proof['validation']['inherited_manual_handlers_verified'] is not True
            or proof['validation']['preferences_before_after_equal'] is not True
            or set(proof['bindings']) != set(callbacks)):
        raise ValueError('XP1 human turn source identity changed')
    for name, rva in callbacks.items():
        row = proof['bindings'][name]
        if (row['callback_rva'] != rva
                or row['lua_callback_abi'] != 'int __cdecl(LuaState*) / Windows x64'):
            raise ValueError('XP1 human turn callback changed: ' + name)
        _body(proof['functions'][hex(rva)])
    if core_sha256==XP2_CORE_SHA256:
        if len(proof['functions'])!=16 or sum(b['bytes'] for b in proof['functions'].values())!=8098:
            raise ValueError('XP2 human turn function closure changed')
        for body in proof['functions'].values():
            if body['all_conditional_targets_captured'] is not True:
                raise ValueError('XP2 human turn source has an incomplete branch')
            _body(body)
    preferences = proof['preference_profile']
    if (preferences['auto_end_turn'] is not False
            or preferences['city_attack_turn_blocking'] is not True
            or preferences['tutorial_active'] is not False
            or preferences['immutable_for_headless_session'] is not True
            or preferences['dynamic_turn_state_replayed'] is not False):
        raise ValueError('XP1 captured preference profile changed')
    return proof


def source_dependencies(*,core_sha256=XP1_CORE_SHA256,execution_image=None):
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .xp1_status_profiles import source_dependencies as status_dependencies
    from .network_timer import PROOF_PATH, PROOF_SHA256
    proof = verify_source(core_sha256)
    if execution_image is not None and core_sha256!=XP2_CORE_SHA256:
        raise ValueError('Selected execution image requires the XP2 turn UI source ABI')
    pins = dict(status_dependencies(core_sha256=core_sha256,execution_image=execution_image))
    selected=source_reference(core_sha256)
    refs = [dict(path=selected[0], sha256=selected[1]),
            dict(path=PROOF_PATH, sha256=PROOF_SHA256),
            *proof['references'], *proof['official_ui_sources'],
            *proof['captured_preferences_witnesses']]
    # Official Lua files are not JSON. Verify their bytes rather than asking the
    # JSON source cache to parse them. No copy of proprietary sources is made.
    for row in refs:
        path = resolve_path(resource_root() / row['path']).resolve()
        raw = path.read_bytes()
        if (hashlib.sha256(raw).hexdigest() != row['sha256']
                or 'bytes' in row and len(raw) != row['bytes']):
            raise ValueError('XP1 human turn dependency changed: ' + str(path))
        key = str(path)
        if key in pins and pins[key] != row['sha256']:
            raise ValueError('Conflicting XP1 human turn dependency')
        pins[key] = row['sha256']
    return pins


def verify_live(base, reader, *,core_sha256=XP1_CORE_SHA256):
    from .xp1_status_profiles import _instruction_spans
    if type(base) is not int or base <= 0 or not callable(reader):
        raise ValueError('Expected the live XP1 module and reader')
    proof = verify_source(core_sha256)
    flat = {'functions': {name: {'instructions': [row
            for fragment in _body(body)['fragments'] for row in fragment['instructions']]}
            for name, body in proof['functions'].items()}}
    spans = _instruction_spans(flat)
    for rva, raw in spans:
        for offset in range(0,len(raw),4096):
            part=raw[offset:offset+4096]
            if reader(base + rva+offset, len(part)) != part:
                raise ValueError('Human turn instruction changed at ' + hex(rva+offset))
    for name, row in proof['bindings'].items():
        literal = name.split('.')[1].encode('ascii') + b'\0'
        if reader(base + row['name_rva'], len(literal)) != literal:
            raise ValueError('XP1 human turn registration literal changed: ' + name)
    return len(spans)


@dataclass(frozen=True)
class VerifiedTurnSource:
    owner: object
    core: object
    base: int
    source_sha256: str
    instruction_read_spans: int


def bind_owner(owner):
    owner.check_thread()
    core_sha256=owner.load_abi.core_sha256
    selected=source_reference(core_sha256)
    core = owner.core
    existing = getattr(owner, '_xp1_turn_ui_source_receipt', None)
    if existing is not None:
        if (type(existing) is not VerifiedTurnSource or existing.owner is not owner
                or existing.core is not core or existing.base != core._handle
                or existing.source_sha256 != selected[1]):
            raise ValueError('Human turn source belongs to another owner lifetime')
        return existing
    from .xp1_status_profiles import bind_owner as bind_status
    bind_status(owner, core, owner.runtime.read)
    source_dependencies(core_sha256=core_sha256)
    count = verify_live(core._handle, owner.runtime.read,core_sha256=core_sha256)
    receipt = VerifiedTurnSource(owner, core, core._handle, selected[1], count)
    owner._xp1_turn_ui_source_receipt = receipt
    return receipt


def query_source(player_id, expected_turn, *, player_ids):
    from .native.native_diagnostic_roster import validate_player
    validate_player(player_id, player_ids)
    if type(expected_turn) is not int or not 0 <= expected_turn <= 100000:
        raise ValueError('Invalid expected human turn')
    return (f'local pid={player_id}\nlocal turn={expected_turn}\n'.encode('ascii') + b'''
assert(Game.GetCurrentGameTurn()==turn and Game.GetLocalPlayer()==pid and
 Game.GetLocalObserver()==pid,'human turn perspective changed')
local p=Players[pid]
assert(p,'native local player absent')
assert(NotificationManager and type(NotificationManager.GetFirstEndTurnBlocking)=='function'
 and type(NotificationManager.GetAllEndTurnBlocking)=='function'
 and type(NotificationManager.FindEndTurnBlocking)=='function'
 and type(NotificationManager.FindType)=='function','native notification readers absent')
local e=EndTurnBlockingTypes
assert(e and type(e.NO_ENDTURN_BLOCKING)=='number' and type(e.ENDTURN_BLOCKING_STACKED_UNITS)=='number'
 and type(e.ENDTURN_BLOCKING_UNIT_NEEDS_ORDERS)=='number'
 and type(e.ENDTURN_BLOCKING_UNITS)=='number','native blocker enums absent')
local primary=NotificationManager.GetFirstEndTurnBlocking(pid)
local all=NotificationManager.GetAllEndTurnBlocking(pid)
assert(type(primary)=='number' and type(all)=='table' and #all<=128,'native blockers malformed')
local rows={}
for _,value in ipairs(all) do
 assert(type(value)=='number' and value==math.floor(value),'native blocker nonintegral')
 rows[#rows+1]=string.format('%.0f',value)
end
assert(type(NotificationTypes.CITY_RANGE_ATTACK)=='number','native city notification enum absent')
local city=NotificationManager.FindType(NotificationTypes.CITY_RANGE_ATTACK,pid)
local dismissed=false
if city~=nil then dismissed=city:IsDismissed() end
local notification=nil
if primary~=e.NO_ENDTURN_BLOCKING then
 notification=NotificationManager.FindEndTurnBlocking(primary,pid)
end
local flags={}
local function flag(value)
 assert(type(value)=='boolean','native human turn predicate is not Boolean')
 flags[#flags+1]=value and '1' or '0'
end
flag(p:IsAlive());flag(p:IsTurnActive());flag(p:IsTurnActiveComplete())
flag(p:CanUnreadyTurn());flag(Game.IsAllowTacticalCommands(pid))
flag(p:GetUnits():GetFirstReadyUnit()~=nil)
flag(city~=nil);flag(dismissed);flag(notification~=nil)
assert(Game.GetCurrentGameTurn()==turn and Game.GetLocalPlayer()==pid and
 Game.GetLocalObserver()==pid,'human turn boundary changed during read')
return string.format('%d|%d|%.0f|%.0f|%s|%s|%.0f,%.0f,%.0f',turn,pid,primary,
 e.NO_ENDTURN_BLOCKING,table.concat(rows,','),table.concat(flags,','),
 e.ENDTURN_BLOCKING_STACKED_UNITS,e.ENDTURN_BLOCKING_UNIT_NEEDS_ORDERS,e.ENDTURN_BLOCKING_UNITS)
''')


def parse_readback(raw, player_id, expected_turn, *, player_ids):
    from .native.native_turn_decisions import parse_blockers
    if type(raw) is not bytes or len(raw) > 8192:
        raise ValueError('Invalid human turn readback capacity')
    parts = raw.split(b'|')
    if len(parts) != 7:
        raise ValueError('Invalid human turn readback shape')
    blockers = parse_blockers(b'|'.join(parts[:5]), player_id, expected_turn,
                               player_ids=player_ids)
    flags = parts[5].split(b',')
    units = [int(value) for value in parts[6].split(b',')]
    if (len(flags) != 9 or any(value not in (b'0', b'1') for value in flags)
            or len(units) != 3 or len(set(units)) != 3
            or any(not -2**31 <= value < 2**32 for value in units)
            or blockers['no_blocker_value'] in units):
        raise ValueError('Invalid human turn predicate or enum values')
    names = ('alive', 'active', 'active_complete', 'can_unready', 'allow_tactical',
             'ready_unit_present', 'city_attack_present', 'city_attack_dismissed',
             'blocking_notification_present')
    result = dict(zip(names, (value == b'1' for value in flags)))
    if result['city_attack_dismissed'] and not result['city_attack_present']:
        raise ValueError('Dismissed city notification has no native object')
    result.update(blockers=blockers, unit_blocker_values=units)
    return result


def classify(readback, timer_elapsed, *,core_sha256=XP1_CORE_SHA256):
    """Project official DoEndTurn ordering; unknown branches stay unknown."""
    if timer_elapsed is not None and type(timer_elapsed) is not bool:
        raise ValueError('Elapsed timer must be Boolean or explicitly unknown')
    r = readback
    unknown = []
    unready = r['can_unready'] and (None if timer_elapsed is None else not timer_elapsed)
    if unready is True:
        normal, reason = False, 'normal_button_routes_to_unready'
    elif unready is None:
        normal, reason = None, 'elapsed_timer_unqualified'
        unknown.append(reason)
    elif r['blockers']['has_primary_blocker']:
        if r['blockers']['primary'] in r['unit_blocker_values']:
            normal, reason = False, 'mandatory_unit_blocker'
        elif r['blocking_notification_present']:
            normal, reason = False, 'activate_blocking_notification'
        else:
            normal, reason = None, 'missing_notification_UI_CanEndTurn_unqualified'
            unknown.append(reason)
    elif r['allow_tactical'] and r['city_attack_present'] and not r['city_attack_dismissed']:
        normal, reason = False, 'city_range_attack_notification'
    else:
        # AutoEndTurn=False in this fixed, captured headless preference profile.
        # Ready units alone do not block the inherited manual button branch.
        normal, reason = True, 'official_normal_request_branch'
    handler_normal = normal
    # The button refresh has a separate active-completion presentation gate;
    # keyboard routing also depends on the surrounding UI context. This source
    # group does not establish normal Enter reachability outside the completed
    # active human phase. Preserve the handler result without inventing denial.
    if normal is True and not (r['alive'] and r['active'] and r['active_complete']):
        normal, reason = None, 'normal_input_reachability_outside_active_phase_unqualified'
        unknown.append(reason)
    return dict(turn_availability=dict(end_turn=normal, force_end_turn=True,
                                      unready_turn=unready),
        diagnostics=dict(**r, timer_elapsed=timer_elapsed, normal_route=reason,
            normal_handler_request=handler_normal,
            auto_end_turn=False, city_attack_turn_blocking=True, tutorial_active=False,
            processing_messages=False, processing_source='official_EXE_039FF0_constant_false',
            force_route='official_ShiftEnter_UserForced_tutorial_inactive',
            native_request_acceptance_inferred=False), unknown=unknown,
        source_sha256=source_reference(core_sha256)[1], core_sha256=core_sha256)


def read(saved, player_id, expected_turn, *, active=False):
    """Fresh UI predicates; active=True borrows the executing continuation only."""
    from .xp1_saved_load_owner import SavedLoadOwner
    from .xp1_session_view import _reference
    from .network_timer import read as read_timer
    if type(saved) is not SavedLoadOwner or type(active) is not bool:
        raise TypeError('Human turn read requires the exact saved owner and phase')
    if active:
        saved._check_active()
    else:
        saved._check('commands', requested='unit_commands_candidate')
        saved.continuation.check(active=False)
    _, ids = _reference(saved, player_id)
    b, p = saved.backend, saved.prefix
    bind_owner(b)
    saved.continuation.transport.require_empty_native_queue()
    b.control(empty=True)
    timer = read_timer(b, core_sha256=b.load_abi.core_sha256)
    raw = p.runtime.evaluate_text(p.ui_child,
        query_source(player_id, expected_turn, player_ids=ids),
        b'@xp1_human_turn_gates', capacity=8192)
    result = classify(parse_readback(raw, player_id, expected_turn, player_ids=ids), timer,
                      core_sha256=b.load_abi.core_sha256)
    saved.continuation.transport.require_empty_native_queue()
    b.control(empty=True)
    saved.continuation.check(active=active)
    return result
