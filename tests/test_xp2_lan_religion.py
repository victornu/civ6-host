"""Exercise the complete secondary religion path with real Lua and queue contracts."""

from copy import deepcopy
import struct
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from lupa.lua51 import LuaRuntime

from civ6_host.contracts import network_turn as turns
from civ6_host.contracts.information import project
from civ6_host.runtime import network_checkpoint, network_timer, player_views, xp1_session_checkpoint
from civ6_host.runtime import xp2_direct_religion_source as direct, xp2_lan_unit_commands
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.native import native_religion_diagnostic, native_saved_religion
from civ6_host.runtime.native.native_player_observation import observe_player
from test_xp1_prophet_activation import ENV as PROPHET
from test_xp1_religion_beliefs import ENV as BELIEFS
from test_xp1_religion_founding import ENV as FOUNDATION
from test_xp2_lan_secondary_commands import SecondaryPurchaseFixture


ACTIVATE = dict(kind='activate_prophet', unit_id=18, x=4, y=0)
FOUND = dict(kind='found_religion', index=9, hash=0xffffffff)
FOLLOWER = dict(kind='add_belief', index=2, hash=0xffffffff, **{'class': 'BELIEF_CLASS_FOLLOWER'})
FOUNDER = dict(kind='add_belief', index=1, hash=11, **{'class': 'BELIEF_CLASS_FOUNDER'})
FOUNDATION_GROUPS = ('prophet_activation', 'religion_founding', 'religion_beliefs')


class ReligionFixture(SecondaryPurchaseFixture):
    def __init__(self):
        super().__init__()
        for field in FOUNDATION_GROUPS:
            setattr(self.saved, 'xp2_' + field, True)
            setattr(self.saved, 'explicit_' + field, {'primary': field})
        actor = self.observations[1]
        actor['units'] = [dict(id=uid, owner=1, type=6, x=x, y=0, moves=2, max_moves=2, damage=0)
                          for uid, x in ((17, 3), (18, 4))]
        self.created, self.earned, self.removed = -1, 0, -1
        self.holy = False
        self.equipped = []
        self.claimed = False
        self.in_flight = None
        self.requests = []
        self.stack.enter_context(patch.object(network_timer, 'read', return_value=False))
        self.stack.enter_context(patch.object(native_saved_religion, 'observe_player', observe_player))
        self.stack.enter_context(patch.object(native_religion_diagnostic, 'request_player_operation',
                                             side_effect=self.request))
        from civ6_host.runtime import xp2_religious_chain_source

        # The existing runtime tests exercise PE, descriptors and ABI guards.
        # Here the native producer is doubled at its machine boundaries.
        self.stack.enter_context(patch.object(xp2_religious_chain_source, 'bind_prefix'))
        self.stack.enter_context(patch.object(direct, 'bind_prefix'))

    def evaluate(self, child, code, name, **options):
        religion_names = (b'@religion_observation', b'@native_own_religion', b'@native_religion',
                          b'@native_prophet', b'@explicit_religion', b'@explicit_prophet',
                          b'@xp2_borrowed_religion_actor')
        if not name.startswith(religion_names):
            return super().evaluate(child, code, name, **options)
        assert child is self.token.ui_child and self.backend.busy and self.player == 1
        lua = LuaRuntime(encoding=None)
        if name.endswith(b'guards'):
            return lua.execute(code)
        if b'prophet' in name or not self.holy:
            env = PROPHET.replace(b"id==17 and UNITX or 1", b"id==17 and UNITX or 4")
            env = env.replace(b"OperationType='UNITOPERATION_FOUND_RELIGION',Hash=",
                              b"OperationType='UNITOPERATION_FOUND_RELIGION',Index=15,VisibleInUI=true,Hash=")
            env = env.replace(b'visible==false', b"type(visible)=='boolean'")
        elif b'founding' in name or self.created < 0:
            env = FOUNDATION
        else:
            env = BELIEFS.replace(b'assert(r==4)', b'assert(r==created)')
        env = (env.replace(b'65536', b'65544').replace(b'Players={[0]', b'Players={[1]')
               .replace(b'GetOwner=function() return 0 end', b'GetOwner=function() return 1 end')
               .replace(b'GetID=function() return 0 end', b'GetID=function() return 1 end')
               .replace(b'p==0 end', b'p==1 end').replace(b'({Founder=1}', b'({Founder=0}')
               .replace(b'Founder=0,Beliefs=', b'Founder=1,Beliefs=')
               .replace(b'{{Founder=0,Religion=', b'{{Founder=1,Religion=')
               .replace(b'foreignHoly and 1 or 0', b'foreignHoly and 2 or 1')
               .replace(b'player=0,type=2,id=65544', b'player=1,type=2,id=65544'))
        values = {b'PID':1,b'OBSERVER':1,b'TURN':8,b'CREATED':self.created,b'EARNED':self.earned,
                  b'HOLY':self.holy,b'CITYOWNER':1,b'REMOVED':self.removed,b'UNITOWNER':1,b'UNITTYPE':6,
                  b'MOVES':2,b'HASPROPHET':True,b'UNITX':3,b'FOREIGN':False,b'CLAIMED':self.claimed}
        for key, value in values.items():
            env = env.replace(key, str(value).lower().encode())
        env = env.replace(b'EQUIPPED', ','.join(map(str, self.equipped)).encode())
        lua.globals().native_actor = lambda: self.player
        lua.globals().host_can_start = lambda uid: uid == 18
        lua.globals().host_request = self.request_prophet
        return lua.execute(env + b'''
Game.GetLocalPlayer=function()return native_actor()end
Game.GetLocalObserver=Game.GetLocalPlayer
''' + code)

    def request_prophet(self, uid, operation):
        assert (uid, operation) == (18, -953161477)
        self.requests.append(('prophet', self.player))
        self.in_flight = 'prophet', uid
        self.token.transport.pending.append(struct.pack('<IHH5I',0x8c0f3f36,1,1,uid,15,0xffffffff,0,0))

    def request(self, core, context, pid, operation, parameters, *, core_sha256, read, religion_permit):
        assert (core, context, pid) == (self.backend.core, self.backend.context, 1)
        name = direct.authorize_request(religion_permit, core, context, pid, operation, parameters,
            core_sha256=core_sha256, submit=True, allow_empty=False)
        if name == 'FOUND_RELIGION':
            assert parameters == {0x22a25b8b:0xffffffff,0xac2fdc09:0x97fea5c6}
            self.in_flight = 'foundation', 9
        else:
            assert name == 'ADD_BELIEF'
            selected = 1 if self.equipped else 2
            assert parameters == {0xa44b2907:(11 if selected == 1 else 0xffffffff),0xac2fdc09:0x97fea5c6}
            self.in_flight = 'belief', selected
        self.requests.append((name, pid))
        self.token.transport.pending.append(
            struct.pack('<6I',0xc45de12f,pid,operation,0,0x80000001,2)
            + b''.join(struct.pack('<IHH10xI',k,0,2,v) for k,v in parameters.items()))
        return dict(can_start=None, native_can_start_called=False, request_invoked=True)

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.in_flight is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
            kind, selected = self.in_flight
            self.in_flight = None
            if kind == 'prophet':
                from civ6_host.runtime.native import native_event_15c35863 as event

                address = 0x78002000
                self.memory.put(address, struct.pack('<HHI',1,1,selected))
                # XP2 producer 0x40fe3 uses selector zero and carries the actor in the descriptor.
                self.owner.dispatch(event.KIND,event.encode_fields(event.EventFields(0,15,address)),0)
                self.removed, self.holy, self.earned = selected, True, 2
                roster = self.observations[1]['units']
                roster[:] = [unit for unit in roster if unit['id'] != selected]
            elif kind == 'foundation':
                self.created = selected
            else:
                self.equipped.append(selected)
        return drain


class SecondaryReligionTests(TestCase):
    def test_player_two_activates_names_and_commits_both_beliefs_then_compares_checkpoint(self):
        f = ReligionFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity,
                                   session=dict(turn=8), catalogues={})
        protocol.selected = lambda request: turns.select_capability(protocol.catalogues[1], request['selection'])

        def reply(seq, action=None, *, refusal=None):
            request = dict(sequence=seq, player_id=1, operation='observe' if action is None else 'act')
            if action is not None:
                request['selection'] = dict(decision_id=protocol.catalogues[1]['decision_id'],
                                            candidate_id=turns.digest(action))
            _, session, observation, decisions, receipt = xp2_lan_unit_commands.read_reply(
                saved, protocol, request, (0, 1))
            turns.validate_catalogue(decisions, identity, seq, 8, player_id=1, observation=observation)
            protocol.session, protocol.catalogues[1] = session, decisions
            if action is not None:
                status = 'completed' if refusal is None else 'refused'
                self.assertEqual(receipt, dict(status=status, reason=refusal, requested_action=action))
            return observation, decisions

        observation, decisions = reply(1)
        self.assertIn(ACTIVATE, [row['action'] for row in decisions['candidates']])
        self.assertNotIn(FOUND, [row['action'] for row in decisions['candidates']])
        observation, decisions = reply(2, ACTIVATE)
        self.assertNotIn(18, [unit['id'] for unit in observation['units']])
        foundation = project('religion_founding', observation, decisions)
        self.assertEqual(foundation['own']['holy_city'], dict(player=1,type=2,id=65544))
        self.assertEqual(decisions['families']['found_religion']['unqualified'], ['custom_religion_names'])
        f.claimed = True
        reply(3, FOUND, refusal='native_religion_offer_changed')
        self.assertEqual(f.requests, [('prophet', 1)])
        f.claimed = False
        reply(4)
        observation, decisions = reply(5, FOUND)
        self.assertEqual(project('religion_beliefs', observation, decisions)['own']['own_religion'],
                         dict(founder=1, religion_index=9, belief_indices=[]))
        reply(6, FOLLOWER)
        observation, decisions = reply(7, FOUNDER)
        self.assertEqual(project('religion_beliefs', observation, decisions)['own']['own_religion']['belief_indices'],
                         [2, 1])
        self.assertEqual(decisions['families']['add_belief']['candidate_ids'], [])
        self.assertEqual(f.requests, [('prophet',1), ('FOUND_RELIGION',1), ('ADD_BELIEF',1), ('ADD_BELIEF',1)])
        self.assertEqual((f.player, f.token.observation['player_id']), (0, 0))
        for field in FOUNDATION_GROUPS:
            self.assertEqual(getattr(saved, 'explicit_' + field), {'primary': field})

        boundary = xp1_session_checkpoint.boundary(saved)
        full = player_views.checkpoint_view_digests(saved, boundary, (0,1), decision_players=(1,))
        old = player_views.checkpoint_view_digests(saved, boundary, (0,1), decision_players=(1,), religion_groups=())
        self.assertEqual(full['religion_groups'], list(FOUNDATION_GROUPS))
        self.assertNotIn('religion_groups', old)
        state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                     host_world_selection=None, network_boundary=boundary, host_secondary_world_selections=[])
        saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        for views in (full, old):
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=views)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
        f.equipped.pop()
        with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=full)):
            with self.assertRaisesRegex(ValueError, 'decision catalogue differs'):
                network_checkpoint.prepare_owner(saved, f.token.observation)


class SecondaryReligiousUnitsFixture(SecondaryPurchaseFixture):
    def __init__(self):
        super().__init__()
        from civ6_host.runtime import xp1_religious_unit_operations as adapter

        self.saved.xp2_religious_unit_operations = True
        self.saved.explicit_religious_unit_operations = {'primary': 'retained'}
        actor = self.observations[1]
        old = actor['units'][0]
        actor['units'] = [dict(old, id=uid, x=3, moves=2) for uid in (28,29,30)]
        self.charges = {28:3,29:3,30:3}
        self.earned = 2
        self.inquisition = False
        self.effect = True
        self.deny_request = False
        self.pending = None
        self.requests = []
        self.by_hash = {bits: name for name, (_, bits, *_) in adapter.source.OPERATIONS.items()}
        reference = self.backend.captured_bundle.reference
        self.ordinals = {kind:adapter.source.xp2.expected_ordinal(reference, kind) for kind in self.by_hash.values()}
        self.stack.enter_context(patch.object(network_timer, 'read', return_value=False))
        self.stack.enter_context(patch.object(adapter.source, 'bind_prefix'))
        self.stack.enter_context(patch.object(adapter, 'observe_player', observe_player))

    def evaluate(self, child, code, name, **options):
        if name not in (b'@explicit_xp1_religious_unit_operations', b'@explicit_xp1_religious_unit_request',
                        b'@explicit_xp1_religious_unit_entitlement'):
            return super().evaluate(child, code, name, **options)
        from civ6_host.runtime import xp1_religious_unit_operations as adapter
        from test_xp1_religious_unit_operations_runtime import _LUA

        assert child is self.token.ui_child and self.backend.busy and self.player == 1
        env = (_LUA.replace(b'return 0 end', b'return 1 end')
               .replace(b'owner==0', b'owner==1').replace(b'actor==0', b'actor==1')
               .replace(b'{HasLaunchedInquisition=function() return inquisition end}',
                        b'{HasLaunchedInquisition=function() return inquisition end,'
                        b' GetNumBeliefsEarned=function() return earned end}'))
        lua = LuaRuntime(encoding=None)
        bindings = lua.globals()
        bindings.unit_rows = lua.table_from([
            lua.table_from([u['id'],u['x'],u['y'],u['moves'],2,self.charges[u['id']]])
            for u in self.observations[1]['units']
        ])
        bindings.inquisition, bindings.earned = self.inquisition, self.earned
        bindings.observer = lambda: self.player
        bindings.definitions = lua.table_from({
            label.encode('ascii'): lua.table_from({
                b'OperationType':label.encode('ascii'), b'Hash':bits if bits<0x80000000 else bits-2**32,
                b'Index':self.ordinals[kind], b'VisibleInUI':True})
            for kind, (label,bits,*_) in adapter.source.OPERATIONS.items()
        })

        def available(uid, sign, visible):
            if (name == b'@explicit_xp1_religious_unit_request' and self.deny_request and not visible):
                return False
            kind = self.by_hash[sign & 0xffffffff]
            return ((uid==28 and self.charges[uid]>0 and kind in ('spread_religion','remove_heresy'))
                    or (uid==29 and kind=='evangelize_belief')
                    or (uid==30 and not self.inquisition and kind=='launch_inquisition'))

        bindings.can_start = available
        bindings.request = self.request
        return lua.execute(env + code)

    def request(self, uid, op_hash):
        kind = self.by_hash[op_hash & 0xffffffff]
        ordinal = self.ordinals[kind]
        self.pending = (kind,uid,ordinal)
        self.requests.append((1,kind,uid))
        self.token.transport.pending.append(struct.pack('<IHH5I',0x8c0f3f36,1,1,uid,ordinal,0xffffffff,0,0))

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.pending is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            from civ6_host.runtime.native import native_event_15c35863 as event

            self.machine.append(('drain',))
            self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
            kind, uid, ordinal = self.pending
            self.pending = None
            pointer = 0x78002000
            self.memory.put(pointer, struct.pack('<HHI',1,1,uid))
            self.owner.dispatch(event.KIND, event.encode_fields(event.EventFields(0,ordinal,pointer)), 0)
            if not self.effect:
                return
            if kind in ('spread_religion', 'remove_heresy'):
                self.charges[uid] -= 1
                return
            units = self.observations[1]['units']
            units[:] = [u for u in units if u['id'] != uid]
            if kind == 'evangelize_belief':
                self.earned += 1
            else:
                self.inquisition = True
        return drain


class SecondaryReligiousUnitsTests(TestCase):
    def test_secondary_unit_offers_refusal_effects_and_checkpoint(self):
        f = SecondaryReligiousUnitsFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity,
                                   session=dict(turn=8), catalogues={})
        protocol.selected = lambda request: turns.select_capability(protocol.catalogues[1], request['selection'])
        offers = [dict(kind=kind, unit_id=uid, x=3, y=0) for kind, uid in (
            ('spread_religion',28),('remove_heresy',28),('evangelize_belief',29),('launch_inquisition',30))]
        spread = offers[0]

        def reply(seq, action=None):
            request = dict(sequence=seq, player_id=1, operation='observe' if action is None else 'act')
            if action is not None:
                request['selection'] = dict(decision_id=protocol.catalogues[1]['decision_id'],
                                            candidate_id=turns.digest(action))
            _, session, observation, decisions, receipt = xp2_lan_unit_commands.read_reply(
                saved, protocol, request, (0, 1))
            turns.validate_catalogue(decisions, identity, seq, 8, player_id=1, observation=observation)
            protocol.session, protocol.catalogues[1] = session, decisions
            info = project('religious_unit_operations', observation, decisions)
            return info, decisions, receipt

        info, decisions, _ = reply(1)
        self.assertTrue(all(action in [row['action'] for row in decisions['candidates']] for action in offers))
        self.assertEqual(info['units'][0]['spread_charges'], 3)
        f.charges[28] = 4
        _, _, receipt = reply(2, spread)
        self.assertEqual(receipt['reason'], 'native_religious_unit_operation_offer_changed')
        f.deny_request = True
        _, _, receipt = reply(3, spread)
        self.assertEqual(receipt['reason'], 'native_religious_unit_operation_can_start_false')
        f.deny_request = False
        self.assertEqual(f.requests, [])
        f.effect = False
        _, _, receipt = reply(4, spread)
        self.assertEqual(receipt['status'], 'submitted')
        self.assertEqual(receipt['reason'], 'native_religious_unit_operation_processed_effect_unconfirmed')
        f.effect = True
        for seq, action in enumerate(offers,5):
            info, decisions, receipt = reply(seq, action)
            self.assertEqual(receipt, dict(status='completed', reason=None, requested_action=action))
        self.assertEqual(f.earned, 3)
        self.assertTrue(info['inquisition_started'])
        self.assertEqual([(r['unit_id'],r['spread_charges']) for r in info['units']],[(28,2)])
        self.assertEqual(f.requests, [(1,a['kind'],a['unit_id']) for a in (spread,*offers)])
        self.assertEqual(saved.explicit_religious_unit_operations, {'primary':'retained'})
        self.assertEqual((f.player, f.token.observation['player_id']), (0,0))

        boundary = xp1_session_checkpoint.boundary(saved)
        stored = player_views.checkpoint_view_digests(saved, boundary, (0,1), decision_players=(1,))
        self.assertEqual(stored['religion_groups'], ['religious_unit_operations'])
        state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                     host_world_selection=None, network_boundary=boundary, checkpoint_public_views=stored,
                     host_secondary_world_selections=[])
        saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        with patch.object(network_checkpoint, 'manifest', return_value=state):
            self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
            f.charges[28] -= 1
            with self.assertRaisesRegex(ValueError, 'decision catalogue differs'):
                network_checkpoint.prepare_owner(saved, f.token.observation)
