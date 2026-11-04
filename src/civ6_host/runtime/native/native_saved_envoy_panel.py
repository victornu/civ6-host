"""Voluntary City States panel review, separate from an obligatory envoy prompt."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
from pathlib import Path
from civ6_host.runtime.native import native_envoy_actions as native
from civ6_host.runtime.native import native_saved_envoys as envoys
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_player_observation import observe_player
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_envoy_panel.py')))).resolve().parents[1]
PROOF = ROOT / 'work/envoy-panel957/source.json'
PROOF_SHA256 = '91d8f0e8563cc79ad8ab86c4ef3cb3adc80c456406340dc909ad62edf052af35'
FIELDS = {'kind'}

def verify_source():
    d = load_pinned_json(PROOF, PROOF_SHA256)
    if d['schema'] != 'civ6rl.envoy_panel957.source.v1' or d['core_sha256'] != native.CORE_SHA256 or d['native_parent']['sha256'] != native.PROOF_SHA256 or (d['contract']['requires_envoy_blocker'] is not False) or (d['contract']['setter'] != 'PlayerInfluence.SetGivingTokensConsidered(true)'):
        raise RuntimeError('Envoy panel source contract changed')
    for r in d['official_sources']:
        if hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(r['path']))).read_bytes()).hexdigest() != r['sha256']:
            raise RuntimeError('Official envoy panel source changed')
    return d
ACCESS_LUA = b"\nassert(GameInfo and GameInfo.GameCapabilities,'native capabilities unavailable')\nlocal panelCapability=GameInfo.GameCapabilities['CAPABILITY_CITY_STATES_VIEW']~=nil\nlocal panelContact=false\nlocal minors=PlayerManager.GetAliveMinors()\nassert(type(minors)=='table' and #minors<=64,'invalid native minor list')\nlocal diplomacy=p:GetDiplomacy()\nassert(diplomacy,'native diplomacy unavailable')\nlocal seen={}\nfor _,minor in ipairs(minors) do\n local id=integer(minor:GetID(),63)\n assert(id~=pid and not seen[id],'duplicate or own minor');seen[id]=true\n if boolean(diplomacy:HasMet(id)) then panelContact=true end\nend\nlocal panelAvailable=panelCapability and panelContact\ncontext()\n"

def validate_catalog(value, turn, *, player_id=0):
    native._context(player_id, turn)
    if type(value) is not dict or set(value) != {'player_id', 'turn', 'capability', 'met_alive_minor', 'available'} or type(value['player_id']) is not int or (value['player_id'] != player_id) or (type(value['turn']) is not int) or (value['turn'] != turn) or any((type(value[k]) is not bool for k in ('capability', 'met_alive_minor', 'available'))) or (value['available'] != (value['capability'] and value['met_alive_minor'])):
        raise ValueError('Malformed envoy panel access')
    return value

def catalog(prefix, turn, *, player_id=0):
    verify_source()
    native.verify_source()
    source = native._common(player_id, turn) + ACCESS_LUA + b"return table.concat({'panel',dec(pid),dec(expectedTurn),bit(panelCapability),bit(panelContact),bit(panelAvailable)},'|')"
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source, b'@explicit_envoy_panel_access', capacity=129)
    if type(raw) is not bytes or len(raw) > 128:
        raise ValueError('Malformed envoy panel wire')
    parts = raw.split(b'|')
    if len(parts) != 6 or parts[:3] != [b'panel', str(player_id).encode(), str(turn).encode()] or any((v not in (b'0', b'1') for v in parts[3:])):
        raise ValueError('Foreign envoy panel access')
    return validate_catalog(dict(player_id=player_id, turn=turn, capability=parts[3] == b'1', met_alive_minor=parts[4] == b'1', available=parts[5] == b'1'), turn, player_id=player_id)

def actions(panel, influence):
    return [dict(kind='review_envoys')] if panel['available'] and (not influence['considered']) and (not influence['giving_tokens_blocker_present']) else []

def apply(owner, prefix, action, turn, before, *, player_id=0):
    if type(action) is not dict or action != {'kind': 'review_envoys'}:
        raise ValueError('Malformed envoy panel choice')
    panel = catalog(prefix, turn, player_id=player_id)
    fresh = envoys.catalog(prefix, turn, player_id=player_id)
    if panel != getattr(owner, 'explicit_envoy_panel', None) or fresh != getattr(owner, 'explicit_envoys', None) or action not in actions(panel, fresh):
        raise RuntimeError('Envoy panel choice is stale or unavailable')
    receipt = prefix.inspect_envoy_choice(player_id, review=True)
    after_influence = envoys.catalog(prefix, turn, player_id=player_id)
    expected = native.verify_considered_effect(fresh, after_influence, require_blocker=False)
    if receipt != expected:
        raise RuntimeError('Envoy panel receipt differs from native effect')
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    if after != before:
        raise RuntimeError('Envoy panel review changed player gameplay observation')
    owner.emit('official_explicit_envoy_panel_effect', action=action, panel=panel, before=fresh, after=after_influence, receipt=receipt, observation_before=before, observation_after=after, source_proof_sha256=PROOF_SHA256, automatic_choices_applied=False, strategic_training_ready=False)
    return after
