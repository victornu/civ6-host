"""Read the official World Rankings score tab from an owned expansion view."""

from pathlib import Path

from civ6_host.contracts import world_score as contract

from .configuration_profiles import _source
from .execution_images import _PROFILE, _XP1_PROFILE, identity
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('evidence/host-expansion-score-ui-source.json',
          '12170bce5f5af9c35cf7dc0c45e7954b81ff1037a6426a5cd5183e616c3c7b94')
_BBG_WORLD_A = ('work/official-capture/bbg751-world-A-ui/manifest.json',
                '0438263e3e78b78233153afe0bc4e1ace6ac8e315aed21e4507f738bae8b285d')


def _configuration(reference, image):
    from . import xp1_saved_load, xp2_bbg_inputs, xp2_bundle_inputs

    if image is _XP1_PROFILE and reference == xp1_saved_load.REFERENCE:
        return ('base', 'team', 'xp1_manifest')
    if image is _PROFILE:
        files = ('base', 'team', 'xp2', 'xp2_manifest')
        if reference == xp2_bundle_inputs.REFERENCE:
            return files
        if reference in (xp2_bbg_inputs.REFERENCE, _BBG_WORLD_A):
            return (*files, 'bbg', 'bbg_manifest')
    raise ValueError('World score requires an exact stock expansion or BBG 7.5.1 LAN capture')


def _proof(image):
    value = _source(SOURCE)
    selected = value['engines'].get(image.id)
    if (value['schema'] != 'civ6-host.expansion-score-ui.source.v1'
            or selected is None or selected['engine'] != identity(image)
            or value['score_path_inherited'] is not True or value['bbg_version'] != 70501):
        raise ValueError('World score UI source profile differs')
    return value, selected['bindings']


def source_dependencies(reference, image):
    files = _configuration(reference, image)
    proof, _ = _proof(image)
    return {
        str((resource_root() / SOURCE[0]).resolve()): SOURCE[1],
        str(Path(image.path).resolve()): image.image_sha256,
        **{str(resolve_path(Path(proof['sources'][key]['path'])).resolve()): proof['sources'][key]['sha256']
           for key in files},
    }


def bind(saved):
    backend = saved.backend
    core = backend.core
    image = getattr(core, '_civ6_host_execution_image', None)
    _configuration(saved.inputs.official_bundle, image)
    _, bindings = _proof(image)
    if saved.continuation.owner is not backend:
        raise ValueError('World score requires the exact live session owner')
    for name, binding in bindings.items():
        raw = bytes.fromhex(binding['raw_hex'])
        literal = name.rpartition('.')[2].encode('ascii') + b'\0'
        if (backend.runtime.read(core._handle + binding['rva'], len(raw)) != raw
                or backend.runtime.read(core._handle + binding['name_rva'], len(literal)) != literal):
            raise ValueError('World score native binding differs: ' + name)
    saved._world_score_core = core


def require_owner(saved):
    core = saved.backend.core
    if core is None or getattr(saved, '_world_score_core', None) is not core:
        raise ValueError('World score requires the bound native session')


def borrowed_enabled(saved, requested=None):
    bound = getattr(saved, '_world_score_core', None)
    enabled = bound is not None and bound is saved.backend.core
    if requested is None:
        return enabled
    if type(requested) is not bool or (requested and not enabled):
        raise ValueError('Borrowed world score requires its bound native session')
    return requested


def build_source(player_id, turn):
    if (type(player_id) is not int or not 0 <= player_id <= 63
            or type(turn) is not int or not 0 <= turn < 2**31):
        raise ValueError('Invalid world score query identity')
    return f'local pid, turn = {player_id}, {turn}\n'.encode('ascii') + _READ


_READ = br'''
local function context()
    assert(Game.GetLocalPlayer() == pid and Game.GetLocalObserver() == pid
           and Game.GetCurrentGameTurn() == turn, 'stale world score perspective')
end
local function int(v, low, high)
    assert(type(v) == 'number' and v == math.floor(v) and v >= low and v <= high, 'invalid world score integer')
    return v
end
local function boolean(v)
    assert(type(v) == 'boolean', 'invalid world score boolean')
    return v
end
local function number(v)
    return string.format('%.0f', v)
end
context()
local enabled = boolean(Game.IsVictoryEnabled('VICTORY_SCORE'))
if not enabled and not boolean(GameConfiguration.IsAnyMultiplayer()) then
    return table.concat({'unavailable', number(pid), number(turn)}, '|')
end
local observer = Players[pid]
assert(observer and observer:IsAlive() == true and observer:IsMajor() == true, 'world score observer is not alive')
local diplomacy = observer:GetDiplomacy()
assert(diplomacy, 'world score diplomacy unavailable')
local minInt, maxInt = -2147483648, 2147483647
local maxTurns = int(Game.GetMaxGameTurns(), minInt, maxInt)
local categories, indexes = {'C'}, {}
local dbCategories = GameInfo.ScoringCategories
int(#dbCategories, 0, 64)
for i = 0, #dbCategories - 1 do
    local row = dbCategories[i]
    assert(type(row.Multiplier) == 'number' and row.Multiplier == row.Multiplier, 'invalid score multiplier')
    if row.Multiplier > 0 then
        local key = row.CategoryType
        assert(type(key) == 'string' and #key <= 96 and string.match(key, '^[A-Z][A-Z0-9_]*$'),
               'invalid score category')
        categories[#categories + 1] = key
        indexes[#indexes + 1] = i
    end
end
local majors = PlayerManager.GetAliveMajors()
assert(type(majors) == 'table' and #majors >= 1 and #majors <= 64, 'invalid world score major roster')
local teams, teamsByID, seen = {}, {}, {}
for _, player in ipairs(majors) do
    local id = int(player:GetID(), 0, 63)
    assert(not seen[id] and player:IsAlive() == true and player:IsMajor() == true, 'stale world score major')
    seen[id] = true
    local teamID = int(player:GetTeam(), 0, 63)
    local score = int(player:GetScore(), minInt, maxInt)
    local team = teamsByID[teamID]
    if team == nil then
        team = {score = 0, players = {}}
        teamsByID[teamID] = team
        teams[#teams + 1] = team
    end
    local visibleID = (id == pid or boolean(diplomacy:HasMet(id))) and number(id) or '-'
    local fields = {'P', visibleID, number(score)}
    for _, index in ipairs(indexes) do
        fields[#fields + 1] = number(int(player:GetCategoryScore(index), minInt, maxInt))
    end
    team.score = team.score + score
    team.players[#team.players + 1] = {score = score, line = table.concat(fields, '|')}
end
assert(seen[pid], 'world score excludes local player')
table.sort(teams, function(a, b) return a.score > b.score end)
local output = {table.concat({'score-v1', number(pid), number(turn), enabled and '1' or '0', number(maxTurns)}, '|'),
                table.concat(categories, '|')}
for _, team in ipairs(teams) do
    output[#output + 1] = 'T|' .. number(team.score)
    table.sort(team.players, function(a, b) return a.score > b.score end)
    for _, player in ipairs(team.players) do
        output[#output + 1] = player.line
    end
end
context()
return table.concat(output, '\n')
'''


def parse(raw, player_id, turn):
    if type(raw) is not bytes or len(raw) > contract.MAX_FRAME_BYTES:
        raise ValueError('Invalid world score frame')
    lines = raw.decode('ascii').splitlines()
    if lines == [f'unavailable|{player_id}|{turn}']:
        return None
    if not 4 <= len(lines) <= 130:
        raise ValueError('Invalid world score frame length')
    header, categories = (line.split('|') for line in lines[:2])
    if (len(header) != 5 or header[:3] != ['score-v1', str(player_id), str(turn)]
            or header[3] not in ('0', '1') or categories[0] != 'C'):
        raise ValueError('World score frame has a foreign boundary')

    def decimal(token):
        if len(token) > 13:
            raise ValueError('World score integer exceeds its wire bound')
        value = int(token)
        if str(value) != token:
            raise ValueError('Noncanonical world score integer')
        return value

    teams = []
    for line in lines[2:]:
        row = line.split('|')
        if row[0] == 'T' and len(row) == 2:
            teams.append(dict(score=decimal(row[1]), players=[]))
        elif row[0] == 'P' and teams and len(row) == 2 + len(categories):
            teams[-1]['players'].append(dict(player_id=None if row[1] == '-' else decimal(row[1]),
                                             score=decimal(row[2]), category_scores=[decimal(v) for v in row[3:]]))
        else:
            raise ValueError('Invalid world score row')
    return contract.validate(dict(schema=contract.SCHEMA, player_id=player_id, turn=turn,
        score_victory_enabled=header[3] == '1', max_game_turns=decimal(header[4]),
        categories=categories[1:], teams=teams), player_id, turn)


def read(saved, observation):
    require_owner(saved)
    player_id, turn = observation['player_id'], observation['turn']
    p = saved.prefix
    raw = p.runtime.evaluate_text(p.ui_child, build_source(player_id, turn),
        b'@public_world_score', capacity=contract.MAX_FRAME_BYTES + 1)
    return parse(raw, player_id, turn)
