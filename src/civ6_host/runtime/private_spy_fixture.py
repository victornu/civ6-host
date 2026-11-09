"""Explicit administrative spy fixture, never an actor action or curriculum.

This installed authored module runs after an intact checkpoint comparison. It
uses the existing Gameplay child and normal publication services. Private lab
resources supply pinned data only; no Python is executed from those resources.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3
import struct

from .paths import resource_root
ROOT = resource_root()
HERE = ROOT / 'work/trade-common-client'
HOST = Path(__file__).resolve().parents[3]
PLAN = HERE / 'spy-native-fixture-plan.json'
PLAN_SHA = '890ebce2ab1bd0a91bf93020b602e1168cd1fd989df9ac68fd35eabac722f0ad'
CHECKPOINT = ROOT / ('work/host-simultaneous/native-runs/'
    'run-a33e6e03fff4461ca5217c907acb0668/checkpoint/checkpoint.json')
CHECKPOINT_SHA = '270bdaf9f3f6b01157354fc7bd1f01c6bc58b0c68fc95f283eaa05c40a34180e'
CORE_SHA = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
WAR_SHA = '0216c99c0ea8b76e972390efb21cb811763e4be8a1d9eebe3b382b205052968f'
HOOK_MARKER = b'# Private administrative spy fixture hook v2.'
SPEC_SCHEMA = 'civ6-host.private-spy-fixture.v2'
SCOPE = dict(public_action=False, training_eligible=False, curriculum_eligible=False,
             natural_progression_witness=False, mission_completion_claimed=False)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def checked(path, expected):
    path = Path(path).resolve()
    if digest(path) != expected:
        raise ValueError('Private fixture source changed: ' + str(path))
    return path


def spans(plan):
    return (plan['new_static_initunit_evidence']['spans']
            + plan['manager_service_resolution']['spans'])


def verify_image_spans(plan):
    """Check retained PE byte spans without mapping or executing the DLL."""
    raw = Path(plan['pins']['core']['path']).read_bytes()
    pe = struct.unpack_from('<I', raw, 0x3c)[0]
    if raw[pe:pe + 4] != b'PE\0\0':
        raise ValueError('Expected pinned PE image')
    sections = struct.unpack_from('<H', raw, pe + 6)[0]
    table = pe + 24 + struct.unpack_from('<H', raw, pe + 20)[0]
    ranges = [struct.unpack_from('<IIII', raw, table + 40 * i + 8)
              for i in range(sections)]
    verified = {}
    image_base = struct.unpack_from('<Q', raw, pe + 24 + 24)[0]
    image_size = struct.unpack_from('<I', raw, pe + 24 + 56)[0]
    for row in spans(plan):
        rva, size = int(row['rva'], 16), row['bytes']
        matches = [(rva - start + offset) for _, start, length, offset in ranges
                   if start <= rva and rva + size <= start + length]
        if len(matches) != 1 or hashlib.sha256(raw[matches[0]:matches[0] + size]).hexdigest() != row['sha256']:
            raise ValueError('InitUnit source span differs: ' + row['rva'])
        verified[row['rva']] = raw[matches[0]:matches[0] + size]
    return image_base, image_size, verified


def live_span_bytes(plan, row, load_base):
    """Only the source-identified UnitManager vtable is pointer-relocated.

    All thirteen entries are exact image pointers, including +48/+50 used by
    InitUnit. Instruction spans remain byte-exact; no general mask is used.
    """
    preferred, image_size, verified = plan['_verified_image_spans']
    raw = verified[row['rva']]
    if row['rva'] != '0xa23c60':
        return raw
    if (len(raw) != 104 or row['sha256'] !=
            '4726ad814cc17da0f7602dd593af9be213e2fe45473582385d1cc431a80405e4'):
        raise ValueError('Unexpected InitUnit vtable source')
    targets = tuple(value-preferred for value in struct.unpack('<13Q',raw))
    if any(not 0 <= value < image_size for value in targets):
        raise ValueError('InitUnit vtable contains a foreign source pointer')
    if targets[9:11] != (0x6505b0,0x650610):
        raise ValueError('InitUnit create delegates changed')
    return struct.pack('<13Q',*(load_base+value for value in targets))


def prepare():
    plan = json.loads(checked(PLAN, PLAN_SHA).read_bytes())
    if plan['schema'] != 'civ6-host.private-spy-native-fixture-plan.v1':
        raise ValueError('Unknown private fixture plan')
    for row in plan['pins'].values():
        path = checked(row['path'], row['sha256'])
        if path.stat().st_size != row['bytes']:
            raise ValueError('Private source length changed')
    plan['_verified_image_spans'] = verify_image_spans(plan)
    head = json.loads(checked(CHECKPOINT, CHECKPOINT_SHA).read_bytes())
    if (head['observed_game_turn'], head['player_id'], head['actual_image_sha256']) != (52, 0, CORE_SHA):
        raise ValueError('Expected exact current-image T52 checkpoint')
    previous = json.loads(CHECKPOINT.parent.parent.joinpath('closure.json').read_bytes())
    if previous['prepared_capture']['sha256'] != head['source_official_bundle']['sha256']:
        raise ValueError('Selected T52 capture and checkpoint differ')
    checked(previous['prepared_capture']['path'], previous['prepared_capture']['sha256'])
    fixture = json.loads(checked(ROOT / head['fixture']['path'], head['fixture']['sha256']).read_bytes())
    database = fixture['databases']['gameplay']
    db_path = checked(database['path'], database['sha256'])
    # T52 uses the recovered exact DB, not the older prepared DB in the plan.
    # Retain both identities and compare the actual relevant rows explicitly.
    queries = {
        'unit': "SELECT UnitType,Spy,IgnoreMoves,InitialLevel,Stackable,PrereqTech,PrereqCivic,PrereqDistrict,Cost FROM Units WHERE UnitType='UNIT_SPY'",
        'capacity': "SELECT m.ModifierId,m.ModifierType,m.OwnerRequirementSetId,m.SubjectRequirementSetId,a.Name,a.Value FROM Modifiers m JOIN ModifierArguments a ON a.ModifierId=m.ModifierId WHERE m.ModifierId IN ('CIVIC_GRANT_SPY','MODIFIER_CAPTURED_ADD_SPY_CAPACITY_BBG')",
        'operations': "SELECT OperationType,PrereqTech,PrereqCivic,Turns,TargetDistrict FROM UnitOperations WHERE OperationType IN ('UNITOPERATION_SPY_COUNTERSPY','UNITOPERATION_SPY_GAIN_SOURCES','UNITOPERATION_SPY_TRAVEL_NEW_CITY')",
    }
    with sqlite3.connect(db_path.as_uri() + '?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        for key, query in queries.items():
            actual = [dict(row) for row in connection.execute(query)]
            order = lambda row: json.dumps(row, sort_keys=True)
            if sorted(actual, key=order) != sorted(plan['captured_database_facts'][key], key=order):
                raise ValueError('T52 database differs from the private spy plan: ' + key)
    plan['selected_database'] = dict(path=str(db_path), sha256=database['sha256'])
    return plan, head, previous


def fixture_spec():
    return dict(schema=SPEC_SCHEMA, module='civ6_host.runtime.private_spy_fixture',
                module_file=str(Path(__file__).resolve()), module_sha256=digest(__file__),
                plan=str(PLAN), plan_sha256=PLAN_SHA,
                checkpoint_sha256=CHECKPOINT_SHA, player_id=0, turn=52,
                scope=deepcopy(SCOPE))


def validate_spec(spec, closure):
    if spec != fixture_spec() or closure.get('input_profile') != 'xp2-lan':
        raise ValueError('Private fixture specification changed')
    if not closure.get('espionage_diagnostic') or not closure.get('trade_diagnostic'):
        raise ValueError('Private spy fixture requires the existing espionage owner')
    for name in ('module_file', 'plan'):
        path = checked(spec[name], spec['module_sha256' if name == 'module_file' else 'plan_sha256'])
        if closure['pins'].get(str(path)) != spec['module_sha256' if name == 'module_file' else 'plan_sha256']:
            raise ValueError('Private fixture is outside the supervised source closure')


def _lua_identity(player, turn, city):
    values = (player, turn, city['id'], city['x'], city['y'])
    if any(type(v) is not int or v < 0 for v in values) or player != 0 or turn != 52:
        raise ValueError('Private fixture requires the exact T52 local owner')
    return f"""
local pid,turn,cityID,x,y={player},{turn},{city['id']},{city['x']},{city['y']}
assert(Game.GetLocalPlayer()==pid and Game.GetCurrentGameTurn()==turn,'fixture perspective changed')
local player=Players[pid];assert(player,'fixture player absent')
local city=player:GetCities():FindID(cityID)
assert(city and city:GetOwner()==pid and city:GetX()==x and city:GetY()==y,'fixture own city changed')
local def=GameInfo.Units['UNIT_SPY'];assert(def and def.Spy,'fixture spy definition absent')
assert(type(UnitManager.InitUnit)=='function','official InitUnit unavailable')
""".encode('ascii')


def capacity_source(player, turn, city, capacity):
    if type(capacity) is not int or not 0 <= capacity <= 2147483646:
        raise ValueError('Invalid baseline spy capacity')
    return _lua_identity(player, turn, city) + f"""
if {capacity}==0 then
 assert(type(player.AttachModifierByID)=='function','official capacity attachment unavailable')
 player:AttachModifierByID('CIVIC_GRANT_SPY')
 return 'attachment_called'
end
return 'no_attachment_needed'
""".encode('ascii')


def creation_source(player, turn, city):
    return _lua_identity(player, turn, city) + b"""
local unit=UnitManager.InitUnit(pid,'UNIT_SPY',x,y)
assert(unit and unit:GetOwner()==pid and unit:GetType()==def.Index,'native spy creation failed')
assert(unit:GetX()==x and unit:GetY()==y,'native spy created outside requested own city')
return string.format('%d,%d,%d,%d,%d',unit:GetID(),unit:GetOwner(),unit:GetType(),unit:GetX(),unit:GetY())
"""


def integers(raw, count):
    if type(raw) is not bytes or not 1 <= len(raw) <= 128:
        raise ValueError('Invalid private native fixture result')
    result = tuple(int(item) for item in raw.split(b','))
    if (len(result) != count or any(not 0 <= item <= 0xffffffff for item in result)
            or raw != ','.join(map(str, result)).encode('ascii')):
        raise ValueError('Noncanonical private native fixture result')
    return result


def _publish(continuation):
    p = continuation.prefix
    p.deferred_events.drain_empty_receivers()
    feedback = continuation.flush_trade_feedback()
    if p.deferred_events.pending:
        raise RuntimeError('Private fixture left deferred events pending')
    p.view_publisher.publish()
    continuation.transport.require_empty_native_queue()
    continuation.owner.control(empty=True)
    return feedback


def install_fixture(saved, closure, emit):
    """Called once on the existing worker thread, after authentic checkpoint reset."""
    validate_spec(closure['private_spy_fixture'], closure)
    plan, _, _ = prepare()
    from civ6_host.runtime.xp1_world_input import _owner
    from civ6_host.runtime.xp1_continuation import ACTIVE, READY
    from civ6_host.runtime.xp1_load_capability import capability_source_scope
    from civ6_host.runtime.saved_load_job_observer import require_quiescent
    from civ6_host.runtime.native.native_player_observation import observe_player
    from civ6_host.runtime.xp2_espionage import catalogue
    from civ6_host.runtime.xp2_bbg_spy import capacity_source as read_capacity, parse_capacity
    saved._check('commands', requested='unit_commands_candidate')
    with saved._attempt():
        b, c, p, identity = _owner(saved, active=False)
        if getattr(c, '_private_spy_fixture_started', False):
            raise ValueError('Private fixture cannot run twice')
        before = deepcopy(c.observation)
        if (before['player_id'], before['turn']) != (0, 52) or not before['cities']:
            raise ValueError('Private fixture is not at the expected own-city boundary')
        if getattr(b.core, '_civ6_host_execution_image', None).image_sha256 != CORE_SHA:
            raise ValueError('Private fixture has a different native image')
        for row in spans(plan):
            raw = b.runtime.read(b.core._handle + int(row['rva'], 16), row['bytes'])
            if raw != live_span_bytes(plan,row,b.core._handle):
                raise ValueError('Live private InitUnit source changed: ' + row['rva'])
        initial = catalogue(saved, before)
        if initial['spies'] or initial['captured'] or initial['off_map']:
            raise ValueError('Private fixture requires the retained empty spy baseline')
        city = min(before['cities'], key=lambda row: row['id'])
        c.transport.require_empty_native_queue(); b.control(empty=True)
        if p.deferred_events.pending or c.trade_feedback.events:
            raise ValueError('Private fixture requires empty event and feedback queues')
        c._private_spy_fixture_started = True
        count = c.publication_count
        try:
            b.stage, b.busy = ACTIVE, True
            c.check(active=True); saved._check_active()
            require_quiescent(b.jobs_snapshot('before'))
            with capability_source_scope(b, 'continuation'):
                cap = initial['capacity']
                independent_before = parse_capacity(p.runtime.evaluate_text(p.ui_child,
                    read_capacity(0), b'@private_spy_capacity_before', capacity=16))
                if independent_before != cap:
                    raise RuntimeError('Independent UI capacity baseline differs')
                raw = p.runtime.evaluate_text(p.game_child,
                    capacity_source(0, 52, city, cap), b'@private_spy_capacity_fixture', capacity=128)
                expected = cap + int(cap == 0)
                if raw != (b'attachment_called' if cap == 0 else b'no_attachment_needed'):
                    raise RuntimeError('Capacity attachment call did not return')
                if cap == 0:
                    _publish(c)
                independent = parse_capacity(p.runtime.evaluate_text(p.ui_child,
                    read_capacity(0), b'@private_spy_capacity_readback', capacity=16))
                if independent != expected:
                    raise RuntimeError('Independent UI capacity readback differs')
                raw = p.runtime.evaluate_text(p.game_child, creation_source(0, 52, city),
                    b'@private_spy_InitUnit_fixture', capacity=128)
                unit_id, owner, unit_type, x, y = integers(raw, 5)
                if (owner, x, y) != (0, city['x'], city['y']):
                    raise RuntimeError('Created native spy identity differs')
                feedback = _publish(c)
                after = observe_player(p.runtime, p.ui_child, 0)
                old_ids = {row['id'] for row in before['units']}
                created = [row for row in after['units'] if row['id'] not in old_ids]
                if (after['turn'] != 52 or len(after['units']) != len(before['units']) + 1
                        or len(created) != 1 or any(created[0][key] != value for key, value in
                            dict(id=unit_id, owner=owner, type=unit_type, x=x, y=y).items())
                        or c.publication_count != count + 1 + int(cap == 0)):
                    raise RuntimeError('Created native spy was not published exactly once')
                require_quiescent(b.jobs_snapshot('after'))
            c.observation = after; c.sequence += 1
            b.stage, b.busy = READY, False
            c.check(active=False)
            refreshed = catalogue(saved, after)
            if (refreshed['capacity'] != expected or len(refreshed['spies']) != 1
                    or refreshed['spies'][0]['unit_id'] != unit_id):
                raise RuntimeError('Public espionage roster does not contain the created native spy')
            emit('private_spy_fixture_created', **SCOPE, episode_id=identity.episode_id,
                 game_generation=identity.game_generation, turn=52, player_id=0,
                 continuation_sequence=c.sequence, unit_id=unit_id, unit_type=unit_type,
                 plan_sha256=PLAN_SHA, capacity_before=cap, capacity_after=expected,
                 observation_before=before, observation_after=deepcopy(after),
                 espionage=refreshed, gameplay_feedback=feedback,
                 administrative_archive_submitted=False)
        except BaseException:
            c.poisoned = True; c.lease.poison(); b.stage = 'poisoned'; b.busy = False
            raise

