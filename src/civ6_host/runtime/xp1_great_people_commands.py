"""Source-bound Great Person recruitment, patronage and rejection."""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from struct import Struct

from . import xp1_great_people as reader
from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE
from .native.native_great_people_actions import _common_guards
from .native.native_player_observation import observe_player
from .native.native_player_operation_request import request_player_operation
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('work/x1trade/great-people-commands-stage/source.json',
          '415d9e3c4e24bcb8cf773b49f599c4b7c939dadcfac481546db1400190d862fa')
RECRUIT = 'recruit_great_person'
PATRONIZE = 'patronize_great_person'
REJECT = 'reject_great_person'
KINDS = (RECRUIT, PATRONIZE, REJECT)
REJECT_SOURCE = ('work/x1trade/great-people-reject-stage/source.json',
                 'ebb58c4481bd92df57fd6f3cc5eb5bc3c604cc73f47705a2f44313174c7e2d7b')
_REJECT_ENUM = ('REJECT_GREAT_PERSON', 0x05ace248)
_CURRENCIES = {'YIELD_GOLD': 2, 'YIELD_FAITH': 5}
_BALANCES = {'YIELD_GOLD': 'gold', 'YIELD_FAITH': 'faith'}
_SIGNED_ENUMS = {
    'RECRUIT_GREAT_PERSON': -387427142,
    'PATRONIZE_GREAT_PERSON': -337724938,
    'PARAM_GREAT_PERSON_INDIVIDUAL_TYPE': 945800002,
    'PARAM_YIELD_TYPE': 730511874,
}
_OPERATIONS = {RECRUIT: 0xe8e854ba, PATRONIZE: 0xebdeb9f6, REJECT: _REJECT_ENUM[1]}
_INDIVIDUAL = 0x385fc342
_YIELD = 0x2b8aba02
_MAX_INT = 0x7fffffff
_OPERATION_MESSAGE = 0xc45de12f
_ARCHIVE_FLAGS = 2
_MAP_MARKER = 0x80000001
_DWORD_TAG = 0x00020000
_HEADER = Struct('<6I')
_ENTRY = Struct('<II10sI')


def supports(reference, image):
    return reader.supports(reference, image)


def verify_source():
    proof = _source(SOURCE)
    contracts = proof['contract']
    if (proof['schema'] != 'civ6-host.xp1-great-people-commands.static.v1'
            or proof['image']['sha256'] != _XP1_PROFILE.image_sha256
            or (proof['capture']['path'], proof['capture']['sha256']) != reader.REFERENCE
            or (proof['reader']['path'], proof['reader']['sha256']) != reader.SOURCE
            or proof['native_execution'] is not False
            or proof['native_actions_qualified_here'] is not False
            or {key: row['signed'] for key, row in proof['enum_registrations'].items()} != _SIGNED_ENUMS
            or (contracts['operation_message'], contracts['archive_flags'], contracts['archive_map_marker'],
                contracts['archive_dword_tag']) != (_OPERATION_MESSAGE, _ARCHIVE_FLAGS, _MAP_MARKER, _DWORD_TAG)
            or contracts['currencies'] != _CURRENCIES):
        raise ValueError('Rise and Fall Great Person command source differs')
    return proof


def require_actions():
    return verify_source()


def verify_reject_source():
    proof = _source(REJECT_SOURCE)
    row = proof['enum_registration']
    source = proof['commands']
    contract = proof['contract']
    if (proof['schema'] != 'civ6-host.xp1-great-person-reject.static.v1'
            or proof['native_execution'] is not False or proof['native_action_qualified_here'] is not False
            or proof['image']['sha256'] != _XP1_PROFILE.image_sha256
            or (proof['capture']['path'], proof['capture']['sha256']) != reader.REFERENCE
            or (source['path'], source['sha256']) != SOURCE
            or (proof['reader']['path'], proof['reader']['sha256']) != reader.SOURCE
            or (row['name'], row['signed']) != _REJECT_ENUM
            or contract['native_operation'] != _REJECT_ENUM[1] or contract['individual_param'] != _INDIVIDUAL
            or contract['cost_wire_domain'] != (-2**31, _MAX_INT)
            or contract['native_archive'] != dict(message=_OPERATION_MESSAGE, flags=_ARCHIVE_FLAGS, entries=1,
                 bytes=_HEADER.size + _ENTRY.size, scalar_entry_bytes=_ENTRY.size)):
        raise ValueError('Rise and Fall Great Person rejection source differs')
    return proof


def source_for(action, *, xp2=False, reference=None):
    validate_action(action)
    if xp2:
        from .xp2_great_people_source import operation_source

        return operation_source(reference)
    return REJECT_SOURCE if action['kind'] == REJECT else SOURCE


def source_dependencies(image, *, include_reject=False):
    pins = reader.source_dependencies(image)
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), verify_source()['image']]
    if include_reject:
        verify_reject_source()
        refs.append(dict(path=REJECT_SOURCE[0], sha256=REJECT_SOURCE[1]))
    for row in refs:
        path = Path(row['path'])
        path = resolve_path(path if path.is_absolute() else resource_root() / path)
        if pins.setdefault(str(path.resolve()), row['sha256']) != row['sha256']:
            raise ValueError('Conflicting Rise and Fall Great Person command source pins')
    verify_pinned_files(pins)
    return pins


def _verify_span(base, read, row):
    raw = bytes.fromhex(row['raw_hex'])
    if (not 0 < len(raw) <= 4096 or len(raw) != row['bytes']
            or sha256(raw).hexdigest() != row['sha256'] or read(base + row['rva'], len(raw)) != raw):
        raise ValueError('Live Rise and Fall Great Person command body differs')


def _verify_literal(base, read, name, row):
    literal = name.encode('ascii') + b'\0'
    if read(base + row['literal_rva'], len(literal)) != literal:
        raise ValueError('Live Rise and Fall Great Person command selector differs')


def _verify_live(saved):
    saved._check_active()
    backend, prefix = saved.backend, saved.prefix
    core = backend.core
    lifetime = (core, prefix)
    if (getattr(saved, 'xp1_great_people', False) is not True
            or getattr(saved, '_xp1_great_people_query_lifetime', None) != lifetime
            or backend.load_abi.core_sha256 != XP1_CORE_SHA256
            or not reader.supports(backend.captured_bundle.reference, getattr(core, '_civ6_host_execution_image', None))
            or prefix.actions.pending or prefix.deferred_events.pending):
        raise ValueError('Great Person command requires its published Rise and Fall query owner and drained queues')
    prefix.actions.require_empty_native_queue()
    if getattr(saved, '_xp1_great_people_commands_lifetime', None) == lifetime:
        return
    proof = verify_source()
    base, read = core._handle, backend.runtime.read
    for row in (*proof['core_bodies'], *proof['enum_registrations'].values()):
        _verify_span(base, read, row)
    for name, row in proof['enum_registrations'].items():
        _verify_literal(base, read, name, row)
    saved._xp1_great_people_commands_lifetime = lifetime


def _verify_live_reject(saved):
    if getattr(saved, 'xp1_great_people_reject', False) is not True:
        raise ValueError('Great Person rejection requires its selected Rise and Fall action owner')
    backend = saved.backend
    lifetime = (backend.core, saved.prefix)
    if getattr(saved, '_xp1_great_people_reject_lifetime', None) == lifetime:
        return
    proof = verify_reject_source()
    base, read = backend.core._handle, backend.runtime.read
    for row in (*proof['core_bodies'], proof['enum_registration']):
        _verify_span(base, read, row)
    _verify_literal(base, read, _REJECT_ENUM[0], proof['enum_registration'])
    saved._xp1_great_people_reject_lifetime = lifetime


def validate_action(action):
    if type(action) is not dict or action.get('kind') not in KINDS:
        raise ValueError('Invalid Great Person command kind')
    fields = {'kind', 'individual_index', 'cost'}
    if action['kind'] == PATRONIZE:
        fields.add('currency')
        if action.get('currency') not in tuple(_CURRENCIES):
            raise ValueError('Unqualified Great Person patronage currency')
    minimum_cost = -2**31 if action['kind'] == REJECT else 0
    if (set(action) != fields or type(action['individual_index']) is not int
            or not 0 <= action['individual_index'] <= _MAX_INT or type(action['cost']) is not int
            or not minimum_cost <= action['cost'] <= _MAX_INT):
        raise ValueError('Invalid Great Person command parameters')
    return action


def actions(catalogue, *, include_reject=False):
    result = []
    for row in catalogue['timeline']:
        i = row['individual_index']
        if i is None:
            continue
        offer = row['recruitment']
        if offer['available']:
            result.append(validate_action(dict(kind=RECRUIT, individual_index=i, cost=offer['cost'])))
        for currency, offer in row['patronage'].items():
            if offer['available']:
                result.append(validate_action(dict(kind=PATRONIZE, individual_index=i,
                                                   currency=currency, cost=offer['cost'])))
        if include_reject and row['rejection']['available']:
            result.append(validate_action(dict(kind=REJECT, individual_index=i, cost=row['rejection']['cost'])))
    return result


def _operation(action):
    parameters = {_INDIVIDUAL: action['individual_index']}
    if action['kind'] == PATRONIZE:
        parameters[_YIELD] = _CURRENCIES[action['currency']]
    return _OPERATIONS[action['kind']], parameters


def verify_archive(payload, player_id, action):
    validate_action(action)
    reader._identity(player_id, 0)
    operation, expected = _operation(action)
    count = len(expected)
    if type(payload) is not bytes or len(payload) != _HEADER.size + count * _ENTRY.size:
        raise RuntimeError('Great Person command archive size differs')
    if _HEADER.unpack_from(payload) != (_OPERATION_MESSAGE, player_id, operation, _ARCHIVE_FLAGS,
                                        _MAP_MARKER, count):
        raise RuntimeError('Great Person command archive header differs')
    actual = {}
    for key, tag, reserved, value in _ENTRY.iter_unpack(payload[_HEADER.size:]):
        if tag != _DWORD_TAG or reserved != bytes(10) or key in actual:
            raise RuntimeError('Great Person command archive entry differs')
        actual[key] = value
    if actual != expected:
        raise RuntimeError('Great Person command archive parameters differ')
    return dict(archive_sha256=sha256(payload).hexdigest(), operation=operation,
                parameters=expected, size_bytes=len(payload))


_EFFECT = br'''
local function index(v)
 assert(type(v)=='number' and v%1==0 and v>=0 and v<=2147483647,'invalid grant index')
 return string.format('%.0f',v)
end
local definition=assert(GameInfo.GreatPersonIndividuals[individual],'missing grant individual')
local class=assert(GameInfo.GreatPersonClasses[classID],'missing grant class')
assert(definition.Index==individual and class.Index==classID and
       definition.GreatPersonClassType==class.GreatPersonClassType,'grant selection differs')
local unitType=assert(GameInfo.Units[class.UnitType],'missing Great Person class unit')
assert(unitType.UnitType==class.UnitType,'Great Person class unit differs')
local past=greatPeople:GetPastTimeline()
assert(type(past)=='table','missing past Great People timeline')
local matched=0
local count=0
for _,entry in ipairs(past) do
 count=count+1
 assert(count<=4096 and type(entry)=='table','invalid past Great People timeline')
 if entry.Individual==individual then
  assert(entry.Class==classID and entry.Claimant==pid and entry.TurnGranted==expectedTurn,
         'Great Person grant does not match selected player and turn')
  matched=matched+1
 end
end
assert(matched==expectedMatches,'Great Person was not granted exactly once')
local own=index(greatPeople:CountPeopleReceivedByPlayer(classID,pid))
assertContext()
return table.concat({'great-person-grant-v1',index(pid),index(expectedTurn),index(individual),
                     index(classID),index(unitType.Index),own,index(matched)},'|')
'''


def effect_source(player_id, turn, individual, class_id, *, granted):
    reader._identity(player_id, turn)
    if type(granted) is not bool or any(type(v) is not int or not 0 <= v <= _MAX_INT
                                        for v in (individual, class_id)):
        raise ValueError('Invalid Great Person effect identity')
    values = f'local individual,classID,expectedMatches={individual},{class_id},{int(granted)}\n'.encode('ascii')
    enums = [f'assert(PlayerOperations.{name}=={value},"Great Person operation enum differs")'
             for name, value in _SIGNED_ENUMS.items()]
    return _common_guards(player_id, turn) + values + ('\n'.join(enums) + '\n').encode('ascii') + _EFFECT


def _effect(prefix, player_id, turn, individual, class_id, *, granted):
    code = effect_source(player_id, turn, individual, class_id, granted=granted)
    raw = prefix.runtime.evaluate_text(prefix.ui_child, code, b'@xp1_great_person_grant', capacity=257)
    if type(raw) is not bytes or len(raw) > 256:
        raise RuntimeError('Great Person grant reply exceeds its bounds')
    label, pid, current_turn, selected, class_value, unit_type, count, matches = raw.decode('ascii').split('|')
    if (label != 'great-person-grant-v1' or tuple(map(reader._number, (pid, current_turn, selected, class_value)))
            != (player_id, turn, individual, class_id) or reader._number(matches, maximum=1) != int(granted)):
        raise RuntimeError('Foreign Great Person grant reply')
    return dict(unit_type=reader._number(unit_type), instances_earned=reader._number(count))


def _confirmed_effect(before, after, prior, grant, cost, currency):
    pid, turn = before['player_id'], before['turn']
    if ((after.get('player_id'), after.get('turn')) != (pid, turn)
            or grant['unit_type'] != prior['unit_type']
            or grant['instances_earned'] != prior['instances_earned'] + 1):
        raise RuntimeError('Great Person grant did not change its exact own class count')
    existing = {row['id'] for row in before['units']}
    added = [row['id'] for row in after['units'] if row['id'] not in existing
             and row['owner'] == pid and row['type'] == grant['unit_type']]
    if len(added) != 1:
        raise RuntimeError('Great Person grant did not create one matching own unit')
    result = dict(player_id=pid, turn=turn, unit_id=added[0], unit_type=grant['unit_type'],
                  instances_before=prior['instances_earned'], instances_after=grant['instances_earned'])
    if currency is not None:
        key = _BALANCES[currency]
        start, end = before['economy'][key], after['economy'][key]
        if start - end != cost:
            raise RuntimeError('Great Person patronage debit differs from the quoted native cost')
        result.update(balance_before=start, balance_after=end, amount_paid=cost)
    return result


_REJECT_EFFECT = br"""
local function integer(v, low, high)
 assert(type(v)=='number' and v%1==0 and v>=low and v<=high,'invalid Great Person rejection integer')
 return string.format('%.0f',v)
end
assert(PlayerOperations.REJECT_GREAT_PERSON==95216200,'Great Person rejection enum differs')
local definition=assert(GameInfo.GreatPersonIndividuals[individual],'missing rejected individual')
local class=assert(GameInfo.GreatPersonClasses[classID],'missing rejection class')
assert(definition.Index==individual and class.Index==classID and
       definition.GreatPersonClassType==class.GreatPersonClassType,'rejection selection differs')
local function selected(rows)
 assert(type(rows)=='table','missing Great People timeline')
 local seen, found=0,nil
 for _,row in ipairs(rows) do
  seen=seen+1
  assert(seen<=4096 and type(row)=='table','invalid Great People rejection timeline')
  if row.Individual==individual then
   assert(found==nil and row.Class==classID,'ambiguous Great Person rejection record')
   found=row
  end
 end
 local actual=0
 for k,_ in pairs(rows) do
  assert(type(k)=='number' and k%1==0 and k>=1 and k<=seen,'non-dense Great People rejection timeline')
  actual=actual+1
 end
 assert(actual==seen,'changed Great People rejection timeline')
 return found
end
local current=selected(greatPeople:GetTimeline())
local past=selected(greatPeople:GetPastTimeline())
local ownedCurrent=current~=nil and current.Claimant==pid
local ownedPast=past~=nil and past.Claimant==pid
local canReject=greatPeople:CanRejectPerson(pid,individual)
assert(type(canReject)=='boolean','invalid native Great Person rejection flag')
local ownPoints=player:GetGreatPeoplePoints():GetPointsTotal(classID)
local count=greatPeople:CountPeopleReceivedByPlayer(classID,pid)
assertContext()
return table.concat({'great-person-reject-v1',integer(pid,0,63),integer(expectedTurn,0,2147483647),
 integer(individual,0,2147483647),integer(classID,0,2147483647),
 integer(ownPoints*256,-2147483648,2147483647),integer(count,0,2147483647),
 ownedCurrent and '1' or '0',ownedPast and '1' or '0',canReject and '1' or '0',
 (current and integer(current.Cost,-2147483648,2147483647) or '-')},'|')
"""


def _reject_state(prefix, player_id, turn, individual, class_id):
    reader._identity(player_id, turn)
    if any(type(v) is not int or not 0 <= v <= _MAX_INT for v in (individual, class_id)):
        raise ValueError('Invalid Great Person rejection identity')
    start = f'local individual,classID={individual},{class_id}\n'.encode('ascii')
    raw = prefix.runtime.evaluate_text(prefix.ui_child, _common_guards(player_id, turn) + start + _REJECT_EFFECT,
                                      b'@xp1_great_person_rejection', capacity=257)
    if type(raw) is not bytes or len(raw) > 256:
        raise RuntimeError('Great Person rejection reply exceeds its bounds')
    label, pid, now, index, group, points, instances, current, past, can_reject, cost = raw.decode('ascii').split('|')
    if (label != 'great-person-reject-v1' or tuple(map(reader._number, (pid, now, index, group)))
            != (player_id, turn, individual, class_id)):
        raise RuntimeError('Foreign Great Person rejection reply')
    return dict(points_q8=reader._number(points, minimum=-2**31), instances=reader._number(instances),
                own_current=reader._bool(current), own_past=reader._bool(past),
                can_reject=reader._bool(can_reject), current_cost=reader._number(cost, minimum=-2**31, optional=True))


def _signed32(value):
    return (value + 2**31) % 2**32 - 2**31


def _confirmed_rejection(before, after, prior, native, cost):
    start, end = prior['points_q8'], native['points_q8']
    expected = max(0, _signed32(start + _signed32(-cost * 256)))
    # The shared points setter has a native guard against new increases. A
    # genuine reservation loss separately proves the rejection even then.
    allowed = (start, expected) if expected > start else (expected,)
    expected_current_cost = max(0, _signed32(prior['current_cost'] - cost))
    pid, turn = before['player_id'], before['turn']
    if ((after.get('player_id'), after.get('turn')) != (pid, turn) or end not in allowed
            or native['own_current'] or native['own_past'] or native['can_reject']
            or native['instances'] != prior['instances']
            or native['current_cost'] not in (None, expected_current_cost)
            or {row['id'] for row in after['units']} != {row['id'] for row in before['units']}
            or any(after['economy'][kind] != before['economy'][kind] for kind in ('gold', 'faith'))):
        raise RuntimeError('Native Great Person rejection lacks reservation loss and exact actor readback')
    return dict(player_id=pid, turn=turn, cost=cost, points_before=start/256, points_after=end/256,
                own_receipts_before=prior['instances'], own_receipts_after=native['instances'])


def catalogue(saved, observation, *, xp2=False):
    value = reader.read(saved, observation, xp2=True) if xp2 else reader.read(saved, observation)
    saved.explicit_great_people_actions = deepcopy(value)
    return value


def apply(saved, action, before, *, borrowed_catalogue=None):
    """Recheck a published native quote and require committed attribution."""
    validate_action(action)
    published = (getattr(saved, 'explicit_great_people_actions', None)
                 if borrowed_catalogue is None else borrowed_catalogue)
    if type(before) is not dict or type(published) is not dict:
        raise ValueError('Great Person command needs its actor observation and published catalogue')
    player_id, turn = reader._identity(before.get('player_id'), before.get('turn'))
    backend = saved.backend
    core_sha256 = backend.load_abi.core_sha256
    xp2 = core_sha256 == XP2_CORE_SHA256
    rejected = action['kind'] == REJECT
    prefix = saved.prefix
    if borrowed_catalogue is not None:
        from civ6_host.contracts import great_people
        from .xp1_session_view import _borrowed_xp2_reference

        _borrowed_xp2_reference(saved, player_id)
        great_people.validate(published, player_id, turn, observation=before)
        if published['schema'] != great_people.SCHEMA_V2 or action not in actions(published, include_reject=True):
            raise ValueError('Borrowed Great Person command lacks its published offer')
    if xp2:
        from .xp2_great_people_source import bind_actions
        bind_actions(saved)
    else:
        _verify_live(saved)
        if rejected:
            _verify_live_reject(saved)
    reference = backend.captured_bundle.reference if xp2 else None
    proof_sha = source_for(action, xp2=xp2, reference=reference)[1]
    fresh = reader._evaluate(prefix, player_id, turn, xp2=xp2)
    available = action in actions(fresh, include_reject=rejected)
    if borrowed_catalogue is not None and not available:
        return dict(status='refused', observation=deepcopy(before),
                    refusal_code='native_great_person_offer_changed', source_sha256=proof_sha)
    if not available or (borrowed_catalogue is None and fresh != published):
        raise RuntimeError('Great Person decision is stale or unavailable')
    individual = action['individual_index']
    row = next(row for row in fresh['timeline'] if row['individual_index'] == individual)
    class_id = row['class_index']
    if rejected:
        prior = _reject_state(prefix, player_id, turn, individual, class_id)
        if (not prior['own_current'] or prior['own_past'] or not prior['can_reject']
                or prior['current_cost'] is None or prior['points_q8'] // 256 < action['cost']):
            raise RuntimeError('Native Great Person rejection lost its current own reservation')
    else:
        prior = _effect(prefix, player_id, turn, individual, class_id, granted=False)
    operation, parameters = _operation(action)
    request = request_player_operation(backend.core, backend.context, player_id, operation,
        parameters, core_sha256=core_sha256, read=backend.runtime.read)
    prefix.emit('native_player_operation_request_returned', kind=action['kind'], **request)
    if request['can_start'] is False and request['request_invoked'] is False:
        prefix.actions.require_empty_native_queue()
        if prefix.deferred_events.pending:
            raise RuntimeError('Refused Great Person request produced deferred game events')
        return dict(status='refused', observation=deepcopy(before), request=request,
                    refusal_code='native_great_person_can_start_false', source_sha256=proof_sha)
    if (request['can_start'] is not True or request['request_invoked'] is not True
            or len(prefix.actions.pending) != 1):
        raise RuntimeError('Great Person request did not produce exactly one native command archive')
    archive = verify_archive(prefix.actions.pending[0], player_id, action)
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()
    prefix.actions.require_empty_native_queue()
    if prefix.deferred_events.pending:
        raise RuntimeError('Great Person request left deferred game events')
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    if rejected:
        native = _reject_state(prefix, player_id, turn, individual, class_id)
        verified = _confirmed_rejection(before, after, prior, native, action['cost'])
        effect_kind = 'rejection'
    else:
        grant = _effect(prefix, player_id, turn, individual, class_id, granted=True)
        verified = _confirmed_effect(before, after, prior, grant, action['cost'], action.get('currency'))
        effect_kind = 'grant'
    effect = dict(individual_index=individual, class_index=class_id, **archive, **verified)
    engine = 'xp2' if xp2 else 'xp1'
    event = f'native_{engine}_great_person_{effect_kind}_verified'
    prefix.emit(event, action=action, effect=effect, source_sha256=proof_sha, eligible_for_training=False)
    return dict(status='completed', observation=after, action=dict(action), effect=effect, source_sha256=proof_sha)
