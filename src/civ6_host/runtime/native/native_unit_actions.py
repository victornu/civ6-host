"""Bounded UI Lua requests using Core's own operation legality and serializer.

Source: native-unit-action-route.json. Returned Lua success only means request
submission; the caller must receive/drain the native message, refresh the view,
and verify its gameplay effect independently before admitting a transition.
"""
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _SESSION_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path

def _identifier(value, label, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'Invalid native {label}')
    return str(value).encode('ascii')

def found_city_candidate_source(player_id, unit_id=None):
    player = _identifier(player_id, 'player ID', 63)
    selected = b'nil' if unit_id is None else _identifier(unit_id, 'unit ID', 4294967295)
    return b'local selectedID=' + selected + b'\nlocal pid=' + player + b"\nassert(UnitManager and type(UnitManager.CanStartOperation)=='function','native operation API unavailable')\nlocal p=Players[pid]\nassert(p and p:IsAlive() and p:IsTurnActive(),'requested player is not active')\nlocal candidate=nil\nlocal count=0\nfor _,u in p:GetUnits():Members() do\n  count=count+1\n  assert(count<=4096,'unit enumeration exceeds bound')\n  assert(u:GetOwner()==pid,'foreign unit in own-unit collection')\n  if (selectedID==nil or u:GetID()==selectedID) and UnitManager.CanStartOperation(u,'UNITOPERATION_FOUND_CITY',nil,false) then\n    if candidate==nil or u:GetID()<candidate:GetID() then candidate=u end\n  end\nend\nif candidate==nil then return 'none' end\nreturn string.format('%d,%d,%d,%d,%d',pid,candidate:GetID(),candidate:GetType(),candidate:GetX(),candidate:GetY())\n"

def found_city_catalog_source(player_id, turn, *, core_sha256=_SESSION_BASE_CORE_SHA256):
    """Expose every currently legal founder; the caller chooses the unit."""
    from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256
    if core_sha256 == BASE_CORE_SHA256:
        from civ6_host.runtime.native.native_unit_skip import verify_source
        verify_source()
    elif core_sha256 in (XP1_CORE_SHA256, XP2_CORE_SHA256):
        from civ6_host.runtime.xp1_status_profiles import verify_source
        from civ6_host.runtime.unit_operation_ui_profile import source as unit_source
        verify_source(core_sha256)
        unit_source(core_sha256=core_sha256)
    else:
        raise ValueError('Unknown engine for shared founder catalogue')
    pid = _identifier(player_id, 'player ID', 63)
    expected = _identifier(turn, 'turn', 4294967295)
    return b'local pid,expectedTurn=' + pid + b',' + expected + b"\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and\n Game.GetCurrentGameTurn()==expectedTurn and Game.IsAllowStrategicCommands(pid)==true,'foundation perspective/turn')\nlocal p=Players[pid]\nassert(p and p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,'foundation player not ready')\nlocal rows,seen,count={}, {},0\nfor _,u in p:GetUnits():Members() do\n count=count+1;assert(count<=4096 and u:GetOwner()==pid,'foundation unit collection')\n local id=u:GetID();assert(type(id)=='number' and id%1==0 and id>=0 and id<=4294967295 and not seen[id],'foundation ID')\n seen[id]=true\n local can=UnitManager.CanStartOperation(u,'UNITOPERATION_FOUND_CITY',nil,false)\n assert(type(can)=='boolean','foundation legality is not Boolean')\n if can then rows[#rows+1]={id,u:GetX(),u:GetY()} end\nend\ntable.sort(rows,function(a,b) return a[1]<b[1] end)\nlocal out={string.format('%d,%d,%d',pid,expectedTurn,#rows)}\nfor _,r in ipairs(rows) do out[#out+1]=string.format('%.0f,%d,%d',r[1],r[2],r[3]) end\nreturn table.concat(out,';')\n"

def parse_founders(raw, player_id, turn):
    from civ6_host.runtime.native.native_unit_skip import _parse_uint32
    if type(raw) is not bytes or len(raw) > 131072:
        raise ValueError('Invalid founder catalogue size')
    rows = raw.split(b';')
    header = rows[0].split(b',')
    if len(header) != 3:
        raise ValueError('Invalid founder header')
    pid, actual, count = [_parse_uint32(v, 'founder header') for v in header]
    if pid != player_id or actual != turn or count > 4096 or (len(rows) != count + 1):
        raise ValueError('Foreign founder catalogue')
    result = []
    previous = -1
    for row in rows[1:]:
        fields = row.split(b',')
        if len(fields) != 3:
            raise ValueError('Invalid founder row')
        uid, x, y = [_parse_uint32(v, 'founder field') for v in fields]
        if uid <= previous or x > 65535 or y > 65535:
            raise ValueError('Duplicate founder or invalid site')
        previous = uid
        result.append(dict(kind='found_city', unit_id=uid, x=x, y=y))
    return result

def request_found_city_source(player_id, unit_id):
    player = _identifier(player_id, 'player ID', 63)
    unit = _identifier(unit_id, 'unit ID', 4294967295)
    return b'local pid,uid=' + player + b',' + unit + b"\nlocal p=Players[pid]\nassert(p and p:IsAlive() and p:IsTurnActive(),'requested player is not active')\nassert(UnitManager and type(UnitManager.CanStartOperation)=='function' and\n       type(UnitManager.RequestOperation)=='function','native operation API unavailable')\nlocal selected=nil\nlocal count=0\nfor _,u in p:GetUnits():Members() do\n  count=count+1\n  assert(count<=4096,'unit enumeration exceeds bound')\n  if u:GetID()==uid then\n    assert(selected==nil and u:GetOwner()==pid,'ambiguous or foreign unit')\n    selected=u\n  end\nend\nassert(selected~=nil,'requested own unit unavailable')\nassert(UnitManager.CanStartOperation(selected,'UNITOPERATION_FOUND_CITY',nil,false),\n       'native found-city legality check rejected request')\nUnitManager.RequestOperation(selected,'UNITOPERATION_FOUND_CITY')\nreturn 'submitted'\n"

def action_guard_case():
    """Run actual request chunks against stale/illegal/missing-unit sentinels."""
    return b"local active,legal,exists=true,true,true\nlocal submitted=0\nlocal u={GetOwner=function() return 0 end,GetID=function() return 17 end,\n GetType=function() return 0 end,GetX=function() return 3 end,GetY=function() return 4 end}\nlocal Players={[0]={IsAlive=function() return true end,\n IsTurnActive=function() return active end,\n GetUnits=function() return {Members=function()\n   local used=false\n   return function() if not used and exists then used=true;return 1,u end end\n end} end}}\nlocal UnitManager={CanStartOperation=function(unit,kind,excluded,flag)\n assert(unit==u and kind=='UNITOPERATION_FOUND_CITY' and excluded==nil and flag==false)\n return legal\nend,RequestOperation=function(unit,kind)\n assert(active and legal and exists and unit==u and kind=='UNITOPERATION_FOUND_CITY')\n submitted=submitted+1\nend}\nlocal function candidate()\n" + found_city_candidate_source(0) + b'end\nlocal function request()\n' + request_found_city_source(0, 17) + b"end\nassert(candidate()=='0,17,0,3,4' and submitted==0)\nlegal=false\nassert(candidate()=='none')\nassert(not pcall(request) and submitted==0,'stale legality was not rechecked')\nlegal=true;active=false\nassert(not pcall(request) and submitted==0,'inactive player submitted an action')\nactive=true;exists=false\nassert(not pcall(request) and submitted==0,'missing unit submitted an action')\nexists=true\nassert(request()=='submitted' and submitted==1)\nreturn 'action-guards-ok'\n"
