"""Public text and icon fields rendered by the pinned DeclareWarPopup UI."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_world_war_display.py')))).resolve().parents[1]
POPUP = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI\\Popups\\DeclareWarPopup.lua"))
POPUP_SHA256 = 'f95b880edb5ee6deb5244b0d82429d8541de93f3cf1c8840bf09fd4deaadd208'
POPUP_XML = POPUP.with_suffix('.xml')
POPUP_XML_SHA256 = '10cb7da15bb5aaa4bdebcbdbf228ea3f7c5884d987fa6efe040e53b809acdf20'
SCHEMA = 'civ6rl.native_world_war_display.v2'
MAX_BYTES = 65536
MAX_TEXT_BYTES = 4096
_DECL = re.compile('^(?:local\\s+)?function\\s+([A-Za-z_][A-Za-z_0-9]*)\\s*\\(')
_PLAYER_MAX = 63
_WAR_MAX = 4294967295

def _popup_bytes(path: Path=POPUP) -> bytes:
    raw = _resolve_resource_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != POPUP_SHA256:
        raise RuntimeError('Pinned official DeclareWarPopup.lua changed')
    return raw

def _extract(raw: bytes, name: str) -> tuple[bytes, int, int]:
    lines = raw.decode('utf-8-sig').splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith(f'function {name}(') or line.startswith(f'local function {name}(')]
    if len(starts) != 1:
        raise RuntimeError('Official war popup function anchor changed: ' + name)
    first = starts[0]
    end = next((i for i in range(first + 1, len(lines)) if _DECL.match(lines[i])), len(lines))
    selected = lines[first:end]
    while selected and (not selected[-1].strip() or selected[-1].lstrip().startswith('--')):
        selected.pop()
    body = ''.join(selected).rstrip() + '\n'
    if not body.rstrip().endswith('end'):
        raise RuntimeError('Official war popup function is incomplete: ' + name)
    body = re.sub('^function ' + re.escape(name) + '\\(', 'local function ' + name + '(', body, count=1)
    return (body.encode('utf-8'), first + 1, first + len(selected))

def _onshow_contract(raw: bytes) -> dict:
    onshow, first, last = _extract(raw, 'OnShow')
    text = onshow.decode('utf-8')
    required = ('local iWarmongerPoints = -1;', 'bSuccess, tResults = DiplomacyManager.TestAction(eFromPlayer, eDefendingPlayer, DiplomacyActionTypes.SET_WAR_STATE, kParams);', 'local tmp = pAttacker:GetDiplomacy():ComputeDOWWarmongerPoints(eDefendingPlayer, kParams.WarState);', 'iWarmongerPoints = math.min(tmp, iWarmongerPoints);', 'Controls.Message:SetText(Locale.Lookup("LOC_DIPLO_WARNING_DECLARE_WAR_FROM_UNIT_ATTACK_INFO_MULTIPLE"));', 'local szWarmongerLevel = pAttacker:GetDiplomacy():GetWarmongerLevel(-iWarmongerPoints);', 'consequenceItem.Text:SetText(Locale.Lookup("LOC_DIPLO_CHOICE_WARMONGER_INFO", szWarmongerLevel));')
    for fragment in required:
        if text.count(fragment) != 1:
            raise RuntimeError('Official war popup display expression changed: ' + fragment)
    return {'source': onshow, 'first_line': first, 'last_line': last, 'sha256': hashlib.sha256(onshow).hexdigest(), 'required': required}

def _xml_texts() -> dict:
    raw = _resolve_resource_path(POPUP_XML).read_bytes()
    if hashlib.sha256(raw).hexdigest() != POPUP_XML_SHA256:
        raise RuntimeError('Pinned official DeclareWarPopup.xml changed')
    root = ET.fromstring(raw)
    labels = {'decline': root.find(".//*[@ID='No']"), 'accept': root.find(".//*[@ID='Yes']"), 'title': root.find(".//Label[@Style='WindowHeader']"), 'warmonger_heading': root.find(".//*[@ID='WarmongerContainer']//Label")}
    expected = {'decline': 'LOC_DIPLOMACY_DEAL_EXIT_DEAL', 'accept': 'LOC_DECLARE_WAR_BUTTON', 'title': '{LOC_DECLARE_WAR_HEADER:upper}', 'warmonger_heading': 'LOC_DECLARE_WAR_WARMONGER_HEADING'}
    if any((node is None or node.get('String') != expected[key] for key, node in labels.items())):
        raise RuntimeError('Official war confirmation label binding changed')
    return expected

def verified_files() -> dict[Path, str]:
    _popup_bytes()
    _xml_texts()
    return {POPUP: POPUP_SHA256, POPUP_XML: POPUP_XML_SHA256}

def source_manifest() -> dict:
    raw = _popup_bytes()
    onshow = _onshow_contract(raw)
    target, target_first, target_last = _extract(raw, 'PopulateTargetInstance')
    required_target = ('local playerName : string;', 'GameConfiguration.IsAnyMultiplayer() and pPlayerCfg:IsHuman()', 'Locale.Lookup( pPlayerCfg:GetCivilizationShortDescription() ) .. " (" .. pPlayerCfg:GetPlayerName() .. ")"', 'playerName = pPlayerCfg:GetCivilizationShortDescription();', 'local iconName = "ICON_"..pPlayerCfg:GetCivilizationTypeName();', 'controls.CivIcon:SetIcon(iconName);', 'controls.TargetName:SetText(Locale.Lookup(playerName));')
    text = target.decode('utf-8')
    for fragment in required_target:
        if text.count(fragment) != 1:
            raise RuntimeError('Official war target display expression changed: ' + fragment)
    return {'schema': 'civ6rl.native_world_war_display_source.v2', 'popup': {'path': str(POPUP), 'sha256': POPUP_SHA256}, 'layout': {'path': str(POPUP_XML), 'sha256': POPUP_XML_SHA256, 'localized_strings': _xml_texts()}, 'functions': {'OnShow': {'first_line': onshow['first_line'], 'last_line': onshow['last_line'], 'source_sha256': onshow['sha256'], 'verified_display_expressions': list(onshow['required'])}, 'PopulateTargetInstance': {'first_line': target_first, 'last_line': target_last, 'source_sha256': hashlib.sha256(target).hexdigest(), 'verified_display_expressions': list(required_target)}}, 'projection': {'emitted': ['player_id', 'turn', 'defender_player_ids', 'war_type', 'targets.player_id', 'targets.display_name', 'targets.icon_name', 'message', 'warmonger_text', 'buttons.accept', 'buttons.text', 'static_text.title', 'static_text.warmonger_heading'], 'excluded': ['ComputeDOWWarmongerPoints raw value', 'raw warmonger level', 'TestAction return values', 'player colors', 'configuration snapshot'], 'source_semantics_preserved': ['target display name/icon use the exact source expressions', 'no widget callbacks or player colors are invoked', 'eFromPlayer is nil in isolated scope', 'initial warmonger points is -1', 'math.min(tmp, iWarmongerPoints) is unchanged']}}

def _projection_sha256() -> str:
    raw = _popup_bytes()
    onshow = _onshow_contract(raw)['source']
    target, _, _ = _extract(raw, 'PopulateTargetInstance')
    _xml_texts()
    return hashlib.sha256(onshow + b'\n' + target + b'\n' + _resolve_resource_path(POPUP_XML).read_bytes()).hexdigest()

def _int(value, name: str, maximum: int) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('invalid ' + name)
    return value

def _war_int(value):
    if type(value) is not int or not -(1 << 31) <= value <= _WAR_MAX:
        raise ValueError('invalid war type')
    return value

def _lua_string(value: str) -> bytes:
    if type(value) is not str or '\x00' in value or len(value.encode('utf-8')) > MAX_TEXT_BYTES:
        raise ValueError('invalid public player-configuration text')
    return ('"' + ''.join(('\\%03d' % byte for byte in value.encode('utf-8'))) + '"').encode('ascii')

def display_source(player_id: int, expected_turn: int, defender_player_ids, war_type: int, configuration_snapshot: dict) -> bytes:
    """Build a read-only projection using the popup's exact display routines.

    `configuration_snapshot` is supplied by native_world_configuration.read;
    no configuration values are inferred here.
    """
    verified_files()
    pid = _int(player_id, 'player ID', _PLAYER_MAX)
    turn = _int(expected_turn, 'turn', 4294967295)
    war = _war_int(war_type)
    if type(defender_player_ids) not in (list, tuple) or not defender_player_ids or len(defender_player_ids) > 64:
        raise ValueError('expected a bounded nonempty defender list')
    defenders = [_int(item, 'defender player ID', _PLAYER_MAX) for item in defender_player_ids]
    if len(set(defenders)) != len(defenders) or pid in defenders:
        raise ValueError('invalid or repeated war target')
    if type(configuration_snapshot) is not dict or set(configuration_snapshot) != {'is_any_multiplayer', 'players'} or type(configuration_snapshot['is_any_multiplayer']) is not bool or (type(configuration_snapshot['players']) is not dict) or (set(configuration_snapshot['players']) != set(defenders)):
        raise ValueError('war display configuration does not match targets')
    from civ6_host.runtime.native.native_world_configuration import lua_bindings
    configuration_bindings = lua_bindings(configuration_snapshot)
    raw = _popup_bytes()
    onshow = _onshow_contract(raw)
    target_source, _, _ = _extract(raw, 'PopulateTargetInstance')
    digest = _projection_sha256()
    prefix = configuration_bindings + b'\n'
    setup = b'local pid,turn,warType=' + b','.join((str(v).encode() for v in (pid, turn, war))) + b'\nlocal defenders={' + b','.join((str(v).encode() for v in defenders)) + b'}\nlocal sourceDigest=' + _lua_string(digest) + b'\nlocal xmlDecline,xmlAccept,xmlTitle,xmlWarmonger=' + b','.join((_lua_string(_xml_texts()[key]) for key in ('decline', 'accept', 'title', 'warmonger_heading'))) + b'\nassert(Game and Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n       Game.GetCurrentGameTurn()==turn,\'war display perspective or turn changed\')\nassert(GameConfiguration and type(GameConfiguration.IsAnyMultiplayer)==\'function\' and\n       Locale and type(Locale.Lookup)==\'function\' and Players and DiplomacyManager and\n       type(DiplomacyManager.TestAction)==\'function\' and DiplomacyActionTypes and\n       WarTypes and warType==WarTypes.SURPRISE_WAR,\n       \'official war display APIs unavailable\')\nlocal attacker=Players[pid]\nassert(attacker and type(attacker.GetDiplomacy)==\'function\',\'attacking diplomacy display API unavailable\')\nlocal pAttacker=attacker\nlocal eFromPlayer=nil\nlocal bSuccess,tResults\nlocal iWarmongerPoints=-1\nlocal targets={}\nfor _,eDefendingPlayer in ipairs(defenders) do\n local kParams={};kParams.WarState=warType\n bSuccess,tResults = DiplomacyManager.TestAction(eFromPlayer, eDefendingPlayer, DiplomacyActionTypes.SET_WAR_STATE, kParams);\n local tmp = pAttacker:GetDiplomacy():ComputeDOWWarmongerPoints(eDefendingPlayer, kParams.WarState);\n iWarmongerPoints = math.min(tmp, iWarmongerPoints);\n local pPlayerCfg=PlayerConfigurations[eDefendingPlayer]\n assert(pPlayerCfg~=nil,\'official target configuration unavailable\')\n local playerName\n if(GameConfiguration.IsAnyMultiplayer() and pPlayerCfg:IsHuman()) then\n  playerName = Locale.Lookup( pPlayerCfg:GetCivilizationShortDescription() ) .. " (" .. pPlayerCfg:GetPlayerName() .. ")"\n else\n  playerName = pPlayerCfg:GetCivilizationShortDescription()\n end\n local iconName = "ICON_"..pPlayerCfg:GetCivilizationTypeName()\n targets[#targets+1]={player_id=eDefendingPlayer,display_name=Locale.Lookup(playerName),icon_name=iconName}\nend\nlocal message=Locale.Lookup("LOC_DIPLO_WARNING_DECLARE_WAR_FROM_UNIT_ATTACK_INFO_MULTIPLE")\nlocal szWarmongerLevel = pAttacker:GetDiplomacy():GetWarmongerLevel(-iWarmongerPoints)\nlocal warmongerText=Locale.Lookup("LOC_DIPLO_CHOICE_WARMONGER_INFO", szWarmongerLevel)\nassert(type(message)==\'string\' and type(warmongerText)==\'string\',\'official localized war text unavailable\')\nlocal function quote(s)\n assert(type(s)==\'string\' and #s<=4096,\'invalid rendered text\')\n local parts={\'"\'}\n for i=1,#s do\n  local n=string.byte(s,i);local c=string.sub(s,i,i)\n  if n==34 or n==92 then parts[#parts+1]=string.char(92)..c\n  elseif n<32 then parts[#parts+1]=string.char(92)..\'u\'..string.format(\'%04x\',n)\n  else parts[#parts+1]=c end\n end\n parts[#parts+1]=\'"\';return table.concat(parts)\nend\nlocal targetRows={}\nfor i,row in ipairs(targets) do\n targetRows[i]=\'{"player_id":\'..string.format(\'%.0f\',row.player_id)..\n  \',"display_name":\'..quote(row.display_name)..\',"icon_name":\'..quote(row.icon_name)..\'}\'\nend\nlocal defenderRows={};for i,id in ipairs(defenders) do defenderRows[i]=string.format(\'%.0f\',id) end\nreturn \'{"schema":"civ6rl.native_world_war_display.v2","player_id":\'..string.format(\'%.0f\',pid)..\n \',"turn":\'..string.format(\'%.0f\',turn)..\',"defender_player_ids":[\'..table.concat(defenderRows,\',\')..\']\'..\n \',"war_type":\'..string.format(\'%.0f\',warType)..\',"targets":[\'..table.concat(targetRows,\',\')..\']\'..\n \',"message":\'..quote(message)..\',"warmonger_text":\'..quote(warmongerText)..\n \',"buttons":[{"accept":false,"text":\'..quote(Locale.Lookup(xmlDecline))..\n \'},{"accept":true,"text":\'..quote(Locale.Lookup(xmlAccept))..\'}]\'..\n \',"static_text":{"title":\'..quote(Locale.Lookup(xmlTitle))..\n \',"warmonger_heading":\'..quote(Locale.Lookup(xmlWarmonger))..\'}\'..\n \',"source_sha256":\'..quote(sourceDigest)..\'}\'\n'
    source = prefix + setup
    if len(source) > MAX_BYTES:
        raise ValueError('war display source exceeds bound')
    return source

def read(owner, observation: dict, prompt: dict) -> dict:
    """Read the public popup text without applying a choice or changing game state."""
    from civ6_host.runtime.native import native_world_configuration
    from civ6_host.runtime.native.native_player_observation import observe_player
    from civ6_host.runtime.native.native_saved_actions import snapshot
    if type(observation) is not dict or type(observation.get('player_id')) is not int or type(observation.get('turn')) is not int:
        raise ValueError('invalid public observation for war display')
    pid, turn = (observation['player_id'], observation['turn'])
    _int(pid, 'player ID', _PLAYER_MAX)
    _int(turn, 'turn', 4294967295)
    if type(prompt) is not dict or set(prompt) != {'attacking_player', 'defending_player', 'war_type'} or type(prompt['attacking_player']) is not int or (prompt['attacking_player'] != pid):
        raise ValueError('invalid public war prompt identity')
    defender = _int(prompt['defending_player'], 'defender player ID', _PLAYER_MAX)
    war = _war_int(prompt['war_type'])
    if defender == pid:
        raise ValueError('war prompt targets the attacking player')
    p = owner.prefix
    owner.control(empty=True)
    before_jobs = snapshot(owner, 'before')
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('war display read requires empty native transports')
    if observe_player(p.runtime, p.ui_child, pid) != observation:
        raise RuntimeError('war display read crossed the public observation boundary')
    configuration = native_world_configuration.read(owner, [defender])
    raw = p.runtime.evaluate_text(p.ui_child, display_source(pid, turn, [defender], war, configuration), b'@official_world_war_display', capacity=MAX_BYTES + 1)
    result = parse_display(raw, pid, turn, [defender], war)
    owner.control(empty=True)
    after_jobs = snapshot(owner, 'after')
    if p.actions.pending or p.deferred_events.pending:
        raise RuntimeError('war display read left native transports pending')
    if after_jobs != before_jobs or observe_player(p.runtime, p.ui_child, pid) != observation:
        raise RuntimeError('read-only war display changed scheduler or public observation')
    owner.emit('official_world_war_display', display=result, public_observation_unchanged=True, scheduler_unchanged=True, native_commands=0, display_payload_contains_private_metadata=False, eligible_for_training=False)
    return result

def parse_display(raw: bytes, player_id: int, expected_turn: int, defender_player_ids, war_type: int) -> dict:
    if type(raw) is not bytes or not raw or len(raw) > MAX_BYTES:
        raise ValueError('invalid war display payload size')
    try:

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError('duplicate war display JSON key')
                result[key] = value
            return result
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=lambda token: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('malformed war display JSON') from exc
    pid = _int(player_id, 'player ID', _PLAYER_MAX)
    turn = _int(expected_turn, 'turn', 4294967295)
    war = _war_int(war_type)
    if type(defender_player_ids) not in (list, tuple) or not defender_player_ids or len(defender_player_ids) > 64:
        raise ValueError('invalid requested defender list')
    defenders = [_int(item, 'defender player ID', _PLAYER_MAX) for item in defender_player_ids]
    if len(set(defenders)) != len(defenders) or pid in defenders:
        raise ValueError('invalid or repeated requested defender')
    if type(value) is not dict or set(value) != {'schema', 'player_id', 'turn', 'defender_player_ids', 'war_type', 'targets', 'message', 'warmonger_text', 'source_sha256', 'buttons', 'static_text'} or value['schema'] != SCHEMA or (type(value['player_id']) is not int) or (value['player_id'] != pid) or (type(value['turn']) is not int) or (value['turn'] != turn) or (type(value['war_type']) is not int) or (value['war_type'] != war) or (type(value['defender_player_ids']) is not list) or (value['defender_player_ids'] != defenders):
        raise ValueError('war display identity or schema mismatch')
    if type(value['targets']) is not list or len(value['targets']) != len(defenders):
        raise ValueError('war display target count mismatch')
    for target, defender in zip(value['targets'], defenders):
        if type(target) is not dict or set(target) != {'player_id', 'display_name', 'icon_name'} or type(target['player_id']) is not int or (target['player_id'] != defender):
            raise ValueError('war display target identity mismatch')
        for key in ('display_name', 'icon_name'):
            _text(value=target[key], name=key)
    _text(value=value['message'], name='message')
    _text(value=value['warmonger_text'], name='warmonger text')
    if type(value['buttons']) is not list or len(value['buttons']) != 2:
        raise ValueError('war confirmation requires both official buttons')
    for button, accept in zip(value['buttons'], (False, True)):
        if type(button) is not dict or set(button) != {'accept', 'text'} or button['accept'] is not accept:
            raise ValueError('war confirmation button order or identity changed')
        _text(button['text'], 'button text')
    if type(value['static_text']) is not dict or set(value['static_text']) != {'title', 'warmonger_heading'}:
        raise ValueError('war confirmation static label fields changed')
    for key, text in value['static_text'].items():
        _text(text, key)
    if type(value['source_sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', value['source_sha256']) or value['source_sha256'] != _projection_sha256():
        raise ValueError('invalid war display source digest')
    return value

def _text(value, name: str):
    if type(value) is not str or len(value.encode('utf-8')) > MAX_TEXT_BYTES or '\x00' in value:
        raise ValueError('malformed displayed ' + name)
    return value
