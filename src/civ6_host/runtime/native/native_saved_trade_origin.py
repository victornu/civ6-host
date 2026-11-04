"""Official trader-origin chooser and native teleport operation, no state patch."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib, json
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_player_observation import observe_player
from civ6_host.runtime.native.native_saved_unit_orders import uint
from civ6_host.runtime.native import native_saved_trade as trade
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_trade_origin.py')))).resolve().parents[1]
PROOF = ROOT / 'work/trade-origin968/source.json'
PROOF_SHA = '16441e00438e3a95a369ba365743f8acf961750ae36cbf653ac8cce18ccff84f'
FIELDS = {'kind', 'unit_id', 'origin_city', 'source_x', 'source_y', 'destination_city', 'x', 'y', 'plot_id'}
LIMIT = 524288

def verify_source():
    p = load_pinned_json(PROOF, PROOF_SHA)
    if p['schema'] != 'civ6rl.trade_origin968.source.v1' or p['definition']['Hash'] != 509098169:
        raise RuntimeError('Trade origin source changed')
    for r in p['official_ui'].values():
        if hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(r['path']))).read_bytes()).hexdigest() != r['sha256']:
            raise RuntimeError('Official trade origin UI changed')
    return p
LUA = trade.COMMON_LUA + "\nassert(Game.IsAllowStrategicCommands(pid)==true,'strategic commands unavailable')\nlocal function snapshot()\n local p=ready();local definition=GameInfo.UnitOperations.UNITOPERATION_TELEPORT_TO_CITY\n assert(definition and definition.Hash==509098169 and definition.Hash==UnitOperationTypes.TELEPORT_TO_CITY\n  and definition.InterfaceMode=='INTERFACEMODE_TELEPORT_TO_CITY','trade origin operation identity differs')\n local op=definition.Hash;local out={player_id=pid,turn=turn,width=width,height=height,units=array()};local choices={}\n local cities,citySeen={},{}\n for _,c in p:GetCities():Members()do\n  assert(c:GetOwner()==pid and not citySeen[c:GetID()],'foreign/duplicate own origin destination')\n  citySeen[c:GetID()]=true;cities[#cities+1]=c;assert(#cities<=4096)\n end\n local seen={};local count,total=0,0\n for _,u in p:GetUnits():Members()do\n  count=count+1;assert(count<=4096 and u:GetOwner()==pid and not seen[u:GetID()],'invalid origin unit collection')\n  seen[u:GetID()]=true;local unitdef=GameInfo.Units[u:GetUnitType()];assert(unitdef,'missing unit definition')\n  if unitdef.MakeTradeRoute and u:GetMovesRemaining()>0 and definition.VisibleInUI\n   and boolean(UnitManager.CanStartOperation(u,op,nil,true),'origin visible')then\n   local available=boolean(UnitManager.CanStartOperation(u,op,nil,false,OperationResultsTypes.NO_TARGETS),'origin available')\n   local origin=Cities.GetCityInPlot(u:GetX(),u:GetY())\n   if origin then\n    assert(origin:GetOwner()==pid,'foreign origin city')\n    local row={unit_id=int(u:GetID(),'origin unit',0,4294967295),origin_city=int(origin:GetID(),'origin city',0,4294967295),\n     x=int(u:GetX(),'origin x',0,width-1),y=int(u:GetY(),'origin y',0,height-1),available=available,targets=array(),map_targets=array()}\n    if available then\n     local results=UnitManager.GetOperationTargets(u,op);assert(type(results)=='table','missing origin target results')\n     local plots=results[UnitOperationResults.PLOTS]\n     if plots~=nil then\n      dense(plots,width*height);local plotSeen={}\n      for _,plot in ipairs(plots)do\n       int(plot,'highlighted origin target',0,width*height-1);assert(not plotSeen[plot],'duplicate origin target plot');plotSeen[plot]=true\n       row.map_targets[#row.map_targets+1]=plot\n      end\n     end\n     -- The side panel independently tests each owned city. The map highlight\n     -- is an observation, not an extra legality filter invented by this host.\n     for _,dest in ipairs(cities)do\n      if dest:GetID()~=origin:GetID()then\n       local x,y=dest:GetX(),dest:GetY()\n       local params={[UnitOperationTypes.PARAM_X]=x,[UnitOperationTypes.PARAM_Y]=y}\n       if boolean(UnitManager.CanStartOperation(u,op,nil,params),'origin target legality')then\n        local d={city_id=int(dest:GetID(),'destination city',0,4294967295),x=int(x,'destination x',0,width-1),\n         y=int(y,'destination y',0,height-1),plot_id=y*width+x,name=text(dest:GetName())}\n        row.targets[#row.targets+1]=d;total=total+1;assert(total<=4096,'too many origin choices')\n        choices[#choices+1]={unit=u,params=params,action={kind='change_trade_origin',unit_id=row.unit_id,origin_city=row.origin_city,\n         source_x=row.x,source_y=row.y,destination_city=d.city_id,x=x,y=y,plot_id=d.plot_id}}\n       end\n      end\n     end\n    end\n    table.sort(row.targets,function(a,b)return a.city_id<b.city_id end);table.sort(row.map_targets)\n    out.units[#out.units+1]=row\n   end\n  end\n end\n table.sort(out.units,function(a,b)return a.unit_id<b.unit_id end);ready();return out,choices\nend\n"

def source(pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    verify_source()
    return f'local pid,turn={pid},{turn}\n'.encode() + LUA.encode()

def validate_action(a, width, height):
    if type(a) is not dict or set(a) != FIELDS or a['kind'] != 'change_trade_origin':
        raise ValueError('Malformed origin action')
    for k in ('unit_id', 'origin_city', 'destination_city'):
        uint(a[k], k)
    for k in ('x', 'source_x'):
        uint(a[k], k, width - 1)
    for k in ('y', 'source_y'):
        uint(a[k], k, height - 1)
    uint(a['plot_id'], 'plot', width * height - 1)
    if a['plot_id'] != a['y'] * width + a['x'] or a['destination_city'] == a['origin_city'] or (a['x'], a['y']) == (a['source_x'], a['source_y']):
        raise ValueError('Invalid origin destination')
    return a

def validate_catalog(v, pid, turn):
    if type(v) is not dict or set(v) != {'player_id', 'turn', 'width', 'height', 'units'}:
        raise ValueError('Malformed origin catalogue')
    if type(v['player_id']) is not int or type(v['turn']) is not int or v['player_id'] != pid or (v['turn'] != turn):
        raise ValueError('Foreign origin catalogue')
    w = uint(v['width'], 'width', 16384)
    h = uint(v['height'], 'height', 16384)
    if not w or not h or w * h > 16384 or (type(v['units']) is not list) or (len(v['units']) > 4096):
        raise ValueError('Unbounded origin catalogue')
    ids = []
    total = 0
    for u in v['units']:
        if type(u) is not dict or set(u) != {'unit_id', 'origin_city', 'x', 'y', 'available', 'targets', 'map_targets'}:
            raise ValueError('Malformed origin unit')
        ids.append(uint(u['unit_id'], 'unit'))
        uint(u['origin_city'], 'city')
        uint(u['x'], 'x', w - 1)
        uint(u['y'], 'y', h - 1)
        if type(u['available']) is not bool or type(u['targets']) is not list or type(u['map_targets']) is not list:
            raise ValueError('Malformed origin targets')
        if len(u['map_targets']) > w * h or any((type(p) is not int or not 0 <= p < w * h for p in u['map_targets'])) or u['map_targets'] != sorted(set(u['map_targets'])):
            raise ValueError('Invalid origin highlights')
        if not u['available'] and (u['targets'] or u['map_targets']):
            raise ValueError('Unavailable origin exposes choices')
        cities = []
        for d in u['targets']:
            if type(d) is not dict or set(d) != {'city_id', 'x', 'y', 'plot_id', 'name'} or type(d['name']) is not str or (len(d['name'].encode('utf8')) > 32768):
                raise ValueError('Malformed origin city')
            validate_action(_action(u, d), w, h)
            cities.append(d['city_id'])
            total += 1
        if cities != sorted(set(cities)):
            raise ValueError('Duplicate origin city')
    if ids != sorted(set(ids)) or total > 4096:
        raise ValueError('Duplicate/unbounded origin units')
    return v

def _action(u, d):
    return dict(kind='change_trade_origin', unit_id=u['unit_id'], origin_city=u['origin_city'], source_x=u['x'], source_y=u['y'], destination_city=d['city_id'], x=d['x'], y=d['y'], plot_id=d['plot_id'])

def actions(v):
    validate_catalog(v, v['player_id'], v['turn'])
    return [_action(u, d) for u in v['units'] for d in u['targets']]

def parse(raw, pid, turn):
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded origin wire')

    def pairs(rows):
        d = {}
        for k, v in rows:
            if k in d:
                raise ValueError('Duplicate origin JSON key')
            d[k] = v
        return d
    return validate_catalog(json.loads(raw, object_pairs_hook=pairs), pid, turn)

def catalog(prefix, turn, *, player_id=0):
    return parse(prefix.runtime.evaluate_text(prefix.ui_child, source(player_id, turn) + b'local value=snapshot();return encode(value)', b'@explicit_trade_origin', capacity=LIMIT + 1), player_id, turn)

def compare_own(v, obs):
    validate_catalog(v, obs['player_id'], obs['turn'])
    units = {u['id']: (u['x'], u['y']) for u in obs['units']}
    cities = {c['id']: (c['x'], c['y']) for c in obs['cities']}
    if (v['width'], v['height']) != (obs['width'], obs['height']):
        raise ValueError('Origin grid differs')
    for u in v['units']:
        if units.get(u['unit_id']) != (u['x'], u['y']) or cities.get(u['origin_city']) != (u['x'], u['y']):
            raise ValueError('Origin unit/city absent from own observation')
        if any((cities.get(d['city_id']) != (d['x'], d['y']) for d in u['targets'])):
            raise ValueError('Origin destination is not an observed own city')

def request_source(a, v):
    if a not in actions(v):
        raise ValueError('Origin action not offered')
    return source(v['player_id'], v['turn']) + f"\nlocal observed,choices=snapshot();assert(same(observed,{trade.literal(v)}),'origin catalogue stale')\nlocal selected={trade.literal(a)};local chosen=nil\nfor _,c in ipairs(choices)do if same(c.action,selected)then assert(not chosen);chosen=c end end\nassert(chosen,'origin choice disappeared');ready()\nassert(UnitManager.CanStartOperation(chosen.unit,UnitOperationTypes.TELEPORT_TO_CITY,nil,chosen.params)==true,'origin veto')\nUnitManager.RequestOperation(chosen.unit,UnitOperationTypes.TELEPORT_TO_CITY,chosen.params)\nreturn 'submitted'\n".encode()

def apply(owner, prefix, a, turn, before, *, player_id=0):
    old = catalog(prefix, turn, player_id=player_id)
    compare_own(old, before)
    if old != getattr(owner, 'explicit_trade_origins', None) or a not in actions(old):
        raise RuntimeError('Origin catalogue stale')
    if prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('Origin transport not empty')
    raw = prefix.runtime.evaluate_text(prefix.ui_child, request_source(a, old), b'@explicit_trade_origin_request')
    if raw != b'submitted' or len(prefix.actions.pending) != 1:
        raise RuntimeError('Origin did not enqueue one command')
    archive = hashlib.sha256(prefix.actions.pending[0]).hexdigest()
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()
    if prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('Origin transport did not drain')
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    unit = next((u for u in after['units'] if u['id'] == a['unit_id']), None)
    if after['turn'] != turn or not unit or unit['owner'] != player_id or ((unit['x'], unit['y']) != (a['x'], a['y'])):
        raise RuntimeError('Native origin relocation not observed')
    new = catalog(prefix, turn, player_id=player_id)
    compare_own(new, after)
    owner.emit('official_explicit_trade_origin_effect', action=a, observation_before=before, observation_after=after, catalogue_before=old, catalogue_after=new, native_archive_sha256=archive, source_proof_sha256=PROOF_SHA, automatic_choices_applied=False, strategic_training_ready=False)
    return after
