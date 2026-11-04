"""Read the native completion Boolean for an already witnessed placement.

This is a player-scoped diagnostic readback, not a construction rule or a
learner observation. Placement, queue progress and inspiration notifications
are never used as substitutes for CityDistricts:IsComplete.
"""
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _PLACEMENT_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_production_placement import _validate_choice
from civ6_host.runtime.native.native_production_placement import _selection_source
from civ6_host.runtime.native.native_production_catalog import _uint
from civ6_host.runtime.native.native_production_catalog import _token
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_district_completion.py')))).resolve().parents[1]
PROOF_SHA256 = '99cff7f864ee6e6c0a7beabbf9934307687ff59bd2eafdde0fef3ca6bd5a3510'

def verify_source(*, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    if core_sha256 != _PLACEMENT_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_production_placement_profile import verify_source as selected_source
        return selected_source(core_sha256)
    proof = load_pinned_json(ROOT / 'evidence/native-district-completion' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_district_completion.static.v1' or proof['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof['registrations']['CityDistricts']['IsComplete']['callback_va'] != '0x180516080' or (proof['registrations']['Cities']['GetPlotPurchaseCity']['callback_va'] != '0x18050e9b0'):
        raise RuntimeError('Native district completion source identity changed')
    return proof

def _checked_choice(choice, expected_turn):
    _validate_choice(choice)
    _uint(expected_turn, 'completion turn')
    if choice['kind'] != 'district' or choice['mode'] != 'place':
        raise ValueError('Completion readback requires a witnessed district placement')
    if expected_turn < choice['current_game_turn']:
        raise ValueError('Completion readback predates placement')
    return {**choice, 'current_game_turn': expected_turn}

def readback_source(choice, expected_turn, *, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    """Read a fresh native cached city within one protected Lua evaluation."""
    verify_source(core_sha256=core_sha256)
    current = _checked_choice(choice, expected_turn)
    return _selection_source(current, core_sha256=core_sha256) + f"local expectedX,expectedY={choice['x']},{choice['y']}\n".encode('ascii') + "\nassert(type(visibility.IsVisible)=='function','district visibility API unavailable')\nlocal visible=visibility:IsVisible(expectedX,expectedY)\nassert(type(visible)=='boolean' and visible,'district completion target is not visible')\n-- No live plot getter precedes the requested player's visibility predicate.\nlocal x,y,plot=plotCoordinates(plotID)\nassert(x==expectedX and y==expectedY,'district completion coordinates changed')\nlocal owner=uint(plot:GetOwner(),'district plot owner',63)\nlocal nativeType=uint(plot:GetDistrictType(),'district plot type',2147483647)\nlocal districtID=uint(plot:GetDistrictID(),'district ID',4294967295)\nassert(owner==pid and nativeType==index,'district completion identity changed')\nassert(Cities and type(Cities.GetPlotPurchaseCity)=='function','plot purchase city API unavailable')\nlocal purchaseCity=Cities.GetPlotPurchaseCity(plot)\nassert(purchaseCity and type(purchaseCity.GetID)=='function' and\n type(purchaseCity.GetOwner)=='function','district owning city unavailable')\nlocal purchaseID=uint(purchaseCity:GetID(),'purchase city ID',4294967295)\nlocal purchaseOwner=uint(purchaseCity:GetOwner(),'purchase city owner',63)\nassert(purchaseID==cityID and purchaseOwner==pid,'district plot belongs to another city')\nlocal districts=city:GetDistricts()\nassert(districts and type(districts.IsComplete)=='function','native district completion API unavailable')\nlocal completed=districts:IsComplete(nativeType,plotID)\nassert(type(completed)=='boolean','invalid native district completion Boolean')\nready()\nassert(city:GetID()==cityID and city:GetOwner()==pid,'district city changed during readback')\nreturn table.concat({'district-completion-v1',n(pid),n(cityID),n(expectedTurn),n(index),n(hash),\n n(plotID),n(x),n(y),n(districtID),n(nativeType),n(owner),n(purchaseID),n(purchaseOwner),\n completed and '1' or '0'},'|')\n".encode('ascii')

def parse_readback(payload, choice, expected_turn):
    _checked_choice(choice, expected_turn)
    if type(payload) is not bytes or len(payload) > 1024:
        raise ValueError('Invalid district completion payload')
    tokens = payload.split(b'|')
    if len(tokens) != 15 or tokens[0] != b'district-completion-v1':
        raise ValueError('Invalid district completion protocol')
    expected = [choice[k] for k in ('player_id', 'city_id')] + [expected_turn] + [choice[k] for k in ('index', 'hash', 'plot_id', 'x', 'y')]
    if tokens[1:9] != [str(v).encode('ascii') for v in expected]:
        raise ValueError('District completion is foreign or stale')
    district_id = _token(tokens[9], 'district ID')
    identities = [choice['index'], choice['player_id'], choice['city_id'], choice['player_id']]
    if tokens[10:14] != [str(v).encode('ascii') for v in identities] or tokens[14] not in (b'0', b'1'):
        raise ValueError('District completion plot/city identity or Boolean mismatch')
    return dict(player_id=choice['player_id'], city_id=choice['city_id'], turn=expected_turn, placement_turn=choice['current_game_turn'], item_index=choice['index'], item_hash=choice['hash'], plot_id=choice['plot_id'], x=choice['x'], y=choice['y'], district_id=district_id, plot_type=choice['index'], plot_owner=choice['player_id'], purchase_city_id=choice['city_id'], purchase_city_owner=choice['player_id'], native_is_complete=tokens[14] == b'1', completion_source='CityDistricts:IsComplete(type,plotID)', district_collection_membership_independently_enumerated=False, visible_to_player=True, exposed_to_learner=False, eligible_for_training=False)

def guard_case():
    from civ6_host.runtime.native.native_district_completion_guards import guard_case as build
    return build()
