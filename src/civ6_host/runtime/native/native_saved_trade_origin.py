"""Official trader-origin chooser and native teleport operation, no state patch."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import hashlib, json
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_player_observation import observe_player
from civ6_host.runtime.native.native_saved_unit_orders import uint
from civ6_host.contracts.trade import (ORIGIN_FIELDS as FIELDS,
    compare_origins as compare_own, origin_actions as actions,
    validate_origin_action as validate_action, validate_origins as validate_catalog)
from civ6_host.runtime.native import native_saved_trade as trade
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_trade_origin.py')))).resolve().parents[1]
PROOF = ROOT / 'work/trade-origin968/source.json'
PROOF_SHA = '16441e00438e3a95a369ba365743f8acf961750ae36cbf653ac8cce18ccff84f'
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
