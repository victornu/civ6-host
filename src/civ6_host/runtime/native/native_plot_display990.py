"""Player-scoped projection of the installed PlotToolTip's displayed fields.

Only the rendered improvement, district status, owner-only worked count and
positive yield text leave this reader. Native getters supply the rules; it does not calculate
terrain, improvement, district or adjacency yields. The only multiplication
is the tooltip's own specialist presentation (plot yield times workers).

This is the shipped Base tooltip projected in the host context, not proof of
the complete client UI or of remembered state on revealed but fogged tiles.
Buildings, wonders, resources and other tooltip sections are out of scope.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import math
from pathlib import Path
import re
SCHEMA = 'civ6rl.plot_display990.v1'
SOURCE_SHA256 = 'fd73dda3ef4e98c69ab75bffe57e17610c226814c97fa98d103cac27a392f1c4'
CAPABILITY_SOURCE_SHA256 = '0e81de39aa32033e4b3ed0660e72f6ca63f3f3bec28ec35d3b61ef780f1ceb0c'
CAPACITY = 16 * 1024 * 1024
_ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_plot_display990.py')))).resolve().parents[1]
_UI = _resolve_resource_path(Path("C:\\Program Files (x86)\\Steam\\steamapps\\common\\Sid Meier's Civilization VI\\Base\\Assets\\UI"))
_PINS = {_UI / 'ToolTips/PlotToolTip.lua': SOURCE_SHA256, _UI / 'Scripts/GameCapabilities.lua': CAPABILITY_SOURCE_SHA256, _ROOT / 'work/phase1-learning989/plot-display-audit.json': '7cb507e278d8c2541bbac33e4b77267c7d05ae2df8a2b611b3215b2f1b1a84aa', _ROOT / 'evidence/native-revealed-plot-observation/cf39cfa0a7da833afc381cd2c2607cd0518182c70d93b895df7918bc8d14d276.json': 'cf39cfa0a7da833afc381cd2c2607cd0518182c70d93b895df7918bc8d14d276', _ROOT / 'evidence/native-player-visibility-static.json': '30690d6ee4e9d208b471955206b67e2ebc48acff6e84480471acc097ee210f86', _ROOT / 'evidence/rea-phase6/0040-plot-yield-governor.c': '543ec6ddfb648d1d5aca8ac6ad4df25d8e327b76a99b67e62b15f41a98b69379', _ROOT / 'evidence/rea-phase6/0050-plot-yield-core.c': '2c9092693b62807ab7c23560f4001ead3009730881bab842bd3a57420f81546a', _ROOT / 'evidence/rea-phase6/0050-plot-yield-core.response.json': 'b5ec01a30dca862a7b12198a531f3d3fb7e059d05e804a00beee9203a65dabbe'}
FIELDS = {'schema', 'player_id', 'turn', 'width', 'height', 'yields_enabled', 'source_sha256', 'capability_source_sha256', 'plots'}
PLOT_FIELDS = {'plot_id', 'improvement', 'district', 'worked', 'plot_yields', 'specialist_yields', 'district_yields'}
YIELD_FIELDS = ('plot_yields', 'specialist_yields', 'district_yields')
_ID = re.compile('[A-Z][A-Z0-9_]{0,127}\\Z')
_NUMBER = re.compile('(?:0|[1-9][0-9]*)(?:\\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\\Z')

def verified_sources():
    """Return the exact files required by the native source closure."""
    for path, expected in _PINS.items():
        if hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest() != expected:
            raise RuntimeError('Pinned plot display source changed: ' + str(path))
    proof = json.loads(_resolve_resource_path(_ROOT / 'evidence/rea-phase6/0050-plot-yield-core.response.json').read_bytes())['structuredContent']
    if proof['subject']['digest']['sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof['operation'] != 'procedure_pseudo_code' or proof['parameters']['procedure'] != '0x18027db40':
        raise RuntimeError('Plot yield native proof identity changed')
    return dict(_PINS)

def _integer(value, label, minimum=0, maximum=2147483647):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError('Invalid plot display ' + label)
    return value

def source(player_id, turn):
    verified_sources()
    pid = _integer(player_id, 'player', maximum=63)
    expected = _integer(turn, 'turn')
    return 'local pid=__PID__;local expectedTurn=__TURN__\nlocal function context()\n assert(Game and type(Game.GetLocalPlayer)==\'function\' and Game.GetLocalPlayer()==pid,\n        \'plot display local player mismatch\')\n assert(type(Game.GetLocalObserver)==\'function\' and Game.GetLocalObserver()==pid,\n        \'plot display observer mismatch\')\n assert(Game.GetCurrentGameTurn()==expectedTurn,\'plot display turn mismatch\')\nend\ncontext()\nassert(Players and Players[pid],\'plot display player unavailable\')\nlocal visibility=assert(PlayersVisibility and PlayersVisibility[pid],\'plot display reveal unavailable\')\nassert(type(visibility.IsRevealed)==\'function\',\'plot display reveal API unavailable\')\nassert(GameInfo and GameInfo.GameCapabilities,\'native capabilities unavailable\')\n-- EXACT expression of shipped GameCapabilities.HasCapability, lines 6-8.\n-- A missing native capabilities collection is an error, never a true default.\nlocal yieldsEnabled=GameInfo.GameCapabilities[\'CAPABILITY_DISPLAY_PLOT_YIELDS\']~=nil\nassert(GameInfo.Districts and GameInfo.Improvements and GameInfo.Yields,\'plot display metadata unavailable\')\nlocal function whole(v,lo,hi)\n assert(type(v)==\'number\' and v==math.floor(v) and v>=lo and v<=hi,\'invalid plot display integer\')\n return string.format(\'%.17g\',v)\nend\nlocal function flag(v)\n assert(type(v)==\'boolean\',\'invalid plot display Boolean\');return v\nend\nlocal function bool(v)return flag(v) and \'true\' or \'false\' end\nlocal function ident(v,prefix)\n assert(type(v)==\'string\' and #v<=128 and v:match(\'^[A-Z][A-Z0-9_]*$\') and\n        v:sub(1,#prefix)==prefix,\'invalid plot display type\')\n return \'"\'..v..\'"\'\nend\nlocal function row(parts)return \'{\'..table.concat(parts,\',\')..\'}\'end\nlocal function positive(v)\n assert(type(v)==\'number\' and v==v and math.abs(v)<=1e12,\'invalid native plot yield\')\n if v<=0 then return nil end\n -- View uses tostring(v); never publish precision hidden by that display.\n local shown=tostring(v)\n assert(#shown<=64 and tonumber(shown) and tonumber(shown)>0,\'invalid shown plot yield\')\n return \'"\'..shown..\'"\'\nend\nlocal function yieldList(items)\n table.sort(items,function(a,b)return a.type<b.type end)\n local out={};local seen={}\n for _,item in ipairs(items)do\n  assert(not seen[item.type],\'duplicate public yield type\');seen[item.type]=true\n  out[#out+1]=row({\'"type":\'..ident(item.type,\'YIELD_\'),\'"value":\'..item.value})\n end\n assert(#out<=256,\'plot yield count bound\');return \'[\'..table.concat(out,\',\')..\']\'\nend\nlocal function metadata(collection,index,key,prefix)\n whole(index,-1,2147483647)\n if index==-1 then return nil end\n local m=assert(collection[index],\'native plot metadata row missing\')\n assert(m.Index==index,\'native plot metadata index mismatch\');ident(m[key],prefix)\n return m\nend\nlocal function yields(plot,isCity,districtID,wantPlot,wantDistrict,owner,workers)\n local ps,ds={},{}\n if not yieldsEnabled or (not wantPlot and not wantDistrict) then return ps,ds end\n if isCity or districtID==-1 then\n  assert(not wantDistrict,\'inconsistent district yield branch\')\n  for y in GameInfo.Yields() do\n   whole(y.Index,0,2147483647);ident(y.YieldType,\'YIELD_\')\n   local shown=positive(plot:GetYield(y.Index))\n   if shown then ps[#ps+1]={type=y.YieldType,value=shown} end\n   assert(#ps<=256,\'plot yield count bound\')\n  end\n else\n  whole(owner,0,63)\n  local p=assert(Players[owner],\'district owner unavailable\')\n  local district=p:GetDistricts():FindID(districtID)\n  if district~=nil then\n   for y in GameInfo.Yields() do\n    whole(y.Index,0,2147483647);ident(y.YieldType,\'YIELD_\')\n    if wantPlot then\n     assert(owner==pid and workers~=nil,\'private specialist context unavailable\')\n     local value=plot:GetYield(y.Index);positive(value)\n     if value>0 and workers>0 then\n      ps[#ps+1]={type=y.YieldType,value=positive(value*workers)}\n     end\n    end\n    if wantDistrict then\n     local shown=positive(district:GetYield(y.Index))\n     if shown then ds[#ds+1]={type=y.YieldType,value=shown} end\n    end\n    assert(#ps<=256 and #ds<=256,\'district yield count bound\')\n   end\n  end\n end\n return ps,ds\nend\nassert(Map and Map.GetGridSize and Map.GetPlotCount and Map.GetPlotByIndex,\'plot map API unavailable\')\nlocal width,height=Map.GetGridSize();local count=Map.GetPlotCount()\nwhole(width,1,16384);whole(height,1,16384);whole(count,1,16384)\nassert(width*height==count,\'plot display map dimensions differ\')\nlocal rows={}\nfor index=0,count-1 do\n -- Reveal is checked BEFORE even acquiring a plot handle or reading details.\n if flag(visibility:IsRevealed(index)) then\n  local plot=assert(Map.GetPlotByIndex(index),\'revealed plot handle missing\')\n  local owner=plot:GetOwner();whole(owner,-1,63)\n  local worked,workers=\'null\',nil\n  -- View:535-538 renders this owner-only label independently of all the\n  -- city/district/impassable branches and the plot-yield capability.\n  if owner==pid then\n   workers=plot:GetWorkerCount();whole(workers,0,2147483647)\n   if workers>0 then worked=whole(workers,1,2147483647) end\n  end\n  local isCity=flag(plot:IsCity())\n  local districtID=plot:GetDistrictID();whole(districtID,-1,2147483647)\n  local districtType=plot:GetDistrictType()\n  local districtMeta=metadata(GameInfo.Districts,districtType,\'DistrictType\',\'DISTRICT_\')\n  local improvement,district=\'null\',\'null\';local py,sy,dy={},{},{}\n  -- These are the exclusive View branches at PlotToolTip.lua:416-490.\n  if isCity and districtMeta then\n   district=row({\'"type":\'..ident(districtMeta.DistrictType,\'DISTRICT_\'),\'"status":"city"\'})\n   py=select(1,yields(plot,isCity,districtID,true,false,owner,workers))\n  elseif districtID~=-1 and districtMeta then\n   if not flag(districtMeta.InternalOnly) then\n    local pillaged,complete=false,false\n    local city=Cities.GetPlotPurchaseCity(plot)\n    if city then\n     local cityDistricts=city:GetDistricts()\n     if cityDistricts then\n      pillaged=flag(cityDistricts:IsPillaged(districtType,index))\n      -- Completeness is not displayed when the pillaged suffix wins.\n      if not pillaged then complete=flag(cityDistricts:IsComplete(districtType,index)) end\n     end\n    end\n    local status=pillaged and \'pillaged\' or (complete and \'complete\' or \'constructing\')\n    district=row({\'"type":\'..ident(districtMeta.DistrictType,\'DISTRICT_\'),\'"status":"\'..status..\'"\'})\n    sy,dy=yields(plot,isCity,districtID,owner==pid,true,owner,workers)\n   end\n  elseif flag(plot:IsImpassable()) then\n   -- These branches render no improvement, district or yield fields; the\n   -- independent owner-only worked label is retained below.\n  else\n   local m=metadata(GameInfo.Improvements,plot:GetImprovementType(),\'ImprovementType\',\'IMPROVEMENT_\')\n   if m then improvement=row({\'"type":\'..ident(m.ImprovementType,\'IMPROVEMENT_\'),\n       \'"pillaged":\'..bool(plot:IsImprovementPillaged())}) end\n   py=select(1,yields(plot,isCity,districtID,true,false,owner,workers))\n  end\n  rows[#rows+1]=row({\'"plot_id":\'..whole(index,0,count-1),\'"worked":\'..worked,\'"improvement":\'..improvement,\n   \'"district":\'..district,\'"plot_yields":\'..yieldList(py),\'"specialist_yields":\'..yieldList(sy),\n   \'"district_yields":\'..yieldList(dy)})\n end\nend\ncontext()\nlocal w2,h2=Map.GetGridSize()\nassert(w2==width and h2==height and Map.GetPlotCount()==count,\'plot display map changed\')\nassert((GameInfo.GameCapabilities[\'CAPABILITY_DISPLAY_PLOT_YIELDS\']~=nil)==yieldsEnabled,\n       \'plot display capability changed\')\nlocal out=row({\'"schema":"civ6rl.plot_display990.v1"\',\'"player_id":\'..whole(pid,0,63),\n \'"turn":\'..whole(expectedTurn,0,2147483647),\'"width":\'..whole(width,1,16384),\n \'"height":\'..whole(height,1,16384),\'"yields_enabled":\'..bool(yieldsEnabled),\n \'"source_sha256":"__SOURCE__"\',\'"capability_source_sha256":"__CAPABILITY__"\',\n \'"plots":[\'..table.concat(rows,\',\')..\']\'})\nassert(#out<16777216,\'plot display result bound\')\nreturn out\n'.replace('__PID__', str(pid)).replace('__TURN__', str(expected)).replace('__SOURCE__', SOURCE_SHA256).replace('__CAPABILITY__', CAPABILITY_SOURCE_SHA256).encode('ascii')

def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate plot display JSON key')
        result[key] = value
    return result

def _type(value, prefix):
    if type(value) is not str or not _ID.fullmatch(value) or (not value.startswith(prefix)):
        raise ValueError('Invalid public plot type')

def parse(payload, player_id, turn):
    """Strict wire validator; no installed files or native process are needed."""
    _integer(player_id, 'player', maximum=63)
    _integer(turn, 'turn')
    if type(payload) is str:
        try:
            payload = payload.encode('ascii')
        except UnicodeEncodeError as exc:
            raise ValueError('Non-ASCII plot display payload') from exc
    if type(payload) is not bytes or not 0 < len(payload) < CAPACITY:
        raise ValueError('Invalid plot display payload bound')
    try:
        value = json.loads(payload.decode('ascii'), object_pairs_hook=_unique, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite plot display')))
    except (UnicodeDecodeError, RecursionError) as exc:
        raise ValueError('Invalid plot display JSON') from exc
    if type(value) is not dict or set(value) != FIELDS or value['schema'] != SCHEMA or (type(value['player_id']) is not int) or (value['player_id'] != player_id) or (type(value['turn']) is not int) or (value['turn'] != turn) or (type(value['yields_enabled']) is not bool) or (value['source_sha256'] != SOURCE_SHA256) or (value['capability_source_sha256'] != CAPABILITY_SOURCE_SHA256):
        raise ValueError('Foreign or malformed public plot display')
    width = _integer(value['width'], 'width', 1, 16384)
    height = _integer(value['height'], 'height', 1, 16384)
    if width * height > 16384 or type(value['plots']) is not list or len(value['plots']) > width * height:
        raise ValueError('Invalid public plot display dimensions')
    previous = -1
    for p in value['plots']:
        if type(p) is not dict or set(p) != PLOT_FIELDS:
            raise ValueError('Invalid public plot display fields')
        index = _integer(p['plot_id'], 'index', 0, width * height - 1)
        if index <= previous:
            raise ValueError('Duplicate or unordered public plot')
        previous = index
        if p['worked'] is not None:
            _integer(p['worked'], 'displayed worked count', 1)
        improvement, district = (p['improvement'], p['district'])
        if improvement is not None:
            if type(improvement) is not dict or set(improvement) != {'type', 'pillaged'} or type(improvement['pillaged']) is not bool:
                raise ValueError('Invalid public improvement')
            _type(improvement['type'], 'IMPROVEMENT_')
        if district is not None:
            if type(district) is not dict or set(district) != {'type', 'status'} or district['status'] not in ('city', 'complete', 'constructing', 'pillaged') or (improvement is not None):
                raise ValueError('Invalid public district')
            _type(district['type'], 'DISTRICT_')
        for key in YIELD_FIELDS:
            entries = p[key]
            if type(entries) is not list or len(entries) > 256 or (entries and (not value['yields_enabled'])):
                raise ValueError('Invalid public yield list')
            seen = ''
            for item in entries:
                if type(item) is not dict or set(item) != {'type', 'value'}:
                    raise ValueError('Invalid displayed yield fields')
                _type(item['type'], 'YIELD_')
                text = item['value']
                if item['type'] <= seen or type(text) is not str or len(text) > 64 or (not _NUMBER.fullmatch(text)) or (not math.isfinite(float(text))) or (not 0 < float(text) <= 1000000000000.0):
                    raise ValueError('Invalid displayed positive yield')
                seen = item['type']
        if district is None or district['status'] == 'city':
            if p['specialist_yields'] or p['district_yields']:
                raise ValueError('District yield outside displayed district branch')
        elif p['plot_yields']:
            raise ValueError('Ordinary yield inside displayed district branch')
    return value

def observe(prefix, visible):
    from civ6_host.runtime.native.native_player_observation import parse_player_observation
    if type(visible) is not dict:
        raise ValueError('Missing visible plot observation')
    observation = parse_player_observation(json.dumps(visible, allow_nan=False), visible.get('player_id'))
    pid, turn = (observation['player_id'], observation['turn'])
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source(pid, turn), b'@explicit_plot_display990', capacity=CAPACITY)
    result = parse(raw, pid, turn)
    if any((result[k] != observation[k] for k in ('width', 'height'))):
        raise ValueError('Plot display and visible map dimensions differ')
    rendered = {p['plot_id']: p for p in result['plots']}
    for plot in observation['plots']:
        if plot['index'] not in rendered:
            raise ValueError('Visible plot absent from revealed display')
        if plot['owner'] != pid and rendered[plot['index']]['specialist_yields']:
            raise ValueError('Foreign specialist display leaked')
        if plot['owner'] != pid and rendered[plot['index']]['worked'] is not None:
            raise ValueError('Foreign worked count display leaked')
    return result
