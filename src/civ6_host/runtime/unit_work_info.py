"""Read UnitPanel-displayed result fields alongside the existing native offers.

The extracted adapter retains the results of its existing availability calls.
No extra availability query, rule formula, or privileged state is introduced.
"""
from civ6_host.contracts.unit_work_info import SCHEMA, MAX_BYTES, validate

_XP2_PANEL_SOURCE = (
    'evidence/host-xp2-adjacent-improvement-ui-route.json',
    '7a501a0461cfa0e7113f0dbe5bd5a6874e793e226b02957be43bbba166c47408',
)


def xp2_source_dependencies():
    """Pin the Base panel and the two installed XP2 replacements that include it."""
    from pathlib import Path
    from .configuration_profiles import XP2_CORE_SHA256, _source
    from .native.native_saved_unit_work import ROOT, SOURCE_SHA
    from .native.native_source_cache import load_pinned_json
    from .resource_resolution import resolve_path

    ui_path = 'Base/Assets/UI/Panels/UnitPanel.lua'
    source_path = resolve_path(ROOT / 'work/unit-work932/source.json')
    base_panel = load_pinned_json(source_path, SOURCE_SHA)['official_ui'][0]
    selected = _source(_XP2_PANEL_SOURCE)
    if (selected['core_sha256'] != XP2_CORE_SHA256
            or selected['sources'][ui_path] != base_panel['sha256']
            or not Path(base_panel['path']).as_posix().endswith('/' + ui_path)):
        raise ValueError('Gathering Storm UnitPanel source selection differs')
    game_root = resolve_path(Path(base_panel['path'])).parents[4]
    files = (ui_path, 'DLC/Expansion2/UI/Replacements/UnitPanel_Expansion1.lua',
             'DLC/Expansion2/UI/Replacements/UnitPanel_Expansion2.lua')
    return {
        str(resolve_path(ROOT / _XP2_PANEL_SOURCE[0])): _XP2_PANEL_SOURCE[1],
        **{str(resolve_path(game_root / path)): selected['sources'][path] for path in files},
    }


LUA = r'''
local out={'work-info-v1|'..n(pid)..'|'..n(turn)}
local function hex(s)
 assert(type(s)=='string' and #s<=4096 and not string.find(s,'\0',1,true),'invalid UnitPanel text')
 return (string.gsub(s,'.',function(c) return string.format('%02x',string.byte(c)) end))
end
local function localized(v)
 assert(type(v)=='string','invalid UnitPanel localization input')
 return hex(Locale.Lookup(v))
end
local function details(row,index)
 local r=row.results
 if r==nil then return end
 assert(type(r)=='table','invalid UnitPanel results')
 local keys=UnitOperationResults
 local name=r[keys.ACTION_NAME]
 if name~=nil and name~='' and row.row.ImprovementType==nil then
  out[#out+1]='A|'..index..'|'..localized(name)
 end
 local feature=r[keys.FEATURE_TYPE]
 if feature~=nil and row.row.ImprovementType==nil then
  integer(feature,'feature',0,2147483647)
  local def=GameInfo.Features[feature];assert(def,'unknown UnitPanel feature')
  out[#out+1]='F|'..index..'|'..n(feature)..'|'..localized(def.Name)
 end
 local function list(key,tag)
  local values=r[key];if values==nil then return end
  assert(type(values)=='table' and #values<=64,'invalid UnitPanel description list')
  for _,v in ipairs(values) do out[#out+1]=tag..'|'..index..'|'..localized(v) end
 end
 list(keys.ADDITIONAL_DESCRIPTION,'D')
 if not row.legal then list(keys.FAILURE_REASONS,'R') end
end
if processing then
 for index,row in ipairs(offers()) do
  out[#out+1]='O|'..row.wire..'|'..(row.legal and '1' or '0')
  details(row,n(index))
 end
end
for _,u in ipairs(ownUnits()) do
 local p=visiblePlot(u:GetX(),u:GetY())
 out[#out+1]=table.concat({'P',n(integer(u:GetID(),'unit',0,4294967295)),
  n(integer(p:GetIndex(),'plot',0,4294967295)),n(integer(p:GetImprovementType(),'improvement',-1,2147483647)),
  bool(p:IsImprovementPillaged(),'improvement pillaged') and '1' or '0',
  n(integer(p:GetRouteType(),'route',-1,2147483647)),bool(p:IsRoutePillaged(),'route pillaged') and '1' or '0'},'|')
end
ready();return table.concat(out,'\n')
'''


def source(player_id, turn, processing=True):
    if type(processing) is not bool:raise ValueError('Invalid processing guard')
    from .native.native_saved_unit_work import preamble
    return preamble(player_id,turn)+f'\nlocal processing={str(processing).lower()}\n'.encode()+LUA.encode()


def parse(raw, player_id, turn, processing=True):
    if type(raw) is not bytes or len(raw)>MAX_BYTES:
        raise ValueError('Unbounded UnitPanel information frame')
    lines=raw.decode('ascii').splitlines()
    if not lines or lines[0]!=f'work-info-v1|{player_id}|{turn}':
        raise ValueError('Foreign UnitPanel information frame')
    from .native.native_saved_unit_work import parse_catalog
    wires=[];info=[];targets=[]
    def integer(token,lo=0,hi=2**32-1):
        v=int(token)
        if str(v)!=token or not lo<=v<=hi:raise ValueError('Invalid UnitPanel integer')
        return v
    def text(token):
        if len(token)>8192:raise ValueError('Unbounded UnitPanel text')
        data=bytes.fromhex(token)
        if data.hex()!=token:raise ValueError('Noncanonical UnitPanel text')
        return data.decode('utf-8')
    for line in lines[1:]:
        v=line.split('|');tag=v[0]
        if tag=='O':
            if len(wires)>=4096:raise ValueError('Unbounded UnitPanel offers')
            wires.append(line[2:]);info.append(dict(action=None,legal=None,action_name=None,feature=None,descriptions=[],failure_reasons=[]))
        elif tag=='P' and len(v)==7:
            if len(targets)>=4096 or v[4] not in ('0','1') or v[6] not in ('0','1'):
                raise ValueError('Invalid UnitPanel targets')
            targets.append(dict(unit_id=integer(v[1]),plot_id=integer(v[2]),improvement=integer(v[3],-1,2**31-1),
                improvement_pillaged=v[4]=='1',route=integer(v[5],-1,2**31-1),route_pillaged=v[6]=='1'))
        elif tag in ('A','F','D','R') and len(v)==(4 if tag=='F' else 3):
            index=integer(v[1],1,4096)
            if index!=len(info):raise ValueError('UnitPanel detail not bound to current offer')
            row=info[index-1]
            if tag=='F':
                if row['feature'] is not None:raise ValueError('Repeated UnitPanel feature')
                row['feature']=dict(index=integer(v[2],0,2**31-1),name=text(v[3]))
            elif tag=='A':
                if row['action_name'] is not None:raise ValueError('Repeated UnitPanel action name')
                row['action_name']=text(v[2])
            else:
                dest=row['descriptions' if tag=='D' else 'failure_reasons']
                if len(dest)>=64:raise ValueError('Unbounded UnitPanel details')
                dest.append(text(v[2]))
        else:raise ValueError('Unknown UnitPanel information record')
    catalog=parse_catalog(('\n'.join([f'work-v1|{player_id}|{turn}',*wires])+'\n').encode(),player_id,turn)
    if not processing:
        if wires:raise ValueError('Closed guard returned UnitPanel offers')
        catalog['enabled']=False
    for row,offer in zip(info,catalog['offers']):row.update(action=offer['action'],legal=offer['legal'])
    result=dict(schema=SCHEMA,player_id=player_id,turn=turn,offers=info,targets=targets)
    return catalog,validate(result,player_id,turn,work_catalog=catalog)


def read_catalog(prefix, turn, *, player_id, processing):
    raw=prefix.runtime.evaluate_text(prefix.ui_child,source(player_id,turn,processing),
        b'@public_unit_panel_work_information',capacity=MAX_BYTES+1)
    return parse(raw,player_id,turn,processing)
