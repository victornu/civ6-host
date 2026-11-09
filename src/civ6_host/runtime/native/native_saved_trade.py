"""Official trade chooser, native quotes/paths, and explicit operation submission."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib, json
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_player_observation import observe_player
from civ6_host.runtime.native.native_saved_unit_orders import uint
from civ6_host.contracts.trade import (ROUTE_FIELDS as FIELDS, _number,
    compare_routes as compare_own, route_actions as actions,
    validate_route_action as validate_action, validate_routes as validate_catalog)
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_trade.py')))).resolve().parents[1]
PROOF = ROOT / 'work/trade-route967/source.json'
PROOF_SHA = '0b7a086925f2a18ee3f9c98c443ea55617c59ca85a1271b98dcbc2fbba67869f'
LIMIT = 1048576

def verify_source():
    p = load_pinned_json(PROOF, PROOF_SHA)
    if p['schema'] != 'civ6rl.trade_route967.source.v1':
        raise RuntimeError('Trade source changed')
    for r in [*p['official_ui'].values(), p['official_helper']]:
        path = _resolve_resource_path(Path(r['path']))
        path = path if path.is_absolute() else ROOT / path
        if hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest() != r['sha256']:
            raise RuntimeError('Official trade helper/UI changed')
    return p

def helper():
    p = verify_source()
    return _resolve_resource_path(ROOT / p['official_helper']['path']).read_bytes()
COMMON_LUA = '\nlocal function int(v,name,lo,hi)\n assert(type(v)==\'number\' and v%1==0 and v>=lo and v<=hi,\'invalid trade \'..name);return v\nend\nlocal function boolean(v,name)assert(type(v)==\'boolean\',\'invalid trade \'..name);return v end\nlocal function finite(v)assert(type(v)==\'number\' and v==v and math.abs(v)<1e12,\'invalid native trade number\');return v end\nlocal function ready()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,\'trade perspective changed\')\n local p=Players[pid];assert(p and p:IsAlive() and p:IsTurnActive() and p:IsTurnActiveComplete(),\'trade actor not ready\');return p\nend\nlocal player=ready()\nlocal width,height=Map.GetGridSize()\nint(width,\'width\',1,16384);int(height,\'height\',1,16384)\nassert(width*height<=16384 and width*height==Map.GetPlotCount(),\'trade map outside bounds\')\nlocal array_tag={}\nlocal function array(t)return setmetatable(t or {},array_tag) end\nlocal function dense(t,maximum)\n assert(type(t)==\'table\' and #t<=maximum,\'invalid trade array\')\n local count=0;for k,_ in pairs(t)do int(k,\'array key\',1,#t);count=count+1 end\n assert(count==#t,\'sparse trade array\');return #t\nend\nlocal function text(v)assert(type(v)==\'string\' and #v<=32768,\'invalid trade text\');return v end\nlocal function quote(v)\n return \'"\'..text(v):gsub(\'[%z\\1-\\31\\\\"]\',function(c)return string.format(\'\\\\u%04x\',c:byte())end)..\'"\'\nend\nlocal function encode(v,depth)\n depth=depth or 0;assert(depth<12,\'trade JSON too deep\')\n if type(v)==\'string\'then return quote(v)\n elseif type(v)==\'boolean\'then return v and \'true\' or \'false\'\n elseif type(v)==\'number\'then return string.format(\'%.17g\',finite(v)) end\n assert(type(v)==\'table\',\'invalid trade JSON type\')\n local parts={}\n if getmetatable(v)==array_tag then\n  dense(v,16384);for _,a in ipairs(v)do parts[#parts+1]=encode(a,depth+1)end\n  return \'[\'..table.concat(parts,\',\')..\']\'\n end\n local keys={};for k,_ in pairs(v)do assert(type(k)==\'string\');keys[#keys+1]=k end;table.sort(keys)\n for _,k in ipairs(keys)do parts[#parts+1]=quote(k)..\':\'..encode(v[k],depth+1)end\n return \'{\'..table.concat(parts,\',\')..\'}\'\nend\nlocal function same(a,b)\n if type(a)~=type(b)then return false end\n if type(a)~=\'table\'then return a==b end\n for k,v in pairs(a)do if not same(v,b[k])then return false end end\n for k,v in pairs(b)do if not same(v,a[k])then return false end end\n return true\nend\n'
LUA = COMMON_LUA + "local function yields(origin,dest,reverse)\n local raw=GetYieldsForRoute(origin,dest,reverse)\n local values=array();dense(raw.kYieldValues,64)\n for _,v in ipairs(raw.kYieldValues)do values[#values+1]=finite(v)end\n return {values=values,majority_religion=int(raw.MajorityReligion,'religion',-1,2147483647),\n  religion_pressure=finite(raw.ReligionPressure),path_bonus=boolean(raw.HasPathBonus,'path bonus'),tooltip=text(raw.TooltipText)}\nend\nlocal function portals(t,path)\n assert(type(t)=='table','native portal table missing')\n local keys={};for k,v in pairs(t)do int(k,'portal step',1,#path);int(v,'portal plot',-1,width*height-1);keys[#keys+1]=k end\n table.sort(keys);local out=array();for _,k in ipairs(keys)do out[#out+1]={step=k,plot=t[k]}end;return out\nend\nlocal function snapshot()\n local p=ready();local result={player_id=pid,turn=turn,width=width,height=height,traders=array(),active_routes=array()}\n local operation=UnitOperationTypes.MAKE_TRADE_ROUTE\n assert(operation==-2089494188,'trade operation enum changed')\n local manager=Game.GetTradeManager();assert(manager,'native trade manager missing')\n local cities,citySeen={},{}\n for _,c in p:GetCities():Members()do\n  assert(c:GetOwner()==pid and not citySeen[c:GetID()],'foreign/duplicate own trade city')\n  citySeen[c:GetID()]=true;cities[#cities+1]=c;assert(#cities<=4096)\n end\n table.sort(cities,function(a,b)return a:GetID()<b:GetID()end)\n for _,c in ipairs(cities)do\n  local routes=c:GetTrade():GetOutgoingRoutes();dense(routes,4096)\n  for _,r in ipairs(routes)do\n   assert(r.OriginCityPlayer==pid and r.OriginCityID==c:GetID(),'outgoing route origin differs')\n   result.active_routes[#result.active_routes+1]={\n    unit_id=int(r.TraderUnitID,'active trader',0,4294967295),origin_owner=pid,origin_city=c:GetID(),\n    destination_owner=int(r.DestinationCityPlayer,'destination owner',0,63),\n    destination_city=int(r.DestinationCityID,'destination city',0,4294967295)}\n   assert(#result.active_routes<=4096)\n  end\n end\n table.sort(result.active_routes,function(a,b)return a.unit_id<b.unit_id end)\n local units,seen={},{}\n for _,u in p:GetUnits():Members()do\n  assert(u:GetOwner()==pid and not seen[u:GetID()],'foreign/duplicate trade unit')\n  seen[u:GetID()]=true;local def=GameInfo.Units[u:GetUnitType()];assert(def,'missing unit definition')\n  if def.MakeTradeRoute and UnitManager.GetActivityType(u)==ActivityTypes.ACTIVITY_AWAKE and u:GetMovesRemaining()>0 then\n   local origin=Cities.GetCityInPlot(u:GetX(),u:GetY())\n   if origin then units[#units+1]={unit=u,origin=origin};assert(#units<=4096)end\n  end\n end\n table.sort(units,function(a,b)return a.unit:GetID()<b.unit:GetID()end)\n local choices={};local destinations=0\n for _,item in ipairs(units)do\n  local u,origin=item.unit,item.origin\n  local row={unit_id=int(u:GetID(),'trader',0,4294967295),x=int(u:GetX(),'trader x',0,width-1),y=int(u:GetY(),'trader y',0,height-1),\n   origin_owner=int(origin:GetOwner(),'origin owner',0,63),origin_city=int(origin:GetID(),'origin city',0,4294967295),destinations=array()}\n  local prevO=u:GetTrade():GetLastOriginTradeCityComponentID()\n  local prevD=u:GetTrade():GetLastDestinationTradeCityComponentID()\n  assert(type(prevO)=='table' and type(prevD)=='table','previous trade components unavailable')\n  local players={p};local playerSeen={[pid]=true}\n  for _,other in ipairs(Game.GetPlayers())do\n   if other:GetID()~=pid then assert(not playerSeen[other:GetID()],'duplicate destination player');playerSeen[other:GetID()]=true;players[#players+1]=other end\n  end\n  for _,other in ipairs(players)do\n   local destSeen={}\n   for _,dest in other:GetCities():Members()do\n    local owner,id=dest:GetOwner(),dest:GetID();assert(owner==other:GetID() and not destSeen[id],'foreign/duplicate destination city');destSeen[id]=true\n    local x,y=dest:GetX(),dest:GetY()\n    local params={[UnitOperationTypes.PARAM_X0]=x,[UnitOperationTypes.PARAM_Y0]=y,[UnitOperationTypes.PARAM_X1]=row.x,[UnitOperationTypes.PARAM_Y1]=row.y}\n    if boolean(UnitManager.CanStartOperation(u,operation,nil,params),'route legality')then\n     local path,entrances,exits=manager:GetTradeRoutePath(row.origin_owner,row.origin_city,owner,id)\n     if path~=nil and dense(path,16384)>0 then\n      local plots=array();for _,v in ipairs(path)do plots[#plots+1]=int(v,'route plot',0,width*height-1)end\n      local repeated=prevO.player==row.origin_owner and prevO.id==row.origin_city and prevD.player==owner and prevD.id==id\n      local confirm=true;if repeated then confirm=boolean(manager:CanStartRoute(row.origin_owner,row.origin_city,owner,id),'repeat legality')end\n      local d={owner=int(owner,'destination owner',0,63),city_id=int(id,'destination city',0,4294967295),\n       x=int(x,'destination x',0,width-1),y=int(y,'destination y',0,height-1),name=text(dest:GetName()),path=plots,\n       portal_entrances=portals(entrances,path),portal_exits=portals(exits,path),repeat_route=repeated,can_confirm=confirm,\n       has_post=boolean(dest:GetTrade():HasActiveTradingPost(row.origin_owner),'trading post'),\n       origin_yields=yields(origin,dest,false),destination_yields=yields(origin,dest,true)}\n      row.destinations[#row.destinations+1]=d;destinations=destinations+1;assert(destinations<=4096,'trade choices exceed bound')\n      if confirm then\n       local action={kind='make_trade_route',unit_id=row.unit_id,origin_owner=row.origin_owner,origin_city=row.origin_city,\n        destination_owner=owner,destination_city=id,x0=x,y0=y,x1=row.x,y1=row.y}\n       choices[#choices+1]={action=action,unit=u,params=params}\n      end\n     end\n    end\n   end\n  end\n  table.sort(row.destinations,function(a,b)return a.owner<b.owner or (a.owner==b.owner and a.city_id<b.city_id)end)\n  result.traders[#result.traders+1]=row\n end\n ready();return result,choices\nend\n"

def source(pid, turn):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    return f'local pid,turn={pid},{turn}\n'.encode() + helper() + LUA.encode()

def parse(raw, pid, turn):
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded trade wire')

    def pairs(rows):
        result = {}
        for k, v in rows:
            if k in result:
                raise ValueError('Duplicate trade JSON key')
            result[k] = v
        return result
    return validate_catalog(json.loads(raw, object_pairs_hook=pairs), pid, turn)

def catalog(prefix, turn, *, player_id=0):
    from civ6_host.runtime.native.native_locale_arguments import attach
    attach(prefix)
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source(player_id, turn) + b'local result=snapshot();return encode(result)', b'@explicit_trade_catalog', capacity=LIMIT + 1)
    return parse(raw, player_id, turn)

def literal(v):
    if type(v) is dict:
        return '{' + ','.join(('[' + literal(k) + ']=' + literal(x) for k, x in sorted(v.items()))) + '}'
    if type(v) is list:
        return '{' + ','.join((literal(x) for x in v)) + '}'
    if type(v) is bool:
        return 'true' if v else 'false'
    if type(v) is str:
        return '"' + ''.join(('\\%03d' % b for b in v.encode('utf8'))) + '"'
    if type(v) in (int, float):
        _number(v)
        return repr(v)
    raise ValueError('Invalid trade Lua literal')

def request_source(a, v):
    validate_action(a, v['width'], v['height'])
    if a not in actions(v):
        raise ValueError('Trade route outside native offers')
    return source(v['player_id'], v['turn']) + f"\nlocal observed,choices=snapshot();assert(same(observed,{literal(v)}),'trade catalogue stale')\nlocal selected={literal(a)};local found=nil\nfor _,c in ipairs(choices)do if same(c.action,selected)then assert(not found);found=c end end\nassert(found,'trade choice no longer offered');ready()\nassert(UnitManager.CanStartOperation(found.unit,UnitOperationTypes.MAKE_TRADE_ROUTE,nil,found.params)==true,'native trade veto')\nUnitManager.RequestOperation(found.unit,UnitOperationTypes.MAKE_TRADE_ROUTE,found.params)\nreturn 'submitted'\n".encode()

def apply(owner, prefix, a, turn, before, *, player_id=0):
    old = catalog(prefix, turn, player_id=player_id)
    compare_own(old, before)
    if old != getattr(owner, 'explicit_trade_routes', None) or a not in actions(old):
        raise RuntimeError('Stale trade decision')
    if prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('Trade transport not empty')
    submitted = prefix.runtime.evaluate_text(prefix.ui_child, request_source(a, old), b'@explicit_trade_request')
    if submitted != b'submitted' or len(prefix.actions.pending) != 1:
        raise RuntimeError('Expected one native trade operation')
    archive = hashlib.sha256(prefix.actions.pending[0]).hexdigest()
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()
    if prefix.actions.pending or prefix.deferred_events.pending:
        raise RuntimeError('Trade transport did not drain')
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    new = catalog(prefix, turn, player_id=player_id)
    compare_own(new, after)
    expected = {k: a[k] for k in ('unit_id', 'origin_owner', 'origin_city', 'destination_owner', 'destination_city')}
    if any((r['unit_id'] == a['unit_id'] for r in old['active_routes'])) or new['active_routes'].count(expected) != 1:
        raise RuntimeError('Native trade command lacks a matching newly active route')
    owner.emit('official_explicit_trade_effect', action=a, observation_before=before, observation_after=after, catalogue_before=old, catalogue_after=new, native_archive_sha256=archive, source_proof_sha256=PROOF_SHA, automatic_choices_applied=False, strategic_training_ready=False)
    return after
