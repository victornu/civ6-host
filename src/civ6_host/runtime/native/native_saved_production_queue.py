"""Official queue views and BUILD insert modes; no production rules."""
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256 as _QUEUE_BASE_CORE_SHA256
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import copy, hashlib, json
from civ6_host.runtime.native import native_production_catalog as production
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_player_observation import observe_player
from civ6_host.runtime.native.native_ui_profile import gate_admitted
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_production_queue.py')))).resolve().parents[1]
PROOF = ROOT / 'work/production-queue962/source.json'
PROOF_SHA = '1ae2a3a5e331bed654ac98fe7b79b2305c5980652c6dc06a4201a53b32e0f322'
PUBLIC_SCHEMA = 'civ6rl.production_queue.public.v2'
PUBLIC_PROOF = ROOT / 'work/ui-availability/queue-public-source.json'
PUBLIC_PROOF_SHA = '51cda4a2c0a0bf7f29c58f853186cf364382ab6e882660ae04e58ae467afab6b'
LIMIT = 524288
FIELDS = {'queue_append': {'kind', 'city_id', 'category', 'index', 'hash', 'item_type', 'mode'}, 'queue_remove': {'kind', 'city_id', 'position'}, 'queue_swap': {'kind', 'city_id', 'source_position', 'destination_position'}}

def verify_source(*, core_sha256=_QUEUE_BASE_CORE_SHA256):
    if core_sha256 != _QUEUE_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_production_queue_profile import verify_source as selected_source
        return selected_source(core_sha256)
    p = load_pinned_json(PROOF, PROOF_SHA)
    if p['schema'] != 'civ6rl.production_queue962.source.v1' or p['contracts']['rules_reimplemented']:
        raise RuntimeError('Production queue source changed')
    for ui in p['official_ui'].values():
        if hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(ui['path']))).read_bytes()).hexdigest() != ui['sha256']:
            raise RuntimeError('Official production queue UI changed')
    public = load_pinned_json(PUBLIC_PROOF, PUBLIC_PROOF_SHA)
    if public['schema'] != 'civ6rl.queue_public_source.v1' or public['previous']['sha256'] != PROOF_SHA or public['contracts']['catalog_schema'] != PUBLIC_SCHEMA:
        raise RuntimeError('Public production queue source changed')
    for ui in public['official_ui']:
        if hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(ui['path']))).read_bytes()).hexdigest() != ui['sha256']:
            raise RuntimeError('Official public production queue UI changed')
    return p
LUA = "\nassert(Game.IsAllowStrategicCommands(pid)==true,'queue commands unavailable')\ncurrentHash=queue:GetCurrentProductionTypeHash();bits(currentHash,'queue current hash')\nassert(queueSize<=8,'queue exceeds the pinned official UI capacity')\nlocal function i32(v,label) assert(type(v)=='number' and v%1==0 and v>=-2147483648 and v<=2147483647,'invalid '..label);return v end\nlocal function entry(i)\n local v=queue:GetAt(i);assert(type(v)=='table','missing queue entry')\n local kinds={};local directives=CityProductionDirectives\n assert(directives,'queue directives unavailable')\n for name,kind in pairs({TRAIN='unit',CONSTRUCT='building',ZONE='district',PROJECT='project'}) do\n  local value=i32(directives[name],'queue directive');assert(kinds[value]==nil,'directive collision');kinds[value]=kind\n end\n local kind=kinds[i32(v.Directive,'entry directive')];assert(kind,'unknown queue directive')\n local rawType=i32(v[fields[kind]],'queue native type')\n local row=tables[kind][rawType];local index,hash,name=identity(row,kind)\n local formation,isCorps,isArmy='-','-','-'\n if kind=='unit' then\n  local value=i32(v.MilitaryFormationType,'queue formation');formation=n(value)\n  assert(type(MilitaryFormationTypes)=='table','UI military formation enums unavailable')\n  local corps=i32(MilitaryFormationTypes.CORPS_FORMATION,'UI corps formation enum')\n  local army=i32(MilitaryFormationTypes.ARMY_FORMATION,'UI army formation enum')\n  assert(corps~=army,'UI formation enums collide')\n  -- Match the official markers; neither true does not assert STANDARD_FORMATION.\n  isCorps=value==corps and '1' or '0';isArmy=value==army and '1' or '0'\n end\n return {category=kind,index=index,hash=hash,name=name,formation=formation,\n  wire=table.concat({'E',n(i),kind,n(index),n(hash),formation,isCorps,isArmy},'|')}\nend\nlocal function queueArgs(row,kind)\n local args={[e[enumFields[kind]]]=row.Hash}\n if queueSize>=8 then args[e.PARAM_INSERT_MODE]=e.VALUE_REPLACE_AT;args[e.PARAM_QUEUE_DESTINATION_LOCATION]=7\n else args[e.PARAM_INSERT_MODE]=e.VALUE_APPEND end\n return args\nend\nparameters=queueArgs\nlocal oldEligible=eligible\neligible=function(row,kind)\n if not oldEligible(row,kind) then return false end\n if row.Hash==currentHash then\n  if kind=='building' then return false end\n  if kind=='district' and flag(row.OnePerCity,'district OnePerCity') then return false end\n  if kind=='project' and row.MaxPlayerInstances==1 then return false end\n end\n return true\nend\nlocal function snapshot()\n local rows={'queue-v2|'..n(pid)..'|'..n(cityID)..'|'..n(expectedTurn)..'|'..(enabled and '1' or '0')..'|'..n(queueSize)}\n local choices={}\n for i=0,queueSize-1 do rows[#rows+1]=entry(i).wire end\n assert(queue:GetAt(queueSize)==nil,'GetAt size bound differs')\n if queueSize>0 then assert(entry(0).hash==bits(currentHash,'head hash'),'head differs from current production')\n else assert(currentHash==0,'empty queue has current production') end\n if enabled then\n  bits(e.VALUE_APPEND,'append mode');bits(e.VALUE_REMOVE_AT,'remove mode');bits(e.VALUE_SWAP,'swap mode')\n  local location=bits(e.PARAM_QUEUE_LOCATION,'queue index key');local source=bits(e.PARAM_QUEUE_SOURCE_LOCATION,'queue source key')\n  assert(location~=source and location~=destination and source~=destination,'queue keys collide')\n  local seenHash,scanned={},0\n  for _,kind in ipairs({'unit','building','project','district'}) do\n   local seenIndex,seenType={},{}\n   for row in tables[kind]() do\n    scanned=scanned+1;assert(scanned<=4096,'queue definition bound exceeded')\n    local index,hash,name=identity(row,kind)\n    assert(not seenHash[hash] and not seenIndex[index] and not seenType[name],'duplicate production identity')\n    seenHash[hash]=true;seenIndex[index]=true;seenType[name]=true\n    if eligible(row,kind) and legal(row,kind) then\n     assert(#choices<256,'queue append bound exceeded')\n     choices[#choices+1]={wire=table.concat({'A',kind,n(index),n(hash),name,queueSize>=8 and 'replace_tail' or 'append'},'|'),args=queueArgs(row,kind),rank=kind,index=index}\n    end\n   end\n  end\n  local rank={unit=1,building=2,project=3,district=4}\n  table.sort(choices,function(a,b) if a.rank~=b.rank then return rank[a.rank]<rank[b.rank] end;return a.index<b.index end)\n  for i=0,queueSize-1 do\n   local args={[e.PARAM_INSERT_MODE]=e.VALUE_REMOVE_AT,[e.PARAM_QUEUE_LOCATION]=i}\n   local can=CityManager.CanStartOperation(city,e.BUILD,args,false);assert(type(can)=='boolean','invalid remove legality')\n   if can then choices[#choices+1]={wire='R|'..n(i),args=args} end\n  end\n  for i=0,queueSize-1 do for j=0,queueSize-1 do if i~=j then\n   local args={[e.PARAM_INSERT_MODE]=e.VALUE_SWAP,[e.PARAM_QUEUE_SOURCE_LOCATION]=i,[e.PARAM_QUEUE_DESTINATION_LOCATION]=j}\n   local can=CityManager.CanStartOperation(city,e.BUILD,args,false);assert(type(can)=='boolean','invalid swap legality')\n   if can then choices[#choices+1]={wire='S|'..n(i)..'|'..n(j),args=args} end\n  end end end\n  for _,c in ipairs(choices) do rows[#rows+1]=c.wire end\n end\n ready()\n assert(queue:GetSize()==queueSize and queue:GetCurrentProductionTypeHash()==currentHash,'queue changed while reading')\n for i=0,queueSize-1 do assert(entry(i).wire==rows[i+2],'queue entry changed while reading') end\n return table.concat(rows,'\\n'),choices\nend\n"

def source(pid, city_id, turn, enabled, *, core_sha256=_QUEUE_BASE_CORE_SHA256):
    if type(enabled) is not bool:
        raise ValueError('Queue diagnostic option must be boolean')
    verify_source(core_sha256=core_sha256)
    return production._preamble(pid, city_id, turn, core_sha256=core_sha256) + f'local enabled={str(enabled).lower()}\n'.encode() + LUA.encode()

def parse_catalog(raw, pid, city_id, turn, enabled):
    if type(enabled) is not bool:
        raise ValueError('Queue diagnostic option must be boolean')
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded queue wire')
    text = raw.decode('ascii')
    lines = text.splitlines()
    if not lines:
        raise ValueError('Missing queue header')
    header = lines[0].split('|')
    if len(header) != 6 or header[0] not in ('queue-v1', 'queue-v2') or header[1:5] != [str(pid), str(city_id), str(turn), str(int(enabled))]:
        raise ValueError('Foreign queue wire')
    public = header[0] == 'queue-v2'
    count = int(header[5])
    uint(count, 'queue size', 8)
    v = dict(player_id=pid, city_id=city_id, turn=turn, enabled=enabled, entries=[], offers=[])
    if public:
        v['schema'] = PUBLIC_SCHEMA
    for line in lines[1:1 + count]:
        t = line.split('|')
        if len(t) != (8 if public else 6) or t[0] != 'E':
            raise ValueError('Missing queue entry')
        row = dict(position=int(t[1]), category=t[2], index=int(t[3]), hash=int(t[4]), formation=None if t[5] == '-' else int(t[5]))
        if public:
            if t[2] == 'unit':
                if t[6] not in ('0', '1') or t[7] not in ('0', '1'):
                    raise ValueError('Invalid formation marker wire')
                row['formation_display'] = {'is_corps': t[6] == '1', 'is_army': t[7] == '1'}
            else:
                if t[6:] != ['-', '-']:
                    raise ValueError('Nonunit formation marker wire')
                row['formation_display'] = None
        v['entries'].append(row)
    if len(v['entries']) != count:
        raise ValueError('Incomplete queue entries')
    for line in lines[1 + count:]:
        t = line.split('|')
        a = dict(city_id=city_id)
        if len(t) == 6 and t[0] == 'A':
            a.update(kind='queue_append', category=t[1], index=int(t[2]), hash=int(t[3]), item_type=t[4], mode=t[5])
        elif len(t) == 2 and t[0] == 'R':
            a.update(kind='queue_remove', position=int(t[1]))
        elif len(t) == 3 and t[0] == 'S':
            a.update(kind='queue_swap', source_position=int(t[1]), destination_position=int(t[2]))
        else:
            raise ValueError('Invalid queue action wire')
        v['offers'].append(a)
    validate_catalog(v, pid, turn)
    if catalog_wire(v) != text:
        raise ValueError('Noncanonical queue wire')
    return v

def catalog(prefix, city_id, turn, *, player_id=0, enabled=False, core_sha256=_QUEUE_BASE_CORE_SHA256):
    raw = prefix.runtime.evaluate_text(prefix.ui_child, source(player_id, city_id, turn, enabled, core_sha256=core_sha256) + b'local text=snapshot();return text', b'@explicit_production_queue', capacity=LIMIT + 1)
    return parse_catalog(raw, player_id, city_id, turn, enabled)

def actions(v):
    return v['offers']

def request_source(a, v, *, core_sha256=_QUEUE_BASE_CORE_SHA256):
    validate_action(a)
    validate_catalog(v, v['player_id'], v['turn'])
    if v.get('schema') != PUBLIC_SCHEMA:
        raise ValueError('Queue request requires a fresh public v2 catalogue')
    if a not in v['offers']:
        raise ValueError('Queue action not in native offers')
    return source(v['player_id'], v['city_id'], v['turn'], v['enabled'], core_sha256=core_sha256) + f"\nlocal text,choices=snapshot();assert(text=={json.dumps(catalog_wire(v))},'stale queue catalogue')\nlocal chosen=nil;for _,c in ipairs(choices) do if c.wire=={json.dumps(action_wire(a))} then assert(not chosen);chosen=c end end\nassert(chosen,'queue action unavailable');ready()\nCityManager.RequestOperation(city,e.BUILD,chosen.args)\nreturn 'submitted'\n".encode()

def apply(owner, prefix, a, turn, before, *, player_id=0, core_sha256=_QUEUE_BASE_CORE_SHA256, gate_owner=None):
    if core_sha256 != _QUEUE_BASE_CORE_SHA256:
        from civ6_host.runtime.xp1_production_queue_profile import source_reference
        selected_queue_source = source_reference(core_sha256)
    validate_action(a)
    if before['player_id'] != player_id or before['turn'] != turn or a['city_id'] not in [c['id'] for c in before['cities']]:
        raise RuntimeError('Queue action differs from player observation')
    if core_sha256 == _QUEUE_BASE_CORE_SHA256:
        if gate_owner is not None:
            raise ValueError('Base queue admission does not accept a foreign gate owner')
        admitted = gate_admitted(owner, 'production_queue')
    else:
        from civ6_host.runtime.xp1_production_queue_profile import gate_admitted as selected_gate
        selected_owner = owner if gate_owner is None else gate_owner
        if selected_owner.prefix is not prefix:
            raise ValueError('Queue admission belongs to a different native prefix')
        admitted = selected_gate(selected_owner)
    if not admitted and (core_sha256 != _QUEUE_BASE_CORE_SHA256 or getattr(owner, 'production_queue_diagnostic', False) is not True):
        raise RuntimeError('Queue gestures require an admitted UI profile or explicit diagnostic scope')
    old = catalog(prefix, a['city_id'], turn, player_id=player_id, enabled=True, core_sha256=core_sha256)
    published = [v for v in getattr(owner, 'explicit_production_queues', []) if v['city_id'] == a['city_id']]
    if published != [old] or a not in old['offers']:
        raise RuntimeError('Stale or unavailable queue action')
    if prefix.actions.pending:
        raise RuntimeError('Queue action transport not empty')
    submitted = prefix.runtime.evaluate_text(prefix.ui_child, request_source(a, old, core_sha256=core_sha256), b'@explicit_production_queue_request')
    if submitted != b'submitted' or len(prefix.actions.pending) != 1:
        raise RuntimeError('Queue request did not enqueue one native operation')
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()
    new = catalog(prefix, a['city_id'], turn, player_id=player_id, enabled=True, core_sha256=core_sha256)
    check_effect(a, old, new)
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    if after['player_id'] != player_id or after['turn'] != turn:
        raise RuntimeError('Queue action crossed actor or turn')
    owner.emit('official_explicit_production_queue_effect', action=a, queue_before=old, queue_after=new, native_archive_delivered=True, automatic_choices_applied=False, source_proof_sha256=PROOF_SHA if core_sha256 == _QUEUE_BASE_CORE_SHA256 else selected_queue_source[1], public_source_proof_sha256=PUBLIC_PROOF_SHA if core_sha256 == _QUEUE_BASE_CORE_SHA256 else selected_queue_source[1], tutorial_gate_qualified=admitted, strategic_training_ready=False)
    return after
from civ6_host.contracts.production_queue import uint, validate_action, action_wire, validate_catalog, catalog_wire, validate_all, check_heads, check_effect
