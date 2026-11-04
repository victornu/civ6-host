"""Source-backed standard unit/building purchases through native CityManager.

Prices, availability and affordability follow native queries and the official
UI predicates. Plot purchases are included only in the explicit city-management
diagnostic. Formation variants and district purchases remain separate gaps.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import math, re
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_player_observation import observe_player
from civ6_host.runtime.native.native_ui_profile import gate_admitted
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_saved_purchases.py')))).resolve().parents[1]
SOURCE_SHA = 'dd6992601925cd47495ae5a182c93a1f54cc6fd8048446dcf5055dbcfa52b637'
FIELDS = {'kind', 'city_id', 'category', 'index', 'hash', 'item_type', 'currency', 'price_token'}
PLOT_FIELDS = {'kind', 'city_id', 'plot_id', 'x', 'y', 'currency', 'price_token'}
LIMIT = 524288

def verify_source():
    proof = load_pinned_json(ROOT / 'work/purchases931/source.json', SOURCE_SHA)
    if proof['schema'] != 'civ6rl.purchase_route931.static.v1' or proof['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof['contract']['native_rules_reimplemented'] is not False:
        raise RuntimeError('Purchase route source differs')

def uint(v, label, maximum=4294967295):
    if type(v) is not int or not 0 <= v <= maximum:
        raise ValueError('Invalid purchase ' + label)
    return v

def price(token):
    if type(token) is not str or len(token) > 32 or (not re.fullmatch('[0-9]+(?:\\.[0-9]+)?(?:e[+-]?[0-9]+)?', token)):
        raise ValueError('Malformed native purchase quote')
    amount = float(token)
    if not math.isfinite(amount) or not 0 <= amount <= 2 ** 53:
        raise ValueError('Unbounded native purchase quote')
    return amount

def action_fields(action):
    """Resolve an exact purchase variant without inventing a GameInfo identity."""
    return PLOT_FIELDS if type(action) is dict and 'plot_id' in action else FIELDS

def validate_action(action):
    if type(action) is not dict or set(action) != action_fields(action) or action['kind'] != 'purchase':
        raise ValueError('Malformed purchase action')
    if 'plot_id' in action:
        for k in ('city_id', 'plot_id', 'x', 'y'):
            uint(action[k], k)
        if action['currency'] != 'YIELD_GOLD':
            raise ValueError('Unsupported plot purchase currency')
        price(action['price_token'])
        return action
    for k in ('city_id', 'index', 'hash'):
        uint(action[k], k)
    if action['category'] not in ('unit', 'building') or action['currency'] not in ('YIELD_GOLD', 'YIELD_FAITH'):
        raise ValueError('Unsupported purchase category or currency')
    if type(action['item_type']) is not str or not re.fullmatch(action['category'].upper() + '_[A-Z0-9_]{1,100}', action['item_type']):
        raise ValueError('Malformed purchase definition')
    price(action['price_token'])
    return action
COMMON = "\nlocal function integer(v,label,low,high)\n assert(type(v)=='number' and v%1==0 and v>=low and v<=high,'invalid purchase '..label);return v\nend\nlocal function bool(v,label) assert(type(v)=='boolean','invalid purchase '..label);return v end\nlocal function n(v) return string.format('%.0f',v) end\nlocal function bits(v) integer(v,'hash',-2147483648,2147483647);return v<0 and v+4294967296 or v end\nlocal function ready()\n assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'stale purchase perspective')\n local p=Players[pid]\n assert(p and p:IsAlive()==true and p:IsTurnActive()==true and p:IsTurnActiveComplete()==true,'purchase player not ready')\n return p\nend\nlocal player=ready()\nlocal city,seen,count=nil,{},0\nfor _,c in player:GetCities():Members() do\n count=count+1;assert(count<=4096 and c:GetOwner()==pid,'purchase city collection')\n local id=integer(c:GetID(),'city',0,4294967295);assert(not seen[id],'duplicate purchase city');seen[id]=true\n if id==cityID then city=c end\nend\nassert(city,'purchase city missing')\nassert(CityManager and type(CityManager.CanStartCommand)=='function' and type(CityManager.RequestCommand)=='function','purchase API missing')\nlocal cc=CityCommandTypes\nfor _,name in ipairs({'PURCHASE','PARAM_UNIT_TYPE','PARAM_BUILDING_TYPE','PARAM_YIELD_TYPE','PARAM_MILITARY_FORMATION_TYPE'}) do\n integer(cc[name],name,-2147483648,2147483647)\nend\nassert(MilitaryFormationTypes,'military formation table missing')\nlocal standard=MilitaryFormationTypes.STANDARD_MILITARY_FORMATION\nif standard~=nil then integer(standard,'formation',-2147483648,2147483647) end\n-- Preserve a nil official UI expression, including omission from the request\n-- table. STANDARD_FORMATION is a different key and must not be substituted.\nlocal gold=city:GetGold()\nlocal function definition(kind,row)\n local name=row[kind=='unit' and 'UnitType' or 'BuildingType']\n assert(type(name)=='string' and #name<=109 and string.match(name,kind=='unit' and '^UNIT_[A-Z0-9_]+$' or '^BUILDING_[A-Z0-9_]+$'),'purchase type')\n integer(row.Index,'index',0,4294967295);bits(row.Hash);return name\nend\nlocal function availableCurrency(kind,row,currency)\n if currency=='YIELD_GOLD' then return row.PurchaseYield==currency end\n if row.PurchaseYield==currency then return true end\n if kind=='unit' then return bool(gold:IsUnitFaithPurchaseEnabled(row.Hash),'unit faith enabled') end\n return bool(gold:IsBuildingFaithPurchaseEnabled(row.Hash),'building faith enabled')\nend\nlocal function quote(kind,row,currency)\n if not availableCurrency(kind,row,currency) then return nil end\n local yield=GameInfo.Yields[currency];assert(yield,'purchase yield missing')\n local params={};params[kind=='unit' and cc.PARAM_UNIT_TYPE or cc.PARAM_BUILDING_TYPE]=row.Hash\n params[cc.PARAM_YIELD_TYPE]=integer(yield.Index,'yield index',0,2147483647)\n -- The UI tests visibility and legality before adding standard formation to\n -- the submitted unit request. Preserve that argument order and distinction.\n local visible=bool(CityManager.CanStartCommand(city,cc.PURCHASE,true,params,false),'visibility')\n if not visible then return nil end\n local legal=bool(CityManager.CanStartCommand(city,cc.PURCHASE,false,params,true),'legality')\n local wallet=currency=='YIELD_GOLD' and player:GetTreasury() or player:GetReligion()\n local afford=bool(wallet:CanAfford(cityID,row.Hash),'affordability')\n local cost\n if kind=='unit' then cost=gold:GetPurchaseCost(yield.Index,row.Hash,standard)\n else cost=gold:GetPurchaseCost(yield.Index,row.Hash) end\n assert(type(cost)=='number' and cost==cost and cost>=0 and cost<=9007199254740992,'invalid purchase price')\n return {price=string.format('%.17g',cost),legal=legal,afford=afford,params=params}\nend\n"

def preamble(pid, city_id, turn):
    verify_source()
    uint(pid, 'player', 63)
    uint(city_id, 'city')
    uint(turn, 'turn', 2147483647)
    return f'local pid,cityID,turn={pid},{city_id},{turn}\n'.encode() + COMMON.encode()

def catalog_source(pid, city_id, turn):
    return preamble(pid, city_id, turn) + "\nlocal out={'purchase-v1|'..n(pid)..'|'..n(turn)..'|'..n(cityID)}\nlocal total=0\nfor _,kind in ipairs({'unit','building'}) do\n local rows=kind=='unit' and GameInfo.Units or GameInfo.Buildings\n local count,seen=0,{}\n for row in rows() do\n  count=count+1;assert(count<=4096,'purchase definitions bound')\n  local name=definition(kind,row);assert(not seen[row.Index],'duplicate purchase definition');seen[row.Index]=true\n  for _,currency in ipairs({'YIELD_GOLD','YIELD_FAITH'}) do\n   local q=quote(kind,row,currency)\n   if q then\n    total=total+1;assert(total<=4096,'purchase catalogue bound')\n    out[#out+1]=table.concat({kind,n(row.Index),n(bits(row.Hash)),name,currency,q.price,q.legal and '1' or '0',q.afford and '1' or '0'},'|')\n   end\n  end\n end\nend\nready();return table.concat(out,'\\n')\n".encode()

def parse_catalog(raw, pid, city_id, turn):
    uint(pid, 'player', 63)
    uint(city_id, 'city')
    uint(turn, 'turn', 2147483647)
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded purchase catalogue')
    lines = raw.decode('ascii').splitlines()
    if not lines or lines[0] != f'purchase-v1|{pid}|{turn}|{city_id}' or len(lines) > 4097:
        raise ValueError('Foreign purchase catalogue')
    rows = []
    seen = set()
    for line in lines[1:]:
        values = line.split('|')
        if len(values) != 8:
            raise ValueError('Malformed purchase row')
        category, index, hash_, name, currency, token, legal, afford = values
        if any((not v.isdigit() or str(int(v)) != v for v in (index, hash_))) or legal not in ('0', '1') or afford not in ('0', '1'):
            raise ValueError('Malformed purchase fields')
        action = dict(kind='purchase', city_id=city_id, category=category, index=int(index), hash=int(hash_), item_type=name, currency=currency, price_token=token)
        validate_action(action)
        key = (category, int(index), currency)
        if key in seen:
            raise ValueError('Duplicate purchase row')
        seen.add(key)
        rows.append(dict(action=action, command_legal=legal == '1', can_afford=afford == '1'))
    return dict(player_id=pid, turn=turn, city_id=city_id, offers=rows)

def validate_catalog(value, pid, turn):
    if type(value) is not dict or set(value) != {'player_id', 'turn', 'city_id', 'offers'} or value['player_id'] != pid or (type(value['player_id']) is not int) or (value['turn'] != turn) or (type(value['turn']) is not int):
        raise ValueError('Foreign purchase catalogue')
    city = uint(value['city_id'], 'city')
    if type(value['offers']) is not list or len(value['offers']) > 4096:
        raise ValueError('Unbounded purchase offers')
    seen = set()
    for row in value['offers']:
        if type(row) is not dict or set(row) != {'action', 'command_legal', 'can_afford'} or any((type(row[k]) is not bool for k in ('command_legal', 'can_afford'))):
            raise ValueError('Malformed purchase legality')
        a = validate_action(row['action'])
        key = ('plot', a['plot_id']) if 'plot_id' in a else (a['category'], a['index'], a['currency'])
        if a['city_id'] != city or key in seen:
            raise ValueError('Foreign or duplicate purchase city/row')
        seen.add(key)
    return value

def actions(catalog):
    return [row['action'] for row in catalog['offers'] if row['command_legal'] and row['can_afford']]

def catalog(prefix, city_id, turn, *, player_id=0, include_plots=False):
    if type(include_plots) is not bool:
        raise ValueError('Exact plot purchase diagnostic flag required')
    raw = prefix.runtime.evaluate_text(prefix.ui_child, catalog_source(player_id, city_id, turn), b'@explicit_purchase_catalog', capacity=LIMIT + 1)
    value = parse_catalog(raw, player_id, city_id, turn)
    if include_plots:
        from civ6_host.runtime.native import native_plot_purchases
        plots = native_plot_purchases.catalog(prefix, city_id, turn, player_id=player_id)
        value['offers'].extend(plots['offers'])
        validate_catalog(value, player_id, turn)
    return value

def selected_source(action, pid, turn):
    validate_action(action)
    table = 'Units' if action['category'] == 'unit' else 'Buildings'
    return preamble(pid, action['city_id'], turn) + f"\nlocal kind,currency='{action['category']}','{action['currency']}'\nlocal row=GameInfo.{table}['{action['item_type']}']\nassert(row and row.Index=={action['index']} and bits(row.Hash)=={action['hash']},'purchase definition changed')\ndefinition(kind,row)\n".encode()

def request_source(action, pid, turn):
    return selected_source(action, pid, turn) + f"\nlocal q=quote(kind,row,currency)\nassert(q and q.legal and q.afford and q.price=='{action['price_token']}','purchase legality, funds or price changed')\nif kind=='unit' then q.params[cc.PARAM_MILITARY_FORMATION_TYPE]=standard end\nready();CityManager.RequestCommand(city,cc.PURCHASE,q.params)\nreturn 'submitted'\n".encode()

def building_source(action, pid, turn):
    if action['category'] != 'building':
        raise ValueError('Expected building purchase')
    return selected_source(action, pid, turn) + b"return bool(city:GetBuildings():HasBuilding(row.Hash),'building possession') and 'present' or 'absent'\n"

def apply(owner, prefix, action, turn, before, *, player_id=0):
    validate_action(action)
    pid = player_id
    if 'plot_id' in action:
        if getattr(owner, 'city_management_diagnostic', False) is not True and (not gate_admitted(owner, 'plot_purchase')):
            raise RuntimeError('Plot purchase requires an admitted UI profile or explicit city-management diagnostic')
        from civ6_host.runtime.native import native_plot_purchases
        return native_plot_purchases.apply(owner, prefix, action, turn, before, player_id=pid)
    fresh = catalog(prefix, action['city_id'], turn, player_id=pid)
    if action not in actions(fresh):
        raise RuntimeError('Purchase no longer offered at its quoted price')
    building_before = None
    if action['category'] == 'building':
        building_before = prefix.runtime.evaluate_text(prefix.ui_child, building_source(action, pid, turn), b'@explicit_purchase_building_before')
        if building_before != b'absent':
            raise RuntimeError('Building purchase was already present or unreadable')
    submitted = prefix.runtime.evaluate_text(prefix.ui_child, request_source(action, pid, turn), b'@explicit_purchase_request')
    if submitted != b'submitted' or len(prefix.actions.pending) != 1:
        raise RuntimeError('Purchase did not enqueue exactly one native command')
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()
    after = observe_player(prefix.runtime, prefix.ui_child, pid)
    if after['turn'] != turn or after['player_id'] != pid:
        raise RuntimeError('Purchase crossed native perspective or turn')
    created = []
    building_after = None
    if action['category'] == 'building':
        building_after = prefix.runtime.evaluate_text(prefix.ui_child, building_source(action, pid, turn), b'@explicit_purchase_building_after')
        if building_after != b'present':
            raise RuntimeError('Purchased building absent after native delivery')
    else:
        old_ids = {u['id'] for u in before['units']}
        created = [u for u in after['units'] if u['id'] not in old_ids and u['type'] == action['index']]
        if not created:
            raise RuntimeError('Purchased unit absent after native delivery')
    currency = 'gold' if action['currency'] == 'YIELD_GOLD' else 'faith'
    owner.emit('official_explicit_purchase_effect', action=action, created_units=created, building_before=None if building_before is None else building_before.decode(), building_after=None if building_after is None else building_after.decode(), quoted_cost=price(action['price_token']), net_currency_debit=before['economy'][currency] - after['economy'][currency], observation_before=before, observation_after=after, automatic_choices_applied=False, strategic_training_ready=False)
    return after
