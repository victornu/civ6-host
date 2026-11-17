"""Read the official Choose Artifact popup data on its owned Gathering Storm view."""

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from struct import pack

from civ6_host.contracts import archaeology

from . import xp2_bbg_inputs, xp2_bundle_inputs
from .configuration_profiles import XP2_CORE_SHA256, _source
from .execution_images import _PROFILE
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('work/xp2-workmove/archaeology-installed-source.json',
          '9be361034559c499d85157d23fce56b0cfd5df6366f0bcd54449712c8eb9b534')
_APPLICATION = ('evidence/host-archaeology-excavation-origin-installed-source.json',
                '077d78eabaab35339ab74106c3e552868829c16e2dae6d05f52f20722c95fb15')
_PANEL = ('work/xp2-workmove/activation-b86b059811544c9d655585e517c2b830455348a7013817bbad9488528a97ca83.json',
          'b86b059811544c9d655585e517c2b830455348a7013817bbad9488528a97ca83')
_PLACEMENT = ('evidence/host-xp2-artifact-placement-source.json',
              'fb9aa6d18a03280fe9533fed4c4f5d046483132c27d88ed53d8feed9cf788f6d')
OPERATION = 0x07247e03
PARAMETER = 0x0483191c
EXCAVATION_OPERATION = 0x5c533acc
UNCONFIRMED = 'native_artifact_origin_effect_unconfirmed'
_SEAL = object()
_CAPTURES = {xp2_bundle_inputs.REFERENCE: 'stock', xp2_bbg_inputs.REFERENCE: 'bbg751'}
_FRAME_LIMIT = 96


def _sources(reference, image):
    if image is not _PROFILE or type(reference) is not tuple or reference not in _CAPTURES:
        raise ValueError('Archaeology requires the exact stock or BBG 7.5.1 Gathering Storm capture')
    proof = _source(SOURCE)
    engine = proof['engines'][image.id]
    capture = proof['captures'][_CAPTURES[reference]]
    tested = capture['capture']
    captured_reference = (tested['path'], tested['sha256'])
    if reference == xp2_bundle_inputs.REFERENCE:
        prepared = _source(captured_reference)
        origin = prepared['origin']
        database = prepared['files']['database_gameplay']
        if (database['sha256'] != capture['database']['sha256']
                or Path(tested['path']).parent / database['path'] != Path(capture['database']['path'])):
            raise ValueError('The prepared archaeology gameplay database differs')
        captured_reference = (origin['path'], origin['sha256'])
    if (proof['schema'] != 'civ6-host.archaeology-installed-source.v1'
            or engine['image']['sha256'] != image.image_sha256
            or captured_reference != reference
            or tuple(proof['ui']['no_second_choice_types']) != archaeology.CONFIRM_ONLY_TYPES):
        raise ValueError('The installed archaeology source differs from the public contract')
    return proof['ui'], engine, capture


def _application_spans(engine):
    from .native.native_event_5d0f4014 import SELECTOR_KEY, VALUE_KEY
    from .native.native_event_great_work import EVENT_KIND
    from .xp2_great_work import SOURCE as WORK_CREATED

    choice = engine['xp2_origin_choice']
    proof = _source(_APPLICATION)
    if (proof['schema'] != 'civ6-host.archaeology-installed-source-delivery.v1'
            or proof['source_audit']['sha256'] != SOURCE[1]
            or (choice['operation'], choice['parameter']) != (OPERATION, PARAMETER)):
        raise ValueError('Artifact origin request source differs')
    placement = _source(_PLACEMENT)
    parents = placement['parents']
    if (placement['schema'] != 'civ6-host.xp2-artifact-placement-source.v1'
            or dict(placement['image']) != dict(id=_PROFILE.id, sha256=_PROFILE.image_sha256)
            or (parents['origin']['path'], parents['origin']['sha256']) != _APPLICATION
            or (parents['great_work_created']['path'], parents['great_work_created']['sha256']) != WORK_CREATED
            or (placement['effect']['event_hash'], placement['effect']['unit_descriptor_type'],
                placement['effect']['artifact_variant_key'], placement['effect']['selector_variant_key'])
               != (EVENT_KIND, 1, VALUE_KEY, SELECTOR_KEY)):
        raise ValueError('Artifact placement source differs from the owned origin and Great Work producers')
    return [choice[key] for key in ('request_gate', 'parameter_encoder', 'application_dispatch')] + [
        proof['xp2_origin_application'], *placement['spans'].values()]


def source_dependencies(reference, image, *, commands=False):
    ui, engine, capture = _sources(reference, image)
    resources = [engine['image'], dict(path=reference[0], sha256=reference[1]),
                 capture['capture'], capture['database'], *ui['scripts']]
    if reference == xp2_bbg_inputs.REFERENCE:
        resources.append(ui['bbg_modinfo'])
    if commands:
        _application_spans(engine)
        resources.append(dict(path=_APPLICATION[0], sha256=_APPLICATION[1]))
        resources.append(dict(path=_PLACEMENT[0], sha256=_PLACEMENT[1]))
        resources.append(dict(path=_PANEL[0], sha256=_PANEL[1]))
        panel = _source(_PANEL)['panel_source']
        if panel['delegates'] != ('GetUnitActionsTable', 'OnUnitActionClicked', 'LateCheckActionBeforeAdd'):
            raise ValueError('Artifact excavation requires the retained UnitPanel delegation')
        resources.extend(panel['scripts'][0 if reference == xp2_bbg_inputs.REFERENCE else 1:])
    pins = {str(resolve_path(resource_root()/SOURCE[0]).resolve(strict=True)): SOURCE[1]}
    for row in resources:
        path = str(resolve_path(resource_root()/Path(row['path'])).resolve(strict=True))
        if pins.setdefault(path, row['sha256']) != row['sha256']:
            raise ValueError('Conflicting archaeology source pins')
    return pins


def verify_live(base, read, *, reference, image, commands=False):
    if type(base) is not int or base <= 0 or not callable(read):
        raise ValueError('Archaeology requires its owned live module reader')
    _, engine, _ = _sources(reference, image)
    spans = [engine['artifact_table'], *engine['artifact_table_fields'].values()]
    for binding in engine['callbacks'].values():
        spans.extend(binding.values())
    if commands:
        spans.extend(_application_spans(engine))
        excavation = engine['xp2_excavation']
        if (excavation['operation'] != EXCAVATION_OPERATION
                or excavation['descriptor']['rva'] != '0xa29718'
                or read(base+0xa29728, 8) != pack('<Q', base+0x6695d0)
                or read(base+0xa29758, 8) != pack('<Q', base+0x669740)):
            raise ValueError('Live artifact excavation descriptor differs')
        spans.extend(excavation[key] for key in ('operation_lookup', 'factory', 'candidate_gate', 'operation_body'))
    for row in spans:
        raw = read(base+int(row['rva'], 16), row['bytes'])
        if type(raw) is not bytes or len(raw) != row['bytes'] or sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Live archaeology binding differs at ' + row['rva'])


def bind(saved, *, commands=False):
    backend = saved.backend
    core = backend.core
    if (core is None or saved.continuation.owner is not backend
            or saved.prefix is not backend.prefix or core is not saved.prefix.core):
        raise ValueError('Archaeology requires its exact live saved owner')
    verify_live(core._handle, backend.runtime.read, reference=saved.inputs.official_bundle,
                image=getattr(core, '_civ6_host_execution_image', None), commands=commands)
    saved._archaeology_core = core
    saved._archaeology_commands_core = core if commands else None


def commands_enabled(saved):
    core = getattr(saved, '_archaeology_commands_core', None)
    return core is not None and core is saved.backend.core


def borrowed_mode(saved, requested=None):
    core = getattr(saved, '_archaeology_core', None)
    mode = 'off'
    if core is not None and core is saved.backend.core:
        mode = 'commands' if commands_enabled(saved) else 'read'
    if requested is None:
        return mode
    if (requested not in ('off', 'read', 'commands')
            or requested != 'off' and (mode == 'off' or requested == 'commands' and mode != 'commands')):
        raise ValueError('Borrowed archaeology requires its admitted reader or command source')
    return requested


def build_source(player, turn):
    return preamble(player, turn) + _READ


def preamble(player, turn):
    if type(player) is not int or not 0 <= player < 64 or type(turn) is not int or not 0 <= turn < 2**31:
        raise ValueError('Invalid archaeology query identity')
    return f'local pid, turn = {player}, {turn}\n'.encode('ascii')


_CONTEXT = br'''
local function context()
    assert(Game.GetLocalPlayer() == pid and Game.GetLocalObserver() == pid
           and Game.GetCurrentGameTurn() == turn, 'stale archaeology perspective')
end
local function number(v, lo, hi)
    assert(type(v) == 'number' and v == math.floor(v) and v >= lo and v <= hi,
           'invalid archaeology integer')
    return string.format('%.0f', v)
end
context()
local player = assert(Players[pid], 'archaeology player is absent')
'''


_READ = _CONTEXT + br'''
local unit = player:GetUnits():GetNextExtractingArchaeologist()
local header = {number(pid, 0, 63), number(turn, 0, 2147483647)}
if unit ~= nil then
    assert(unit:GetOwner() == pid, 'archaeology unit is foreign')
    local id = unit:GetArchaeology():GetArtifactIndex()
    number(id, -2147483648, 2147483647)
    local artifact = Game.GetArtifactByIndex(id)
    if artifact ~= nil then
        header[3] = number(unit:GetID(), 0, 4294967295)
        header[4] = number(id, 0, 2147483647)
        header[5] = number(artifact.Type, 0, 5)
        header[6] = number(artifact.ActingPlayerEra, 0, 2147483647)
        assert(GameInfo.Eras[artifact.ActingPlayerEra], 'archaeology era is absent')
        header[7] = number(artifact.ActingPlayerID, 0, 63)
        if artifact.Type ~= 1 and artifact.Type ~= 2 and artifact.Type ~= 5 then
            header[8] = number(artifact.TargetPlayerID, 0, 63)
        end
        context()
        return table.concat(header, '|')
    end
end
context()
header[3] = 'none'
return table.concat(header, '|')
'''


def parse(raw, observation):
    return _parse_frame(raw, observation)[0]


def _parse_frame(raw, observation):
    player, turn = observation['player_id'], observation['turn']
    if type(raw) is not bytes or not 1 <= len(raw) <= _FRAME_LIMIT:
        raise ValueError('Invalid archaeology frame')
    fields = raw.split(b'|')
    if fields[:2] != [str(player).encode('ascii'), str(turn).encode('ascii')]:
        raise ValueError('Foreign archaeology frame')
    pending = None
    artifact_index = None
    if fields[2:] != [b'none']:
        if len(fields) not in (7, 8) or any(not row.isdigit() or row != str(int(row)).encode('ascii')
                                            for row in fields[2:]):
            raise ValueError('Malformed public artifact frame')
        unit, artifact_index, artifact, era, *origins = map(int, fields[2:])
        if not 0 <= artifact_index < 2**31:
            raise ValueError('Invalid native artifact index')
        pending = dict(unit_id=unit, artifact_type=artifact, era_index=era, origin_player_ids=origins)
    public = archaeology.validate(dict(schema=archaeology.SCHEMA, player_id=player, turn=turn, pending=pending),
                                   player, turn, observation=observation)
    return public, artifact_index


def read(saved, observation, *, panel=None, borrowed=False):
    if borrowed:
        saved._check_active()
    else:
        saved._check_query()
    prefix = saved.prefix
    if prefix.core is not getattr(saved, '_archaeology_core', None):
        raise ValueError('Archaeology requires its source-bound saved owner')
    state, index = _state(prefix, observation)
    snapshot = deepcopy(state), index
    if panel is not None:
        state = dict(state, schema=archaeology.MUSEUM_SCHEMA,
                     museum_artifacts=read_museum_artifacts(prefix, observation, panel))
        archaeology.validate(state, observation['player_id'], observation['turn'],
                             observation=observation, panel=panel)
    if borrowed:
        if not hasattr(saved, '_xp2_borrowed_archaeology'):
            saved._xp2_borrowed_archaeology = {}
        saved._xp2_borrowed_archaeology[observation['player_id']] = snapshot
    else:
        saved.explicit_archaeology = snapshot
    return state


_MUSEUM = _CONTEXT + br'''
local rows = {number(pid, 0, 63) .. '|' .. number(turn, 0, 2147483647)}
for _, requested in ipairs(slots) do
    local cityID, building, slot, work = unpack(requested)
    local city = assert(player:GetCities():FindID(cityID), 'museum city disappeared')
    assert(city:GetOwner() == pid, 'foreign museum city')
    local buildings = city:GetBuildings()
    assert(buildings:HasBuilding(building) == true and buildings:GetGreatWorkInSlot(building, slot) == work,
           'museum artifact slot changed')
    local definition = assert(GameInfo.GreatWorks[buildings:GetGreatWorkTypeFromIndex(work)])
    assert(definition.GreatWorkObjectType == 'GREATWORKOBJECT_ARTIFACT', 'museum work is not an artifact')
    local era = definition.EraType
    assert(type(era) == 'string' and #era <= 104 and era:match('^ERA_[A-Z0-9_]+$') and GameInfo.Eras[era],
           'artifact era is absent')
    local origin = number(Game.GetGreatWorkPlayer(work), -1, 63)
    rows[#rows + 1] = table.concat({number(work, 0, 2147483647), era, origin}, '|')
end
context()
return table.concat(rows, '\n')
'''


def read_museum_artifacts(prefix, observation, panel):
    slots = archaeology.museum_slots(panel)
    if not slots:
        return []
    player, turn = observation['player_id'], observation['turn']
    source = preamble(player, turn)
    encoded_slots = ','.join('{%d,%d,%d,%d}' % slot for slot in slots)
    source += f'local slots = {{{encoded_slots}}}\n'.encode('ascii') + _MUSEUM
    limit = 32 + 120 * len(slots)
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source, b'@public_museum_artifacts', capacity=limit + 1)
    if type(raw) is not bytes or not 0 < len(raw) <= limit:
        raise ValueError('Invalid museum artifact frame')
    header, *lines = raw.decode('ascii').split('\n')
    if header != f'{player}|{turn}' or len(lines) != len(slots):
        raise ValueError('Foreign museum artifact frame')
    rows = []
    for line, (city, building, slot, work) in zip(lines, slots, strict=True):
        fields = line.split('|')
        if len(fields) != 3 or fields[0] != str(work):
            raise ValueError('Museum artifact frame differs from the owned slot')
        origin = int(fields[2])
        if fields[2] != str(origin) or not -1 <= origin < 64:
            raise ValueError('Malformed native museum artifact origin')
        rows.append(dict(city_id=city, building_index=building, slot=slot, work_index=work,
                         era_type=fields[1], origin_player_id=None if origin == -1 else origin))
    return rows


def _state(prefix, observation):
    raw = prefix.runtime.evaluate_text(prefix.ui_child,
        build_source(observation['player_id'], observation['turn']), b'@public_archaeology', capacity=_FRAME_LIMIT+1)
    return _parse_frame(raw, observation)


@dataclass(frozen=True)
class _Permit:
    seal: object
    core: object
    context: int
    actor: int
    origin: int


def authorize_request(permit, core, context, player, operation, parameters, *, core_sha256, submit, allow_empty):
    if (type(permit) is not _Permit or permit.seal is not _SEAL or core is not permit.core
            or core_sha256 != XP2_CORE_SHA256 or getattr(core, '_civ6_host_execution_image', None) is not _PROFILE
            or context != permit.context or type(player) is not int or player != permit.actor or operation != OPERATION
            or type(parameters) is not dict or parameters != {PARAMETER: permit.origin}
            or type(parameters[PARAMETER]) is not int or not 0 <= permit.origin < 64
            or submit is not True or allow_empty is not False):
        raise ValueError('Missing exact artifact origin request permit')
    return 'CHOOSE_ARTIFACT_PLAYER'


def verify_archive(payload, actor, origin):
    expected = pack('<7IHH10xI', 0xc45de12f, actor, OPERATION, 2, 0x80000001, 1, PARAMETER, 0, 2, origin)
    if type(payload) is not bytes or payload != expected:
        raise RuntimeError('Artifact origin archive differs from its exact actor or origin')
    return sha256(payload).hexdigest()


_READY = _CONTEXT + br'''
assert(PlayerOperations.CHOOSE_ARTIFACT_PLAYER == 119832067
       and PlayerOperations.PARAM_PLAYER_ONE == 75700508, 'artifact operation enums changed')
return (player:IsTurnActive() == true and player:IsTurnActiveComplete() == true) and 'ready' or 'waiting'
'''


_AFTER = _CONTEXT + br'''
local unit = player:GetUnits():FindID(selectedUnit)
if unit == nil then context(); return 'removed' end
assert(unit:GetOwner() == pid, 'artifact unit changed owner')
local index = number(unit:GetArchaeology():GetArtifactIndex(), -1, 2147483647)
context()
return index
'''


def unit_artifact_index(prefix, observation, unit):
    actor, turn = observation['player_id'], observation['turn']
    source = f'local pid, turn, selectedUnit = {actor}, {turn}, {unit}\n'.encode('ascii')
    native = prefix.runtime.evaluate_text(prefix.ui_child, source+_AFTER, b'@artifact_origin_effect', capacity=16)
    present = any(row['id'] == unit for row in observation['units'])
    if native == b'removed' and not present:
        return None
    if not present or native == b'removed':
        raise RuntimeError('Artifact archaeologist readback differs from the published own roster')
    if native == b'-1':
        return -1
    if type(native) is not bytes or not native.isdigit() or int(native) >= 2**31 or str(int(native)).encode('ascii') != native:
        raise RuntimeError('Unexpected native archaeologist artifact index')
    return int(native)


def apply(saved, action, before, *, borrowed_public=None):
    from .native.native_player_observation import observe_player
    from .native.native_player_operation_request import request_player_operation
    from .xp1_great_person_activation import _work_record

    archaeology.validate_action(action)
    saved._check_active()
    if not commands_enabled(saved):
        raise ValueError('Artifact origin choice requires its source-bound saved owner')
    backend, prefix, token = saved.backend, saved.prefix, saved.continuation
    actor, turn = before['player_id'], before['turn']
    origin, unit = action['origin_player_id'], action['unit_id']
    source = f'local pid, turn, selectedUnit = {actor}, {turn}, {unit}\n'.encode('ascii')
    refused = dict(status='refused', observation=before, refusal_code='native_artifact_origin_choice_changed')
    available = prefix.runtime.evaluate_text(prefix.ui_child, source+_READY, b'@artifact_origin_ready', capacity=16)
    if available == b'waiting':
        return dict(refused, refusal_code='native_archaeology_actor_waiting')
    if available != b'ready':
        raise RuntimeError('Unexpected artifact origin command boundary')
    fresh = _state(prefix, before)
    if borrowed_public is None:
        matches = fresh == getattr(saved, 'explicit_archaeology', None)
    else:
        borrowed = getattr(saved, '_xp2_borrowed_archaeology', {})
        matches = (fresh == borrowed.get(actor)
                   and all(fresh[0][key] == borrowed_public.get(key) for key in ('player_id', 'turn', 'pending')))
    if not matches or action not in archaeology.actions(fresh[0]):
        return refused
    token.transport.require_empty_native_queue()
    backend.control(empty=True)
    permit = _Permit(_SEAL, backend.core, backend.context, actor, origin)
    receipt = request_player_operation(backend.core, backend.context, actor, OPERATION, {PARAMETER: origin},
        core_sha256=XP2_CORE_SHA256, read=backend.runtime.read, archaeology_permit=permit)
    if receipt['request_invoked'] is not True or receipt['can_start'] is not None or len(prefix.actions.pending) != 1:
        raise RuntimeError('Artifact origin request did not enqueue exactly one native archive')
    digest = verify_archive(prefix.actions.pending[0], actor, origin)
    events = prefix.deferred_events
    if events.pending:
        raise RuntimeError('Artifact origin request queued effects before native archive delivery')
    first_sequence = events.consumed_count
    prefix.actions.deliver_one()
    after_last_sequence = first_sequence + len(events.pending) + 1
    artifact_index = fresh[1]
    created = sum(
        _work_record(row, actor, unit, before['cities'], first_sequence, after_last_sequence)
        and int.from_bytes(row[116:120], 'little') == artifact_index for row in events.pending
    ) == 1
    events.drain_empty_receivers()
    if token.trade_feedback is not None and token.trade_feedback.events:
        token.flush_trade_feedback()
    prefix.view_publisher.publish()
    token.transport.require_empty_native_queue()
    after = observe_player(prefix.runtime, prefix.ui_child, actor)
    if (after['player_id'], after['turn']) != (actor, turn):
        raise RuntimeError('Artifact origin choice crossed its actor or turn')
    pending_cleared = unit_artifact_index(prefix, after, unit) in (None, -1)
    confirmed = pending_cleared and created
    if borrowed_public is None:
        saved.explicit_archaeology = None
    else:
        borrowed.pop(actor)
    return dict(status='completed' if confirmed else 'submitted', observation=after,
                refusal_code=None if confirmed else UNCONFIRMED,
                receipt=dict(action=deepcopy(action), native_archive_sha256=digest,
                             native_archive_delivered=True, native_pending_cleared=pending_cleared,
                             native_artifact_creation_observed=created))
