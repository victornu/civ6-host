"""Heuristic routing toward a visible, completed own district.

This is only a destination preference.  It does not claim that a district is a
legal FOUND_RELIGION site; the native CanStartOperation check remains decisive
after each move.  Actual moves must still come from native_unit_movement's
catalog and request path.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import re
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native import native_district_completion
from civ6_host.runtime.native import native_unit_movement
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_prophet_navigation.py')))).resolve().parents[1]
RELIGION_PROOF_SHA256 = 'c5f6dd96698059bf7fc4b8c4bf765d4876857f1963d1772657c67866f32609e0'
MAX_PLOTS = 16384
MAX_TARGETS = 4096
MAX_BYTES = 1048576
_UI_ROOT = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI"))
_DISTANCE_UI = ('Choosers/TradeRouteChooser.lua', '376d11e1bcde35bbddf04276ffa71867acc2ec758892f705d948afe37e4c3eeb')
_PLOT_INDEX_UI = ('MinimapPanel.lua', '2848955c4eb3d27647568a348637ba611c1d16b3a69a50b52abefea34ad409eb')

def verify_source() -> None:
    proof = load_pinned_json(ROOT / 'evidence/native-religion-founding-actions' / f'{RELIGION_PROOF_SHA256}.json', RELIGION_PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_religion_founding_actions.static.v1' or proof.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof.get('functions', {}).get('unit_found_religion_location', {}).get('start_va') != '0x1804f1e80':
        raise RuntimeError('FOUND_RELIGION location source identity changed')
    native_district_completion.verify_source()
    native_unit_movement.verify_source()
    for relative, expected in (_DISTANCE_UI, _PLOT_INDEX_UI):
        raw = _resolve_resource_path(_UI_ROOT / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise RuntimeError('Pinned native navigation UI source changed')
        text = raw.decode('utf-8-sig')
        if relative == _DISTANCE_UI[0] and 'Map.GetPlotDistance(originCity:GetX(), originCity:GetY(), destinationCity:GetX(), destinationCity:GetY())' not in text:
            raise RuntimeError('Official UI Map.GetPlotDistance usage changed')
        if relative == _PLOT_INDEX_UI[0] and 'Map.GetPlotIndex(plotX, plotY)' not in text:
            raise RuntimeError('Official UI Map.GetPlotIndex usage changed')

def _uint(value: int, label: str, maximum: int=4294967295) -> int:
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'Invalid {label}')
    return value

def target_catalog_source(player_id: int, turn: int, district_type_names: tuple[str, ...]) -> bytes:
    """Enumerate explicitly selected visible own districts as heuristic targets."""
    verify_source()
    pid = _uint(player_id, 'player ID', 63)
    expected_turn = _uint(turn, 'turn')
    if type(district_type_names) is not tuple or not district_type_names or len(district_type_names) > 32 or any((type(n) is not str or not re.fullmatch('DISTRICT_[A-Z0-9_]+', n) for n in district_type_names)) or (len(set(district_type_names)) != len(district_type_names)):
        raise ValueError('Explicit district type names required')
    encoded_names = ','.join(district_type_names).encode('ascii')
    script = "\nassert(Game and type(Game.GetLocalPlayer)=='function' and Game.GetLocalPlayer()==pid and\n type(Game.GetLocalObserver)=='function' and Game.GetLocalObserver()==pid,\n 'district target perspective mismatch')\nassert(type(Game.GetCurrentGameTurn)=='function' and Game.GetCurrentGameTurn()==expectedTurn,\n 'district target turn is stale')\nlocal player=Players and Players[pid]\nassert(player and type(player.GetID)=='function' and player:GetID()==pid and\n player:IsAlive()==true and player:IsTurnActive()==true and\n player:IsTurnActiveComplete()==true,'district target player is not ready')\nlocal visibility=PlayersVisibility and PlayersVisibility[pid]\nassert(visibility and type(visibility.IsVisible)=='function' and\n type(visibility.IsRevealed)=='function','district visibility API unavailable')\nassert(Map and type(Map.GetGridSize)=='function' and type(Map.GetPlotCount)=='function' and\n type(Map.GetPlotByIndex)=='function' and type(Map.GetPlotIndex)=='function',\n 'district map API unavailable')\nassert(Cities and type(Cities.GetPlotPurchaseCity)=='function','district city lookup unavailable')\nlocal w,h=Map.GetGridSize();local count=Map.GetPlotCount()\nassert(type(w)=='number' and w==math.floor(w) and type(h)=='number' and h==math.floor(h) and\n type(count)=='number' and count==math.floor(count) and w>0 and h>0 and w*h==count and\n count<=16384,'district map is outside bounds')\nlocal function n(v)\n assert(type(v)=='number' and v==math.floor(v),'invalid district target integer')\n return string.format('%.0f',v)\nend\nlocal rows={}\nlocal allowed={}\nlocal names='DISTRICT_NAMES'\nfor name in string.gmatch(names,'[^,]+') do\n local row=GameInfo and GameInfo.Districts and GameInfo.Districts[name]\n assert(row and type(row.Index)=='number' and row.Index==math.floor(row.Index) and row.Index>=0,\n  'explicit district type unavailable')\n allowed[row.Index]=true\nend\nfor index=0,count-1 do\n local x,y=index%w,math.floor(index/w)\n assert(x>=0 and x<w and y>=0 and y<h and Map.GetPlotIndex(x,y)==index,\n  'plot index/coordinate geometry mismatch')\n local visible=visibility:IsVisible(x,y)\n local revealed=visibility:IsRevealed(index)\n assert(type(visible)=='boolean' and type(revealed)=='boolean','visibility result must be Boolean')\n if visible and revealed then\n   local plotLive=Map.GetPlotByIndex(index)\n   assert(plotLive~=nil,'missing visible plot')\n   assert(plotLive:GetX()==x and plotLive:GetY()==y,\n    'plot handle coordinates differ from index geometry')\n   local owner=plotLive:GetOwner()\n   assert(type(owner)=='number' and owner==math.floor(owner),'invalid revealed plot owner')\n   if owner==pid then\n    local districtType=plotLive:GetDistrictType()\n    assert(type(districtType)=='number' and districtType==math.floor(districtType) and districtType>=-1,\n     'invalid own revealed district type')\n    if districtType>=0 and allowed[districtType] then\n     local districtID=plotLive:GetDistrictID()\n     assert(type(districtID)=='number' and districtID==math.floor(districtID) and districtID>=0,\n      'invalid own revealed district ID')\n     local city=Cities.GetPlotPurchaseCity(plotLive)\n     assert(city and type(city.GetID)=='function' and type(city.GetOwner)=='function',\n      'district owning city unavailable')\n     local cityID,cityOwner=city:GetID(),city:GetOwner()\n     assert(type(cityID)=='number' and cityID==math.floor(cityID) and\n      type(cityOwner)=='number' and cityOwner==pid,'district purchase city is not owned')\n     local districts=city:GetDistricts()\n     assert(districts and type(districts.IsComplete)=='function','district completion API unavailable')\n     local complete=districts:IsComplete(districtType,index)\n     assert(type(complete)=='boolean','invalid native district completion result')\n     if complete then\n      rows[#rows+1]=table.concat({n(index),n(x),n(y),n(districtType),n(districtID),n(cityID)},',')\n      assert(#rows<=4096,'own district target bound exceeded')\n     end\n    end\n   end\n end\nend\ntable.sort(rows,function(a,b) return tonumber(a:match('^[^,]+'))<tonumber(b:match('^[^,]+')) end)\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n Game.GetCurrentGameTurn()==expectedTurn,'district target context changed')\nreturn table.concat({n(pid),n(expectedTurn),n(w),n(h),table.concat(rows,';')},'|')\n"
    return b'local pid,expectedTurn=' + str(pid).encode() + b',' + str(expected_turn).encode() + b'\n' + script.replace('DISTRICT_NAMES', encoded_names.decode('ascii')).encode('ascii')

def prophet_roster_source(player_id: int, turn: int) -> bytes:
    """Read only the current player's own Great Prophet roster."""
    verify_source()
    pid, expected_turn = (_uint(player_id, 'player ID', 1), _uint(turn, 'turn'))
    prefix = f'local pid,expectedTurn={pid},{expected_turn}\n'.encode('ascii')
    return prefix + "\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n Game.GetCurrentGameTurn()==expectedTurn,'prophet roster context is stale')\nlocal player=Players and Players[pid]\nassert(player and type(player.GetID)=='function' and player:GetID()==pid and\n player:IsAlive()==true and player:IsTurnActive()==true and\n player:IsTurnActiveComplete()==true,'prophet roster player is not ready')\nlocal units=player:GetUnits()\nassert(units and type(units.Members)=='function' and type(units.FindID)=='function',\n 'own unit roster API unavailable')\nlocal row=GameInfo and GameInfo.Units and GameInfo.Units.UNIT_GREAT_PROPHET\nassert(row and type(row.Index)=='number' and row.Index==math.floor(row.Index) and row.Index>=0,\n 'Great Prophet type is unavailable')\nlocal w,h=Map.GetGridSize();local count=Map.GetPlotCount()\nassert(type(w)=='number' and w==math.floor(w) and type(h)=='number' and h==math.floor(h) and\n type(count)=='number' and count==math.floor(count) and w>0 and h>0 and w*h==count and count<=16384,\n 'prophet map geometry is invalid')\nlocal out={}\nfor _,unit in units:Members() do\n assert(unit and type(unit.GetID)=='function' and type(unit.GetOwner)=='function' and\n  type(unit.GetType)=='function' and type(unit.GetX)=='function' and type(unit.GetY)=='function',\n  'own unit API incomplete')\n local owner,id,kind=unit:GetOwner(),unit:GetID(),unit:GetType()\n assert(type(owner)=='number' and owner==pid and type(id)=='number' and id==math.floor(id) and\n  id>=0 and id<=4294967295 and type(kind)=='number' and kind==math.floor(kind),\n  'invalid own unit identity')\n if kind==row.Index then\n  assert(#out<4096,'prophet roster exceeds bound')\n  local x,y=unit:GetX(),unit:GetY()\n  assert(type(x)=='number' and x==math.floor(x) and x>=0 and x<w and\n   type(y)=='number' and y==math.floor(y) and y>=0 and y<h,\n   'invalid Great Prophet position')\n  local plotID=Map.GetPlotIndex(x,y)\n  assert(type(plotID)=='number' and plotID==y*w+x and plotID>=0 and plotID<count,\n   'Great Prophet plot geometry mismatch')\n  out[#out+1]=string.format('%.0f,%.0f,%.0f,%.0f',id,plotID,x,y)\n end\n local found=units:FindID(id)\n assert(found and found:GetID()==id and found:GetOwner()==pid and unit:GetOwner()==pid,\n  'own unit lookup/owner changed')\nend\nassert(#out<=4096,'prophet roster exceeds bound')\ntable.sort(out,function(a,b) return tonumber(a:match('^[^,]+'))<tonumber(b:match('^[^,]+')) end)\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n Game.GetCurrentGameTurn()==expectedTurn,'prophet roster context changed')\nreturn table.concat({tostring(pid),tostring(expectedTurn),tostring(row.Index),tostring(w),tostring(h),table.concat(out,';')},'|')\n".encode('ascii')

def parse_prophet_roster(payload: bytes, player_id: int, turn: int) -> dict:
    pid, expected_turn = (_uint(player_id, 'player ID', 1), _uint(turn, 'turn'))
    if type(payload) is not bytes or not payload or len(payload) > 65536:
        raise ValueError('Invalid prophet roster payload')
    parts = payload.split(b'|')
    if len(parts) != 6 or parts[:2] != [str(pid).encode(), str(expected_turn).encode()]:
        raise ValueError('Stale or malformed prophet roster')
    type_index = _uint_token(parts[2], 'Great Prophet type', 2147483647)
    width = _uint_token(parts[3], 'map width', 16384)
    height = _uint_token(parts[4], 'map height', 16384)
    if not width or not height or width * height > MAX_PLOTS:
        raise ValueError('Invalid prophet map dimensions')
    roster, previous = ([], -1)
    rows = [] if not parts[5] else parts[5].split(b';')
    if len(rows) > 4096:
        raise ValueError('Prophet roster count exceeds bound')
    for raw in rows:
        fields = raw.split(b',')
        if len(fields) != 4:
            raise ValueError('Malformed prophet roster row')
        uid, plot_id, x, y = (_uint_token(t, 'prophet field', m) for t, m in zip(fields, (4294967295, MAX_PLOTS - 1, 16383, 16383)))
        if uid <= previous or x >= width or y >= height or (plot_id != y * width + x):
            raise ValueError('Unordered or geometrically invalid prophet row')
        previous = uid
        roster.append({'owner': pid, 'unit_id': uid, 'unit_type_index': type_index, 'plot_id': plot_id, 'x': x, 'y': y})
    return {'player_id': pid, 'turn': expected_turn, 'width': width, 'height': height, 'great_prophet_type_index': type_index, 'units': tuple(roster)}

def parse_target_catalog(payload: bytes, player_id: int, turn: int) -> dict:
    pid = _uint(player_id, 'player ID', 63)
    expected_turn = _uint(turn, 'turn')
    if type(payload) is not bytes or not payload or len(payload) > MAX_BYTES:
        raise ValueError('Invalid district target payload')
    parts = payload.split(b'|')
    if len(parts) != 5:
        raise ValueError('Malformed district target header')
    header = tuple((_uint_token(t, label, maxv) for t, label, maxv in zip(parts[:4], ('player', 'turn', 'width', 'height'), (63, 4294967295, 16384, 16384))))
    if header[:2] != (pid, expected_turn) or not header[2] or (not header[3]) or (header[2] * header[3] > MAX_PLOTS):
        raise ValueError('Stale or invalid district target context')
    rows = [] if not parts[4] else parts[4].split(b';')
    if len(rows) > MAX_TARGETS:
        raise ValueError('District target count exceeds bound')
    targets, previous = ([], -1)
    for row in rows:
        fields = row.split(b',')
        if len(fields) != 6:
            raise ValueError('Malformed district target row')
        values = tuple((_uint_token(t, 'district field', maxv) for t, maxv in zip(fields, (MAX_PLOTS - 1, 16383, 16383, 2147483647, 4294967295, 4294967295))))
        plot_id, x, y, district_type, district_id, city_id = values
        if plot_id <= previous or x >= header[2] or y >= header[3] or (plot_id != y * header[2] + x) or (district_type < 0):
            raise ValueError('Unordered or invalid own district target')
        previous = plot_id
        targets.append({'plot_id': plot_id, 'x': x, 'y': y, 'district_type': district_type, 'district_id': district_id, 'city_id': city_id, 'owner': pid, 'visible': True, 'complete': True, 'legal_founding_site': None})
    return {'player_id': pid, 'turn': expected_turn, 'width': header[2], 'height': header[3], 'targets': tuple(targets), 'target_semantics': 'heuristic destinations only; not FOUND_RELIGION legality'}

def _uint_token(token: bytes, label: str, maximum: int) -> int:
    if not token or any((c < 48 or c > 57 for c in token)) or (len(token) > 1 and token[0] == 48):
        raise ValueError(f'Invalid {label}')
    result = int(token)
    if result > maximum:
        raise ValueError(f'Out-of-range {label}')
    return result

def distance_source(player_id: int, turn: int, target: dict, movement_catalog: dict, unit_id: int) -> bytes:
    """Revalidate a visible completed own district and obtain native distances.

    It does not ask whether FOUND_RELIGION is legal there. Destination plot
    choices must already be in the native MOVE_TO catalog.
    """
    verify_source()
    pid, expected_turn = (_uint(player_id, 'player ID', 1), _uint(turn, 'turn'))
    uid = _uint(unit_id, 'unit ID')
    required_target = {'plot_id', 'x', 'y', 'district_type', 'district_id', 'city_id', 'owner', 'visible', 'complete', 'legal_founding_site'}
    _validate_target(target, pid)
    if type(movement_catalog) is not dict or movement_catalog.get('status') != 'catalog' or movement_catalog.get('player_id') != pid or (movement_catalog.get('current_game_turn') != expected_turn):
        raise ValueError('Movement catalog player/turn differs from distance query')
    candidates = [c for c in movement_catalog.get('choices', ()) if c.get('unit_id') == uid]
    if not candidates or len(candidates) > 4096:
        raise ValueError('No bounded native movement candidates for this unit')
    native_unit_movement.choose(movement_catalog, uid, candidates[0].get('destination_plot_id'))
    if len({c['destination_plot_id'] for c in candidates}) != len(candidates):
        raise ValueError('Duplicate native movement destination')
    rows = []
    for c in candidates:
        for key in ('source_plot_id', 'destination_plot_id', 'source_x', 'source_y', 'destination_x', 'destination_y'):
            _uint(c[key], key, MAX_PLOTS - 1 if 'plot_id' in key else 16383)
        rows.append((c['destination_plot_id'], c['source_plot_id'], c['source_x'], c['source_y'], c['destination_x'], c['destination_y']))
    if len({(r[1], r[2], r[3]) for r in rows}) != 1:
        raise ValueError('Native movement catalog has inconsistent source positions')
    tx = b','.join((str(v).encode() for v in (uid, target['plot_id'], target['x'], target['y'], target['district_type'], target['district_id'], target['city_id'], rows[0][1], rows[0][2], rows[0][3])))
    encoded_rows = b';'.join((b','.join((str(v).encode() for v in row)) for row in rows))
    return b'local pid,expectedTurn=' + str(pid).encode() + b',' + str(expected_turn).encode() + b'\n' + b'local uid,targetIndex,tx,ty,districtType,districtID,cityID,sourceIndex,sx,sy=' + tx + b'\n' + b"local candidates='" + encoded_rows + b"'\n" + "\nassert(Game and Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n Game.GetCurrentGameTurn()==expectedTurn,'navigation distance context is stale')\nlocal player=Players and Players[pid]\nassert(player and type(player.GetID)=='function' and player:GetID()==pid and\n player:IsAlive()==true and player:IsTurnActive()==true and\n player:IsTurnActiveComplete()==true,'navigation player is not ready')\nassert(Map and type(Map.GetPlotByIndex)=='function' and type(Map.GetPlotIndex)=='function' and\n type(Map.GetGridSize)=='function' and type(Map.GetPlotCount)=='function' and\n type(Map.GetPlotDistance)=='function' and\n PlayersVisibility and PlayersVisibility[pid],'native plot-distance APIs unavailable')\nlocal visibility=PlayersVisibility[pid]\nassert(type(visibility.IsVisible)=='function' and type(visibility.IsRevealed)=='function',\n 'native district visibility APIs unavailable')\nlocal w,h=Map.GetGridSize();local count=Map.GetPlotCount()\nassert(type(w)=='number' and w==math.floor(w) and type(h)=='number' and h==math.floor(h) and\n type(count)=='number' and count==math.floor(count) and w>0 and h>0 and w*h==count and\n count<=16384 and tx<w and ty<h and\n targetIndex==ty*w+tx and Map.GetPlotIndex(tx,ty)==targetIndex,\n 'district target geometry changed')\nlocal visible,revealed=visibility:IsVisible(tx,ty),visibility:IsRevealed(targetIndex)\nassert(type(visible)=='boolean' and type(revealed)=='boolean' and visible and revealed,\n 'district target is no longer visible')\nlocal target=Map.GetPlotByIndex(targetIndex)\nassert(target~=nil and target:GetX()==tx and target:GetY()==ty,\n 'district target geometry changed')\nassert(target:GetOwner()==pid and target:GetDistrictType()==districtType and\n target:GetDistrictID()==districtID,'district target identity changed')\nlocal city=Cities.GetPlotPurchaseCity(target)\nlocal complete=city and city:GetDistricts():IsComplete(districtType,targetIndex)\nassert(city and city:GetID()==cityID and city:GetOwner()==pid and\n type(complete)=='boolean' and complete==true,\n 'district target is no longer an owned completed district')\nlocal units=player:GetUnits();assert(units and type(units.FindID)=='function','own unit lookup unavailable')\nlocal unit=units:FindID(uid)\nlocal prophet=GameInfo and GameInfo.Units and GameInfo.Units.UNIT_GREAT_PROPHET\nassert(prophet and type(prophet.Index)=='number','Great Prophet type unavailable')\nassert(unit and unit:GetID()==uid and unit:GetOwner()==pid and unit:GetType()==prophet.Index and\n Map.GetPlotIndex(unit:GetX(),unit:GetY())==sourceIndex and unit:GetX()==sx and unit:GetY()==sy,\n 'selected unit is not the current own Great Prophet')\nassert(sourceIndex==sy*w+sx,'prophet source geometry changed')\nlocal startDistance=Map.GetPlotDistance(sx,sy,tx,ty)\nassert(type(startDistance)=='number' and startDistance==math.floor(startDistance) and\n startDistance>=0 and startDistance<=16384,'invalid native start distance')\nlocal out={string.format('%.0f',startDistance)}\nfor row in string.gmatch(candidates,'[^;]+') do\n local d,sidx,x,y,dx,dy=string.match(row,'^(%d+),(%d+),(%d+),(%d+),(%d+),(%d+)$')\n assert(d and tonumber(sidx)==sourceIndex and tonumber(x)==sx and tonumber(y)==sy,\n  'candidate source changed')\n assert(tonumber(d)==tonumber(dy)*w+tonumber(dx) and tonumber(dx)<w and tonumber(dy)<h,\n  'candidate destination geometry changed')\n local distance=Map.GetPlotDistance(tonumber(dx),tonumber(dy),tx,ty)\n assert(type(distance)=='number' and distance==math.floor(distance) and\n  distance>=0 and distance<=16384,'invalid native destination distance')\n out[#out+1]=d..':'..string.format('%.0f',distance)\nend\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n Game.GetCurrentGameTurn()==expectedTurn,'navigation context changed during distance query')\nreturn table.concat(out,';')\n".encode('ascii')

def parse_distances(payload: bytes, movement_catalog: dict, target: dict, unit_id: int) -> dict:
    uid = _uint(unit_id, 'unit ID')
    if type(payload) is not bytes or len(payload) > 65536:
        raise ValueError('Invalid native distance payload')
    fields = payload.split(b';')
    candidates = [c for c in movement_catalog['choices'] if c['unit_id'] == uid]
    if len(fields) != len(candidates) + 1:
        raise ValueError('Native distance count differs from movement catalog')
    start = _uint_token(fields[0], 'starting distance', MAX_PLOTS)
    distances = {}
    expected = {c['destination_plot_id'] for c in candidates}
    for field in fields[1:]:
        parts = field.split(b':')
        if len(parts) != 2:
            raise ValueError('Malformed native distance row')
        plot = _uint_token(parts[0], 'destination plot', MAX_PLOTS - 1)
        distance = _uint_token(parts[1], 'destination distance', MAX_PLOTS)
        if plot in distances or plot not in expected:
            raise ValueError('Unknown or duplicate native distance destination')
        distances[plot] = distance
    if set(distances) != expected:
        raise ValueError('Native distances do not cover movement candidates')
    return {'unit_id': uid, 'target_plot_id': _uint(target['plot_id'], 'target plot', MAX_PLOTS - 1), 'start_distance': start, 'destination_distances': distances}

def choose_navigation_step(movement_catalog: dict, target: dict, distances: dict, unit_id: int) -> dict:
    """Choose a strictly closer step among existing native MOVE_TO candidates.

    ``distances`` is a native Map.GetPlotDistance readback for each candidate
    destination and for the unit's current plot. It is a ranking heuristic only.
    """
    catalog = movement_catalog
    if type(catalog) is not dict or catalog.get('status') != 'catalog' or type(catalog.get('choices')) is not tuple or (len(catalog['choices']) > 4096):
        raise ValueError('Invalid native movement catalog')
    pid, turn = (catalog.get('player_id'), catalog.get('current_game_turn'))
    _uint(pid, 'player ID', 1)
    _uint(turn, 'turn')
    _validate_target(target, pid)
    if type(distances) is not dict or set(distances) != {'unit_id', 'target_plot_id', 'start_distance', 'destination_distances'}:
        raise ValueError('Malformed native target-distance report')
    uid = _uint(unit_id, 'unit ID')
    if distances['unit_id'] != uid or distances['target_plot_id'] != target['plot_id']:
        raise ValueError('Distance report does not match navigation target')
    start = _distance(distances['start_distance'])
    dest_dists = distances['destination_distances']
    if type(dest_dists) is not dict:
        raise ValueError('Malformed destination distance map')
    eligible = [c for c in catalog['choices'] if c.get('unit_id') == uid]
    if not eligible:
        raise ValueError('No native movement candidates for selected unit')
    expected_plots = {c['destination_plot_id'] for c in eligible}
    if set(dest_dists) != expected_plots:
        raise ValueError('Distance map does not exactly cover native candidates')
    progressing = [(_distance(dest_dists[c['destination_plot_id']]), c['destination_plot_id'], c) for c in eligible]
    progressing = [item for item in progressing if item[0] < start]
    if not progressing:
        raise ValueError('No native candidate strictly approaches the selected district')
    distance, plot, _ = min(progressing, key=lambda item: (item[0], item[1]))
    choice = native_unit_movement.choose(catalog, uid, plot)
    return {'choice': choice, 'heuristic': 'native plot-distance decreases toward own completed district', 'distance_before': start, 'distance_after': distance, 'target_is_legal_founding_site': None, 'requires_fresh_native_founding_check': True}

def _distance(value) -> int:
    return _uint(value, 'native plot distance', MAX_PLOTS)

def _validate_target(target: dict, player_id: int) -> None:
    required = {'plot_id', 'x', 'y', 'district_type', 'district_id', 'city_id', 'owner', 'visible', 'complete', 'legal_founding_site'}
    if type(target) is not dict or set(target) != required:
        raise ValueError('Malformed district target')
    if target['owner'] != player_id or target['visible'] is not True or target['complete'] is not True or (target['legal_founding_site'] is not None):
        raise ValueError('Target must be a visible completed own district, not a claimed legal site')
    for key, maximum in (('plot_id', MAX_PLOTS - 1), ('x', 16383), ('y', 16383), ('district_type', 2147483647), ('district_id', 4294967295), ('city_id', 4294967295)):
        _uint(target[key], key, maximum)
