"""Verify an already selected wonder placement through native plot/city APIs.

This is a readback only. A placed wonder plot is not reported complete unless
the owning city's native HasBuilding query confirms the same building index.
"""
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _PLACEMENT_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_production_catalog import _uint
from civ6_host.runtime.native.native_production_catalog import _token
from civ6_host.runtime.native.native_production_placement import _selection_source
from civ6_host.runtime.native.native_production_placement import _validate_choice
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_wonder_completion.py')))).resolve().parents[1]
PROOF_SHA256 = '9a5af5a2acf89d4bc8702b36a9b0da0898b52eb0189880b911d05022f96822f0'
ABSENCE_PROOF_SHA256 = '20eb225628f00ba613d3ff9fa19923de83b239ec521261000c74d2ddbfbb31e6'

def verify_source(*, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    if core_sha256 != _PLACEMENT_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_production_placement_profile import verify_source as selected_source
        return selected_source(core_sha256)
    proof = load_pinned_json(ROOT / 'evidence/native-wonder-completion' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_wonder_completion.static.v1' or proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof['registrations']['Plot.GetWonderType']['callback_va'] != '0x18001b5b0') or (proof['registrations']['CityBuildings.HasBuilding']['callback_va'] != '0x180514de0') or (proof['registrations']['Cities.GetPlotPurchaseCity']['callback_va'] != '0x18050e9b0'):
        raise RuntimeError('Native wonder completion source identity changed')
    return proof

def verify_absence_source(*, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    """Keep the no-wonder sentinel contract separate from completion evidence."""
    if core_sha256 != _PLACEMENT_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_production_placement_profile import verify_source as selected_source
        return selected_source(core_sha256)
    proof = load_pinned_json(ROOT / 'evidence/native-wonder-absence' / (ABSENCE_PROOF_SHA256 + '.json'), ABSENCE_PROOF_SHA256)
    contract = proof['contract']
    branch = contract['admitted_readback']
    if proof.get('schema') != 'civ6rl.native_wonder_absence.static.v1' or proof['images']['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof['parents']['wonder_completion']['sha256'] != PROOF_SHA256 or (contract['no_wonder_sentinel'] != -1) or (contract['has_building_independent_of_plot'] is not True) or (contract['has_building_argument'] != 'selected-current-GameInfo.Buildings.Index') or (branch['negative_branch_expected_native_has_building'] is not False) or (branch['independent_city_membership_query_required'] is not True) or (contract['gameplay_mutation_performed'] is not False):
        raise RuntimeError('Native wonder absence source identity changed')
    return proof

def _checked_choice(choice, expected_turn):
    _validate_choice(choice)
    _uint(expected_turn, 'wonder readback turn')
    if choice['kind'] != 'building' or choice['mode'] != 'place':
        raise ValueError('Wonder readback requires a placed building choice')
    if expected_turn < choice['current_game_turn']:
        raise ValueError('Wonder readback predates placement')
    return choice

def readback_source(choice, expected_turn, *, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    """Read plot identity and native city membership in one protected Lua call."""
    verify_source(core_sha256=core_sha256)
    verify_absence_source(core_sha256=core_sha256)
    choice = _checked_choice(choice, expected_turn)
    selected_context = {**choice, 'current_game_turn': _uint(expected_turn, 'turn')}
    source = _selection_source(selected_context, core_sha256=core_sha256)
    source += f"local readbackTurn={_uint(expected_turn, 'turn')}\nlocal expectedX,expectedY={choice['x']},{choice['y']}\nlocal expectedPlotID={choice['plot_id']}\n".encode('ascii')
    source += "\nassert(kind=='building' and flag(row.IsWonder,'building IsWonder') and row.IsWonder==true,\n       'selected production row is not a native wonder')\nassert(type(plotID)=='number' and plotID>=0 and plotID==expectedPlotID,\n       'wonder placement requires the selected plot')\nassert(type(visibility.IsVisible)=='function' and type(visibility.IsRevealed)=='function',\n       'wonder plot visibility API unavailable')\nlocal visible=visibility:IsVisible(expectedX,expectedY)\nassert(type(visible)=='boolean' and visible,'wonder plot is not visible')\nlocal revealed=visibility:IsRevealed(plotID)\nassert(type(revealed)=='boolean' and revealed,'wonder plot is not revealed')\n-- Only now may the live Plot userdata and its fields be read.\nlocal plot=Map.GetPlotByIndex(plotID)\nassert(plot and type(plot.GetIndex)=='function','wonder plot is unavailable')\nlocal actualIndex=uint(plot:GetIndex(),'wonder plot index',width*height-1)\nlocal actualX=uint(plot:GetX(),'wonder plot X',width-1)\nlocal actualY=uint(plot:GetY(),'wonder plot Y',height-1)\nassert(actualIndex==plotID and actualX==expectedX and actualY==expectedY and\n       actualY*width+actualX==plotID,'wonder placement coordinates changed')\nlocal owner=uint(plot:GetOwner(),'wonder plot owner',63)\nassert(owner==pid,'wonder plot belongs to another player')\nlocal wonderType=plot:GetWonderType()\nassert(type(wonderType)=='number' and wonderType%1==0 and\n       (wonderType==-1 or wonderType==index),\n       'native wonder plot type does not match selected building index')\nassert(Cities and type(Cities.GetPlotPurchaseCity)=='function',\n       'native plot purchase-city API unavailable')\nlocal purchaseCity=Cities.GetPlotPurchaseCity(plot)\nassert(purchaseCity and type(purchaseCity.GetID)=='function' and\n       type(purchaseCity.GetOwner)=='function','wonder purchase city unavailable')\nlocal purchaseID=uint(purchaseCity:GetID(),'wonder purchase city ID',4294967295)\nlocal purchaseOwner=uint(purchaseCity:GetOwner(),'wonder purchase city owner',63)\nassert(purchaseID==cityID and purchaseOwner==pid,\n       'wonder plot is not owned by the selected city')\nlocal buildings=city:GetBuildings()\nassert(buildings and type(buildings.HasBuilding)=='function',\n       'native city building membership API unavailable')\n-- The official PlotToolTip passes GetWonderType() (the native plot type index)\n-- directly to HasBuilding. This is intentionally not row.Hash.\nlocal hasBuilding\nif wonderType==-1 then\n  -- The placement may have disappeared. Read membership of the selected\n  -- building independently; never pass the no-wonder sentinel as a type.\n  hasBuilding=buildings:HasBuilding(index)\nelse\n  hasBuilding=buildings:HasBuilding(wonderType)\nend\nassert(type(hasBuilding)=='boolean','invalid native HasBuilding Boolean')\nassert(wonderType~=-1 or hasBuilding==false,\n       'absent wonder plot conflicts with selected city building membership')\nready()\nassert(city:GetOwner()==pid and city:GetID()==cityID,\n       'wonder readback city changed during query')\nlocal protocol=wonderType==-1 and 'wonder-absence-v1' or 'wonder-completion-v1'\nreturn table.concat({protocol,n(pid),n(cityID),n(readbackTurn),n(index),n(hash),\n n(plotID),n(actualX),n(actualY),n(owner),n(purchaseID),n(purchaseOwner),n(wonderType),\n hasBuilding and '1' or '0'},'|')\n".encode('ascii')
    return source

def parse_readback(payload, choice, expected_turn):
    _checked_choice(choice, expected_turn)
    expected_turn = _uint(expected_turn, 'wonder readback turn')
    if type(payload) is not bytes or len(payload) > 1024:
        raise ValueError('Invalid wonder completion payload')
    tokens = payload.split(b'|')
    if len(tokens) != 14 or tokens[0] not in (b'wonder-completion-v1', b'wonder-absence-v1'):
        raise ValueError('Invalid wonder completion protocol')
    absent = tokens[0] == b'wonder-absence-v1'
    values = [choice[k] for k in ('player_id', 'city_id')]
    values += [expected_turn] + [choice[k] for k in ('index', 'hash', 'plot_id', 'x', 'y')]
    if tokens[1:9] != [str(v).encode('ascii') for v in values]:
        raise ValueError('Foreign or stale wonder readback')
    actuals = [_token(tokens[9], 'plot owner', 63), _token(tokens[10], 'purchase city ID'), _token(tokens[11], 'purchase city owner', 63), -1 if absent and tokens[12] == b'-1' else _token(tokens[12], 'native wonder type', 2147483647)]
    expected_actuals = [choice['player_id'], choice['city_id'], choice['player_id'], -1 if absent else choice['index']]
    if actuals != expected_actuals or tokens[13] not in (b'0', b'1'):
        raise ValueError('Wonder plot/city identity or completion Boolean mismatch')
    if absent and tokens[13] != b'0':
        raise ValueError('Absent wonder conflicts with city building membership')
    result = dict(player_id=choice['player_id'], city_id=choice['city_id'], turn=expected_turn, placement_turn=choice['current_game_turn'], item_type=choice['item_type'], item_index=choice['index'], item_hash=choice['hash'], plot_id=choice['plot_id'], x=choice['x'], y=choice['y'], plot_owner=actuals[0], purchase_city_id=actuals[1], purchase_city_owner=actuals[2], native_wonder_type=actuals[3], city_has_building=tokens[13] == b'1', completion_source='CityBuildings:HasBuilding(Plot:GetWonderType())', placement_and_city_identity_verified=True, exposed_to_learner=False, eligible_for_training=False)
    if absent:
        result.update(completion_source='CityBuildings:HasBuilding(selected GameInfo Buildings.Index)', placement_and_city_identity_verified=False, plot_and_city_identity_verified=True, wonder_absent=True, cause='not_inferred')
    return result

def guard_case():
    from civ6_host.runtime.native import native_production_placement as placement
    catalog_payload = b'placement-v1|0|65536|60|catalog|1|7|12|90|13|14|16|17|18|31|74|46|1|building:BUILDING_HANGING_GARDENS:49:3540715778:place:1251:67:16'
    catalog = placement.parse_catalog(catalog_payload, 0, 65536, 60)
    choice = placement.choose(catalog, 'building', 49, 1251)
    source = readback_source(choice, 61).decode('ascii')
    return ("local localID,observer,turn=0,0,61\nlocal cityOwner,cityID,plotOwner,purchaseOwner,purchaseID=0,65536,0,0,65536\nlocal visible,revealed=true,true\nlocal wonderType,hasBuilding=49,true\nlocal plotReads,plotFieldReads,hasBuildingCalls=0,0,0\nlocal row={BuildingType='BUILDING_HANGING_GARDENS',Index=49,Hash=-754251518,IsWonder=true,RequiresPlacement=true}\nlocal buildings={HasBuilding=function(_,value)\n hasBuildingCalls=hasBuildingCalls+1;assert(value==49,'HasBuilding must receive the plot type index');return hasBuilding end}\nlocal function unusedProductionAPI() error('wonder readback invoked a production API') end\nlocal queue={GetSize=function() return 1 end,CanProduce=unusedProductionAPI,\n HasBeenPlaced=unusedProductionAPI}\nlocal CityManager={CanStartOperation=unusedProductionAPI,RequestOperation=unusedProductionAPI,\n GetOperationTargets=unusedProductionAPI}\nlocal city={GetID=function() return cityID end,GetOwner=function() return cityOwner end,\n GetBuildQueue=function() return queue end,GetBuildings=function() return buildings end}\nlocal player={IsAlive=function() return true end,IsTurnActive=function() return true end,\n IsTurnActiveComplete=function() return true end,\n GetCities=function() return {Members=function() local once=false;return function()\n  if not once then once=true;return 1,city end end end} end}\nlocal GameInfo={Buildings={BUILDING_HANGING_GARDENS=row,[49]=row},Units={},Projects={},Districts={}}\nlocal Game={GetLocalPlayer=function() return localID end,\n GetLocalObserver=function() return observer end,GetCurrentGameTurn=function() return turn end}\nlocal Players={[0]=player}\nlocal PlayersVisibility={[0]={\n IsVisible=function(_,x,y) assert(x==67 and y==16);return visible end,\n IsRevealed=function(_,id) assert(id==1251);return revealed end}}\nlocal plot={GetIndex=function() plotFieldReads=plotFieldReads+1;return 1251 end,\n GetX=function() plotFieldReads=plotFieldReads+1;return 67 end,\n GetY=function() plotFieldReads=plotFieldReads+1;return 16 end,\n GetOwner=function() plotFieldReads=plotFieldReads+1;return plotOwner end,\n GetWonderType=function() plotFieldReads=plotFieldReads+1;return wonderType end}\nlocal Map={GetGridSize=function() return 74,46 end,GetPlotCount=function() return 3404 end,\n GetPlotByIndex=function(id) plotReads=plotReads+1;assert(id==1251);return plot end}\nlocal Cities={GetPlotPurchaseCity=function(p)\n assert(p==plot,'purchase-city query got wrong plot')\n return {GetID=function() return purchaseID end,GetOwner=function() return purchaseOwner end}\nend}\nlocal CityOperationTypes={BUILD=7,PARAM_INSERT_MODE=12,VALUE_REPLACE_AT=90,\n PARAM_QUEUE_DESTINATION_LOCATION=13,PARAM_BUILDING_TYPE=14,PARAM_DISTRICT_TYPE=16,\n PARAM_X=17,PARAM_Y=18,PARAM_UNIT_TYPE=11,PARAM_PROJECT_TYPE=15}\nlocal CityOperationResults={PLOTS=31}\nlocal function readback()\n" + source + "\nend\nlocal function rejected() local ok=pcall(readback);assert(not ok,'invalid wonder readback accepted') end\nlocal payload=readback()\nassert(payload=='wonder-completion-v1|0|65536|61|49|3540715778|1251|67|16|0|65536|0|49|1')\nlocal beforePlots,beforeFields=plotReads,plotFieldReads\nvisible=false;rejected();assert(plotReads==beforePlots and plotFieldReads==beforeFields,'hidden plot read')\nvisible=true;revealed=false;rejected();assert(plotReads==beforePlots and plotFieldReads==beforeFields,'unrevealed plot read')\nrevealed=true\nlocal old=localID;localID=1;rejected();localID=old\nold=observer;observer=1;rejected();observer=old\nold=turn;turn=62;rejected();turn=old\nold=cityOwner;cityOwner=1;rejected();cityOwner=old\nold=plotOwner;plotOwner=1;rejected();plotOwner=old\nold=purchaseID;purchaseID=7;rejected();purchaseID=old\nold=purchaseOwner;purchaseOwner=1;rejected();purchaseOwner=old\nold=wonderType;wonderType=50;rejected();wonderType=old\n-- A disappeared placement is a distinct observation, never a completion or\n-- an inferred loss/refund. The mock rejects HasBuilding(-1) itself.\nwonderType=-1;hasBuilding=false\nlocal absent=readback()\nassert(absent=='wonder-absence-v1|0|65536|61|49|3540715778|1251|67|16|0|65536|0|-1|0')\nhasBuilding=true;rejected()\nwonderType=-2;hasBuilding=false;rejected()\nwonderType=49;hasBuilding=true\nold=hasBuilding;hasBuilding=nil;rejected();hasBuilding=old\nassert(hasBuildingCalls>0,'native membership getter was not called')\nrow.IsWonder=false;local n=plotReads;rejected();assert(plotReads==n,'non-wonder accessed plot')\nrow.IsWonder=true\nlocal oldName=row.BuildingType;row.BuildingType='BUILDING_OTHER_WONDER';n=plotReads\nrejected();assert(plotReads==n,'changed building identity accessed plot');row.BuildingType=oldName\nreturn 'native-wonder-completion-guards-ok'\n").encode('ascii')
