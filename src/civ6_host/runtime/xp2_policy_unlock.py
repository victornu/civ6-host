"""Paid policy-window control through the official XP2 player operation."""
from math import isfinite

from civ6_host.contracts import policy_unlock as contract
from .configuration_profiles import XP2_CORE_SHA256
from .native import native_policy_actions as policy
from .native.native_player_operation_request import request_player_operation
from .xp2_policy_controls_source import bind_owner, UNLOCK_POLICIES, SOURCE


def query_source(player_id, turn):
    return policy._lua_common(policy._player_id(player_id), policy._uint(turn, 'turn')) + b'''
assert(Game.GetLocalObserver()==pid,'policy unlock observer differs')
local culture,n=baseContext()
local player=Players[pid]
local cost,changed=culture:GetCostToUnlockPolicies(),culture:PolicyChangeMade()
assert(type(cost)=='number' and cost%1==0 and cost>=0 and cost<=2147483647 and
       type(changed)=='boolean','invalid native policy unlock state')
local parameter=GameInfo.GlobalParameters['GOVERNMENT_UNLOCK_WITH_FAITH']
assert(parameter and tonumber(parameter.Value)~=nil,'policy unlock currency parameter absent')
local faith=tonumber(parameter.Value)~=0
local currency=faith and 'YIELD_FAITH' or 'YIELD_GOLD'
local balance=faith and player:GetReligion():GetFaithBalance() or player:GetTreasury():GetGoldBalance()
assert(type(balance)=='number' and balance==balance and balance>-math.huge and balance<math.huge,
       'invalid native unlock balance')
local operation=PlayerOperations.UNLOCK_POLICIES
assert(type(operation)=='number' and operation%1==0,'native policy unlock operation absent')
if operation<0 then operation=operation+4294967296 end
assert(operation==3176265204,'native unlock enum differs from its source')
return table.concat({string.format('%.0f',pid),string.format('%.0f',expectedTurn),
 string.format('%.0f',cost),currency,changed and '1' or '0',
 string.format('%.17g',balance),string.format('%.0f',operation)},'|')
'''


def parse_query(raw, player_id, turn):
    if type(raw) is not bytes or len(raw) > 1024:
        raise ValueError('Invalid policy unlock readback size')
    parts = raw.split(b'|')
    if len(parts) != 7 or parts[3] not in (b'YIELD_GOLD', b'YIELD_FAITH') or parts[4] not in (b'0', b'1'):
        raise ValueError('Malformed native policy unlock readback')
    pid = policy._parse_u32(parts[0], 'player ID', 63)
    seen_turn = policy._parse_u32(parts[1], 'turn')
    cost = policy._parse_u32(parts[2], 'cost', 0x7fffffff)
    operation = policy._parse_u32(parts[6], 'operation')
    balance = float(parts[5])
    if pid != player_id or seen_turn != turn or operation != UNLOCK_POLICIES or not isfinite(balance):
        raise ValueError('Foreign policy unlock readback')
    return dict(player_id=pid, turn=seen_turn, cost=cost, currency=parts[3].decode('ascii'),
                changed=parts[4] == b'1', balance=balance, operation=operation)


def _raw(saved, observation):
    bind_owner(saved)
    pid, turn = observation['player_id'], observation['turn']
    prefix = saved.prefix
    raw = prefix.runtime.evaluate_text(prefix.ui_child, query_source(pid, turn),
                                       b'@xp2_policy_unlock_state', capacity=1025)
    return parse_query(raw, pid, turn)


def _operation(saved, player_id, *, submit):
    prefix = saved.prefix
    return request_player_operation(prefix.core, prefix.context, player_id, UNLOCK_POLICIES, {},
        core_sha256=XP2_CORE_SHA256, submit=submit, allow_empty=True)


def read(saved, observation):
    raw = _raw(saved, observation)
    native = _operation(saved, raw['player_id'], submit=False)
    reason = ('already_changed' if raw['changed'] else 'no_cost' if raw['cost'] == 0
              else 'insufficient_funds' if raw['balance'] < raw['cost']
              else 'available' if native['can_start'] else 'native_unavailable')
    public = dict(player_id=raw['player_id'], turn=raw['turn'], cost=raw['cost'],
                  currency=raw['currency'], reason=reason, can_unlock=reason == 'available')
    contract.validate(public, observation['player_id'], observation['turn'])
    saved.continuation.explicit_policy_unlock = public
    # Exact wallet precision is administrative evidence, never a public feature.
    saved.continuation.explicit_policy_unlock_raw = raw
    return public


def apply(saved, action, before):
    from .native.native_player_observation import observe_player
    contract.validate_action(action)
    fresh = read(saved, before)
    if contract.actions(fresh) != [action]:
        raise RuntimeError('Native paid policy window no longer offers this cost/currency')
    prior = dict(saved.continuation.explicit_policy_unlock_raw)
    prefix = saved.prefix
    if prefix.actions.pending:
        raise RuntimeError('Policy unlock cannot share an unrelated pending archive')
    result = _operation(saved, before['player_id'], submit=True)
    if not result['request_invoked'] or len(prefix.actions.pending) != 1:
        raise RuntimeError('Policy unlock did not enqueue exactly one native request')
    saved.emit('xp2_policy_unlock_submitted', action=action, result=result,
               source_proof_sha256=SOURCE[1], native_effect_verified=False)
    prefix.actions.deliver_one()
    prefix.deferred_events.drain()
    prefix.view_publisher.publish()
    after = _raw(saved, before)
    if (after['cost'] != 0 or after['changed'] or after['currency'] != prior['currency']
            or abs((prior['balance'] - after['balance']) - action['cost']) > 1e-6):
        raise RuntimeError('Native policy unlock state/payment differs from the request')
    effect = dict(verified=True, player_id=before['player_id'], turn=before['turn'],
                  currency=action['currency'], cost=action['cost'], resulting_unlock_cost=after['cost'])
    saved.emit('xp2_policy_unlock_effect_verified', action=action, effect=effect,
               administrative_wallet_before=prior['balance'], administrative_wallet_after=after['balance'],
               source_proof_sha256=SOURCE[1], automatic_choices_applied=False)
    observed = observe_player(prefix.runtime, prefix.ui_child, before['player_id'])
    return dict(observation=observed, effect=effect)
