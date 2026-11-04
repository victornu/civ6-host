"""Official city plot-purchase requests, with native targets and prices.

This adapter uses the ordinary city purchase interface, not district/wonder
placement. It is diagnostic until its UI admission is independently retained.
No ownership, price, border-growth or affordability rule is reimplemented.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
from civ6_host.runtime.native import native_saved_purchases as purchases
from civ6_host.runtime.native.native_player_observation import observe_player
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_plot_purchases.py')))).resolve().parents[1]
SOURCE_PATH = 'work/plot-purchase/route.json'
SOURCE_SHA256 = 'cc72520484a16e29ab0bf6413629bc2d3e442476e08b32c07957f89420e500d1'
LIMIT = 524288

def verify_source():
    if SOURCE_SHA256 is None:
        raise RuntimeError('Plot purchase command route is not yet qualified')
    proof = load_pinned_json(ROOT / SOURCE_PATH, SOURCE_SHA256)
    if proof.get('schema') != 'civ6rl.plot_purchase_route.v1' or proof.get('core_sha256') != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3' or proof.get('contract', {}).get('native_rules_reimplemented') is not False:
        raise RuntimeError('Plot purchase source route differs')
    return proof
COMMON = "\nassert(type(CityManager.GetCommandTargets)=='function','plot purchase targets API missing')\nfor _,name in ipairs({'PARAM_PLOT_PURCHASE','PARAM_X','PARAM_Y'}) do\n integer(cc[name],name,-2147483648,2147483647)\nend\nassert(cc.PURCHASE==1490793096 and cc.PARAM_PLOT_PURCHASE==-780910418,'plot purchase enum changed')\nassert(CityCommandResults.PLOTS==1933683541,'plot purchase result enum changed')\nlocal function parameters()\n local params={}\n params[cc.PARAM_PLOT_PURCHASE]=plotPurchaseParameter\n return params\nend\nlocal function offers()\n local result=CityManager.GetCommandTargets(city,cc.PURCHASE,parameters())\n local targets=result and result[CityCommandResults.PLOTS] or nil\n if targets==nil then return {} end\n assert(type(targets)=='table','invalid plot purchase targets')\n local rows,seen,count={},{},0\n local balance=player:GetTreasury():GetGoldBalance()\n assert(type(balance)=='number' and balance==balance,'invalid plot purchase balance')\n -- The official ShowPurchases uses pairs, not an assumed dense Lua array.\n for _,id in pairs(targets) do\n  count=count+1;assert(count<=4096,'unbounded plot purchase targets')\n  integer(id,'plot',0,16383);assert(not seen[id],'duplicate plot purchase target');seen[id]=true\n  local plot=Map.GetPlotByIndex(id);assert(plot and plot:GetIndex()==id,'purchase target missing')\n  local x,y=integer(plot:GetX(),'x',0,16383),integer(plot:GetY(),'y',0,16383)\n  local cost=gold:GetPlotPurchaseCost(id)\n  assert(type(cost)=='number' and cost==cost and cost>=0 and cost<=9007199254740992,'invalid plot purchase cost')\n  local params=parameters();params[cc.PARAM_X]=x;params[cc.PARAM_Y]=y\n  local legal=bool(CityManager.CanStartCommand(city,cc.PURCHASE,params),'plot legality')\n  rows[#rows+1]={id=id,x=x,y=y,price=string.format('%.17g',cost),legal=legal,\n    afford=cost<=balance,params=params}\n end\n return rows\nend\n"

def preamble(pid, city_id, turn):
    proof = verify_source()
    parameter = proof['contract']['parameter_value']
    if type(parameter) is not int or not -2 ** 31 <= parameter < 2 ** 31:
        raise ValueError('Plot purchase parameter is not a qualified integer')
    return purchases.preamble(pid, city_id, turn) + f'\nlocal plotPurchaseParameter={parameter}\n'.encode('ascii') + COMMON.encode('ascii')

def catalog_source(pid, city_id, turn):
    return preamble(pid, city_id, turn) + "\nlocal out={'plot-purchases-v1|'..n(pid)..'|'..n(turn)..'|'..n(cityID)}\nfor _,q in ipairs(offers()) do\n out[#out+1]=table.concat({n(q.id),n(q.x),n(q.y),q.price,q.legal and '1' or '0',q.afford and '1' or '0'},'|')\nend\nready();return table.concat(out,'\\n')\n".encode('ascii')

def parse_catalog(raw, pid, city_id, turn):
    purchases.uint(pid, 'player', 63)
    purchases.uint(city_id, 'city')
    purchases.uint(turn, 'turn', 2147483647)
    if type(raw) is not bytes or len(raw) > LIMIT:
        raise ValueError('Unbounded plot purchase catalogue')
    lines = raw.decode('ascii').splitlines()
    if not lines or lines[0] != f'plot-purchases-v1|{pid}|{turn}|{city_id}' or len(lines) > 4097:
        raise ValueError('Foreign plot purchase catalogue')
    rows = []
    for line in lines[1:]:
        values = line.split('|')
        if len(values) != 6:
            raise ValueError('Malformed plot purchase row')
        plot_id, x, y, token, legal, afford = values
        if any((not v.isdigit() or str(int(v)) != v for v in (plot_id, x, y))) or legal not in ('0', '1') or afford not in ('0', '1'):
            raise ValueError('Malformed plot purchase fields')
        action = dict(kind='purchase', city_id=city_id, plot_id=int(plot_id), x=int(x), y=int(y), currency='YIELD_GOLD', price_token=token)
        rows.append(dict(action=action, command_legal=legal == '1', can_afford=afford == '1'))
    rows.sort(key=lambda row: row['action']['plot_id'])
    value = dict(player_id=pid, turn=turn, city_id=city_id, offers=rows)
    purchases.validate_catalog(value, pid, turn)
    return value

def catalog(prefix, city_id, turn, *, player_id=0):
    raw = prefix.runtime.evaluate_text(prefix.ui_child, catalog_source(player_id, city_id, turn), b'@explicit_plot_purchase_catalog', capacity=LIMIT + 1)
    return parse_catalog(raw, player_id, city_id, turn)

def _action(action):
    purchases.validate_action(action)
    if set(action) != purchases.PLOT_FIELDS:
        raise ValueError('Expected plot purchase action')
    return action

def request_source(action, pid, turn):
    _action(action)
    return preamble(pid, action['city_id'], turn) + f"\nlocal selected=nil\nfor _,q in ipairs(offers()) do\n if q.id=={action['plot_id']} then selected=q end\nend\nassert(selected and selected.x=={action['x']} and selected.y=={action['y']}\n and selected.price=='{action['price_token']}' and selected.legal and selected.afford,\n 'plot purchase target, price, legality or funds changed')\nready();CityManager.RequestCommand(city,cc.PURCHASE,selected.params)\nreturn 'submitted'\n".encode('ascii')

def ownership_source(action, pid, turn):
    _action(action)
    from civ6_host.runtime.native.native_district_completion import verify_source as verify_city_lookup
    verify_city_lookup()
    return preamble(pid, action['city_id'], turn) + f"\nlocal plot=Map.GetPlotByIndex({action['plot_id']})\nassert(plot and plot:GetX()=={action['x']} and plot:GetY()=={action['y']},'purchased plot identity changed')\nassert(plot:GetOwner()==pid,'purchased plot owner differs')\nlocal owningCity=Cities.GetPlotPurchaseCity(plot)\nassert(owningCity and owningCity:GetOwner()==pid and owningCity:GetID()==cityID,'purchased plot city differs')\nready();return 'owned'\n".encode('ascii')

def apply(owner, prefix, action, turn, before, *, player_id=0):
    _action(action)
    if len(prefix.actions.pending) != 0:
        raise RuntimeError('Plot purchase cannot overtake pending native actions')
    fresh = catalog(prefix, action['city_id'], turn, player_id=player_id)
    if action not in purchases.actions(fresh):
        raise RuntimeError('Plot purchase no longer offered at its quoted price')
    submitted = prefix.runtime.evaluate_text(prefix.ui_child, request_source(action, player_id, turn), b'@explicit_plot_purchase_request')
    if submitted != b'submitted' or len(prefix.actions.pending) != 1:
        raise RuntimeError('Plot purchase did not enqueue exactly one native command')
    prefix.actions.deliver_one()
    prefix.deferred_events.drain_empty_receivers()
    prefix.view_publisher.publish()
    after = observe_player(prefix.runtime, prefix.ui_child, player_id)
    if after['turn'] != turn or after['player_id'] != player_id:
        raise RuntimeError('Plot purchase crossed native perspective or turn')
    owned = prefix.runtime.evaluate_text(prefix.ui_child, ownership_source(action, player_id, turn), b'@explicit_plot_purchase_ownership')
    if owned != b'owned':
        raise RuntimeError('Plot purchase ownership receipt missing')
    owner.emit('official_explicit_plot_purchase_effect', action=action, quoted_cost=purchases.price(action['price_token']), net_currency_debit=before['economy']['gold'] - after['economy']['gold'], native_ownership_confirmed=True, observation_before=before, observation_after=after, automatic_choices_applied=False, ui_tutorial_gate_qualified=gate_admitted(owner, 'plot_purchase'), strategic_training_ready=False)
    return after
from civ6_host.runtime.native.native_ui_profile import gate_admitted
