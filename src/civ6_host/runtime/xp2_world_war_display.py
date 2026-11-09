"""Public XP2 war-confirmation text, using the selected official popup source.

The existing Base projector supplies target identity, warning, buttons and
static labels. This module runs the pinned XP2 OnShow body for its final visible
consequence text while replacing only presentation-only Base popup controls
with inert collectors. It does not infer or reimplement grievance rules.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from .configuration_profiles import XP2_CORE_SHA256
from .resource_resolution import resolve_path

BASE = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI")
POPUP = BASE / "Base/Assets/UI/Popups/DeclareWarPopup.lua"
POPUP_XML = POPUP.with_suffix('.xml')
XP1_POPUP = BASE / "DLC/Expansion1/UI/Replacements/DeclareWarPopup_Expansion1.lua"
XP2_POPUP = BASE / "DLC/Expansion2/UI/Replacements/DeclareWarPopup_Expansion2.lua"
XP1_MODINFO = BASE / "DLC/Expansion1/Expansion1.modinfo"
XP2_MODINFO = BASE / "DLC/Expansion2/Expansion2.modinfo"
BBG_MODINFO = Path(r"C:\Program Files (x86)\Steam\steamapps\workshop\content\289070\2865001760\BetterBalancedGame.modinfo")

PINS = {
    'base_popup': (POPUP, 'f95b880edb5ee6deb5244b0d82429d8541de93f3cf1c8840bf09fd4deaadd208'),
    'base_popup_xml': (POPUP_XML, '10cb7da15bb5aaa4bdebcbdbf228ea3f7c5884d987fa6efe040e53b809acdf20'),
    'xp1_popup': (XP1_POPUP, 'd49ec995d82fc01e636198286b2968d38caebe370dcdc51423cc24b722a2e2cb'),
    'xp2_popup': (XP2_POPUP, 'a58be51b1ff8a39b6380940d2944ea1d4a6e14c9818506d5ad80fd07fc91e53f'),
    'xp1_modinfo': (XP1_MODINFO, 'ed8e3ef9276d694f91e76fe8237361b457a0a6ee653cd506ca8dc4089e56db7d'),
    'xp2_modinfo': (XP2_MODINFO, 'b528a7c25f5977aed1ace8a54a0828025e061d880685d347c8bcf5ccd1473d87'),
    'bbg_modinfo': (BBG_MODINFO, 'f4f918bd18a7189d9f8ee64a4123952e72bded754e5154d7521d25f90bf305a5'),
}
SCHEMA = 'civ6-host.xp2-world-war-display.v1'
MAX_BYTES = 131072
MAX_TEXT_BYTES = 4096
PLAYER_MAX = 63
WAR_MAX = 0xffffffff
_DECL = re.compile(r'^(?:local\s+)?function\s+([A-Za-z_][A-Za-z_0-9]*)\s*\(')
_OVERLAY_REQUIRED = (
    'BASE_OnShow(eAttackingPlayer, kDefendingPlayers, eWarType, confirmCallbackFn);',
    'DiplomacyManager.TestAction(eFromPlayer, eDefendingPlayer, DiplomacyActionTypes.SET_WAR_STATE, kParams);',
    'local tmp = pAttacker:GetDiplomacy():ComputeDOWWarmongerPoints(eDefendingPlayer, kParams.WarState);',
    'iWarmongerPoints = math.max(tmp, iWarmongerPoints);',
    'Players[eDefendingPlayer]:IsMajor()',
    'Players[eDefendingMinor]:GetInfluence()',
    'local pMinorPlayerInfluence:table = Players[eDefendingMinor]:GetInfluence();',
    'pMinorPlayerInfluence:GetSuzerain()',
    'PlayerManager.GetAliveMajors()',
    'player:GetID()',
    'pMinorPlayerInfluence:GetTokensReceived(player:GetID())',
    'GlobalParameters.GRIEVANCES_SUZERAIN_CITY_STATE_DOW',
    'GlobalParameters.GRIEVANCES_HAVE_ENVOYS_CITY_STATE_DOW',
    'Locale.Lookup(szString, iWarmongerPoints)',
)


def _read_pin(name: str) -> bytes:
    path, expected = PINS[name]
    raw = resolve_path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError('Pinned official XP2 war source changed: ' + name)
    return raw


def _extract(raw: bytes, name: str) -> tuple[bytes, int, int]:
    lines = raw.decode('utf-8-sig').splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines)
              if re.match(r'^function\s+' + re.escape(name) + r'\s*\(', line)
              or re.match(r'^local\s+function\s+' + re.escape(name) + r'\s*\(', line)]
    if len(starts) != 1:
        raise RuntimeError('Official XP2 war popup function anchor changed: ' + name)
    first = starts[0]
    end = next((i for i in range(first + 1, len(lines))
                if _DECL.match(lines[i])), len(lines))
    selected = lines[first:end]
    while selected and (not selected[-1].strip()
                         or selected[-1].lstrip().startswith('--')):
        selected.pop()
    body = ''.join(selected).rstrip() + '\n'
    if not body.rstrip().endswith('end'):
        raise RuntimeError('Official XP2 war popup function is incomplete: ' + name)
    body = re.sub(r'^function\s+' + re.escape(name) + r'\s*\(',
                  'local function ' + name + '(', body, count=1)
    return body.encode('utf-8'), first + 1, first + len(selected)


def _replacement_rows(path: Path) -> list[tuple[str | None, str | None, str | None]]:
    root = ET.fromstring(resolve_path(path).read_bytes())
    rows = []
    for node in root.iter():
        if node.tag.split('}')[-1] != 'ReplaceUIScript':
            continue
        props = {child.tag.split('}')[-1]: (child.text or '').strip()
                 for child in node.iter() if child is not node}
        rows.append((props.get('LuaContext'), props.get('LuaReplace'),
                     node.attrib.get('criteria', node.attrib.get('Criteria'))))
    return rows


def _verify_selection() -> None:
    xp1 = _replacement_rows(XP1_MODINFO)
    xp2 = _replacement_rows(XP2_MODINFO)
    bbg = _replacement_rows(BBG_MODINFO)
    if ('DeclareWarPopup', 'UI/Replacements/DeclareWarPopup_Expansion1.lua', 'Expansion1') not in xp1:
        raise RuntimeError('Expansion1 no longer selects the pinned war-popup predecessor')
    if ('DeclareWarPopup', 'UI/Replacements/DeclareWarPopup_Expansion2.lua', 'Expansion2') not in xp2:
        raise RuntimeError('Expansion2 no longer selects the pinned XP2 war-popup overlay')
    if any(context in ('DeclareWarPopup', 'Civ6Common', 'WorldInput')
           for context, _, _ in bbg):
        raise RuntimeError('BBG now replaces a selected war-popup dependency')
    xp1_source = _read_pin('xp1_popup').decode('utf-8-sig')
    xp2_source = _read_pin('xp2_popup').decode('utf-8-sig')
    if 'include("DeclareWarPopup");' not in xp1_source:
        raise RuntimeError('XP1 war popup no longer includes Base')
    if 'include("DeclareWarPopup_Expansion1");' not in xp2_source:
        raise RuntimeError('XP2 war popup no longer includes XP1')
    declare, _, _ = _extract(xp1_source.encode('utf-8'), 'DeclareWar')
    declare_text = declare.decode('utf-8')
    if 'return BASE_DeclareWar(eAttackingPlayer, eDefendingPlayer, eWarType);' not in declare_text:
        raise RuntimeError('XP1 surprise-war fallback to Base changed')
    if 'WarTypes.SURPRISE_WAR' in declare_text:
        raise RuntimeError('XP1 now has a surprise-war-specific replacement')


def _overlay_source() -> tuple[bytes, int, int]:
    raw = _read_pin('xp2_popup')
    body, first, last = _extract(raw, 'OnShow')
    source = body.decode('utf-8')
    for expression in _OVERLAY_REQUIRED:
        if source.count(expression) < 1:
            raise RuntimeError('Official XP2 war consequence expression changed: ' + expression)
    # eFromPlayer is read as a global by the original source. It is not assigned
    # by this overlay; the runtime refuses a child where that global is non-nil.
    if re.search(r'\beFromPlayer\s*=', source):
        raise RuntimeError('XP2 war popup now assigns eFromPlayer; review source semantics')
    return body, first, last


def _base_module():
    from civ6_host.runtime.native import native_world_war_display as base
    return base


def verify_source() -> dict:
    """Verify the exact installed Base→XP1→XP2 popup selection and inputs."""
    files = {}
    for name, (path, expected) in PINS.items():
        raw = _read_pin(name)
        files[name] = {'path': str(resolve_path(path)), 'sha256': expected,
                       'bytes': len(raw)}
    _verify_selection()
    overlay, first, last = _overlay_source()
    base = _base_module()
    base_manifest = base.source_manifest()
    digest_parts = [b'civ6-host.xp2-world-war-display.v1\0']
    for name in PINS:
        digest_parts.append(name.encode('ascii') + b'\0' + bytes.fromhex(files[name]['sha256']))
    digest_parts.extend((base._projection_sha256().encode('ascii'),
                         overlay, b'\0eFromPlayer:unassigned-global-must-resolve-nil'))
    source_digest = hashlib.sha256(b'\0'.join(digest_parts)).hexdigest()
    return {
        'schema': 'civ6-host.xp2-world-war-display-source.v1',
        'core_sha256': XP2_CORE_SHA256,
        'files': files,
        'selected_popup_chain': [
            'Expansion1.modinfo: Expansion1_DeclareWarPopup',
            'Expansion2.modinfo: Expansion2_DeclareWarPopup',
            'DeclareWarPopup_Expansion2', 'DeclareWarPopup_Expansion1', 'DeclareWarPopup'],
        'xp2_onshow': {'first_line': first, 'last_line': last,
                       'sha256': hashlib.sha256(overlay).hexdigest()},
        'base_projection_source_sha256': base._projection_sha256(),
        'base_manifest': base_manifest,
        'source_sha256': source_digest,
        'selection': 'XP2 replaces XP1 which includes Base; BBG has no matching popup/common/world-input replacement',
        'e_from_player': 'The pinned Base and XP2 functions only read this global. This child projection asserts it resolves to nil and does not infer an attacker context.',
        'presentation_boundary': [
            'Base public fields come from the existing Base projector.',
            'The XP2 source body is executed for the final consequence string.',
            'BASE_OnShow and the consequence InstanceManager are inert collectors; no GameCore service is replaced.',
        ],
        'live_binding_boundary': {
            'runtime_callable_guards': ['DiplomacyManager.TestAction', 'Player.GetDiplomacy',
                'Diplomacy.ComputeDOWWarmongerPoints', 'Player.IsMajor', 'Player.GetInfluence',
                'Influence.GetSuzerain', 'PlayerManager.GetAliveMajors', 'Player.GetID',
                'Influence.GetTokensReceived', 'XP2 grievance GlobalParameters'],
            'source_static_only': ['Lua registration/callback body bytes for TestAction, ComputeDOWWarmongerPoints, GetSuzerain and XP2 grievance constants are pinned in the LAB v4 supplement; this module does not read/verify those GameCore bytes live. XP2 UI registration and Lua-callability are checked separately.'],
            'global_parameters_namespace': {
                'source_module': 'civ6_host.runtime.native.native_script_namespaces',
                'native_namespace_id': 2,
                'root_service': 'NativeScriptRuntime.bind_core_services binds the selected Core gameplay database before child registration.',
                'child_attachment': 'The retained XP2 UI child registers the existing GlobalParameters namespace once per runtime/child pair.',
                'conditional_use': 'The official XP2 OnShow reads grievance constants only when no major defender is present, and selects each constant in its original suzerain/envoy branch.',
            },
        },
    }


def source_dependencies(*, execution_image=None) -> dict[str, str]:
    manifest = verify_source()
    result = {row['path']: row['sha256'] for row in manifest['files'].values()}
    base = _base_module()
    for path in (Path(base.__file__).resolve(), Path(__file__).resolve()):
        result[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    # The XP2 UI binding and XP2 world-configuration service are part of the
    # existing owner pipeline and are pinned into its dependency closure.
    from . import xp2_ui_binding_source, xp2_world_configuration
    from .native import native_script_namespaces, native_script_runtime
    for module in (xp2_ui_binding_source, xp2_world_configuration,
                   native_script_namespaces, native_script_runtime):
        path = Path(module.__file__).resolve()
        result[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    result.update(xp2_ui_binding_source.source_dependencies())
    result.update(xp2_world_configuration.source_dependencies())
    from .runtime_source_dependencies import materialize_runtime_source_pins
    return materialize_runtime_source_pins(result,execution_image=execution_image)


def ensure_global_parameters_namespace(owner, backend, prefix, identity) -> None:
    """Attach the already-bound native database namespace to this retained UI child."""
    checked = owner._check()
    if (type(checked) not in (tuple, list) or len(checked) != 4
            or checked[0] is not backend or checked[2] is not prefix
            or checked[3] is not identity):
        raise RuntimeError('XP2 GlobalParameters attachment lost its saved owner identity')
    runtime = prefix.runtime
    child = prefix.ui_child
    if (runtime is None or child is None or prefix.backend is not backend
            or prefix.core is not backend.core or prefix.host is not backend.host
            or getattr(runtime, 'database_bound', False) is not True
            or getattr(runtime, 'service_owner', None) is not prefix.host
            or getattr(prefix, 'closed', True) is not False
            or getattr(prefix, 'quarantined', True) is not False):
        raise RuntimeError('XP2 GlobalParameters requires the retained Core gameplay database and UI child')
    runtime.registry.validate(child)
    current = (backend, runtime, child, identity)
    prior = getattr(prefix, '_war_global_parameters_binding', None)
    if prior is not None:
        if not all(prior[index] is value for index, value in enumerate(current)):
            raise RuntimeError('XP2 GlobalParameters UI child was replaced or rebound')
        return
    runtime.namespaces.register(child, 'GlobalParameters')
    checked = owner._check()
    if (checked[0] is not backend or checked[2] is not prefix or checked[3] is not identity
            or prefix.runtime is not runtime or prefix.ui_child is not child):
        raise RuntimeError('XP2 GlobalParameters attachment crossed its owner or child lifetime')
    runtime.registry.validate(child)
    prefix._war_global_parameters_binding = current


def _int(value, name: str, maximum: int) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError('invalid ' + name)
    return value


def _war_int(value) -> int:
    if type(value) is not int or not -(1 << 31) <= value <= WAR_MAX:
        raise ValueError('invalid war type')
    return value


def _lua_quote(value: str) -> bytes:
    if type(value) is not str or '\x00' in value or len(value.encode('utf-8')) > MAX_TEXT_BYTES:
        raise ValueError('invalid public war text')
    return ('"' + ''.join('\\%03d' % b for b in value.encode('utf-8')) + '"').encode('ascii')


def display_source(player_id, turn, defender_ids, war_type, configuration) -> bytes:
    """Build a Lua chunk that joins the Base display projection and XP2 overlay."""
    manifest = verify_source()
    pid = _int(player_id, 'player ID', PLAYER_MAX)
    expected_turn = _int(turn, 'turn', WAR_MAX)
    war = _war_int(war_type)
    if type(defender_ids) not in (list, tuple) or not defender_ids or len(defender_ids) > 64:
        raise ValueError('expected a bounded nonempty defender list')
    defenders = [_int(value, 'defender player ID', PLAYER_MAX) for value in defender_ids]
    if pid in defenders or len(set(defenders)) != len(defenders):
        raise ValueError('invalid or repeated war target')
    # The root-owned XP2 configuration reader returns the same narrow data
    # shape as the Base projector. Reuse only its pure Lua serializer here.
    from . import xp2_world_configuration
    from civ6_host.runtime.native import native_world_war_display as base
    configuration_lua = xp2_world_configuration.lua_bindings(configuration)
    base_source = base.display_source(pid, expected_turn, defenders, war, configuration)
    if not base_source.startswith(configuration_lua):
        raise RuntimeError('Base popup projection no longer uses the shared XP2 configuration serializer')
    overlay, _, _ = _overlay_source()
    # Only popup presentation work is stubbed. The actual XP2 body, its math,
    # GameCore methods, enums, grievance constants and localization are intact.
    setup = (
        b'local pid,expectedTurn,warType=' + b','.join(str(v).encode('ascii') for v in (pid, expected_turn, war)) +
        b'\nlocal defenders={' + b','.join(str(v).encode('ascii') for v in defenders) + b'}\n' +
        b'local sourceDigest=' + _lua_quote(manifest['source_sha256']) + b'\n' +
        b'local function runBase()\n' + base_source + b'\nend\nlocal baseRaw=runBase()\n' +
        b'local capturedConsequence=nil\n'
        b'local Controls={WarmongerStack={}}\n'
        b'local g_ConsequenceItemIM={ResetInstances=function() end, GetInstance=function(_,stack) '
        b'assert(stack==Controls.WarmongerStack); return {Text={SetText=function(_,value) '
        b'assert(type(value)=="string"); capturedConsequence=value end}} end}\n'
        b'local BASE_OnShow=function() end\n'
        b'assert(eFromPlayer==nil,"XP2 popup eFromPlayer global is not nil")\n'
    )
    invocation = b'\nassert(Game and Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==expectedTurn, "war display perspective or turn changed")\n'
    invocation += (b'assert(DiplomacyManager and type(DiplomacyManager.TestAction)=="function" and '
        b'Players, '
        b'"XP2 war display services unavailable")\n'
        b'local sourceAttacker=assert(Players[pid],"XP2 war attacker unavailable")\n'
        b'assert(type(sourceAttacker.GetDiplomacy)=="function" and '
        b'type(sourceAttacker:GetDiplomacy().ComputeDOWWarmongerPoints)=="function", "XP2 diplomacy display unavailable")\n'
        b'local majorDefenderFound=false; local lastMinor=nil\n'
        b'for _,id in ipairs(defenders) do local target=assert(Players[id],"XP2 war target unavailable"); '
        b'assert(type(target.IsMajor)=="function", "XP2 major/minor API unavailable"); '
        b'if target:IsMajor() then majorDefenderFound=true else lastMinor=target end end\n'
        b'if not majorDefenderFound then local influence=assert(lastMinor:GetInfluence(),"XP2 target influence unavailable"); '
        b'assert(type(influence.GetSuzerain)=="function", "XP2 city-state suzerain API unavailable"); '
        b'local suzerain=influence:GetSuzerain(); if suzerain==pid or suzerain==-1 then '
        b'assert(type(PlayerManager.GetAliveMajors)=="function", "XP2 alive-major API unavailable"); '
        b'for _,player in ipairs(PlayerManager.GetAliveMajors()) do if player:GetID()~=pid then '
        b'assert(type(influence.GetTokensReceived)=="function", "XP2 envoy API unavailable") end end end end\n')
    invocation += (
        b'local xp2Ok,xp2Error=pcall(xp2OnShow,pid,defenders,warType,nil)\n'
        b'if not xp2Ok then local message=tostring(xp2Error); '
        b'if string.find(message,"GlobalParameters",1,true) then '
        b'error("XP2 city-state grievance requires the native GlobalParameters namespace") end; '
        b'error(xp2Error) end\n'
        b'assert(type(capturedConsequence)=="string" and #capturedConsequence<=4096,"XP2 consequence text unavailable")\n')
    quote = (
        b'local function quote(s) local out={"\\\""}; for i=1,#s do local n=string.byte(s,i); '
        b'local c=string.sub(s,i,i); if n==34 or n==92 then out[#out+1]=string.char(92)..c '
        b'elseif n<32 then out[#out+1]=string.char(92).."u"..string.format("%04x",n) '
        b'else out[#out+1]=c end end; out[#out+1]="\\\""; return table.concat(out) end\n'
    )
    # Firaxis UI Lua carries type annotations in declarations; the owned Lua
    # 5.1 child accepts the same source after removing declaration-only types.
    declaration, separator, remainder = overlay.partition(b'\n')
    if not declaration.startswith(b'local function OnShow('):
        raise RuntimeError('XP2 overlay function declaration changed')
    declaration = re.sub(rb'\s*:\s*[A-Za-z_][A-Za-z_0-9]*(?=[,)])', b'', declaration)
    overlay = declaration + separator + remainder
    overlay, count = re.subn(rb'(?m)^(\s*local\s+pMinorPlayerInfluence)\s*:\s*table\b',
                             rb'\1', overlay, count=1)
    if count != 1:
        raise RuntimeError('XP2 overlay local type annotation changed')
    result = (setup + overlay.replace(b'local function OnShow(', b'local function xp2OnShow(', 1)
              + invocation + quote +
              b'return "{\\"schema\\":\\"civ6-host.xp2-world-war-display-envelope.v1\\",\\"source_sha256\\":"..quote(sourceDigest)..",\\"base_raw\\":"..quote(baseRaw)..",\\"consequences\\":"..quote(capturedConsequence).."}"\n')
    if len(result) > MAX_BYTES:
        raise ValueError('XP2 war display source exceeds bound')
    return result


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate XP2 display key')
        result[key] = value
    return result


def _text(value, name: str) -> str:
    try:
        encoded = value.encode('utf-8') if type(value) is str else b''
    except UnicodeEncodeError as exc:
        raise ValueError('malformed displayed ' + name) from exc
    if type(value) is not str or '\x00' in value or len(encoded) > MAX_TEXT_BYTES:
        raise ValueError('malformed displayed ' + name)
    return value


def parse_display(raw, player_id, turn, defender_ids, war_type) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= MAX_BYTES:
        raise ValueError('invalid XP2 war display response size')
    pid = _int(player_id, 'player ID', PLAYER_MAX)
    expected_turn = _int(turn, 'turn', WAR_MAX)
    war = _war_int(war_type)
    if type(defender_ids) not in (list, tuple) or not defender_ids or len(defender_ids) > 64:
        raise ValueError('invalid XP2 war display target list')
    defenders = [_int(value, 'defender player ID', PLAYER_MAX) for value in defender_ids]
    if pid in defenders or len(set(defenders)) != len(defenders):
        raise ValueError('invalid XP2 war display targets')
    expected_source = verify_source()['source_sha256']
    try:
        envelope = json.loads(raw.decode('utf-8'), object_pairs_hook=_json_object,
                              parse_constant=lambda value: (_ for _ in ()).throw(ValueError('non-finite JSON')))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('malformed XP2 war display JSON') from exc
    if (type(envelope) is not dict or set(envelope) !=
            {'schema', 'source_sha256', 'base_raw', 'consequences'}
            or envelope['schema'] != 'civ6-host.xp2-world-war-display-envelope.v1'
            or envelope['source_sha256'] != expected_source):
        raise ValueError('XP2 war display envelope or source mismatch')
    consequences = _text(envelope['consequences'], 'XP2 consequence')
    try:
        base_raw = envelope['base_raw'].encode('utf-8') if type(envelope['base_raw']) is str else b''
    except UnicodeEncodeError as exc:
        raise ValueError('invalid XP2 Base display envelope') from exc
    if not base_raw or len(base_raw) > _base_module().MAX_BYTES:
        raise ValueError('invalid XP2 Base display envelope')
    base = _base_module()
    base_display = base.parse_display(base_raw, pid,
                                      expected_turn, defenders, war)
    result = {
        'schema': SCHEMA,
        'player_id': pid,
        'turn': expected_turn,
        'defender_player_ids': defenders,
        'war_type': war,
        'targets': base_display['targets'],
        'message': base_display['message'],
        'consequences': consequences,
        'buttons': base_display['buttons'],
        'static_text': base_display['static_text'],
        'source_sha256': expected_source,
    }
    from civ6_host.contracts.xp2_war_confirmation import parse_display as parse_public_display
    encoded = json.dumps(result, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return parse_public_display(encoded, pid, expected_turn, defenders, war,
                                expected_source_sha256=expected_source)


def read(owner, observation: dict, prompt: dict) -> dict:
    """Read one XP2 popup projection through the retained owner/UI child."""
    from civ6_host.runtime.native.native_player_observation import observe_player
    from .saved_load_job_observer import require_quiescent
    from . import xp2_world_configuration
    if type(observation) is not dict or type(observation.get('player_id')) is not int or type(observation.get('turn')) is not int:
        raise ValueError('invalid public observation for XP2 war display')
    pid = _int(observation['player_id'], 'player ID', PLAYER_MAX)
    turn = _int(observation['turn'], 'turn', WAR_MAX)
    if (type(prompt) is not dict or set(prompt) !=
            {'attacking_player', 'defending_player', 'war_type'}
            or type(prompt['attacking_player']) is not int
            or prompt['attacking_player'] != pid):
        raise ValueError('invalid public XP2 war prompt identity')
    defender = _int(prompt['defending_player'], 'defender player ID', PLAYER_MAX)
    war = _war_int(prompt['war_type'])
    if defender == pid:
        raise ValueError('XP2 war prompt targets the attacking player')
    backend, _, prefix, identity = owner._check()
    if backend.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('XP2 war display refuses a non-XP2 core')
    if prefix.ui_child is None or prefix.runtime.registry.validate(prefix.ui_child) is None:
        raise RuntimeError('XP2 war display requires the retained owned UI child')
    owner.control(empty=True)
    before_jobs = backend.jobs.query_snapshot(owner.saved,'before')
    require_quiescent(before_jobs)
    if prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('XP2 war display read requires empty native transports')
    ensure_global_parameters_namespace(owner, backend, prefix, identity)
    if observe_player(prefix.runtime, prefix.ui_child, pid) != observation:
        raise RuntimeError('XP2 war display read crossed the public observation boundary')
    configuration = xp2_world_configuration.read(backend, [defender])
    raw = prefix.runtime.evaluate_text(
        prefix.ui_child, display_source(pid, turn, [defender], war, configuration),
        b'@xp2_official_world_war_display', capacity=MAX_BYTES + 1)
    result = parse_display(raw, pid, turn, [defender], war)
    owner.control(empty=True)
    after_jobs = backend.jobs.query_snapshot(owner.saved,'after')
    require_quiescent(after_jobs)
    if prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('XP2 war display read left native transports pending')
    if after_jobs != before_jobs or observe_player(prefix.runtime, prefix.ui_child, pid) != observation:
        raise RuntimeError('XP2 war display changed scheduler or public observation')
    backend.emit('xp2_official_world_war_display', display=result,
               public_observation_unchanged=True, scheduler_unchanged=True,
               native_commands=0, display_payload_contains_private_metadata=False,
               eligible_for_training=False)
    return result
