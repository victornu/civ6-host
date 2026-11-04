"""Read native chooser costs, turns and boosts through the shipped UI getters.

Only presentation of the turn count is reproduced (999 cap, -1 hidden).
Research costs, durations and boost rules remain inside the official GameCore.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from civ6_host.runtime.native import native_saved_research_progress971 as progress
from civ6_host.contracts.research_info983 import SCHEMA
from civ6_host.contracts.research_info983 import validate
_CAPACITY = 4 * 1024 * 1024

def verified_files():
    progress.verify_source()
    files = {progress._ASSETS / progress._SUPPORT_REL: progress._SUPPORT_SHA256, progress._ASSETS / progress._LAUNCHBAR_REL: progress._LAUNCHBAR_SHA256, progress._XREF_PATH: progress._XREF_SHA256, progress._ASSETS / 'ToolTipHelper.lua': '3929f5528f4499cf675868638e98b55b40796b922dc414e9ec34ae3d044a6ce7'}
    files.update({progress._REA_ROOT / name: digest for name, digest in progress._REA_EXTRACT_SHA256.items()})
    for path, digest in files.items():
        if hashlib.sha256(_resolve_resource_path(path).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Pinned research chooser source changed: ' + path.name)
    return files

def source(player_id, turn, selected, choices):
    pid = progress._player_id(player_id)
    if type(turn) is not int or not 0 <= turn <= 2147483647:
        raise ValueError('Invalid research information turn')
    if type(selected) is not dict or set(selected) != {'research', 'civic'} or type(choices) is not dict or (set(choices) != set(selected)):
        raise ValueError('Invalid research selections or choices')
    headers = []
    for kind in ('research', 'civic'):
        index = selected[kind]
        if index is not None and (type(index) is not int or not 0 <= index <= 4294967295):
            raise ValueError('Invalid selected research index')
        rows = choices[kind]
        if type(rows) not in (list, tuple) or len(rows) > 4096:
            raise ValueError('Unbounded research choices')
        seen_indexes, seen_hashes = (set(), set())
        literals = []
        for row in rows:
            if type(row) is not dict or set(row) != {'index', 'hash'} or any((type(v) is not int or not 0 <= v <= 4294967295 for v in row.values())) or (row['index'] in seen_indexes) or (row['hash'] in seen_hashes):
                raise ValueError('Invalid or duplicate research choice')
            seen_indexes.add(row['index'])
            seen_hashes.add(row['hash'])
            literals.append((row['index'], '{index=%d,hash=%d}' % (row['index'], row['hash'])))
        headers.append('local %sSelected=%d;local %sChoices={%s}' % (kind, -1 if index is None else index, kind, ','.join((text for _, text in sorted(literals)))))
    header = b'local pid=' + pid + b';local expectedTurn=' + str(turn).encode('ascii') + b'\n'
    header += ('\n'.join(headers) + '\n').encode('ascii')
    return header + b'\nassert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,\'research info perspective mismatch\')\nassert(Game.GetCurrentGameTurn()==expectedTurn,\'research info turn mismatch\')\nlocal player=assert(Players[pid],\'research info player unavailable\')\nlocal techs=assert(player:GetTechs());local culture=assert(player:GetCulture())\nlocal function integer(v,lo,hi)\n assert(type(v)==\'number\' and v==math.floor(v) and v>=lo and v<=hi,\'invalid research integer\')\n return v\nend\nlocal function num(v)return string.format(\'%.0f\',v)end\nlocal function selection(manager,method)\n assert(type(manager[method])==\'function\',\'research selection getter missing\')\n local index=integer(manager[method](manager),-2147483648,4294967295)\n return index<0 and -1 or index\nend\nassert(selection(techs,\'GetResearchingTech\')==researchSelected,\'technology selection mismatch\')\nassert(selection(culture,\'GetProgressingCivic\')==civicSelected,\'civic selection mismatch\')\nlocal function topic(manager,info,selected,choices,costMethod,turnsMethod)\n assert(type(manager[costMethod])==\'function\' and type(manager[turnsMethod])==\'function\' and\n        type(manager.HasBoostBeenTriggered)==\'function\',\'research information getters missing\')\n local function row(index,expectedHash)\n  local item=assert(info[index],\'research GameInfo row unavailable\')\n  assert(item.Index==index,\'research GameInfo index mismatch\')\n  local hash=integer(item.Hash,-2147483648,4294967295);if hash<0 then hash=hash+4294967296 end\n  assert(expectedHash==nil or hash==expectedHash,\'research GameInfo hash mismatch\')\n  local cost=integer(manager[costMethod](manager,index),-2147483648,2147483647)\n  local turns=integer(manager[turnsMethod](manager,index),-2147483648,2147483647)\n  local boosted=manager:HasBoostBeenTriggered(index)\n  assert(type(boosted)==\'boolean\',\'research boost must be boolean\')\n  -- TechAndCivicSupport.RealizeTurnsLeft: cap at 999 and hide exactly -1.\n  local shown=turns==-1 and \'null\' or num(math.min(turns,999))\n  return \'{"index":\'..num(index)..\',"hash":\'..num(hash)..\',"cost":\'..num(cost)..\n   \',"raw_turns":\'..num(turns)..\',"turns_display":\'..shown..\',"boosted":\'..tostring(boosted)..\'}\'\n end\n local rows={};local selectedRow=nil\n for _,choice in ipairs(choices)do\n  local value=row(choice.index,choice.hash);rows[#rows+1]=value\n  if choice.index==selected then selectedRow=value end\n end\n if selected>=0 and selectedRow==nil then selectedRow=row(selected,nil)end\n return \'{"selected":\'..(selected<0 and \'null\' or num(selected))..\n   \',"selected_info":\'..(selectedRow or \'null\')..\',"choices":[\'..table.concat(rows,\',\')..\']}\'\nend\nlocal technology=topic(techs,GameInfo.Technologies,researchSelected,researchChoices,\'GetResearchCost\',\'GetTurnsToResearch\')\nlocal civic=topic(culture,GameInfo.Civics,civicSelected,civicChoices,\'GetCultureCost\',\'GetTurnsToProgressCivic\')\nassert(selection(techs,\'GetResearchingTech\')==researchSelected and selection(culture,\'GetProgressingCivic\')==civicSelected,\n       \'research selection changed during read\')\nassert(Game.GetCurrentGameTurn()==expectedTurn and Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid,\n       \'research info boundary changed\')\nreturn \'{"schema":"civ6rl.native_research_info983.v1","player_id":\'..num(pid)..\',"turn":\'..num(expectedTurn)..\n \',"technology":\'..technology..\',"civic":\'..civic..\'}\'\n'

def observe(prefix, player_id, turn, selected, choices):
    verified_files()
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source(player_id, turn, selected, choices), b'@explicit_research_info983', capacity=_CAPACITY)
    if type(raw) is not bytes or len(raw) >= _CAPACITY:
        raise ValueError('Invalid research info payload')
    value = json.loads(raw.decode('ascii'), object_pairs_hook=progress._unique_object, parse_constant=lambda v: (_ for _ in ()).throw(ValueError('Nonfinite research info')))
    candidates = [dict(candidate_id=f"{kind}:{row['index']}", action=dict(kind=kind, **row)) for kind, rows in choices.items() for row in rows]
    return validate(value, player_id, turn, research=selected, candidates=candidates)
