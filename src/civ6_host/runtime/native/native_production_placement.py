"""Native production targets for districts and buildings that need placement.

The Core supplies candidate plots and checks the selected operation. This
adapter does not reconstruct placement rules. Normal-panel replacement is
explicitly enabled by callers; legacy diagnostics retain the empty-queue gate.
"""
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _PLACEMENT_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native.native_production_catalog import _preamble as base_preamble
from civ6_host.runtime.native.native_production_catalog import _uint
from civ6_host.runtime.native.native_production_catalog import _type_name
from civ6_host.runtime.native.native_production_catalog import _token
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = '89b02d38d96f6cc7a1b9c59231179045994d4aa1beb7131555f10b4b5a082557'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_production_placement.py')))).resolve().parents[1]
MAX_CANDIDATES = 256
MAX_PLOTS = 65536
NOT_WIRED = ('purchases', 'queue_append_placements', 'multiple_district_repair_locations')
KINDS = ('building', 'district')

def verify_source(*, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    if core_sha256 != _PLACEMENT_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_production_placement_profile import verify_source as selected_source
        return selected_source(core_sha256)
    proof = load_pinned_json(ROOT / 'evidence/native-production-placement' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.native_production_placement.static.v1' or proof['images']['core']['sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof['images']['exe']['sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63':
        raise RuntimeError('Unexpected native placement source proof')
    return proof
RESUME_PROOF = ROOT / 'work/production-resume965/source.json'
RESUME_SHA = 'ddca212a13d22d3234636d2e2d2475fab01a042534a2658547fb898be36c4aa6'

def verify_resume_source(*, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    if core_sha256 != _PLACEMENT_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_production_placement_profile import verify_source as selected_source
        return selected_source(core_sha256)
    import hashlib
    p = load_pinned_json(RESUME_PROOF, RESUME_SHA)
    if p['schema'] != 'civ6rl.production_resume965.static.v1':
        raise RuntimeError('Placement resume source changed')
    row = p['official_ui']
    if hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(row['path']))).read_bytes()).hexdigest() != row['sha256']:
        raise RuntimeError('Official placement/resume UI changed')
    return p
_COMMON = "\nassert(type(CityManager.GetOperationTargets)=='function','native placement target API unavailable')\nassert(type(queue.HasBeenPlaced)=='function','native placement state query unavailable')\nlocal xKey,yKey=bits(e.PARAM_X,'placement X key'),bits(e.PARAM_Y,'placement Y key')\nassert(not enumSeen[xKey] and not enumSeen[yKey] and xKey~=yKey,'placement enum keys collide')\nassert(CityOperationResults,'native operation results enum unavailable')\nlocal plotsKey=bits(CityOperationResults.PLOTS,'placement results key')\nassert(Map and type(Map.GetGridSize)=='function' and type(Map.GetPlotCount)=='function' and\n type(Map.GetPlotByIndex)=='function','native placement map unavailable')\nlocal width,height=Map.GetGridSize()\nuint(width,'map width',65536);uint(height,'map height',65536)\nassert(width>0 and height>0 and width*height<=65536 and Map.GetPlotCount()==width*height,\n 'invalid placement map shape')\nlocal visibility=PlayersVisibility and PlayersVisibility[pid]\nassert(visibility and type(visibility.IsRevealed)=='function','player placement visibility unavailable')\nlocal function placementEligible(row,kind)\n if replaceCurrent and row.Hash==currentHash and\n    (kind~='district' or flag(row.OnePerCity,'district OnePerCity')) then return false end\n if kind=='district' then\n  return flag(row.RequiresPlacement,'district RequiresPlacement') and not flag(row.InternalOnly,'district InternalOnly')\n end\n if kind~='building' then return false end\n if not (flag(row.RequiresPlacement,'building RequiresPlacement') or flag(row.IsWonder,'building IsWonder')) then return false end\n if flag(row.MustPurchase,'building MustPurchase') then\n  local buildings=city:GetBuildings()\n  assert(buildings and type(buildings.IsPillaged)=='function','building repair query unavailable')\n  local pillaged=buildings:IsPillaged(row.Hash)\n  assert(type(pillaged)=='boolean','invalid building pillage query');return pillaged\n end\n return true\nend\nlocal function needsPlacement(row,kind)\n local needs=flag(row.RequiresPlacement,'RequiresPlacement')\n local placed=queue:HasBeenPlaced(row.Hash)\n assert(type(placed)=='boolean','invalid HasBeenPlaced result')\n if placed then needs=false end\n if needs and kind=='building' then\n  local buildings=city:GetBuildings()\n  assert(buildings and type(buildings.HasBuilding)=='function','native HasBuilding unavailable')\n  local has=buildings:HasBuilding(row.Hash)\n  assert(type(has)=='boolean','invalid HasBuilding result')\n  if has then needs=false end\n end\n return needs\nend\nlocal function plotCoordinates(plotID)\n uint(plotID,'placement plot ID',width*height-1)\n local revealed=visibility:IsRevealed(plotID)\n assert(type(revealed)=='boolean' and revealed,'native target includes an unrevealed plot')\n if requireVisible then\n  assert(type(visibility.IsVisible)=='function','placement current visibility unavailable')\n  assert(visibility:IsVisible(plotID%width,math.floor(plotID/width))==true,'placement target is not currently visible')\n end\n -- No plot getter is reached before the current player's visibility gate.\n local plot=Map.GetPlotByIndex(plotID)\n assert(plot and plot:GetIndex()==plotID,'placement plot identity changed')\n local x,y=uint(plot:GetX(),'plot X',width-1),uint(plot:GetY(),'plot Y',height-1)\n assert(y*width+x==plotID,'placement plot coordinates disagree with index')\n return x,y,plot\nend\nlocal function targetPlots(row,kind)\n local input={};input[e[enumFields[kind]]]=row.Hash\n local results=CityManager.GetOperationTargets(city,e.BUILD,input)\n assert(type(results)=='table','invalid native placement targets')\n local values=results[CityOperationResults.PLOTS]\n if values==nil then return {} end\n assert(type(values)=='table','invalid native placement plot list')\n local count,seen,plots=0,{},{}\n for key,value in pairs(values) do\n  count=count+1;assert(count<=width*height,'placement target bound exceeded')\n  uint(key,'placement list key',width*height);assert(key>=1,'invalid placement list origin')\n  uint(value,'placement target',width*height-1)\n  assert(not seen[value],'duplicate native placement target');seen[value]=true\n  if requireVisible then\n   assert(type(visibility.IsVisible)=='function','placement current visibility unavailable')\n   local visible=visibility:IsVisible(value%width,math.floor(value/width))\n   assert(type(visible)=='boolean','invalid placement current visibility')\n   if visible then plots[#plots+1]=value end\n  else plots[#plots+1]=value end\n end\n for i=1,count do assert(values[i]~=nil,'sparse native placement target list') end\n table.sort(plots)\n return plots\nend\nlocal function placementParameters(row,kind,mode,plotID)\n local args=parameters(row,kind)\n if mode=='place' then\n  local x,y=plotCoordinates(plotID)\n  args[e.PARAM_X]=x;args[e.PARAM_Y]=y\n else assert(mode=='resume' and plotID==-1,'invalid placement mode') end\n return args\nend\nlocal function placementLegal(row,kind,mode,plotID)\n local allowed=CityManager.CanStartOperation(city,e.BUILD,\n  placementParameters(row,kind,mode,plotID),mode=='place')\n assert(type(allowed)=='boolean','invalid native placement legality result')\n return allowed\nend\n"

def _preamble(player_id, city_id, expected_turn, *, visible_only=False, replace_current=False, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    if type(visible_only) is not bool:
        raise ValueError('Exact placement visibility mode required')
    verify_source(core_sha256=core_sha256)
    if type(replace_current) is not bool:
        raise ValueError('Exact placement replacement mode required')
    if replace_current:
        verify_resume_source(core_sha256=core_sha256)
    return base_preamble(player_id, city_id, expected_turn, replace_current=replace_current, core_sha256=core_sha256) + (b'local requireVisible=true\n' if visible_only else b'local requireVisible=false\n') + _COMMON.encode('ascii')

def catalog_source(player_id, city_id, expected_turn, *, visible_only=False, replace_current=False, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    if type(visible_only) is not bool:
        raise ValueError('Exact placement visibility mode required')
    header = _preamble(player_id, city_id, expected_turn, visible_only=visible_only, replace_current=replace_current, core_sha256=core_sha256)
    return header + "\nlocal choices,scanned,seenHash={ },0,{}\nlocal function add(row,kind,mode,plotID)\n if not placementLegal(row,kind,mode,plotID) then return end\n assert(#choices<256,'placement candidate bound exceeded; refusing truncation')\n local index,hash,name=identity(row,kind)\n local x,y=-1,-1\n if mode=='place' then x,y=plotCoordinates(plotID) end\n choices[#choices+1]={kind=kind,index=index,hash=hash,name=name,mode=mode,plot=plotID,x=x,y=y}\nend\nif replaceCurrent or queueSize==0 then\n for _,kind in ipairs({'building','district'}) do\n  local seenIndex,seenName={},{}\n  for row in tables[kind]() do\n   scanned=scanned+1;assert(scanned<=4096,'placement definition bound exceeded')\n   local index,hash,name=identity(row,kind)\n   assert(not seenIndex[index] and not seenName[name] and not seenHash[hash],\n    'ambiguous placement definition identity')\n   seenIndex[index]=true;seenName[name]=true;seenHash[hash]=true\n   if placementEligible(row,kind) and producible(row,kind) then\n    if needsPlacement(row,kind) then\n     for _,plotID in ipairs(targetPlots(row,kind)) do add(row,kind,'place',plotID) end\n    else add(row,kind,'resume',-1) end\n   end\n  end\n end\nend\ntable.sort(choices,function(a,b)\n if a.kind~=b.kind then return a.kind=='building' end\n if a.index~=b.index then return a.index<b.index end\n return a.plot<b.plot\nend)\nready()\nassert(city:GetOwner()==pid and queue:GetSize()==queueSize,'placement context changed during enumeration')\nlocal out={'placement-v1',n(pid),n(cityID),n(expectedTurn),(replaceCurrent or queueSize==0) and 'catalog' or 'queue_nonempty',\n n(scanned),n(op),n(insert),n(replace),n(destination),n(keys.building),n(keys.district),\n n(xKey),n(yKey),n(plotsKey),n(width),n(height),n(#choices)}\nfor _,c in ipairs(choices) do\n out[#out+1]=table.concat({c.kind,c.name,n(c.index),n(c.hash),c.mode,n(c.plot),n(c.x),n(c.y)},':')\nend\nreturn table.concat(out,'|')\n".encode('ascii')

def _coordinate(token):
    return -1 if token == b'-1' else _token(token, 'placement coordinate', MAX_PLOTS - 1)

def parse_catalog(payload, player_id, city_id, expected_turn):
    expected = (_uint(player_id, 'player', 63), _uint(city_id, 'city'), _uint(expected_turn, 'turn'))
    if type(payload) is not bytes or len(payload) > 65536:
        raise ValueError('Invalid placement payload')
    t = payload.split(b'|')
    if len(t) < 18 or t[0] != b'placement-v1' or t[4] not in (b'catalog', b'queue_nonempty'):
        raise ValueError('Invalid placement protocol')
    if tuple((_token(v, 'placement identity') for v in t[1:4])) != expected:
        raise ValueError('Foreign or stale placement catalogue')
    scanned = _token(t[5], 'definition count', 4096)
    op, insert, replace, dest, building, district, xkey, ykey, plotskey = (_token(v, 'placement enum') for v in t[6:15])
    if len({insert, dest, building, district, xkey, ykey}) != 6:
        raise ValueError('Placement enum keys collide')
    width, height = (_token(v, 'map size', MAX_PLOTS) for v in t[15:17])
    if width == 0 or height == 0 or width * height > MAX_PLOTS:
        raise ValueError('Invalid placement map dimensions')
    count = _token(t[17], 'candidate count', MAX_CANDIDATES)
    if count != len(t) - 18 or (t[4] == b'queue_nonempty' and (count or scanned)):
        raise ValueError('Invalid placement counts')
    catalog = dict(player_id=expected[0], city_id=expected[1], current_game_turn=expected[2], status=t[4].decode('ascii'), definitions_scanned=scanned, operation=op, insert_key=insert, replace_value=replace, destination_key=dest, parameter_keys={'building': building, 'district': district}, x_key=xkey, y_key=ykey, plots_key=plotskey, width=width, height=height, not_wired=NOT_WIRED, complete_action_space=False)
    choices = []
    previous = (-1, -1, -2)
    definitions = {}
    hashes = {}
    names = {}
    for token in t[18:]:
        row = token.split(b':')
        if len(row) != 8:
            raise ValueError('Malformed placement candidate')
        try:
            kind, name, mode = (row[i].decode('ascii') for i in (0, 1, 4))
        except UnicodeError as exc:
            raise ValueError('Invalid placement string') from exc
        if kind not in KINDS or mode not in ('place', 'resume'):
            raise ValueError('Unknown placement category or mode')
        _type_name(kind, name)
        index, row_hash = (_token(row[2], 'item index', 2147483647), _token(row[3], 'item hash'))
        plot, x, y = map(_coordinate, row[5:8])
        if mode == 'resume':
            if (plot, x, y) != (-1, -1, -1):
                raise ValueError('Resume must not choose a new plot')
        elif not (0 <= x < width and 0 <= y < height and (plot == y * width + x)):
            raise ValueError('Placement coordinate mismatch')
        order = (KINDS.index(kind), index, plot)
        if order <= previous:
            raise ValueError('Unsorted or duplicate placement candidate')
        previous = order
        definition = (kind, index)
        identity = (name, row_hash, mode)
        if definition in definitions and definitions[definition] != identity or (row_hash in hashes and hashes[row_hash] != definition) or (name in names and names[name] != definition):
            raise ValueError('Ambiguous placement definition identity')
        definitions[definition] = identity
        hashes[row_hash] = definition
        names[name] = definition
        args = [(catalog['parameter_keys'][kind], row_hash), (insert, replace), (dest, 0)]
        if mode == 'place':
            args.extend(((xkey, x), (ykey, y)))
        choices.append(dict(kind=kind, item_type=name, index=index, hash=row_hash, mode=mode, plot_id=plot, x=x, y=y, arguments=tuple(sorted(args))))
    if len(definitions) > scanned:
        raise ValueError('Placement definition count too small')
    catalog['candidates'] = tuple(choices)
    return catalog

def choose(catalog, kind, index, plot_id):
    if type(catalog) is not dict or catalog.get('status') != 'catalog':
        raise ValueError('Placement catalogue is not selectable')
    _uint(index, 'item index', 2147483647)
    if type(plot_id) is not int or plot_id < -1 or plot_id >= MAX_PLOTS:
        raise ValueError('Invalid placement plot ID')
    matches = [r for r in catalog['candidates'] if (r['kind'], r['index'], r['plot_id']) == (kind, index, plot_id)]
    if len(matches) != 1:
        raise ValueError('Placement choice is not a unique catalogue member')
    choice = {k: catalog[k] for k in ('player_id', 'city_id', 'current_game_turn', 'operation', 'insert_key', 'replace_value', 'destination_key', 'x_key', 'y_key', 'plots_key', 'width', 'height')}
    choice.update(matches[0])
    choice['parameter_key'] = catalog['parameter_keys'][kind]
    _validate_choice(choice)
    return choice

def _validate_choice(choice):
    expected = {'player_id', 'city_id', 'current_game_turn', 'operation', 'insert_key', 'replace_value', 'destination_key', 'x_key', 'y_key', 'plots_key', 'width', 'height', 'kind', 'item_type', 'index', 'hash', 'mode', 'plot_id', 'x', 'y', 'arguments', 'parameter_key'}
    if type(choice) is not dict or set(choice) != expected:
        raise ValueError('Invalid placement choice schema')
    for key in expected - {'kind', 'item_type', 'mode', 'plot_id', 'x', 'y', 'arguments'}:
        _uint(choice[key], key, 63 if key == 'player_id' else 2147483647 if key == 'index' else 4294967295)
    if choice['kind'] not in KINDS:
        raise ValueError('Invalid placement kind')
    _type_name(choice['kind'], choice['item_type'])
    width, height = (choice['width'], choice['height'])
    if width == 0 or height == 0 or width * height > MAX_PLOTS:
        raise ValueError('Invalid placement map shape')
    p, x, y = (choice[k] for k in ('plot_id', 'x', 'y'))
    if any((type(v) is not int for v in (p, x, y))):
        raise ValueError('Invalid plot identity')
    if choice['mode'] == 'place':
        if not (0 <= x < width and 0 <= y < height and (p == y * width + x)):
            raise ValueError('Invalid placement coordinates')
    elif choice['mode'] != 'resume' or (p, x, y) != (-1, -1, -1):
        raise ValueError('Invalid placement mode')
    keys = [choice[k] for k in ('parameter_key', 'insert_key', 'destination_key', 'x_key', 'y_key')]
    if len(set(keys)) != 5:
        raise ValueError('Placement argument keys collide')
    args = [(keys[0], choice['hash']), (keys[1], choice['replace_value']), (keys[2], 0)]
    if choice['mode'] == 'place':
        args.extend(((keys[3], x), (keys[4], y)))
    actual = choice['arguments']
    if type(actual) is not tuple or any((type(r) is not tuple or len(r) != 2 or any((type(v) is not int for v in r)) for r in actual)) or actual != tuple(sorted(args)):
        raise ValueError('Placement argument tuple changed')

def _selection_source(choice, *, visible_only=False, replace_current=False, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    if type(visible_only) is not bool:
        raise ValueError('Exact placement visibility mode required')
    _validate_choice(choice)
    header = _preamble(choice['player_id'], choice['city_id'], choice['current_game_turn'], visible_only=visible_only, replace_current=replace_current, core_sha256=core_sha256)
    constants = f"local kind,name,wantedIndex,wantedHash,mode,plotID='{choice['kind']}','{choice['item_type']}',{choice['index']},{choice['hash']},'{choice['mode']}',{choice['plot_id']}\nassert(op=={choice['operation']} and insert=={choice['insert_key']} and replace=={choice['replace_value']} and destination=={choice['destination_key']} and keys[kind]=={choice['parameter_key']} and xKey=={choice['x_key']} and yKey=={choice['y_key']} and plotsKey=={choice['plots_key']},'placement enums changed')\nassert(width=={choice['width']} and height=={choice['height']},'placement map changed')\n"
    return header + constants.encode('ascii') + "\nlocal row=tables[kind][name]\nlocal index,hash,rowName=identity(row,kind)\nassert(index==wantedIndex and hash==wantedHash and rowName==name,'placement row identity changed')\nlocal i2,h2,n2=identity(tables[kind][wantedIndex],kind)\nassert(i2==index and h2==hash and n2==name,'placement index/name lookup mismatch')\n".encode('ascii')

def request_source(choice, *, visible_only=False, replace_current=False, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    return _selection_source(choice, visible_only=visible_only, replace_current=replace_current, core_sha256=core_sha256) + "\nassert(replaceCurrent or queueSize==0,'placement request requires empty queue')\nassert(placementEligible(row,kind) and producible(row,kind),'native placement production unavailable')\nassert(needsPlacement(row,kind)==(mode=='place'),'placement or resume mode changed')\nif mode=='place' then\n local found=0\n for _,p in ipairs(targetPlots(row,kind)) do if p==plotID then found=found+1 end end\n assert(found==1,'selected plot no longer in native placement targets')\nend\nready()\nassert(city:GetOwner()==pid and queue:GetSize()==queueSize,'placement context changed before legality query')\nassert(placementLegal(row,kind,mode,plotID),'native placement legality rejected request')\nready()\nassert(city:GetOwner()==pid and queue:GetSize()==queueSize,'placement context changed during legality query')\nCityManager.RequestOperation(city,e.BUILD,placementParameters(row,kind,mode,plotID))\nreturn 'submitted'\n".encode('ascii')

def effect_source(choice, *, visible_only=False, replace_current=False, core_sha256=_PLACEMENT_BASE_CORE_SHA256):
    return _selection_source(choice, visible_only=visible_only, replace_current=replace_current, core_sha256=core_sha256) + "\nlocal placed=queue:HasBeenPlaced(row.Hash)\nassert(type(placed)=='boolean','invalid placement readback')\nlocal x,y,nativeType,owner=-1,-1,-1,-1\nif mode=='place' then\n local plot;x,y,plot=plotCoordinates(plotID)\n owner=uint(plot:GetOwner(),'placement plot owner',63)\n if kind=='district' then nativeType=plot:GetDistrictType() else nativeType=plot:GetWonderType() end\n uint(nativeType,'placed plot type',2147483647)\nend\nready()\nreturn table.concat({'placement-effect-v1',n(pid),n(cityID),n(expectedTurn),kind,n(index),n(hash),\n mode,n(plotID),n(x),n(y),placed and '1' or '0',n(nativeType),n(owner)},'|')\n".encode('ascii')

def parse_effect(payload, choice):
    _validate_choice(choice)
    if type(payload) is not bytes or len(payload) > 1024:
        raise ValueError('Invalid placement effect')
    t = payload.split(b'|')
    if len(t) != 14 or t[0] != b'placement-effect-v1':
        raise ValueError('Invalid placement effect protocol')
    try:
        expected = [str(choice[k]).encode('ascii') for k in ('player_id', 'city_id', 'current_game_turn', 'kind', 'index', 'hash', 'mode', 'plot_id', 'x', 'y')]
    except (UnicodeError, KeyError) as exc:
        raise ValueError('Invalid placement effect identity') from exc
    if t[1:11] != expected or t[11] not in (b'0', b'1'):
        raise ValueError('Placement effect identity mismatch')
    native_type = _coordinate(t[12])
    owner = _coordinate(t[13])
    if choice['mode'] == 'place' and (t[11] != b'1' or native_type != choice['index'] or owner != choice['player_id']):
        raise ValueError('Native plot did not confirm the selected placement')
    if choice['mode'] == 'resume' and (native_type, owner) != (-1, -1):
        raise ValueError('Unexpected resume plot readback')
    return dict(player_id=choice['player_id'], city_id=choice['city_id'], turn=choice['current_game_turn'], kind=choice['kind'], item_index=choice['index'], item_hash=choice['hash'], mode=choice['mode'], plot_id=choice['plot_id'], x=choice['x'], y=choice['y'], has_been_placed=t[11] == b'1', plot_type=native_type, plot_owner=owner, new_placement_verified=choice['mode'] == 'place', item_completed=False, eligible_for_training=False)

def guard_case():
    from civ6_host.runtime.native.native_production_placement_guards import guard_case as build
    return build()
