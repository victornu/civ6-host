"""Native UnitPanel improvement choices and immediate terrain operations.

No terrain rule, charge cost, yield or native legality is implemented here.
The UI's returned improvement selector is distinct from the requested hash.
Tutorial and UI mod hooks remain an explicit action-parity limitation.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import math, re
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_player_observation import observe_player
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_unit_work.py')))).resolve().parents[1]
SOURCE_SHA = '4e69b7dbc641961e19ce107a17fbad2c827a5a6e9b71bf79f218b8a76ed80c3e'
from civ6_host.contracts.unit_work import (
    ADJACENT_FIELDS, BUILD_FIELDS, COMMON_FIELDS, OP_FIELDS, OPS, actions,
    moves, uint, validate_action, validate_catalog, wire,
)
LIMIT = 524288

ADJACENT_LUA = """
local function adjacentOffers(add,u,x,y,source,remaining)
 local operation=integer(op.BUILD_IMPROVEMENT_ADJACENT,'adjacent operation',-2147483648,2147483647)
 local can,details=UnitManager.CanStartOperation(u,operation,nil,{},true)
 if not bool(can,'adjacent improvement visibility') or not details then return end
 local selectors=details[UnitOperationResults.IMPROVEMENTS]
 if not selectors then return end
 assert(type(selectors)=='table','adjacent improvement selectors')
 local seen,count={},0
 for _,selector in ipairs(selectors) do
  count=count+1;assert(count<=32,'adjacent selector bound')
  local key=bits(selector);assert(not seen[key],'duplicate adjacent selector');seen[key]=true
  local row=GameInfo.Improvements[selector];assert(row,'unknown adjacent improvement')
  local name=row.ImprovementType
  assert(type(name)=='string' and #name<=112 and string.match(name,'^IMPROVEMENT_[A-Z0-9_]+$'),'improvement type')
  integer(row.Index,'improvement index',0,4294967295);bits(row.Hash)
  local targets=UnitManager.GetOperationTargets(u,operation,{[op.PARAM_IMPROVEMENT_TYPE]=row.Hash})
  assert(type(targets)=='table','adjacent improvement targets')
  local plots=targets[UnitOperationResults.PLOTS] or {}
  local plotCount,seenPlots=0,{}
  for _,id in pairs(plots) do
   plotCount=plotCount+1
   integer(id,'target plot',0,4294967295)
   assert(plotCount<=32 and Map.IsPlot(id) and id~=source:GetIndex() and not seenPlots[id],'invalid adjacent target')
   seenPlots[id]=true
   local plot=Map.GetPlotByIndex(id)
   local tx,ty=plot:GetX(),plot:GetY()
   assert(visiblePlot(tx,ty):GetIndex()==id,'adjacent target identity')
   local params={[op.PARAM_X]=tx,[op.PARAM_Y]=ty,[op.PARAM_IMPROVEMENT_TYPE]=row.Hash}
   local legal=bool(UnitManager.CanStartOperation(u,operation,nil,params),'adjacent legality')
   local head=table.concat({'A',n(u:GetID()),n(tx),n(ty),n(id),
     n(integer(u:GetBuildCharges(),'charges',0,4294967295)),string.format('%.17g',remaining)},'|')
   local tail=table.concat({n(row.Index),n(bits(row.Hash)),name,n(key),n(x),n(y),n(source:GetIndex())},'|')
   add(u,head,tail,legal,row,operation,params,nil)
  end
 end
end
"""

LUA = "\nlocal function integer(v,label,lo,hi)\n assert(type(v)=='number' and v%1==0 and v>=lo and v<=hi,'invalid unit work '..label);return v\nend\nlocal function bool(v,label) assert(type(v)=='boolean','invalid unit work '..label);return v end\nlocal function n(v) return string.format('%.0f',v) end\nlocal function bits(v) integer(v,'hash',-2147483648,2147483647);return v<0 and v+4294967296 or v end\nlocal function ready()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'stale unit work perspective')\n local p=Players[pid]\n assert(p and p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,'unit work player not ready')\n return p\nend\nlocal player=ready()\nlocal visibility=PlayersVisibility[pid];assert(visibility,'unit work visibility missing')\nlocal op=UnitOperationTypes\nfor _,key in ipairs({'BUILD_IMPROVEMENT','PARAM_X','PARAM_Y','PARAM_IMPROVEMENT_TYPE'}) do integer(op[key],key,-2147483648,2147483647) end\nlocal function ownUnits()\n local list,seen,count={},{},0\n for _,u in player:GetUnits():Members() do\n  count=count+1;assert(count<=4096 and u:GetOwner()==pid,'unit work ownership/count')\n  local id=integer(u:GetID(),'unit',0,4294967295);assert(not seen[id],'duplicate unit work unit');seen[id]=true\n  list[#list+1]=u\n end\n return list\nend\nlocal function visiblePlot(x,y)\n local p=Map.GetPlot(x,y);assert(p and visibility:IsVisible(x,y)==true and visibility:IsRevealed(p:GetIndex())==true,'unit work target not visible')\n return p\nend\n" + ADJACENT_LUA + "\nlocal function offers()\n local result={}\n local function add(u,head,tail,legal,row,operation,params,results)\n  assert(#result<4096,'unit work offer bound')\n  result[#result+1]={wire=head..'|'..tail,legal=legal,unit=u,row=row,operation=operation,params=params,results=results}\n end\n for _,u in ipairs(ownUnits()) do\n  local remaining=u:GetMovesRemaining()\n  assert(type(remaining)=='number' and remaining==remaining and remaining>=0 and remaining<=2147483648,'unit work moves')\n  if remaining>0 then\n   local x,y=u:GetX(),u:GetY();integer(x,'x',0,4294967295);integer(y,'y',0,4294967295)\n   local p=visiblePlot(x,y)\n   local common\n   local function unitFields()\n    if not common then\n     common=table.concat({n(u:GetID()),n(x),n(y),n(integer(p:GetIndex(),'plot',0,4294967295)),\n      n(integer(u:GetBuildCharges(),'charges',0,4294967295)),string.format('%.17g',remaining)},'|')\n    end\n    return common\n   end\n   local params={[op.PARAM_X]=x,[op.PARAM_Y]=y}\n   local can,details=UnitManager.CanStartOperation(u,op.BUILD_IMPROVEMENT,nil,params,true)\n   bool(can,'improvement visibility')\n   if can and details and details[UnitOperationResults.IMPROVEMENTS] then\n    local selectors=details[UnitOperationResults.IMPROVEMENTS];assert(type(selectors)=='table','improvement selectors')\n    local seen,count={},0\n    for _,selector in ipairs(selectors) do\n     count=count+1;assert(count<=4096,'improvement selector bound')\n     local key=bits(selector);assert(not seen[key],'duplicate improvement selector');seen[key]=true\n     local row=GameInfo.Improvements[selector];assert(row,'unknown native improvement')\n     local name=row.ImprovementType\n     assert(type(name)=='string' and #name<=112 and string.match(name,'^IMPROVEMENT_[A-Z0-9_]+$'),'improvement type')\n     integer(row.Index,'improvement index',0,4294967295);bits(row.Hash)\n     local selected={[op.PARAM_X]=x,[op.PARAM_Y]=y,[op.PARAM_IMPROVEMENT_TYPE]=selector}\n     local permitted,results=UnitManager.CanStartOperation(u,op.BUILD_IMPROVEMENT,nil,selected,true)\n     local legal=bool(permitted,'improvement legality')\n     -- The native result supplies selectors; the official click submits Hash.\n     local request={[op.PARAM_X]=x,[op.PARAM_Y]=y,[op.PARAM_IMPROVEMENT_TYPE]=row.Hash}\n     add(u,'I|'..unitFields(),table.concat({n(row.Index),n(bits(row.Hash)),name,n(key)},'|'),legal,row,op.BUILD_IMPROVEMENT,request,results)\n    end\n   end\n   if adjacentEnabled then adjacentOffers(add,u,x,y,p,remaining) end\n   for _,name in ipairs({'HARVEST_RESOURCE','REMOVE_FEATURE','REMOVE_IMPROVEMENT','REPAIR','REPAIR_ROUTE'}) do\n    local row=GameInfo.UnitOperations['UNITOPERATION_'..name]\n    if row and row.VisibleInUI then\n     local immediate=row.InterfaceMode==nil or DB.MakeHash(row.InterfaceMode)==InterfaceModeTypes.NONE\n     assert(immediate,'terrain operation requires unimplemented interface mode')\n     -- Generic UnitPanel actions use operationRow.Hash; enum aliases are not\n     -- guaranteed to exist (the installed Base API omits REPAIR_ROUTE).\n     local operation=integer(row.Hash,name,-2147483648,2147483647)\n     if bool(UnitManager.CanStartOperation(u,operation,nil,true),'operation visibility') then\n      local permitted,results=UnitManager.CanStartOperation(u,operation,nil,false,OperationResultsTypes.NO_TARGETS)\n      local legal=bool(permitted,'operation legality')\n      add(u,'O|'..unitFields(),name..'|'..n(bits(operation)),legal,row,operation,nil,results)\n     end\n    end\n   end\n  end\n end\n ready();return result\nend\n"

def preamble(pid, turn, *, adjacent=False):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    p = load_pinned_json(ROOT / 'work/unit-work932/source.json', SOURCE_SHA)
    if p['schema'] != 'civ6rl.unit_work932.source.v1' or p['contracts']['rules_reimplemented'] is not False:
        raise RuntimeError('Unit work route source differs')
    enabled = 'true' if adjacent else 'false'
    return f'local pid,turn={pid},{turn}\nlocal adjacentEnabled={enabled}\n'.encode() + LUA.encode()

def catalog_source(pid, turn, *, adjacent=False):
    return preamble(pid, turn, adjacent=adjacent) + b"local out={'work-v1|'..n(pid)..'|'..n(turn)}\nfor _,a in ipairs(offers()) do out[#out+1]=a.wire..'|'..(a.legal and '1' or '0') end\nreturn table.concat(out,'\\n')\n"

def parse_catalog(raw, pid, turn, *, adjacent=False):
    uint(pid, 'player', 63)
    uint(turn, 'turn', 2147483647)
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded unit work catalogue')
    rows = raw.decode('ascii').splitlines()
    if not rows or rows[0] != f'work-v1|{pid}|{turn}' or len(rows) > 4097:
        raise ValueError('Foreign unit work catalogue')
    result = dict(player_id=pid, turn=turn, enabled=True, offers=[])
    for line in rows[1:]:
        v = line.split('|')
        lengths = {'I': 12, 'O': 10}
        if adjacent:
            lengths['A'] = 15
        if len(v) != lengths.get(v[0]) or v[-1] not in ('0', '1'):
            raise ValueError('Malformed unit work row')
        a = dict(zip(('unit_id', 'x', 'y', 'plot_id', 'charges'), map(int, v[1:6])), moves_token=v[6])
        if v[0] in ('I', 'A'):
            a.update(kind='build_improvement', index=int(v[7]), hash=int(v[8]), item_type=v[9], selector=int(v[10]))
            if v[0] == 'A':
                a.update(kind='build_improvement_adjacent', source_x=int(v[11]),
                         source_y=int(v[12]), source_plot_id=int(v[13]))
        else:
            a.update(kind='terrain_operation', operation=v[7], hash=int(v[8]))
        if wire(a) + '|' + v[-1] != line:
            raise ValueError('Noncanonical unit work row')
        result['offers'].append(dict(action=a, legal=v[-1] == '1'))
    return validate_catalog(result, pid, turn)

def catalog(prefix, turn, *, player_id=0, adjacent=False):
    raw = prefix.runtime.evaluate_text(prefix.ui_child, catalog_source(player_id, turn, adjacent=adjacent), b'@explicit_unit_work_catalog', capacity=LIMIT + 1)
    return parse_catalog(raw, player_id, turn, adjacent=adjacent)

def request_source(action, pid, turn):
    token = wire(action)
    return preamble(pid, turn, adjacent=action['kind'] == 'build_improvement_adjacent') + f"\nlocal chosen=nil\nfor _,a in ipairs(offers()) do if a.wire=='{token}' then assert(not chosen,'duplicate unit work choice');chosen=a end end\nassert(chosen and chosen.legal,'unit work choice changed or disabled')\nready()\nif chosen.params then UnitManager.RequestOperation(chosen.unit,chosen.operation,chosen.params)\nelse UnitManager.RequestOperation(chosen.unit,chosen.operation) end\nreturn 'submitted'\n".encode()

def effect_source(action, pid, turn):
    validate_action(action)
    return preamble(pid, turn) + f"\nlocal p=visiblePlot({action['x']},{action['y']})\nassert(p:GetIndex()=={action['plot_id']},'unit work effect plot changed')\nlocal found=nil\nfor _,u in ipairs(ownUnits()) do if u:GetID()=={action['unit_id']} then found=u end end\nlocal fields={{n(integer(p:GetImprovementType(),'improvement',-1,2147483647)),\n n(integer(p:GetFeatureType(),'feature',-1,2147483647)),n(integer(p:GetRouteType(),'route',-1,2147483647)),\n bool(p:IsImprovementPillaged(),'improvement pillaged') and '1' or '0',bool(p:IsRoutePillaged(),'route pillaged') and '1' or '0'}}\n-- Match the existing observation predicate: unrevealed resources and absence\n-- have the same external representation; no raw hidden type/count is returned.\nlocal resource,amount=-1,0\nlocal rawResource=integer(p:GetResourceType(),'resource',-1,2147483647)\nif rawResource>=0 then\n local definition=GameInfo.Resources[rawResource];assert(definition,'resource definition missing')\n if bool(player:GetResources():IsResourceVisible(definition.Hash),'resource visibility') then\n  resource=rawResource;amount=integer(p:GetResourceCount(),'resource amount',0,2147483647)\n end\nend\nfields[#fields+1]=n(resource);fields[#fields+1]=n(amount)\nif found then\n fields[#fields+1]='present';fields[#fields+1]=n(integer(found:GetBuildCharges(),'charges',0,4294967295))\n fields[#fields+1]=string.format('%.17g',found:GetMovesRemaining())\nelse fields[#fields+1]='consumed' end\nready();return table.concat(fields,'|')\n".encode()

def parse_effect(raw):
    if type(raw) is not bytes or len(raw) > 256:
        raise ValueError('Invalid unit work effect')
    v = raw.decode('ascii').split('|')
    if len(v) not in (8, 10) or v[3] not in ('0', '1') or v[4] not in ('0', '1') or ((v[7], len(v)) not in (('present', 10), ('consumed', 8))):
        raise ValueError('Malformed unit work effect')
    r = dict(improvement=int(v[0]), feature=int(v[1]), route=int(v[2]), improvement_pillaged=v[3] == '1', route_pillaged=v[4] == '1', resource=int(v[5]), resource_count=uint(int(v[6]), 'resource count', 2147483647), unit_present=v[7] == 'present')
    if any((not -1 <= r[k] <= 2147483647 for k in ('improvement', 'feature', 'route', 'resource'))):
        raise ValueError('Invalid plot definition index')
    if r['resource'] == -1 and r['resource_count'] != 0:
        raise ValueError('Hidden or absent resource has count')
    if r['unit_present']:
        r.update(charges=uint(int(v[8]), 'charges'), moves=float(v[9]))
        if not math.isfinite(r['moves']) or not 0 <= r['moves'] <= 2 ** 31:
            raise ValueError('Invalid effect movement')
    return r

def apply(owner, prefix, action, turn, before, *, player_id=0):
    validate_action(action)
    pid = player_id
    adjacent = action['kind'] == 'build_improvement_adjacent'
    if action not in actions(catalog(prefix, turn, player_id=pid, adjacent=adjacent)):
        raise RuntimeError('Unit work choice no longer offered')

    def state():
        return parse_effect(prefix.runtime.evaluate_text(prefix.ui_child, effect_source(action, pid, turn), b'@explicit_unit_work_effect'))
    start = state()
    submitted = prefix.runtime.evaluate_text(prefix.ui_child, request_source(action, pid, turn), b'@explicit_unit_work_request')
    if submitted != b'submitted' or len(prefix.actions.pending) != 1:
        raise RuntimeError('Unit work did not enqueue exactly one native command')
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()
    end = state()
    after = observe_player(prefix.runtime, prefix.ui_child, pid)
    if after['turn'] != turn or after['player_id'] != pid:
        raise RuntimeError('Unit work crossed actor/turn')
    if action['kind'] != 'terrain_operation' and (end['improvement'] != action['index'] or start['improvement'] == end['improvement']):
        raise RuntimeError('Native improvement change absent')
    if action['kind'] == 'terrain_operation':
        removed = {'REMOVE_IMPROVEMENT': 'improvement', 'REMOVE_FEATURE': 'feature', 'HARVEST_RESOURCE': 'resource'}
        repaired = {'REPAIR': 'improvement_pillaged', 'REPAIR_ROUTE': 'route_pillaged'}
        operation = action['operation']
        if operation in removed:
            field = removed[operation]
            if start[field] < 0 or end[field] != -1:
                raise RuntimeError('Native terrain removal absent')
        elif start[repaired[operation]] is not True or end[repaired[operation]] is not False:
            raise RuntimeError('Native terrain repair absent')
    owner.emit('official_explicit_unit_work_effect', action=action, plot_before=start, plot_after=end, observation_before=before, observation_after=after, automatic_choices_applied=False, strategic_training_ready=False)
    return after
