"""Drive the existing LAN worker and public client with a composed XP2 fixture."""

from contextlib import redirect_stdout
from copy import deepcopy
from io import BytesIO, StringIO
import json
import struct
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from uuid import uuid4

from civ6_host.client import ProtocolError
from civ6_host.contracts import capability_policies, captured_city, city_ranged
from civ6_host.contracts import city_state_levies, envoys
from civ6_host.contracts import government, network_turn as turns, plot_purchases, policies, policy_unlock
from civ6_host.contracts import unit_work as work_contract
from civ6_host.contracts import unit_work_info as work_info_contract, unit_work_state as work_state_contract
from civ6_host.contracts.production_queue import PUBLIC_SCHEMA as QUEUE_SCHEMA
from civ6_host.runtime import captured_city_session, explicit_production_operation, network_timer, xp1_choice_queries
from civ6_host.runtime import xp1_action_transport, xp1_production_queue, xp2_lan_production_queue
from civ6_host.runtime import xp2_lan_city_controls, xp2_lan_production, xp2_lan_research, xp2_lan_unit_commands
from civ6_host.runtime import xp2_lan_ranged_shots
from civ6_host.runtime import xp2_government, xp2_lan_government, xp2_policies, xp2_policy_unlock
from civ6_host.runtime import xp1_city_state_levies, xp2_city_state_levies, xp2_envoys, xp2_lan_city_states
from civ6_host.runtime import unit_work_info, unit_work_state, xp2_lan_unit_work
from civ6_host.runtime import xp2_lan_unit_attacks
from civ6_host.runtime import xp2_lan_unit_development, xp2_lan_world_input, xp2_plot_purchases, xp2_promotions, xp2_unit_upgrades
from civ6_host.runtime.execution_images import _PROFILE, identity
from civ6_host.runtime.native import native_checkpoint_stream, native_probe
from civ6_host.runtime.native import native_saved_captured_city, native_saved_combat
from civ6_host.runtime.native import native_saved_city_shot, native_saved_district_shot
from civ6_host.runtime.native import native_plot_purchases, native_saved_purchases
from civ6_host.runtime.native import native_policy_actions
from civ6_host.runtime.native import native_saved_unit_work
from civ6_host.runtime.native import native_saved_city_focus1000 as focus, native_saved_citizens as citizens
from civ6_host.runtime.native.network_session import NativeNetworkSession
from civ6_host.runtime.network_protocol import CLOSURE_SCHEMA, SCHEMA
from civ6_host.runtime.source_verification import file_sha256
from civ6_host.runtime.workers import network_worker as worker
from civ6_host.session_client import SessionClient
from test_xp2_human_perspective import PerspectiveFixture


class SupervisedStop(BaseException):
    pass


class SecondaryOccupationFixture(PerspectiveFixture):
    flags = {'KEEP': 2, 'RAZE': 3, 'LIBERATE_FOUNDER': 0, 'LIBERATE_PREVIOUS_OWNER': 1}

    def __init__(self):
        super().__init__()
        self.enable_turn_fixture()
        self.enable_research_fixture()
        self.enable_world_fixture()
        self.enable_unit_development_fixture()
        self.saved._xp2_lan_unit_attacks_enabled = True
        self.saved._xp2_lan_occupation_enabled = True
        self.token.captured_city_core = self.backend.core
        self.token.explicit_captured_city = {'unchanged_primary_cache': True}
        self.turn_rows[2] = (0, 0, 0)
        self.strategic_allowed = False
        self.previous_owner = 2
        self.archive_actor = 1
        self.waiting_for_choice = False
        self.city_owner = None
        self.occupation_pending = None

    def make_city_pending(self):
        observation = self.observations[1]
        observation['plots'][0]['owner'] = 1
        observation['cities'][:] = [dict(id=65544, owner=1, x=3, y=0, population=1,
            yields=dict(food=2, production=1, gold=0, science=1, culture=1, faith=0))]
        self.waiting_for_choice = True
        self.city_owner = 1

    def evaluate(self, child, source, name, **options):
        if not name.startswith(b'@explicit_captured_city_'):
            return super().evaluate(child, source, name, **options)
        assert self.player == 1
        if name == b'@explicit_captured_city_catalog':
            assert child is self.token.ui_child and b'local pid,turn=1,8\n' in source
            header = 'captured-city-v1|1|8'
            if not self.waiting_for_choice:
                return header.encode()
            rows = [header, f'city|65544|3|0|5|{self.previous_owner}|6']
            rows.extend('choice|' + key for key in self.flags)
            return '\n'.join(rows).encode()
        if name == b'@explicit_captured_city_request':
            assert child is self.token.ui_child and b'row.city_id==65544' in source
            directive, = (d for d in self.flags if f"choice.directive=='{d}'".encode() in source)
            self.occupation_pending = directive
            value = self.flags[directive]
            self.token.transport.pending.append(struct.pack('<IHH6I', 0x346b0a13, self.archive_actor,
                2, 65544, 4, value, 1, 0, value))
            return b'submitted'
        assert child is self.token.game_child and b'Cities.GetCityInPlot' in source
        if name == b'@explicit_captured_city_raze_before':
            return b'verified' if self.city_owner == 1 else b'mismatch'
        if name == b'@explicit_captured_city_raze_effect':
            return b'verified' if self.city_owner is None else b'mismatch'
        assert name == b'@explicit_captured_city_liberation_effect'
        return b'verified' if f'8, 3, 0, {self.city_owner}\n'.encode() in source else b'mismatch'

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.occupation_pending is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
            directive = self.occupation_pending
            self.city_owner = {'KEEP': 1, 'RAZE': None, 'LIBERATE_FOUNDER': 5,
                               'LIBERATE_PREVIOUS_OWNER': self.previous_owner}[directive]
            self.occupation_pending = None
            self.waiting_for_choice = False
            observation = self.observations[1]
            if self.city_owner != 1:
                observation['cities'].clear()
                observation['plots'][0]['owner'] = -1 if self.city_owner is None else self.city_owner
            if self.token.trade_feedback is not None:
                self.token.trade_feedback.events.append(directive)

        return drain


class SecondaryCombatFixture(PerspectiveFixture):
    def __init__(self):
        super().__init__()
        from civ6_host.runtime.native.native_player_observation import observe_player

        self.stack.enter_context(patch.object(native_saved_combat, 'observe_player', observe_player))
        self.enable_turn_fixture()
        self.enable_research_fixture()
        self.enable_production_fixture()
        self.enable_world_fixture()
        self.enable_unit_development_fixture()
        self.saved._xp2_lan_unit_attacks_enabled = True
        self.turn_rows[2] = (0, 0, 0)
        observation = self.observations[1]
        observation['plots'].append(dict(observation['plots'][0], index=4, x=4, owner=2))
        observation['visible_enemy_units'] = [dict(owner=2, id=58, type=1, x=4, y=0,
                                                   visible=True, damage=0)]
        self.mode = 'ranged'
        self.remaining = 1
        self.city_damage = 0
        self.attack_pending = False
        self.at_war = True
        self.wrong_owner = False

    def evaluate(self, child, source, name, **kw):
        if name not in (b'@explicit_combat_catalog', b'@explicit_visible_city_targets',
                        b'@explicit_visible_combat_diplomacy', b'@explicit_combat_units',
                        b'@xp2_borrowed_attack_index', b'@explicit_unit_attack_request'):
            return super().evaluate(child, source, name, **kw)
        assert self.player == 1 and child is self.token.ui_child
        unit = self.observations[1]['units'][0]
        identity = dict(player_id=1, turn=8, width=74, height=46)
        operation = 'MOVE_TO' if self.mode == 'queued' else 'RANGE_ATTACK'
        candidate = dict(unit_id=unit['id'], target_owner=2, target_id=58, operation=operation, x=4, y=0)
        if name == b'@explicit_combat_catalog':
            offers = [candidate] if self.mode != 'city' and self.remaining else []
            return json.dumps(dict(identity, schema='civ6rl-combat-candidates-v1', candidates=offers)).encode()
        if name == b'@explicit_visible_city_targets':
            cities, offers = [], []
            if self.mode == 'city':
                cities.append(dict(owner=2, city_id=77, district_id=78, plot_id=4, x=4, y=0,
                    garrison_damage=0, garrison_max=200, outer_damage=self.city_damage, outer_max=100,
                    defense_strength=20.5))
                if self.remaining and b'if false then' not in source:
                    offers.append(dict(candidate, target_id=77, input_route='dedicated_ranged'))
            return json.dumps(dict(identity, cities=cities, candidates=offers)).encode()
        if name == b'@explicit_visible_combat_diplomacy':
            return json.dumps([dict(owner=2, at_war=self.at_war)]).encode()
        if name == b'@explicit_combat_units':
            row = dict(unit_id=unit['id'], unit_type=unit['type'], x=unit['x'], y=unit['y'],
                       damage=unit['damage'], moves=unit['moves'], attacks_remaining=self.remaining)
            return json.dumps(dict(player_id=1, turn=8, units=[row])).encode()
        index = 19 if operation == 'MOVE_TO' else 26
        if name == b'@xp2_borrowed_attack_index':
            assert f"GameInfo.UnitOperations['UNITOPERATION_{operation}']".encode() in source
            return str(index).encode()
        assert name == b'@explicit_unit_attack_request'
        self.attack_pending = True
        actor = 0 if self.wrong_owner else self.player
        self.token.transport.pending.append(struct.pack('<IHH9I', 0x8c0f3f36, actor, 1, unit['id'], index,
            0xffffffff, 0, 1, 4, 0, 16 if self.mode == 'queued' else 0, 0))
        return b'submitted'

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or not self.attack_pending:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
            self.attack_pending = False
            observation = self.observations[self.player]
            if self.mode == 'queued':
                self.destinations[self.player] = 4
            else:
                self.remaining = 0
                observation['units'][0]['moves'] = 0
                if self.mode == 'city':
                    self.city_damage = 31
                else:
                    observation['visible_enemy_units'][0]['damage'] = 28

        return drain


class SecondaryRangedFixture(SecondaryCombatFixture):
    def __init__(self):
        super().__init__()
        from civ6_host.runtime.native.native_player_observation import observe_player

        self.stack.enter_context(patch.object(native_saved_city_shot, 'observe_player', observe_player))
        self.saved._xp2_lan_ranged_shots_enabled = True
        self.observations[1]['cities'].append(dict(id=65544, owner=1, x=3, y=0, population=1,
            yields=dict(food=2, production=1, gold=0, science=1, culture=1, faith=0)))
        self.center_id = 65543
        self.shot_available = {'city': True, 'district': True}
        self.shot_pending = None
        self.capacity = {'city': 23, 'district': 18}
        self.archive_type = None

    def evaluate(self, child, source, name, **kw):
        if name not in (b'@explicit_city_shots', b'@explicit_district_shots',
                        b'@explicit_city_shot_request', b'@explicit_district_shot_request'):
            return super().evaluate(child, source, name, **kw)
        assert self.player == 1 and child is self.token.ui_child and b'local pid,turn=1,8\n' in source
        identity = dict(player_id=1, turn=8, width=74, height=46)
        shooter = 'city' if name.startswith(b'@explicit_city') else 'district'
        ready = self.shot_available[shooter]
        targets = [4] if ready else []
        if name == b'@explicit_city_shots':
            return native_saved_city_shot.wire(dict(identity, cities=[dict(
                city_id=65544, district_id=self.center_id, x=3, y=0, available=ready, targets=targets)])).encode()
        if name == b'@explicit_district_shots':
            return native_saved_district_shot.wire(dict(identity, districts=[dict(
                city_id=65544, district_id=65544, type_index=2, x=5, y=0, complete=True,
                banner_eligible=True, available=ready, targets=targets)])).encode()
        assert b'T|65544|4|4|0' in source and ready
        self.shot_pending = shooter
        type_id = {'city': 2, 'district': 3}[shooter] if self.archive_type is None else self.archive_type
        self.token.transport.pending.append(struct.pack('<IHH7I', 0x346b0a13, 1, type_id,
            65544, 1, 0, 1, 0, 4, 0))
        return b'submitted'

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.shot_pending is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
            shooter = self.shot_pending
            self.shot_pending = None
            self.shot_available[shooter] = False
            self.observations[1]['visible_enemy_units'][0]['damage'] += self.capacity[shooter]
        return drain


class SecondaryPurchaseFixture(SecondaryRangedFixture):
    def __init__(self):
        super().__init__()
        from civ6_host.runtime.native.native_player_observation import observe_player

        for codec in (native_plot_purchases, native_saved_purchases):
            self.stack.enter_context(patch.object(codec, 'observe_player', observe_player))
        self.saved._xp2_lan_purchases_enabled = True
        observation = self.observations[1]
        observation['economy'].update(gold=300, faith=125)
        observation['plots'].append(dict(observation['plots'][0], index=6, x=6, owner=-1))
        self.items = [
            ('unit', 20, 1872107673, 'UNIT_SCOUT', 'YIELD_GOLD', 60),
            ('building', 0, 2269901728, 'BUILDING_MONUMENT', 'YIELD_GOLD', 120),
            ('unit', 5, 1164184259, 'UNIT_INQUISITOR', 'YIELD_FAITH', 70),
        ]
        self.plot_price = 45
        self.purchased_plot = False
        self.buildings = set()
        self.purchase_pending = None
        self.archive_currency = None

    def evaluate(self, child, source, name, **kw):
        observation = self.observations[self.player]
        if name == b'@explicit_plot_purchase_catalog':
            assert self.player == 1 and child is self.token.ui_child
            rows = b'' if self.purchased_plot else f'\n6|6|0|{self.plot_price}|1|1'.encode()
            return b'plot-purchases-v1|1|8|65544' + rows
        if name == b'@explicit_purchase_catalog':
            assert self.player == 1 and b"{'YIELD_GOLD','YIELD_FAITH'}" in source
            rows = ['purchase-v1|1|8|65544']
            for item in self.items:
                currency = item[4].removeprefix('YIELD_').lower()
                afford = observation['economy'][currency] >= item[5]
                if item[3] not in self.buildings:
                    rows.append('|'.join(map(str, (*item, 1, int(afford)))))
            return '\n'.join(rows).encode()
        if name in (b'@explicit_purchase_building_before', b'@explicit_purchase_building_after'):
            assert self.player == 1 and b"GameInfo.Buildings['BUILDING_MONUMENT']" in source
            return b'present' if 'BUILDING_MONUMENT' in self.buildings else b'absent'
        if name == b'@explicit_plot_purchase_ownership':
            assert self.player == 1 and b'Cities.GetPlotPurchaseCity(plot)' in source
            return b'owned' if self.purchased_plot else b'mismatch'
        if name in (b'@explicit_plot_purchase_request', b'@explicit_purchase_request'):
            assert self.player == 1 and child is self.token.ui_child
            head = struct.pack('<IHH5I', 0x346b0a13, 1, 2, 65544, 0, 0, 1, 0)
            if name == b'@explicit_plot_purchase_request':
                assert b'selected.x==6' in source
                self.purchase_pending = ('plot', 6, 0, '', 'YIELD_GOLD', self.plot_price)
                tail = struct.pack('<4I', 4, 0xffffffff, 6, 0)
            else:
                item, = (row for row in self.items if f"['{row[3]}']".encode() in source)
                self.purchase_pending = item
                category, index, _, _, currency, _ = item
                currency_id = self.archive_currency or {'YIELD_GOLD': 2, 'YIELD_FAITH': 5}[currency]
                tail = (struct.pack('<IIiIii', 0, index, -1, currency_id, -9999, -9999) if category == 'unit'
                        else struct.pack('<IIIii', 1, index, currency_id, -9999, -9999))
            self.token.transport.pending.append(head + tail)
            return b'submitted'
        raw = super().evaluate(child, source, name, **kw)
        later = observation['units'][1:]
        if later and name in (b'@explicit_unit_orders', b'@explicit_promotions_catalog'):
            lines = raw.decode().splitlines()
            if name == b'@explicit_unit_orders':
                units = [f"U|{u['id']}|0|0|0" for u in later]
            else:
                units = [f"U|{u['id']}|0|{u['moves']}|{u['damage']}|" for u in later]
            return '\n'.join(lines[:2] + units + lines[2:]).encode()
        if later and name == b'@explicit_combat_units':
            rows = json.loads(raw)
            rows['units'].extend(dict(unit_id=u['id'], unit_type=u['type'], x=u['x'], y=u['y'],
                damage=u['damage'], moves=u['moves'], attacks_remaining=0) for u in later)
            return json.dumps(rows).encode()
        return raw

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.purchase_pending is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
            category, index, _, name, currency, cost = self.purchase_pending
            self.purchase_pending = None
            observation = self.observations[1]
            observation['economy'][currency.removeprefix('YIELD_').lower()] -= cost
            if category == 'plot':
                self.purchased_plot = True
                next(row for row in observation['plots'] if row['index'] == index)['owner'] = 1
            elif category == 'building':
                self.buildings.add(name)
            else:
                observation['units'].append(dict(id=50+len(observation['units']), owner=1, type=index,
                    x=3, y=0, damage=0, moves=0, max_moves=2))
        return drain


class SecondaryCityPanelsFixture(SecondaryPurchaseFixture):
    def __init__(self):
        super().__init__()
        from civ6_host.runtime import expansion_city_growth, expansion_city_loyalty, xp2_city_buildings
        from civ6_host.runtime import xp2_great_work_commands

        lease = object()
        for module in (expansion_city_growth, xp2_city_buildings):
            self.stack.enter_context(patch.object(module, 'check_bound', return_value=lease))
        self.stack.enter_context(patch.object(xp2_city_buildings, 'NativeScriptRuntime',
                                             type(self.saved.prefix.runtime)))
        self.stack.enter_context(patch.object(xp2_great_work_commands, '_verify_live', return_value=True))
        expansion_city_growth.bind(self.saved)
        expansion_city_loyalty.bind(self.saved)
        self.saved.xp2_city_buildings = True
        self.loyalty = 74

    def evaluate(self, child, source, name, **options):
        if name not in (b'@expansion_city_growth', b'@expansion_city_loyalty',
                        b'@xp2_city_building_inventory', b'@xp2_public_great_work_slots'):
            return super().evaluate(child, source, name, **options)
        assert self.player == 1 and child is self.token.ui_child
        assert self.backend.busy and b'Game.GetLocalObserver()==pid' in source
        if name == b'@xp2_public_great_work_slots':
            assert b'local pid,expectedTurn,width,height=1,8,' in source
            return b'great-work-slots-v3|1|8'
        if name == b'@xp2_city_building_inventory':
            assert b'local pid,expectedTurn,width,height=1,8,' in source
            header = b'city-buildings-v1|1|8'
            return header + (b'\n65544|3|0|2269901728|BUILDING_MONUMENT|1|0'
                             if 'BUILDING_MONUMENT' in self.buildings else b'')
        if name == b'@expansion_city_loyalty':
            assert b'local pid,turn=1,8\n' in source
            return (f'city-loyalty-v1|1|8\nC|65544|{self.loyalty}|100|3|1|4c6f79616c|'
                    '537461626c65|gaining|9|-1\nS|65544|4d6f6e756d656e74|1|0').encode()
        from civ6_host.contracts.city_growth import EXPANSION_TEXT_FIELDS

        assert b'local pid,turn,version=1,8,2\n' in source
        rows = ['city-growth-v2|1|8', 'C|65544|1|0|4|2|1|3']
        rows.extend(f'V|65544|{key}|string|{b"present".hex()}' for key in EXPANSION_TEXT_FIELDS)
        rows.extend(('V|65544|GrowthLongNum|number|7', 'V|65544|starving|boolean|0',
                     'V|65544|icon_u|number|0', 'V|65544|icon_v|number|0'))
        color = b'StatNormalCSGlow'.hex()
        rows.extend(f'V|65544|{key}|string|{color}' for key in
                    ('CitizenGrowthStatus2_color','CitizenGrowthStatusIcon2_color'))
        rows.append('R|65544|12345|20|3|7|-1')
        return '\n'.join(rows).encode()


class SecondaryCityReligionFixture(SecondaryPurchaseFixture):
    def __init__(self):
        super().__init__()
        from civ6_host.runtime import xp2_city_religion_source

        self.saved.xp2_city_religion_details = True
        self.followers = 1
        self.city_owner = 1

        def bind(prefix):
            assert prefix is self.saved.prefix and self.backend.busy and self.player == 1

        self.stack.enter_context(patch.object(xp2_city_religion_source, 'bind_prefix', side_effect=bind))
        self.stack.enter_context(patch.object(network_timer, 'read', return_value=False))

    def evaluate(self, child, source, name, **options):
        if name != b'@xp2_own_city_religion_details':
            return super().evaluate(child, source, name, **options)
        from lupa.lua51 import LuaRuntime

        assert child is self.token.ui_child and self.backend.busy
        lua = LuaRuntime(encoding=None)
        lua.globals().observer = lambda: self.player
        lua.globals().city_owner = lambda: self.city_owner
        lua.globals().followers = lambda: self.followers
        return lua.execute(br'''
local function foreign() error('foreign religion query') end
local Game={GetLocalPlayer=observer,GetLocalObserver=observer,
            GetCurrentGameTurn=function() return 8 end}
local Map={GetGridSize=function() return 74,46 end,GetPlotCount=function() return 3404 end}
local religion={
 GetMajorityReligion=function() return 3 end,
 GetReligionsInCity=function() return {{Religion=3,Followers=followers(),Pressure=41.5}} end,
 GetTotalPressureOnCity=function(_,index) assert(index==3); return 1.5 end,
 GetPressureFromCity=foreign,
}
local cities={{GetID=function() return 65544 end,GetOwner=function() return city_owner() end,
               GetReligion=function() return religion end}}
local Players=setmetatable({[1]={GetCities=function()
 return {Members=function() return ipairs(cities) end}
end}},{__index=foreign})
''' + source)


class SecondaryGreatPeopleFixture(SecondaryPurchaseFixture):
    def __init__(self):
        super().__init__()
        from civ6_host.runtime import xp1_great_people_commands, xp2_great_people_source
        from civ6_host.runtime.native.native_player_observation import observe_player

        self.saved.xp2_great_people = self.saved.xp2_great_people_actions = True
        self.saved.explicit_great_people_actions = {'primary': 'retained'}
        self.observations[1]['economy']['gold'] = 730.75
        self.cost = 550
        self.granted = self.congress = self.in_flight = False
        self.can_start = True
        self.requests = []
        self.stack.enter_context(patch.object(network_timer, 'read', return_value=False))
        import pefile

        reference = self.backend.captured_bundle.reference
        reader = xp2_great_people_source.require_source(_PROFILE, reference=reference)
        actions = xp2_great_people_source.require_actions(_PROFILE, reference=reference)
        with pefile.PE(_PROFILE.path, fast_load=True) as pe:
            def copy_span(span):
                self.memory.put(self.memory.base + span['rva'], pe.get_data(span['rva'], span['bytes']))

            for row in reader['bindings'].values():
                literal_size = len(row['name']) + 1
                copy_span(dict(rva=row['name_rva'], bytes=literal_size))
                for span in (row['registration'], *row['bodies']):
                    copy_span(span)
            for name, row in reader['timeline_fields'].items():
                copy_span(dict(rva=row['rva'], bytes=len(name) + 1))
            for name, row in reader['operation_enums'].items():
                copy_span(dict(rva=row['literal_rva'], bytes=len(name) + 1))
                copy_span(row['registration'])
            for span in (*reader['timeline_reifier'], *actions['spans'].values()):
                copy_span(span)
        self.stack.enter_context(patch.object(xp1_great_people_commands, 'observe_player', observe_player))
        self.stack.enter_context(patch.object(xp1_great_people_commands, 'request_player_operation',
                                             side_effect=self.great_person_request))

    def evaluate(self, child, source, name, **options):
        if name not in (b'@xp2_public_great_people', b'@xp1_great_person_grant'):
            return super().evaluate(child, source, name, **options)
        from lupa.lua51 import LuaRuntime
        from test_xp1_great_people import _ENV
        from test_xp1_great_people_commands import _LUA

        assert child is self.token.ui_child and self.player == 1 and self.backend.busy
        world = (_ENV + _LUA).replace(b'pid==0', b'pid==1').replace(b'Players={[0]', b'Players={[1]')
        world += f'''
cfg.pid=1; cfg.observer=1; rows[2].Claimant=1
Game.GetWorldCongress=function() return {{IsInSession=function()
 return {str(self.congress).lower()} end}} end
great.GetPatronizeCost=function(_,pid,id,yield)
 assert(pid==1); return yield==2 and {self.cost} or 70
end
'''.encode('ascii')
        if self.granted:
            world += br'''
table.remove(rows,1)
great.GetPastTimeline=function() return {{Individual=117,Class=4,Claimant=1,TurnGranted=8}} end
great.CountPeopleReceivedByPlayer=function(_,id,pid) assert(pid==1); return id==4 and 1 or 2 end
'''
        return LuaRuntime(encoding=None).execute(world + source)

    def great_person_request(self, core, context, player_id, operation, parameters, **options):
        from test_xp1_great_people_commands import _GOLD, packet

        assert (core, context, player_id) == (self.backend.core, self.backend.context, self.player)
        assert player_id == 1 and self.backend.busy
        assert (operation, parameters) == (0xebdeb9f6, {0x385fc342: 117, 0x2b8aba02: 2})
        self.requests.append(player_id)
        if self.can_start:
            self.in_flight = True
            self.token.transport.pending.append(packet(dict(_GOLD, cost=self.cost), pid=player_id))
        return dict(can_start=self.can_start, request_invoked=self.can_start)

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or not self.in_flight:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
            self.granted, self.in_flight = True, False
            observation = self.observations[1]
            observation['economy']['gold'] -= self.cost
            observation['units'].append(dict(id=71, owner=1, type=13,
                x=3, y=0, damage=0, moves=0, max_moves=2))
        return drain


class SecondaryPantheonFixture(SecondaryPurchaseFixture):
    def __init__(self):
        super().__init__()
        from civ6_host.runtime import xp2_direct_religion_source
        from civ6_host.runtime.native import native_saved_pantheon, native_player_operation_request
        from civ6_host.runtime.native.native_player_observation import observe_player

        self.saved.xp2_pantheon = True
        self.saved.explicit_pantheon = {'primary': 'retained'}
        self.pantheon = -1
        self.taken = set()
        self.pending_pantheon = None
        self.wrong_observer = False
        self.requests = []
        self.stack.enter_context(patch.object(network_timer, 'read', return_value=False))
        # Keep the exact permit, archive decoder and notification consumer
        # running on the composed graph. Only the machine boundaries are doubled.
        self.stack.enter_context(patch.object(xp2_direct_religion_source, 'bind_prefix'))
        self.stack.enter_context(patch.object(native_saved_pantheon, 'observe_player', observe_player))
        self.stack.enter_context(patch.object(native_player_operation_request, 'request_player_operation',
                                             side_effect=self.request_pantheon))

    def evaluate(self, child, source, name, **options):
        if name not in (b'@native_pantheon_guards', b'@native_pantheon_turn',
                        b'@native_pantheon_catalog', b'@explicit_pantheon_catalog',
                        b'@native_pantheon_revalidation', b'@native_pantheon_effect',
                        b'@explicit_pantheon_index', b'@xp2_borrowed_religion_actor'):
            return super().evaluate(child, source, name, **options)
        from lupa.lua51 import LuaRuntime

        assert child is self.token.ui_child and self.player == 1 and self.backend.busy
        lua = LuaRuntime(encoding=None)
        if name == b'@native_pantheon_guards':
            return lua.execute(source)
        lua.globals().local_actor = lambda: self.player
        lua.globals().local_observer = lambda: 0 if self.wrong_observer else self.player
        lua.globals().current_pantheon = lambda: self.pantheon
        lua.globals().used = lambda index: index in self.taken or index == self.pantheon
        return lua.execute(br'''
local function yes() return true end
local religion={GetPantheon=function()return current_pantheon()end,
                CanCreatePantheon=function() return current_pantheon()<0 end}
local global={IsInSomePantheon=function(_,index)return used(index)end,
              IsInSomeReligion=function()return false end}
local Players={[1]={GetReligion=function() return religion end,
 IsAlive=yes,IsTurnActive=yes,IsTurnActiveComplete=yes}}
local Game={GetLocalPlayer=function()return local_actor()end,
 GetLocalObserver=function()return local_observer()end,GetCurrentGameTurn=function()return 8 end,
 IsAllowStrategicCommands=yes,GetReligion=function()return global end}
local rows={{Index=4,Hash=-2147483648,BeliefClassType='BELIEF_CLASS_PANTHEON'},
            {Index=7,Hash=123,BeliefClassType='BELIEF_CLASS_PANTHEON'}}
local GameInfo={Beliefs=function()
 local index=0; return function() index=index+1; return rows[index] end
end}
local PlayerOperations={FOUND_PANTHEON=-1770928175,PARAM_BELIEF_TYPE=-1538578169,
 PARAM_INSERT_MODE=-1406149623,VALUE_EXCLUSIVE=-1744919098}
''' + source)

    def request_pantheon(self, core, context, player, operation, parameters, **options):
        from lupa.lua51 import LuaError
        from civ6_host.runtime import xp2_direct_religion_source as source

        authorize = source.authorize_request
        permit = options['religion_permit']
        abi = dict(core_sha256=options['core_sha256'], submit=True, allow_empty=False)
        self.wrong_observer = True
        try:
            try:
                authorize(permit, core, context, player, operation, parameters, **abi)
            except LuaError as error:
                assert 'borrowed religious perspective changed' in str(error)
            else:
                raise AssertionError('Wrong native observer received a pantheon permit')
        finally:
            self.wrong_observer = False
        assert authorize(permit, core, context, player, operation, parameters, **abi) == 'FOUND_PANTHEON'
        assert (player, operation, parameters) == (1, source.PANTHEON, {0xa44b2907:123,0xac2fdc09:0x97fea5c6})
        self.requests.append(player)
        self.pending_pantheon = 7
        self.token.transport.pending.append(
            struct.pack('<6I',0xc45de12f,player,operation,0,0x80000001,2)
            + b''.join(struct.pack('<IHH10xI',key,0,2,value) for key,value in parameters.items()))
        return dict(can_start=None, native_can_start_called=False, request_invoked=True)

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.pending_pantheon is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
            self.pantheon, self.pending_pantheon = self.pending_pantheon, None
            self.observations[1]['economy']['faith'] -= 25
            fields = {key:struct.pack('<H6xQ4xI',tag,value,0) for key,tag,value in (
                (0xa1e5a149,3,0),(0xd6fcf3e4,2,1),(0xa1fbc372,2,self.pantheon))}
            self.owner.dispatch(0x565abe26, fields, 0)
        return drain


class SecondaryGovernmentFixture(SecondaryPurchaseFixture):
    def __init__(self):
        super().__init__()
        self.saved._xp2_lan_government_enabled = True
        self.token.explicit_government = self.token.explicit_policies = {'primary': 'retained'}
        self.token.explicit_policy_unlock = {'primary': 'retained'}
        self.current_government = 0
        self.considered = False
        self.policy_cost = 55
        self.policy_changed = False
        self.slots = [0, 1]
        self.culture_pending = None
        self.wrong_policy_actor = False

        def operation(saved, actor, *, submit):
            assert saved is self.saved and actor == self.player == 1
            if submit:
                self.culture_pending = 'unlock'
                self.token.transport.pending.append(struct.pack('<5I', 0xc45de12f, actor, 3176265204, 2, 0))
            return dict(can_start=True, request_invoked=submit)
        self.stack.enter_context(patch.object(xp2_policy_unlock, '_operation', side_effect=operation))

    def evaluate(self, child, source, name, **kw):
        if name == b'@explicit_government_catalog':
            assert self.player == 1 and child is self.token.ui_child
            return (f'catalog|1|8|{self.current_government}|1|{int(self.current_government==3)}|1|2|'
                    '0:100:1:0:0|3:809918684:1:1:0').encode()
        if name == b'@explicit_government_consideration':
            return f'readback|1|8|{self.current_government}|{int(self.considered)}|{int(not self.considered)}'.encode()
        if name == b'@xp2_retain_government':
            assert self.player == 1 and not self.considered
            self.considered = True
            return f'considered|1|8|{self.current_government}|1|0'.encode()
        if name == b'@xp2_government_request':
            assert self.player == 1 and self.current_government == 0
            self.culture_pending = 'government'
            self.token.transport.pending.append(struct.pack('<7I', 0xe57882af, 1, 1, 3, 0xffffffff, 0, 0))
            return b'submitted|1|8|0|3|809918684|1'
        if name == b'@xp2_government_effect':
            return f'effect|1|8|0|3|809918684|{self.current_government}|{int(self.current_government==3)}'.encode()
        if name == b'@xp2_policy_unlock_state':
            gold = self.observations[1]['economy']['gold']
            return f'1|8|{self.policy_cost}|YIELD_GOLD|{int(self.policy_changed)}|{gold}|3176265204'.encode()
        if name == b'@xp2_explicit_policy_catalog':
            reason = 'already_changed' if self.policy_changed else 'not_free' if self.policy_cost else 'available'
            options = '0:10:10:POLICY_FIRST,1:20:20:POLICY_SECOND' if reason == 'available' else ''
            return (f'1|8|{reason}|2\n0|{self.slots[0]}|{options}\n1|{self.slots[1]}|{options}').encode()
        if name == b'@xp2_policy_confirmation_state':
            return f'1|8|2|{int(self.policy_changed)}|0|1|{self.policy_cost}'.encode()
        if name == b'@xp2_explicit_policy_request':
            assert self.player == 1 and not self.policy_changed
            self.culture_pending = 'assign'
            actor = 0 if self.wrong_policy_actor else 1
            self.token.transport.pending.append(struct.pack('<13I', 0xe57882af, actor, 3,
                0xffffffff, 0xffffffff, 2, 0, 1, 2, 10, 1, 20, 0))
            return b'accepted,1,8,2'
        if name == b'@xp2_explicit_policy_effect':
            return f'verified,1,8,2,0:{self.slots[0]},1:{self.slots[1]}'.encode()
        return super().evaluate(child, source, name, **kw)

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.culture_pending is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
            operation, self.culture_pending = self.culture_pending, None
            if operation == 'government':
                self.current_government = 3
            elif operation == 'unlock':
                self.observations[1]['economy']['gold'] -= self.policy_cost
                self.policy_cost = 0
            else:
                self.slots = [1, 0]
                self.policy_changed = True
        return drain


class SecondaryCityStateFixture(SecondaryGovernmentFixture):
    def __init__(self):
        super().__init__()
        from civ6_host.runtime.native import native_player_operation_request

        self.saved._xp2_lan_city_states_enabled = True
        self.saved.xp2_city_state_levies_enabled = True
        self.token.explicit_envoys = self.token.explicit_city_state_levies = {'primary': 'retained'}
        self.tokens = 2
        self.envoys_considered = False
        self.tokens_received = 2
        self.levy_active = False
        self.levy_cost = 100
        self.city_state_pending = None
        self.wrong_target = False

        def submit(core, context, actor, operation, parameters, *, core_sha256, levy_permit=None):
            assert actor == self.player == 1 and parameters == {0x0483191c: 2}
            if operation == 0xe6e2dbb2:
                route = xp2_city_state_levies.authorize_request(levy_permit, core, context, actor,
                    operation, parameters, core_sha256=core_sha256, submit=True, allow_empty=False)
                assert route == 'LEVY_MILITARY'
                result = dict(request_invoked=True, native_can_start_called=False,
                              source_qualified_request_only=route)
                self.city_state_pending = 'levy'
            else:
                assert operation == 0x99ec0bce and levy_permit is None
                result = dict(request_invoked=True, can_start=True)
                self.city_state_pending = 'envoy'
            self.token.transport.pending.append(struct.pack('<7I14sI', 0xc45de12f, 1, operation, 2,
                0x80000001, 1, 0x0483191c, bytes.fromhex('0000020000000000000000000000'),
                3 if self.wrong_target else 2))
            return result
        self.stack.enter_context(patch.object(native_player_operation_request, 'request_player_operation',
                                              side_effect=submit))

    def evaluate(self, child, source, name, **kw):
        if name == b'@xp2_envoy_checkpoint_consideration':
            assert self.player == 1 and self.envoys_considered
            assert b'SetGivingTokensConsidered(false)' in source
            self.envoys_considered = False
            return b'restored'
        if name in (b'@xp2_envoy_catalogue', b'@xp2_envoy_revalidation', b'@xp2_envoy_consideration'):
            assert self.player == 1 and child is self.token.ui_child
            if name == b'@xp2_envoy_consideration':
                self.envoys_considered = True
            return (f'catalog|1|8|{self.tokens}|1|{int(self.envoys_considered)}|'
                    f'{int(not self.envoys_considered)}|1|2:1:{self.tokens_received}').encode()
        if name == b'@xp2_city_state_levies':
            assert self.player == 1 and b'CanLevyMilitary' in source
            return b'1:8:1|2:0:-:-:1' if self.levy_active else f'1:8:1|2:1:{self.levy_cost}:30:0'.encode()
        if name == b'@xp2_unit_levies':
            assert self.player == 1 and b'IsUnitVisible' in source
            return b'1:8|1:51:2:30' if self.levy_active else b'1:8'
        return super().evaluate(child, source, name, **kw)

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.city_state_pending is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
            operation, self.city_state_pending = self.city_state_pending, None
            if operation == 'envoy':
                self.tokens -= 1
                self.tokens_received += 2
            else:
                self.levy_active = True
                observation = self.observations[1]
                observation['economy']['gold'] -= self.levy_cost
                observation['units'].append(dict(id=51, owner=1, type=21, x=3, y=0,
                    damage=0, moves=0, max_moves=2))
        return drain


class SecondaryWorkFixture(SecondaryGovernmentFixture):
    def __init__(self):
        super().__init__()
        from civ6_host.runtime.native.native_player_observation import observe_player

        self.stack.enter_context(patch.object(native_saved_unit_work, 'observe_player', observe_player))
        self.saved._xp2_lan_city_states_enabled = True
        self.saved._xp2_lan_unit_work_enabled = True
        self.strategic_allowed = False
        self.work_pending = None
        self.charges = 3
        self.improvement = -1
        self.wrong_archive = False

    def evaluate(self, child, source, name, **kw):
        labels = (b'@public_unit_panel_work_information', b'@public_own_unit_work_state',
                  b'@explicit_unit_work_catalog', b'@explicit_unit_work_request',
                  b'@explicit_unit_work_effect', b'@xp2_borrowed_unit_work_index')
        if name not in labels:
            return super().evaluate(child, source, name, **kw)
        assert self.player == 1 and child is self.token.ui_child
        unit = self.observations[1]['units'][0]
        moves = unit['moves']
        building = self.improvement == -1
        if building:
            wire = f'I|28|3|0|3|{self.charges}|{moves}|1|168372657|IMPROVEMENT_FARM|1'
            operation, index = 'BUILD_IMPROVEMENT', 2
        else:
            wire = f'O|28|3|0|3|{self.charges}|{moves}|REMOVE_IMPROVEMENT|2980263204'
            operation, index = 'REMOVE_IMPROVEMENT', 30
        offer = f'\n{wire}|1' if moves else ''
        if name == b'@public_unit_panel_work_information':
            offer = f'\nO|{wire}|1' if moves else ''
            return (f'work-info-v1|1|8{offer}\nP|28|3|{self.improvement}|0|-1|0').encode()
        if name == b'@public_own_unit_work_state':
            return f'unit-work-state-v2|1|8\nU|28|3|{self.charges}|{moves}|{self.improvement}|0|-1|0'.encode()
        if name == b'@explicit_unit_work_catalog':
            return ('work-v1|1|8' + offer).encode()
        if name == b'@explicit_unit_work_effect':
            return f'{self.improvement}|-1|-1|0|0|-1|0|present|{self.charges}|{moves}'.encode()
        if name == b'@xp2_borrowed_unit_work_index':
            assert f"GameInfo.UnitOperations['UNITOPERATION_{operation}']".encode() in source
            return str(index).encode()
        assert name == b'@explicit_unit_work_request' and wire.encode() in source
        self.work_pending = operation
        head = struct.pack('<IHH4I', 0x8c0f3f36, 1, 1, 28, index, 0xffffffff, 0)
        tail = struct.pack('<4I', 1, 0, 168372658 if self.wrong_archive else 168372657, 0) if building else struct.pack('<I', 0)
        self.token.transport.pending.append(head + tail)
        return b'submitted'

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.work_pending is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
            if self.work_pending == 'BUILD_IMPROVEMENT':
                self.improvement = 1
                self.charges -= 1
            else:
                self.improvement = -1
            self.work_pending = None
            self.observations[1]['units'][0]['moves'] = 0
        return drain


class AdjacentWorkFixture(SecondaryWorkFixture):
    def __init__(self, actor=1):
        self.work_actor = actor
        super().__init__()
        import pefile

        core = self.backend.core
        with pefile.PE(core._name, fast_load=True) as image:
            for rva, size, _ in xp2_lan_unit_work._ADJACENT_LAYOUT:
                self.memory.put(core._handle + rva, image.get_data(rva, size))
            for slot, _ in xp2_lan_unit_work._ADJACENT_SLOTS:
                pointer, = struct.unpack('<Q', image.get_data(slot, 8))
                self.memory.put(core._handle + slot, struct.pack(
                    '<Q', pointer - image.OPTIONAL_HEADER.ImageBase + core._handle))
        xp2_lan_unit_work.bind_adjacent(self.saved)
        observation = self.observations[actor]
        self.work_unit = observation['units'][0]['id']
        self.source_x = observation['units'][0]['x']
        self.target_x = 2 if actor == 1 else 1
        plots = observation['plots']
        observed_x = self.target_x if actor == 1 else self.source_x
        plots.insert(0, dict(plots[0], index=observed_x, x=observed_x))
        if actor == 0:
            self.token.observation = deepcopy(observation)
        self.target_improvement = -1
        self.charges = 1
        self.force_offer = True

    def evaluate(self, child, source, name, **options):
        if name == b'@public_own_unit_work_state':
            self._assert_work_actor(child)
            units = self.observations[self.work_actor]['units']
            row = (f"\nU|{self.work_unit}|{self.source_x}|{self.charges}|{units[0]['moves']}|-1|0|-1|0"
                   if units else '')
            return f'unit-work-state-v2|{self.work_actor}|8{row}'.encode()
        if name not in (b'@public_unit_panel_work_information', b'@explicit_unit_work_catalog',
                        b'@explicit_unit_work_request', b'@explicit_unit_work_effect',
                        b'@xp2_borrowed_unit_work_index'):
            return super().evaluate(child, source, name, **options)
        self._assert_work_actor(child)
        actor, uid = self.work_actor, self.work_unit
        units = self.observations[actor]['units']
        moves = units[0]['moves'] if units else 0
        offer = (f'A|{uid}|{self.target_x}|0|{self.target_x}|{self.charges}|{moves}'
                 f'|21|4294967254|IMPROVEMENT_MOUNTAIN_ROAD|12|{self.source_x}|0|{self.source_x}')
        adjacent = b'local adjacentEnabled=true' in source
        available = bool(units) and self.force_offer and adjacent
        if name == b'@public_unit_panel_work_information':
            rows = [f'work-info-v{2 if adjacent else 1}|{actor}|8']
            if available:
                rows.append('O|' + offer + '|1')
            if units:
                rows.append(f'P|{uid}|{self.source_x}|-1|0|-1|0')
            if adjacent and self.target_improvement != -1:
                rows.append(f'V|{self.target_x}|{self.target_improvement}|0|-1|0')
            return '\n'.join(rows).encode('ascii')
        if name == b'@explicit_unit_work_catalog':
            return (f'work-v1|{actor}|8' + ('\n' + offer + '|1' if available else '')).encode('ascii')
        if name == b'@xp2_borrowed_unit_work_index':
            assert b"UNITOPERATION_BUILD_IMPROVEMENT_ADJACENT" in source and b'945035974' in source
            return b'55'
        if name == b'@explicit_unit_work_effect':
            assert f'p=visiblePlot({self.target_x},0)'.encode() in source
            suffix = f'present|{self.charges}|{moves}' if units else 'consumed'
            return f'{self.target_improvement}|-1|-1|0|0|-1|0|{suffix}'.encode('ascii')
        assert available and offer.encode('ascii') in source
        self.work_pending = 'BUILD_IMPROVEMENT_ADJACENT'
        archive = struct.pack('<IHH10I', 0x8c0f3f36, actor, 1, uid, 55, 0xffffffff, 0,
                              1, 0, 4294967254, self.target_x, 0, 0)
        self.token.transport.pending.append(archive)
        return b'submitted'

    def _assert_work_actor(self, child):
        assert self.player == self.work_actor and child is self.token.ui_child

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva != self.token.transport.transport_abi.drain_rva or self.work_pending is None:
            return super().virtual(core, pointer, slot, rva, result, *args)

        def drain(_):
            self.machine.append(('drain',))
            self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
            assert self.work_pending == 'BUILD_IMPROVEMENT_ADJACENT'
            self.work_pending = None
            self.target_improvement = 21
            self.observations[self.work_actor]['units'].clear()
        return drain


class SecondaryCommandTests(unittest.TestCase):
    def test_secondary_archaeology_offers_excavation_then_origin_and_matches_checkpoint_scope(self):
        from civ6_host.contracts import archaeology
        from civ6_host.contracts.information import project
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime import xp2_archaeology, xp2_archaeology_excavation
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        f = SecondaryPurchaseFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        saved._archaeology_core = saved._archaeology_commands_core = f.backend.core
        saved.explicit_archaeology = object()
        original = saved.explicit_archaeology
        unit = f.observations[1]['units'][0]
        uid, x, y = (unit[key] for key in ('id', 'x', 'y'))
        phase = 'excavate'
        actor = 1
        applied = []
        evaluate = saved.prefix.runtime.evaluate_text

        def query(child, source, name, **options):
            if name not in (b'@public_archaeology', b'@public_artifact_excavations'):
                return evaluate(child, source, name, **options)
            self.assertEqual(f.player, actor)
            self.assertIn(b'local pid, turn = 1, 8', source)
            if name == b'@public_archaeology':
                return (f'1|8|{uid}|906|0|6|4|{actor}'.encode('ascii') if phase == 'origin' else b'1|8|none')
            return f'{uid}|{x}|{y}'.encode('ascii') if phase == 'excavate' else b''

        def execute(_, action, observation, *, borrowed_public=None):
            nonlocal phase
            self.assertEqual((f.player, observation['player_id'], observation['turn']), (actor, actor, 8))
            self.assertEqual(action['unit_id'], uid)
            if phase == 'excavate':
                self.assertEqual(action, dict(kind=archaeology.EXCAVATE, unit_id=uid, x=x, y=y))
                phase = 'origin'
            else:
                self.assertEqual(phase, 'origin')
                self.assertEqual(action['origin_player_id'], 4)
                self.assertEqual(borrowed_public['pending']['unit_id'], uid)
                phase = 'complete'
            applied.append(action['kind'])
            return dict(status='completed', refusal_code=None, observation=deepcopy(f.observations[actor]))

        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity, session=dict(turn=8),
                                   catalogues={})
        protocol.selected = lambda message: turns.select_capability(protocol.catalogues[actor], message['selection'])

        def reply(sequence, action=None):
            request = dict(sequence=sequence, player_id=actor, operation='observe' if action is None else 'act')
            if action is not None:
                request['selection'] = dict(decision_id=protocol.catalogues[actor]['decision_id'],
                                            candidate_id=turns.digest(action))
            _, protocol.session, observation, choices, receipt = xp2_lan_unit_commands.read_reply(
                saved, protocol, request, (0, 1))
            turns.validate_catalogue(choices, identity, sequence, 8, player_id=actor, observation=observation)
            protocol.catalogues[actor] = choices
            self.assertIs(saved.explicit_archaeology, original)
            self.assertEqual(f.player, 0)
            return observation, choices, receipt

        with (patch.object(saved.prefix.runtime, 'evaluate_text', side_effect=query),
              patch.object(network_timer, 'read', return_value=False),
              patch.object(xp2_archaeology_excavation, 'apply', side_effect=execute),
              patch.object(xp2_archaeology, 'apply', side_effect=execute)):
            observation, choices, _ = reply(1)
            self.assertIsNone(project('archaeology', observation, choices)['pending'])
            dig = dict(kind=archaeology.EXCAVATE, unit_id=uid, x=x, y=y)
            observation, choices, receipt = reply(2, dig)
            self.assertEqual(receipt['status'], 'completed')
            pending = project('archaeology', observation, choices)['pending']
            self.assertEqual(pending['origin_player_ids'], [4, actor])
            self.assertNotIn('artifact_index', pending)
            self.assertEqual(saved._xp2_borrowed_archaeology[actor][1], 906)
            origin = dict(kind=archaeology.KIND, unit_id=uid, origin_player_id=4)
            observation, choices, receipt = reply(3, origin)
            self.assertEqual(receipt['status'], 'completed')
            self.assertIsNone(project('archaeology', observation, choices)['pending'])
            self.assertEqual(applied, [archaeology.EXCAVATE, archaeology.KIND])

            boundary = xp1_session_checkpoint.boundary(saved)
            current = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
            prior = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,),
                                                        archaeology_mode='off')
            self.assertEqual(current['archaeology_mode'], 'commands')
            self.assertNotIn('archaeology_mode', prior)
            self.assertNotEqual(current['players'][1]['decisions_sha256'], prior['players'][1]['decisions_sha256'])
            body = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                        host_world_selection=None, network_boundary=boundary, host_secondary_world_selections=[])
            saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
            for views in (current, prior):
                with patch.object(network_checkpoint, 'manifest', return_value=dict(body, checkpoint_public_views=views)):
                    self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))

    def test_secondary_world_score_waiting_visibility_and_checkpoint(self):
        from lupa.lua51 import LuaRuntime
        from civ6_host.contracts.information import project
        from civ6_host.runtime import network_checkpoint, player_views, world_score, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        from test_world_score import PRELUDE

        f = SecondaryPurchaseFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        world_score.bind(saved)
        lua = LuaRuntime(encoding=None)
        lua.execute(PRELUDE + b'''
local second=major(1, 2, 21, 4, 1)
local stranger=major(7, 3, 9, 3, 0)
second.GetDiplomacy=function() return {HasMet=function(_,id) return id==0 end} end
Players[1]=second
PlayerManager.GetAliveMajors=function() return {owner,second,stranger} end
Game.GetLocalPlayer=function() return viewer end
Game.GetLocalObserver=function() return viewer end
Game.GetCurrentGameTurn=function() return 8 end
''')
        evaluate = saved.prefix.runtime.evaluate_text

        def query(child, source, name, **options):
            if name != b'@public_world_score':
                return evaluate(child, source, name, **options)
            self.assertIs(child, saved.prefix.ui_child)
            lua.globals()[b'viewer'] = f.player
            return lua.execute(source)

        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity, session=dict(turn=8))
        with (patch.object(saved.prefix.runtime, 'evaluate_text', side_effect=query),
              patch.object(network_timer, 'read', return_value=False)):
            primary = world_score.read(saved, f.observations[0])
            self.assertEqual([p['player_id'] for t in primary['teams'] for p in t['players']], [None, 0, 7])
            before = deepcopy(f.token.observation)
            for sequence, flags in enumerate(((1, 1, 0), (0, 0, 0)), start=1):
                f.turn_rows[1] = flags
                request = dict(sequence=sequence, player_id=1, operation='observe')
                _, protocol.session, observation, choices, _ = xp2_lan_unit_commands.read_reply(
                    saved, protocol, request, (0, 1))
                turns.validate_catalogue(choices, identity, sequence, 8, player_id=1, observation=observation)
                score = project('world_score', observation, choices)
                self.assertEqual([p['player_id'] for t in score['teams'] for p in t['players']], [1, 0, None])
                self.assertEqual((score['player_id'], score['turn'], f.player), (1, 8, 0))
                self.assertEqual(choices['turn_controls']['active'], bool(flags[0]))
                bad = deepcopy(choices)
                bad['world_score']['player_id'] = 0
                with self.assertRaisesRegex(ValueError, 'world score boundary'):
                    turns.validate_catalogue(bad, identity, sequence, 8, player_id=1, observation=observation)
            self.assertEqual(f.token.observation, before)

            f.turn_rows[1] = (1, 1, 0)
            boundary = xp1_session_checkpoint.boundary(saved)
            actual = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
            previous = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,),
                                                            world_score_enabled=False)
            self.assertIs(actual['world_score_enabled'], True)
            self.assertNotIn('world_score_enabled', previous)
            self.assertNotEqual(actual['players'][1]['decisions_sha256'], previous['players'][1]['decisions_sha256'])
            state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                         host_world_selection=None, network_boundary=boundary, host_secondary_world_selections=[])
            saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
            for views in (actual, previous):
                with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=views)):
                    self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
            bad_score = deepcopy(actual)
            bad_score['players'][1]['decisions_sha256'] = 'b' * 64
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=bad_score)):
                with self.assertRaisesRegex(ValueError, 'decision catalogue differs'):
                    network_checkpoint.prepare_owner(saved, f.token.observation)
            with self.assertRaisesRegex(ValueError, 'world score scope'):
                network_checkpoint._checkpoint_view_scope(dict(state, checkpoint_public_views=dict(
                    actual, world_score_enabled=1)))

    def test_secondary_city_panels_follow_the_city_purchase_and_preserve_resume_scope(self):
        from civ6_host.contracts import city_buildings
        from civ6_host.contracts.information import project
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        f = SecondaryCityPanelsFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity, session=dict(turn=8))
        selected = None
        protocol.selected = lambda request: turns.select_capability(selected, request['selection'])
        groups = ['city_buildings', 'city_growth', 'city_loyalty']

        def reply(sequence, action=None):
            nonlocal selected
            request = dict(sequence=sequence, player_id=1, operation='observe' if action is None else 'act')
            if action is not None:
                request['selection'] = dict(decision_id=selected['decision_id'], candidate_id=turns.digest(action))
            _, session, observation, selected, receipt = xp2_lan_unit_commands.read_reply(
                saved, protocol, request, (0, 1))
            turns.validate_catalogue(selected, identity, sequence, 8, player_id=1, observation=observation)
            protocol.session = session
            return observation, selected, receipt

        with patch.object(network_timer, 'read', return_value=False):
            observation, choices, _ = reply(1)
            self.assertEqual(project('city_buildings', observation, choices)['rows'], [])
            city_growth, = project('growth', observation, choices)['cities']
            self.assertEqual(city_growth['display']['GrowthLongNum'], 7)
            self.assertNotIn('food_stock', city_growth)
            self.assertEqual(project('city_loyalty', observation, choices)['cities'][0]['current'], 74)
            foreign = deepcopy(choices)
            foreign['city_growth']['player_id'] = 0
            with self.assertRaisesRegex(ValueError, 'Foreign or unbounded'):
                turns.validate_catalogue(foreign, identity, 1, 8, player_id=1, observation=observation)

            action, = (row['action'] for row in choices['candidates']
                       if row['action'].get('item_type') == 'BUILDING_MONUMENT'
                       and row['action']['kind'] == 'purchase')
            observation, choices, receipt = reply(2, action)
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(observation['economy']['gold'], 180)
            building, = project('city_buildings', observation, choices)['rows']
            self.assertEqual((building['city_id'], building['plot_id'], building['item_type'], building['complete']),
                             (65544, 3, 'BUILDING_MONUMENT', True))

            boundary = xp1_session_checkpoint.boundary(saved)
            views = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
            self.assertEqual(views['city_panel_groups'], groups)
            self.assertEqual(views['city_building_version'], city_buildings.GREAT_WORK_OVERVIEW_SCHEMA)
            legacy = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,),
                city_building_version=city_buildings.SCHEMA)
            self.assertNotIn('city_building_version', legacy)
            self.assertNotEqual(views['players'][1]['decisions_sha256'], legacy['players'][1]['decisions_sha256'])
            old = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,),
                                                      city_panel_groups=())
            self.assertNotIn('city_panel_groups', old)
            state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                         host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views,
                         host_secondary_world_selections=[])
            saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
            with patch.object(network_checkpoint, 'manifest', return_value=state):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
                f.loyalty = 73
                with self.assertRaisesRegex(ValueError, 'decision catalogue differs'):
                    network_checkpoint.prepare_owner(saved, f.token.observation)
            f.loyalty = 74
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=legacy)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=old)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
            invalid = dict(views, city_panel_groups=['city_growth', 'city_growth'])
            with self.assertRaisesRegex(ValueError, 'city panel groups'):
                network_checkpoint._checkpoint_view_scope(dict(state, checkpoint_public_views=invalid))

    def test_secondary_city_religion_reuses_lua_and_exact_checkpoint_scope(self):
        from lupa.lua51 import LuaError
        from civ6_host.contracts import city_religion
        from civ6_host.contracts.information import project
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        f = SecondaryCityReligionFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity, session=dict(turn=8))
        request = dict(sequence=1, player_id=1, operation='observe')
        _, _, observation, choices, _ = xp2_lan_unit_commands.read_reply(saved, protocol, request, (0, 1))
        turns.validate_catalogue(choices, identity, 1, 8, player_id=1, observation=observation)
        public = project('city_religion', observation, choices)
        self.assertEqual(public, dict(schema=city_religion.DETAILS_SCHEMA, player_id=1, turn=8,
            cities=[dict(city_id=65544, majority_religion=3, religions=[
                dict(religion_index=3, followers=1, pressure_per_turn=2, lifetime_pressure=42)])]))
        self.assertEqual((f.player, f.token.observation['player_id']), (0, 0))
        with self.assertRaisesRegex(ValueError, 'authorized human'):
            xp2_lan_unit_commands.read_reply(saved, protocol, request, (0,))
        foreign = deepcopy(choices)
        foreign['city_religion']['cities'][0]['city_id'] = 65543
        with self.assertRaisesRegex(ValueError, 'exact own city set'):
            turns.validate_catalogue(foreign, identity, 1, 8, player_id=1, observation=observation)
        foreign['city_religion'] = city_religion.project_majority(public, 1, 8)
        with self.assertRaisesRegex(ValueError, 'Malformed city religion details'):
            turns.validate_catalogue(foreign, identity, 1, 8, player_id=1, observation=observation)

        boundary = xp1_session_checkpoint.boundary(saved)
        views = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
        self.assertEqual(views['city_panel_groups'], ['city_religion'])
        prior_views = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,),
                                                          city_panel_groups=())
        state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                     host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views,
                     host_secondary_world_selections=[])
        saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        with patch.object(network_checkpoint, 'manifest', return_value=state):
            self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
            f.followers = 2
            with self.assertRaisesRegex(ValueError, 'decision catalogue differs'):
                network_checkpoint.prepare_owner(saved, f.token.observation)
        with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=prior_views)):
            self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
        f.city_owner = 0
        with self.assertRaisesRegex(LuaError, 'belongs to another player'):
            xp2_lan_unit_commands.read_reply(saved, protocol, request, (0, 1))

    def test_secondary_great_people_guard_native_offer_charge_and_checkpoint(self):
        from civ6_host.contracts import great_people_actions
        from civ6_host.contracts.information import project
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        from test_xp1_great_people_commands import _GOLD, _FAITH, _RECRUIT

        f = SecondaryGreatPeopleFixture()
        self.addCleanup(f.close)
        primary_gold = f.observations[0]['economy']['gold']
        saved, identity = f.saved, f.token.identity
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity,
                                   session=dict(turn=8), catalogues={})
        protocol.selected = lambda req: turns.select_capability(protocol.catalogues[1], req['selection'])

        def reply(sequence, action=None):
            request = dict(sequence=sequence, player_id=1, operation='observe' if action is None else 'act')
            if action is not None:
                request['selection'] = dict(decision_id=protocol.catalogues[1]['decision_id'],
                                            candidate_id=turns.digest(action))
            _, session, observation, choices, receipt = xp2_lan_unit_commands.read_reply(
                saved, protocol, request, (0, 1))
            turns.validate_catalogue(choices, identity, sequence, 8, player_id=1, observation=observation)
            protocol.session, protocol.catalogues[1] = session, choices
            return observation, choices, receipt

        f.congress = True
        observation, choices, _ = reply(1)
        self.assertTrue(project('great_people', observation, choices)['read_only'])
        self.assertFalse([row for row in choices['candidates'] if row['action']['kind'] in great_people_actions.KINDS])
        f.congress = False
        _, choices, _ = reply(2)
        self.assertEqual([row['action'] for row in choices['candidates']
                          if row['action']['kind'] in great_people_actions.KINDS],
                         [_GOLD, _FAITH, _RECRUIT, dict(kind='reject_great_person', individual_index=51, cost=2)])
        f.cost = 555
        _, _, refusal = reply(3, _GOLD)
        self.assertEqual(refusal['reason'], 'native_great_person_offer_changed')
        self.assertEqual(f.requests, [])
        action = dict(_GOLD, cost=555)
        f.can_start = False
        _, _, refusal = reply(4, action)
        self.assertEqual(refusal['reason'], 'native_great_person_can_start_false')
        self.assertFalse(f.granted)
        self.assertFalse(any(call[0] == 'receive' for call in f.machine))
        f.can_start = True
        observation, choices, receipt = reply(5, action)
        self.assertEqual(receipt, dict(status='completed', reason=None, requested_action=action))
        self.assertEqual((observation['economy']['gold'], f.observations[0]['economy']['gold']), (175.75, primary_gold))
        self.assertIn((71, 1, 13), [(r['id'], r['owner'], r['type']) for r in observation['units']])
        self.assertEqual(f.requests, [1, 1])
        self.assertEqual((f.player, f.token.observation['player_id']), (0, 0))
        self.assertEqual(saved.explicit_great_people_actions, {'primary': 'retained'})
        self.assertFalse([a for a in great_people_actions.actions(choices['great_people'], include_reject=True)
                          if a['individual_index'] == 117])

        boundary = xp1_session_checkpoint.boundary(saved)
        def checkpoint(**options):
            return player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,), **options)
        modes = [checkpoint(great_people_mode=mode) for mode in ('off', 'read', 'actions')]
        self.assertEqual([item.get('great_people_mode') for item in modes], [None, 'read', 'actions'])
        self.assertEqual(len({item['players'][1]['decisions_sha256'] for item in modes}), 3)
        state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                     host_world_selection=None, network_boundary=boundary,
                     host_secondary_world_selections=[])
        saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        for views in modes:
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=views)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
        f.congress = True
        with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=modes[2])):
            with self.assertRaisesRegex(ValueError, 'decision catalogue differs'):
                network_checkpoint.prepare_owner(saved, f.token.observation)

    def test_secondary_pantheon_routes_the_offered_belief_and_preserves_resume(self):
        from civ6_host.contracts.information import project
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        f = SecondaryPantheonFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        primary_faith = f.observations[0]['economy']['faith']
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity,
                                   session=dict(turn=8), catalogues={})
        protocol.selected = lambda req: turns.select_capability(protocol.catalogues[1], req['selection'])

        def reply(sequence, action=None):
            request = dict(sequence=sequence, player_id=1, operation='observe' if action is None else 'act')
            if action is not None:
                request['selection'] = dict(decision_id=protocol.catalogues[1]['decision_id'],
                                            candidate_id=turns.digest(action))
            _, session, observation, choices, receipt = xp2_lan_unit_commands.read_reply(
                saved, protocol, request, (0, 1))
            turns.validate_catalogue(choices, identity, sequence, 8, player_id=1, observation=observation)
            protocol.session, protocol.catalogues[1] = session, choices
            return observation, choices, receipt

        first = dict(kind='pantheon', index=4, hash=0x80000000)
        second = dict(kind='pantheon', index=7, hash=123)
        f.strategic_allowed = False
        _, choices, _ = reply(1)
        self.assertIsNone(choices['pantheon'])
        self.assertEqual(choices['families']['pantheon']['status'], 'unqualified')
        f.strategic_allowed = True
        observation, choices, _ = reply(2)
        self.assertEqual(project('pantheon', observation, choices)['pantheon_index'], -1)
        self.assertEqual([row['action'] for row in choices['candidates'] if row['action']['kind'] == 'pantheon'],
                         [first, second])
        f.taken.add(4)
        _, _, refusal = reply(3, first)
        self.assertEqual(refusal['reason'], 'native_pantheon_offer_changed')
        self.assertEqual(f.requests, [])
        observation, choices, receipt = reply(4, second)
        self.assertEqual(receipt, dict(status='completed', reason=None, requested_action=second))
        self.assertEqual(project('pantheon', observation, choices)['pantheon_index'], 7)
        self.assertEqual(choices['families']['pantheon']['candidate_ids'], [])
        self.assertEqual((observation['economy']['faith'], f.observations[0]['economy']['faith']), (100, primary_faith))
        self.assertEqual(f.requests, [1])
        self.assertEqual((f.player, f.token.observation['player_id']), (0, 0))
        self.assertEqual(saved.explicit_pantheon, {'primary': 'retained'})

        boundary = xp1_session_checkpoint.boundary(saved)
        live = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
        older = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,),
                                                    pantheon_enabled=False)
        self.assertIs(live['pantheon_enabled'], True)
        self.assertNotIn('pantheon_enabled', older)
        state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                     host_world_selection=None, network_boundary=boundary,
                     host_secondary_world_selections=[])
        saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        for views in (live, older):
            with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=views)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
        f.pantheon = 4
        with patch.object(network_checkpoint, 'manifest', return_value=dict(state, checkpoint_public_views=live)):
            with self.assertRaisesRegex(ValueError, 'decision catalogue differs'):
                network_checkpoint.prepare_owner(saved, f.token.observation)
            self.assertEqual(f.player, 0)

    def test_primary_adjacent_work_uses_the_saved_continuation_and_reads_the_effect(self):
        from civ6_host.runtime.xp1_session_view import _add_unit_work

        f = AdjacentWorkFixture(actor=0)
        self.addCleanup(f.close)
        starting = f.token.observation
        view = dict(turn_controls=dict(active=True, active_complete=True, can_unready=False),
                    families={}, candidates=[])
        _add_unit_work(f.saved, starting, view, actions_closed=False)
        action, = work_contract.actions(view['unit_work'])
        self.assertEqual(action['kind'], work_contract.ADJACENT_KIND)
        self.assertEqual((action['source_plot_id'], action['plot_id']), (0, 1))
        result = f.saved.execute(action)
        self.assertEqual(result['action'], action)
        self.assertEqual(result['observation_after']['units'], [])
        self.assertEqual(result['publication_count'], 1)
        receipt, = [row for stage, row in f.emitted if stage == 'official_explicit_unit_work_effect']
        self.assertEqual(receipt['plot_after']['improvement'], 21)
        self.assertFalse(receipt['plot_after']['unit_present'])
        updated = dict(turn_controls=view['turn_controls'], families={}, candidates=[])
        _add_unit_work(f.saved, f.token.observation, updated, actions_closed=False)
        self.assertEqual(updated['unit_work_info']['visible_plots_with_work'][0]['plot_id'], 1)
        self.assertEqual(updated['unit_work']['offers'], [])

    def test_secondary_adjacent_work_reads_target_after_builder_consumption_and_checkpoint(self):
        from civ6_host.contracts.information import project
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        f = AdjacentWorkFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity,
                                   session=dict(turn=8), catalogue=None)
        protocol.selected = lambda request: turns.select_capability(protocol.catalogue, request['selection'])
        kind = work_contract.ADJACENT_KIND

        def reply(sequence, select=False):
            request = dict(sequence=sequence, player_id=1, operation='act' if select else 'observe')
            if select:
                candidate, = protocol.catalogue['families'][kind]['candidate_ids']
                request['selection'] = dict(decision_id=protocol.catalogue['decision_id'], candidate_id=candidate)
            _, session, observation, choices, receipt = xp2_lan_unit_commands.read_reply(saved, protocol, request, (0, 1))
            turns.validate_catalogue(choices, identity, sequence, 8, player_id=1, observation=observation)
            protocol.session, protocol.catalogue = session, choices
            return observation, choices, receipt

        with patch.object(network_timer, 'read', return_value=False):
            observation, choices, _ = reply(1)
            self.assertEqual(choices['schema'], turns.CAPABILITY_SECONDARY_ADJACENT_WORK_SCHEMA)
            self.assertEqual(choices['families'][kind]['status'], 'queried_complete')
            target, = work_contract.actions(choices['unit_work'])
            self.assertEqual((target['source_plot_id'], target['plot_id']), (3, 2))
            hidden = deepcopy(observation)
            hidden['plots'][0]['visible'] = False
            with self.assertRaisesRegex(ValueError, 'visible source or target'):
                project('unit_work', hidden, choices)
            wrong_target = struct.pack('<IHH10I', 0x8c0f3f36, 1, 1, 28, 55, 0xffffffff, 0,
                                       1, 0, 4294967254, 2, 1, 0)
            with self.assertRaises(ValueError):
                xp2_lan_unit_work.require_archive(wrong_target, 1, target, operation_index=55)

            f.force_offer = False
            _, choices, receipt = reply(2, select=True)
            self.assertEqual(receipt['reason'], 'native_unit_work_choice_unavailable')
            self.assertFalse(any(call[0] == 'receive' for call in f.machine))
            f.force_offer = True
            reply(3)
            observation, choices, receipt = reply(4, select=True)
            self.assertEqual(receipt['status'], 'completed')
            public = project('unit_work', observation, choices)
            self.assertEqual(public['state']['units'], [])
            self.assertEqual(public['info']['visible_plots_with_work'], [
                dict(plot_id=2, improvement=21, improvement_pillaged=False, route=-1, route_pillaged=False)])

            boundary = xp1_session_checkpoint.boundary(saved)
            views = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
            self.assertEqual(views['schema'], player_views.CHECKPOINT_ADJACENT_WORK_SCHEMA)
            state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                         host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views,
                         host_secondary_world_selections=[])
            saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
            with patch.object(saved, '_xp2_lan_adjacent_work_enabled', False):
                previous_views = player_views.checkpoint_view_digests(saved, boundary, (0, 1),
                                                                      decision_players=(1,))
            self.assertEqual(previous_views['schema'], player_views.CHECKPOINT_UNIT_WORK_SCHEMA)
            with patch.object(network_checkpoint, 'manifest', return_value=dict(
                    state, checkpoint_public_views=previous_views)):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
                self.assertTrue(saved._xp2_lan_adjacent_work_enabled)
            with patch.object(network_checkpoint, 'manifest', return_value=state):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
                f.target_improvement = -1
                with self.assertRaisesRegex(ValueError, 'decision catalogue differs'):
                    network_checkpoint.prepare_owner(saved, f.token.observation)
            self.assertEqual(f.player, 0)

    def test_secondary_builder_revalidates_charges_and_reads_back_current_tile_work(self):
        from civ6_host.contracts.information import project
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        f = SecondaryWorkFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity,
                                   session=dict(turn=8), catalogues={})
        protocol.selected = lambda request: turns.select_capability(protocol.catalogues[1], request['selection'])

        def reply(sequence, kind=None):
            request = dict(sequence=sequence, player_id=1, operation='observe' if kind is None else 'act')
            if kind is not None:
                prior = protocol.catalogues[1]
                candidate_id, = prior['families'][kind]['candidate_ids']
                request['selection'] = dict(decision_id=prior['decision_id'], candidate_id=candidate_id)
            _, session, observation, choices, receipt = xp2_lan_unit_commands.read_reply(saved, protocol, request, (0, 1))
            turns.validate_catalogue(choices, identity, sequence, 8, player_id=1, observation=observation)
            protocol.session, protocol.catalogues[1] = session, choices
            return observation, choices, receipt

        with patch.object(network_timer, 'read', return_value=False):
            _, choices, _ = reply(1)
            self.assertEqual(choices['schema'], turns.CAPABILITY_SECONDARY_UNIT_WORK_SCHEMA)
            self.assertIsNone(choices['unit_orders'])
            f.charges = 2
            _, _, receipt = reply(2, 'build_improvement')
            self.assertEqual(receipt['reason'], 'native_unit_work_choice_unavailable')
            self.assertFalse(any(c[0]=='receive' for c in f.machine))
            observation, choices, receipt = reply(3, 'build_improvement')
            self.assertEqual(receipt['status'], 'completed')
            public = project('unit_work', observation, choices)
            self.assertEqual(public['state']['units'][0]['charges'], 1)
            self.assertEqual(public['state']['units'][0]['improvement'], 1)
            self.assertEqual(public['catalogue']['offers'], [])
            f.observations[1]['units'][0]['moves'] = 1
            reply(4)
            _, choices, receipt = reply(5, 'terrain_operation')
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(choices['unit_work_state']['units'][0]['improvement'], -1)
            self.assertEqual(choices['unit_work_state']['units'][0]['charges'], 1)

            boundary = xp1_session_checkpoint.boundary(saved)
            views = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
            self.assertEqual(views['schema'], player_views.CHECKPOINT_UNIT_WORK_SCHEMA)
            state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                         host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views,
                         host_secondary_world_selections=[])
            saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
            with patch.object(network_checkpoint, 'manifest', return_value=state):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
            self.assertEqual(f.player, 0)
            f.observations[1]['units'][0]['moves'] = 1
            reply(6)
            f.wrong_archive = True
            with self.assertRaisesRegex(ValueError, 'actor, unit or operation'):
                reply(7, 'build_improvement')
            self.assertEqual(sum(c[0]=='receive' for c in f.machine), 2)
            self.assertTrue(saved.poisoned)
    def test_secondary_city_states_restore_pending_envoys_and_verify_native_levy(self):
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        f = SecondaryCityStateFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity,
                                   session=dict(turn=8), catalogues={})
        protocol.selected = lambda request: turns.select_capability(protocol.catalogues[1], request['selection'])

        def reply(sequence, kind=None):
            request = dict(sequence=sequence, player_id=1, operation='observe' if kind is None else 'act')
            if kind is not None:
                prior = protocol.catalogues[1]
                candidate_id, = prior['families'][kind]['candidate_ids']
                request['selection'] = dict(decision_id=prior['decision_id'], candidate_id=candidate_id)
            _, session, observation, choices, receipt = xp2_lan_unit_commands.read_reply(saved, protocol, request, (0, 1))
            turns.validate_catalogue(choices, identity, sequence, 8, player_id=1, observation=observation)
            protocol.session, protocol.catalogues[1] = session, choices
            return observation, choices, receipt

        with patch.object(network_timer, 'read', return_value=False):
            _, initial, _ = reply(1)
            self.assertEqual(initial['schema'], turns.CAPABILITY_SECONDARY_CITY_STATES_SCHEMA)
            boundary = xp1_session_checkpoint.boundary(saved)
            views = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
            self.assertEqual(views['schema'], player_views.CHECKPOINT_CITY_STATES_SCHEMA)
            self.assertEqual(views['players'][1]['envoys'], initial['envoys'])
            state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                         host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views,
                         host_secondary_world_selections=[])
            saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
            f.envoys_considered = True
            with patch.object(network_checkpoint, 'manifest', return_value=state):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
            self.assertFalse(f.envoys_considered)
            _, choices, receipt = reply(2, 'retain_envoys')
            self.assertEqual(receipt['status'], 'completed')
            self.assertTrue(choices['envoys']['considered'])
            self.assertEqual(choices['envoys']['tokens_to_give'], 2)
            self.assertFalse(any(call[0]=='receive' for call in f.machine))
            _, choices, receipt = reply(3, 'send_envoy')
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(choices['envoys']['tokens_to_give'], 1)
            self.assertEqual(choices['envoys']['targets'][0]['tokens_received'], 4)

            f.strategic_allowed = False
            _, choices, _ = reply(4)
            self.assertIsNone(choices['envoys'])
            self.assertIsNone(choices['unit_orders'])
            f.levy_cost = 110
            _, _, receipt = reply(5, city_state_levies.ACTION)
            self.assertEqual(receipt['reason'], 'native_city_state_choice_changed')
            observation, choices, receipt = reply(6, city_state_levies.ACTION)
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(observation['economy']['gold'], 190)
            self.assertIn(51, [row['id'] for row in observation['units']])
            self.assertEqual(choices['unit_levies']['units'],
                             [dict(owner=1, unit_id=51, original_owner=2, turns_remaining=30)])
            self.assertTrue(choices['city_state_levies']['city_states'][0]['own_levy_active'])
            self.assertEqual(f.token.explicit_envoys, {'primary': 'retained'})
            self.assertEqual(f.token.explicit_city_state_levies, {'primary': 'retained'})
            self.assertEqual(f.player, 0)
            f.strategic_allowed = True
            reply(7)
            f.wrong_target = True
            with self.assertRaisesRegex(ValueError, 'actor, operation or target'):
                reply(8, 'send_envoy')
            self.assertEqual(sum(call[0]=='receive' for call in f.machine), 2)
            self.assertTrue(saved.poisoned)
    def test_secondary_government_and_policies_route_exact_actor_slots_and_payment(self):
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        f = SecondaryGovernmentFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity,
                                   session=dict(turn=8), catalogues={})
        protocol.selected = lambda request: turns.select_capability(protocol.catalogues[1], request['selection'])

        def reply(sequence, kind=None):
            request = dict(sequence=sequence, player_id=1, operation='observe' if kind is None else 'act')
            if kind is not None:
                prior = protocol.catalogues[1]
                candidate, = (row for row in prior['candidates'] if row['action']['kind'] == kind)
                selection = dict(decision_id=prior['decision_id'], candidate_id=candidate['candidate_id'])
                if kind == 'policies':
                    selection['parameters'] = dict(assignments=[20, 10])
                request['selection'] = selection
            _, session, observation, choices, receipt = xp2_lan_unit_commands.read_reply(saved, protocol, request, (0, 1))
            turns.validate_catalogue(choices, identity, sequence, 8, player_id=1, observation=observation)
            protocol.session, protocol.catalogues[1] = session, choices
            return observation, choices, receipt

        with patch.object(network_timer, 'read', return_value=False):
            _, first, _ = reply(1)
            self.assertEqual(first['schema'], turns.CAPABILITY_SECONDARY_GOVERNMENT_SCHEMA)
            _, choices, receipt = reply(2, 'retain_government')
            self.assertEqual(receipt['status'], 'completed')
            self.assertTrue(choices['government']['considered'])
            self.assertFalse(any(call[0]=='receive' for call in f.machine))
            _, choices, receipt = reply(3, 'government')
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(choices['government']['current_index'], 3)
            f.policy_cost = 65
            _, _, receipt = reply(4, 'policy_unlock')
            self.assertEqual(receipt['reason'], 'native_government_choice_changed')
            self.assertEqual(sum(call[0]=='receive' for call in f.machine), 1)
            observation, choices, receipt = reply(5, 'policy_unlock')
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(observation['economy']['gold'], 235)
            self.assertEqual(choices['policy_unlock']['cost'], 0)
            _, choices, receipt = reply(6, 'policies')
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual([row['prior_index'] for row in choices['policies']['slots']], [1, 0])

            boundary = xp1_session_checkpoint.boundary(saved)
            views = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
            self.assertEqual(views['schema'], player_views.CHECKPOINT_GOVERNMENT_SCHEMA)
            state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                         host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views,
                         host_secondary_world_selections=[])
            saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
            with patch.object(network_checkpoint, 'manifest', return_value=state):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
            self.assertEqual(f.player, 0)
            self.assertEqual(f.token.explicit_government, {'primary': 'retained'})
            self.assertEqual(f.token.explicit_policies, {'primary': 'retained'})
            self.assertEqual(f.token.explicit_policy_unlock, {'primary': 'retained'})
            f.policy_changed = False
            reply(7)
            f.wrong_policy_actor = True
            with self.assertRaisesRegex(ValueError, 'Policy archive header'):
                reply(8, 'policies')
            self.assertEqual(sum(call[0]=='receive' for call in f.machine), 3)
            self.assertTrue(saved.poisoned)
    def test_secondary_purchases_requote_guard_currency_and_refresh_the_own_roster(self):
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        f = SecondaryPurchaseFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity,
                                   session=dict(turn=8), catalogues={})
        protocol.selected = lambda request: turns.select_capability(protocol.catalogues[1], request['selection'])

        def reply(sequence, item=None):
            request = dict(sequence=sequence, player_id=1, operation='observe' if item is None else 'act')
            if item is not None:
                prior = protocol.catalogues[1]
                candidate, = (r for r in prior['candidates'] if r['action']['kind'] == 'purchase'
                              and r['action'].get('item_type', 'plot') == item)
                request['selection'] = dict(decision_id=prior['decision_id'], candidate_id=candidate['candidate_id'])
            _, session, observation, choices, receipt = xp2_lan_unit_commands.read_reply(saved, protocol, request, (0, 1))
            turns.validate_catalogue(choices, identity, sequence, 8, player_id=1, observation=observation)
            protocol.session, protocol.catalogues[1] = session, choices
            return observation, choices, receipt

        with patch.object(network_timer, 'read', return_value=False):
            _, first, _ = reply(1)
            self.assertEqual(first['schema'], turns.CAPABILITY_SECONDARY_PURCHASE_SCHEMA)
            self.assertEqual(len(first['families']['purchase']['candidate_ids']), 4)
            f.plot_price = 50
            _, _, receipt = reply(2, 'plot')
            self.assertEqual(receipt['reason'], 'native_purchase_quote_changed')
            self.assertFalse(any(call[0] == 'receive' for call in f.machine))
            observation, choices, receipt = reply(3, 'plot')
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(observation['economy']['gold'], 250)
            self.assertEqual(choices['plot_purchases'][0]['offers'], [])
            observation, _, receipt = reply(4, 'BUILDING_MONUMENT')
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(observation['economy']['gold'], 130)
            self.assertEqual(f.buildings, {'BUILDING_MONUMENT'})
            observation, choices, receipt = reply(5, 'UNIT_INQUISITOR')
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(observation['economy']['faith'], 55)
            self.assertIn(5, [row['type'] for row in observation['units']])
            self.assertEqual(len(choices['unit_orders']['units']), 2)

            boundary = xp1_session_checkpoint.boundary(saved)
            views = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
            self.assertEqual(views['schema'], player_views.CHECKPOINT_PURCHASE_SCHEMA)
            state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                         host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views,
                         host_secondary_world_selections=[])
            saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
            with patch.object(network_checkpoint, 'manifest', return_value=state):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
            self.assertEqual(f.player, 0)
            f.archive_currency = 5
            with self.assertRaisesRegex(ValueError, 'actor, city, currency or item'):
                reply(6, 'UNIT_SCOUT')
            self.assertEqual(sum(call[0] == 'receive' for call in f.machine), 3)
            self.assertTrue(saved.poisoned)
    def test_secondary_city_and_district_shots_have_distinct_receipts(self):
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        f = SecondaryRangedFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        f.token.explicit_ranged_shots = {'primary': 'retained'}
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity,
                                   session=dict(turn=8), catalogues={})
        protocol.selected = lambda request: turns.select_capability(protocol.catalogues[1], request['selection'])

        def reply(sequence, kind=None):
            request = dict(sequence=sequence, player_id=1, operation='observe' if kind is None else 'act')
            if kind is not None:
                prior = protocol.catalogues[1]
                family = prior['families'][kind]
                candidate_id, = family['candidate_ids']
                request['selection'] = dict(decision_id=prior['decision_id'], candidate_id=candidate_id)
            _, session, observation, choices, receipt = xp2_lan_unit_commands.read_reply(saved, protocol, request, (0, 1))
            turns.validate_catalogue(choices, identity, sequence, 8, player_id=1, observation=observation)
            protocol.session, protocol.catalogues[1] = session, choices
            return observation, choices, receipt

        with patch.object(network_timer, 'read', return_value=False):
            _, choices, _ = reply(1)
            self.assertEqual(choices['schema'], turns.CAPABILITY_SECONDARY_RANGED_SHOTS_SCHEMA)
            self.assertIsNone(choices['captured_city'])
            self.assertNotEqual(choices['families']['city_range_attack']['candidate_ids'],
                                choices['families']['district_range_attack']['candidate_ids'])
            f.center_id = 65545
            _, _, receipt = reply(2, 'city_range_attack')
            self.assertEqual(receipt['reason'], 'native_city_shot_state_changed')
            self.assertFalse(any(call[0] == 'receive' for call in f.machine))
            observation, choices, receipt = reply(3, 'city_range_attack')
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(observation['visible_enemy_units'][0]['damage'], 23)
            self.assertEqual(choices['families']['city_range_attack']['candidate_ids'], [])
            observation, choices, receipt = reply(4, 'district_range_attack')
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(observation['visible_enemy_units'][0]['damage'], 41)
            self.assertEqual(choices['families']['district_range_attack']['candidate_ids'], [])
            self.assertEqual(f.token.explicit_ranged_shots, {'primary': 'retained'})
            self.assertEqual(f.player, 0)
            self.assertEqual(sum(call[0] == 'receive' for call in f.machine), 2)

            boundary = xp1_session_checkpoint.boundary(saved)
            views = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
            self.assertEqual(views['schema'], player_views.CHECKPOINT_RANGED_SHOTS_SCHEMA)
            self.assertIs(views['occupation_enabled'], False)
            state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                         host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views,
                         host_secondary_world_selections=[])
            saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
            with patch.object(network_checkpoint, 'manifest', return_value=state):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
                f.shot_available['district'] = True
                with self.assertRaisesRegex(ValueError, 'public decision catalogue differs for player 1'):
                    network_checkpoint.prepare_owner(saved, f.token.observation)
            reply(5)
            f.archive_type = 2
            with self.assertRaisesRegex(ValueError, 'actor, shooter or destination'):
                reply(6, 'district_range_attack')
            self.assertEqual(sum(call[0] == 'receive' for call in f.machine), 2)
            self.assertTrue(saved.poisoned)

    def test_secondary_captured_city_choices_execute_and_keep_public_recipients_scoped(self):
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        f = SecondaryOccupationFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity, session=dict(turn=8), catalogues={})
        protocol.selected = lambda request: turns.select_capability(protocol.catalogues[1], request['selection'])

        def reply(sequence, directive=None):
            request = dict(sequence=sequence, player_id=1, operation='observe' if directive is None else 'act')
            if directive is not None:
                previous = protocol.catalogues[1]
                action = dict(kind=captured_city.KIND, city_id=65544, directive=directive)
                request['selection'] = dict(decision_id=previous['decision_id'], candidate_id=turns.digest(action))
            _, session, observation, choices, receipt = xp2_lan_unit_commands.read_reply(saved, protocol, request, (0, 1))
            turns.validate_catalogue(choices, identity, sequence, 8, player_id=1, observation=observation)
            protocol.session, protocol.catalogues[1] = session, choices
            return observation, choices, receipt

        feedback_events, flushed = [], []

        def flush():
            flushed.extend(feedback_events)
            feedback_events.clear()
            f.observations[1]['economy']['faith'] += 1
            return []

        with patch.object(network_timer, 'read', return_value=False):
            f.make_city_pending()
            _, first, _ = reply(1)
            self.assertEqual(first['schema'], turns.CAPABILITY_SECONDARY_OCCUPATION_SCHEMA)
            self.assertIsNone(first['unit_orders'])
            self.assertEqual(first['captured_city']['city'], dict(city_id=65544, x=3, y=0,
                liberation_recipients={'LIBERATE_FOUNDER': 5, 'LIBERATE_PREVIOUS_OWNER': 2}))
            f.previous_owner = 4
            _, changed, refused = reply(2, 'LIBERATE_PREVIOUS_OWNER')
            self.assertEqual(refused['reason'], 'native_captured_city_state_changed')
            self.assertFalse(any(call[0] == 'receive' for call in f.machine))
            self.assertEqual(changed['captured_city']['city']['liberation_recipients']['LIBERATE_PREVIOUS_OWNER'], 4)

            boundary = xp1_session_checkpoint.boundary(saved)
            views = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
            self.assertEqual(views['schema'], player_views.CHECKPOINT_OCCUPATION_SCHEMA)
            state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                         host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views,
                         host_secondary_world_selections=[])
            saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
            with patch.object(network_checkpoint, 'manifest', return_value=state):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
                f.previous_owner = 2
                with self.assertRaisesRegex(ValueError, 'public decision catalogue differs for player 1'):
                    network_checkpoint.prepare_owner(saved, f.token.observation)
                f.previous_owner = 4

            f.token.trade_feedback = SimpleNamespace(events=feedback_events, flush=flush)
            for step, directive, owner in ((3, 'LIBERATE_PREVIOUS_OWNER', 4), (5, 'KEEP', 1),
                                          (7, 'RAZE', None), (9, 'LIBERATE_FOUNDER', 5)):
                if step != 3:
                    f.make_city_pending()
                    reply(step - 1)
                observation, after, receipt = reply(step, directive)
                self.assertEqual(receipt['status'], 'completed')
                self.assertEqual(f.city_owner, owner)
                self.assertEqual(bool(observation['cities']), owner == 1)
                self.assertIsNone(after['captured_city']['city'])
                self.assertEqual(observation['economy']['faith'], f.observations[1]['economy']['faith'])
            self.assertEqual(len(flushed), 4)
            self.assertEqual(sum(call[0] == 'receive' for call in f.machine), 4)
            self.assertEqual(f.player, 0)
            self.assertEqual(f.token.explicit_captured_city, {'unchanged_primary_cache': True})
            f.make_city_pending()
            reply(10)
            f.archive_actor = 0
            with self.assertRaisesRegex(ValueError, 'actor, city or directive'):
                reply(11, 'KEEP')
            self.assertEqual(sum(call[0] == 'receive' for call in f.machine), 4)
            self.assertTrue(saved.poisoned)

    def test_attack_catalogue_and_effects_keep_the_secondary_perspective(self):
        from civ6_host.contracts.information import project
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        f = SecondaryCombatFixture()
        self.addCleanup(f.close)
        saved, identity = f.saved, f.token.identity
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity,
                                   session=dict(turn=8), catalogues={})
        protocol.selected = lambda request: turns.select_capability(protocol.catalogues[1], request['selection'])

        def reply(sequence, action=None):
            request = dict(sequence=sequence, player_id=1, operation='observe' if action is None else 'act')
            if action is not None:
                request['selection'] = dict(decision_id=protocol.catalogues[1]['decision_id'],
                                            candidate_id=turns.digest(action))
            _, session, observation, choices, receipt = xp2_lan_unit_commands.read_reply(saved, protocol, request, (0, 1))
            turns.validate_catalogue(choices, identity, sequence, 8, player_id=1, observation=observation)
            protocol.session, protocol.catalogues[1] = session, choices
            return observation, choices, receipt

        def dedicated(choices):
            action, = (row for row in choices['unit_attacks']['offers']
                       if row['input_route'] == 'dedicated_ranged')
            return action

        with patch.object(network_timer, 'read', return_value=False):
            _, choices, _ = reply(1)
            self.assertEqual(choices['schema'], turns.CAPABILITY_SECONDARY_COMBAT_SCHEMA)
            self.assertEqual(choices['families']['unit_attack']['status'], 'queried_partial')
            attack = dedicated(choices)
            f.at_war = False
            _, choices, receipt = reply(2, attack)
            self.assertEqual(receipt['reason'], 'native_unit_attack_unavailable')
            self.assertEqual(choices['unit_attacks']['offers'], [])
            self.assertFalse(any(call[0] == 'receive' for call in f.machine))
            f.at_war = True
            _, choices, _ = reply(3)
            observation, choices, receipt = reply(4, dedicated(choices))
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(observation['visible_enemy_units'][0]['damage'], 28)
            self.assertEqual(choices['unit_attacks']['units'][0]['attacks_remaining'], 0)
            self.assertEqual(choices['unit_attacks']['offers'], [])
            f.remaining, f.mode = 1, 'city'
            f.observations[1]['units'][0]['moves'] = 2
            f.observations[1]['visible_enemy_units'] = []
            observation, choices, _ = reply(5)
            self.assertEqual(choices['unit_attacks']['cities'][0]['defense_strength'], 21)
            self.assertEqual(project('combat', observation, choices)['unit_attacks'], choices['unit_attacks'])
            _, choices, receipt = reply(6, dedicated(choices))
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(choices['unit_attacks']['cities'][0]['outer_damage'], 31)
            f.remaining, f.mode = 1, 'queued'
            f.observations[1]['visible_enemy_units'] = [dict(owner=2, id=58, type=1, x=4, y=0,
                                                           visible=True, damage=0)]
            _, choices, _ = reply(7)
            melee, = choices['unit_attacks']['offers']
            _, choices, receipt = reply(8, melee)
            self.assertEqual((receipt['status'], receipt['reason']),
                             ('submitted', 'native_combat_resolution_pending'))
            self.assertEqual(choices['queued_orders']['units'][0]['plot_id'], 4)
            self.assertEqual(choices['unit_attacks']['units'][0]['attacks_remaining'], 1)
            self.assertEqual(sum(call[0] == 'receive' for call in f.machine), 3)

            boundary = xp1_session_checkpoint.boundary(saved)
            views = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
            self.assertEqual(views['schema'], player_views.CHECKPOINT_COMBAT_SCHEMA)
            state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                         host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views,
                         host_secondary_world_selections=[])
            saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
            with patch.object(network_checkpoint, 'manifest', return_value=state):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
        self.assertEqual(f.player, 0)
        self.assertIsNone(f.token.explicit_combat_units)

    def test_rejects_wrong_seat_attack_before_native_delivery(self):
        from civ6_host.runtime import xp2_human_perspective

        f = SecondaryCombatFixture()
        self.addCleanup(f.close)
        with patch.object(network_timer, 'read', return_value=False):
            initial = xp2_human_perspective.read_network_boundary(f.saved, 1, None)
            attack = next(row for row in initial.unit_attacks['offers'] if row['input_route'] == 'dedicated_ranged')
            f.wrong_owner = True
            with self.assertRaisesRegex(ValueError, 'actor, unit, route or destination'):
                xp2_human_perspective.read_network_boundary(
                    f.saved, 1, attack, expected_city_state=initial.unit_attacks)
        self.assertFalse(any(call[0] == 'receive' for call in f.machine))
        self.assertTrue(f.saved.poisoned)

    def test_promote_and_upgrade_secondary_with_owned_native_quotes(self):
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        f = PerspectiveFixture()
        self.addCleanup(f.close)
        f.enable_turn_fixture()
        f.enable_research_fixture()
        f.enable_production_fixture()
        f.enable_world_fixture()
        f.enable_unit_development_fixture()
        f.turn_rows[2] = (0, 0, 0)
        f.strategic_allowed = False
        f.observations[1]['economy']['gold'] = 120
        saved, identity = f.saved, f.token.identity
        saved.explicit_promotions = {'primary': 'promotions'}
        saved.explicit_unit_upgrades = saved.xp2_unit_upgrades = {'primary': 'quotes'}
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity,
                                   session=dict(turn=8), catalogues={})
        protocol.selected = lambda request: turns.select_capability(protocol.catalogues[1], request['selection'])

        def reply(sequence, action=None):
            request = dict(sequence=sequence, player_id=1, operation='observe' if action is None else 'act')
            if action is not None:
                request['selection'] = dict(decision_id=protocol.catalogues[1]['decision_id'],
                                            candidate_id=turns.digest(action))
            _, session, observation, choices, receipt = xp2_lan_unit_commands.read_reply(saved, protocol, request, (0, 1))
            turns.validate_catalogue(choices, identity, sequence, 8, player_id=1, observation=observation)
            protocol.session, protocol.catalogues[1] = session, choices
            return observation, choices, receipt

        with patch.object(network_timer, 'read', return_value=False):
            _, initial, _ = reply(1)
            self.assertEqual(initial['schema'], turns.CAPABILITY_SECONDARY_DEVELOPMENT_SCHEMA)
            self.assertIsNone(initial['unit_upgrades'])
            self.assertIsNone(initial['unit_orders'])
            promotion, = initial['unit_promotions']['offers']
            _, promoted, receipt = reply(2, promotion)
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual(promoted['unit_promotions']['units'][0]['promotions'], [7])
            f.strategic_allowed = True
            _, opened, _ = reply(3)
            upgrade, = (row['action'] for row in opened['candidates'] if row['action']['kind'] == 'upgrade_unit')
            self.assertEqual((upgrade['cost'], upgrade['resource_type'], upgrade['resource_cost']), (75, 43, 5))
            f.resource_cost = 6
            _, updated, refused = reply(4, upgrade)
            self.assertEqual(refused['reason'], 'native_unit_development_state_changed')
            self.assertEqual(sum(call[0] == 'receive' for call in f.machine), 1)
            events, flushed = [], []

            def flush_feedback():
                flushed.extend(events)
                events.clear()
                f.observations[1]['economy']['faith'] += 1
                return []

            f.token.trade_feedback = SimpleNamespace(events=events, flush=flush_feedback)
            upgrade, = (row['action'] for row in updated['candidates'] if row['action']['kind'] == 'upgrade_unit')
            observation, updated, receipt = reply(5, upgrade)
            self.assertEqual(receipt['status'], 'completed')
            self.assertEqual((observation['units'][0]['id'], observation['units'][0]['type']), (44, 36))
            self.assertEqual(observation['economy']['gold'], 45)
            self.assertEqual(flushed, ['upgrade'])
            self.assertEqual(observation['economy']['faith'], f.observations[1]['economy']['faith'])
            self.assertEqual(updated['unit_upgrades']['offers'], [])
            effect, = (row for stage, row in f.emitted if stage == 'official_xp2_unit_upgrade_effect')
            self.assertEqual((effect['resource_before'], effect['resource_after']), (15, 9))

            boundary = xp1_session_checkpoint.boundary(saved)
            views = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
            self.assertEqual(views['schema'], player_views.CHECKPOINT_DEVELOPMENT_SCHEMA)
            state = dict(observation=deepcopy(f.token.observation), decisions={}, host_placement_tracking=[],
                         host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views,
                         host_secondary_world_selections=[])
            saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
            with patch.object(network_checkpoint, 'manifest', return_value=state):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, f.token.observation)))
        self.assertEqual(saved.explicit_promotions, {'primary': 'promotions'})
        self.assertEqual(saved.xp2_unit_upgrades, {'primary': 'quotes'})
        self.assertEqual(f.player, 0)

        wrong_promotion = struct.pack('<IHH6I', 0x493830af, 1, 1, 28, 13, 0, 1, 0, 19)
        with self.assertRaisesRegex(ValueError, 'actor, unit or operation'):
            xp2_lan_unit_development.validate_archive(wrong_promotion, 1, promotion)

    def test_world_move_checks_actor_and_destination_and_reuses_native_readback(self):
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256

        f = PerspectiveFixture()
        self.addCleanup(f.close)
        f.enable_turn_fixture()
        f.enable_research_fixture()
        f.enable_production_fixture()
        f.enable_world_fixture()
        f.turn_rows[2] = (0, 0, 0)
        saved, identity = f.saved, f.token.identity
        protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=identity,
                                   session=dict(turn=8), catalogues={})
        protocol.selected = lambda request: turns.select_capability(protocol.catalogues[1], request['selection'])

        def read(sequence, action=None):
            request = dict(sequence=sequence, player_id=1, operation='observe' if action is None else 'act')
            if action is not None:
                request['selection'] = dict(decision_id=protocol.catalogues[1]['decision_id'],
                                            candidate_id=turns.digest(action))
            _, session, observation, choices, result = xp2_lan_unit_commands.read_reply(
                saved, protocol, request, (0, 1))
            turns.validate_catalogue(choices, identity, sequence, 8, player_id=1, observation=observation)
            protocol.session, protocol.catalogues[1] = session, choices
            return observation, choices, result

        with patch.object(network_timer, 'read', return_value=False):
            _, choices, _ = read(1)
            self.assertEqual(choices['schema'], turns.CAPABILITY_SECONDARY_WORLD_SCHEMA)
            generated = dict(kind='world_select_unit', unit_id=28)
            _, choices, result = read(2, generated)
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(choices['world_input']['selected_unit_id'], 28)
            self.assertEqual(len(choices['families']['world_plot_click']['candidate_ids']), 74 * 46)
            move = dict(kind='world_plot_click', unit_id=28, plot_id=4, x=4, y=0)
            f.world_click_mode = 'arrive'
            observation, _, result = read(3, move)
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(observation['units'][0]['x'], 4)
            f.world_click_mode = 'queue'
            destination = dict(move, plot_id=8, x=8)
            _, choices, result = read(4, destination)
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(choices['queued_orders']['units'], [dict(unit_id=28, plot_id=8)])
            f.world_click_mode = 'unsupported'
            _, _, result = read(5, dict(move, plot_id=9, x=9))
            self.assertEqual(result['reason'], 'native_world_input_branch_unqualified')
            self.assertEqual(sum(row[0] == 'receive' for row in f.machine), 2)

            boundary = xp1_session_checkpoint.boundary(saved)
            views = player_views.checkpoint_view_digests(saved, boundary, (0, 1), decision_players=(1,))
            primary = f.token.observation
            manifest = dict(observation=deepcopy(primary), decisions={}, host_placement_tracking=[],
                host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views,
                host_secondary_world_selections=[dict(player_id=1, unit_id=28)])
            f.token.world_input_selections = {}
            saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
            with patch.object(network_checkpoint, 'manifest', return_value=manifest):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, primary)))
            self.assertEqual(f.token.world_input_selections, {0: None, 1: 28})
        self.assertEqual(f.player, 0)
        self.assertEqual(f.observations[0]['units'][0]['x'], f.token.observation['units'][0]['x'])
        wrong_actor = struct.pack('<IHH9I', 0x8c0f3f36, 0, 1, 28, 19, 0xffffffff, 0, 1, 4, 0, 16400, 0)
        with self.assertRaisesRegex(ValueError, 'owner, unit, route or destination'):
            xp2_lan_world_input.require_archive(wrong_actor, 1, move)

    def test_city_focus_rejects_the_second_foreign_archive_before_the_first_delivery(self):
        action = dict(kind='city_focus', city_id=65544, yield_type='YIELD_PRODUCTION',
                      yield_index=1, favored=True, disfavored=False)
        city = 65544
        first = struct.pack('<IHH7IB', 0x346b0a13, 1, 2, city, 2, 0, 1, 0, 0, 1, 0)
        foreign_second = struct.pack('<IHH7IB', 0x346b0a13, 0, 2, city, 2, 1, 1, 0, 1, 1, 1)
        transport = xp1_action_transport.SavedActionTransport.__new__(xp1_action_transport.SavedActionTransport)
        transport.transport_abi = SimpleNamespace(core_sha256=xp2_lan_research.XP2_CORE_SHA256)
        transport.pending = []
        transport.require_transition = lambda: None
        transport.require_empty_native_queue = lambda: self.assertEqual(transport.pending, [])
        validators = tuple(lambda archive, request=request: xp2_lan_city_controls.require_archive(
            archive, 1, action, focus_request=request) for request in ((0, 0), (1, 1)))
        with patch.object(xp1_action_transport.NativeActionTransport, 'deliver_one') as receive:
            with self.assertRaisesRegex(RuntimeError, 'player, city or parameters'):
                with transport.require_xp2_archives(validators):
                    transport.pending.extend((first, foreign_second))
                    transport.deliver_one()
            receive.assert_not_called()
        self.assertEqual(transport.pending, [first, foreign_second])

    def test_city_control_refuses_stale_own_city_before_transport(self):
        action = dict(kind='city_citizen', city_id=65544, plot_id=3, x=3, y=0, occupied=True,
                      locked=False, workers=None, capacity=None)
        state = ([], [{'city_id': 65544}], {'city_citizen': [action]})
        with patch.object(citizens, 'apply') as execute:
            receipt, observation = xp2_lan_city_controls.apply(
                None, action, {}, state, expected_city={'city_id': 5})
            execute.assert_not_called()
        self.assertEqual(receipt['reason'], 'native_city_control_state_changed')
        self.assertIsNone(observation)

    def test_queue_changes_refuse_stale_entries_and_wrong_archive_positions(self):
        swap = dict(kind='queue_swap', city_id=65544, source_position=2, destination_position=1)
        current = dict(city_id=65544, offers=[swap], entries=[1, 2, 3])
        receipt, view = xp2_lan_production_queue.apply(
            None, swap, {}, [current], expected_queue={'entries': [1, 3, 2]})
        self.assertEqual(receipt['reason'], 'native_queue_entries_changed')
        self.assertIsNone(view)
        none = 0xffffffff
        wire = [0x7ce9adc2, 0x20001, 65544, 0, 8, 1, none, none, none, none, none,
                0, 0xffffd8f1, 0xffffd8f1, 9, 1, 2]
        xp2_lan_production_queue.require_archive(struct.pack('<17I', *wire), 1, swap)
        wire[-2:] = [2, 1]
        with self.assertRaisesRegex(RuntimeError, 'item or positions'):
            xp2_lan_production_queue.require_archive(struct.pack('<17I', *wire), 1, swap)
        wire[4], wire[7], wire[8], wire[14:] = 0, 1558890441, 0, [0xb, 7, none]
        tail = dict(kind='queue_append', category='unit', city_id=65544, index=22,
                    item_type='UNIT_SLINGER', hash=1558890441, mode='replace_tail')
        xp2_lan_production_queue.require_archive(struct.pack('<17I', *wire), 1, tail)
        with self.assertRaisesRegex(RuntimeError, 'item or positions'):
            xp2_lan_production_queue.require_archive(struct.pack('<17I', *wire), 1,
                                                     dict(tail, mode='append'))

    def test_replacement_refuses_a_stale_city_head_before_request(self):
        action = dict(kind='production', city_id=3, category='unit', index=1,
                      hash=299201842, item_type='UNIT_BUILDER')
        old = dict(city_id=3, queue_size=0, kind='N', item_index=None, hash=0, formation=None)
        snapshot = dict(cities=[dict(city_id=3, queue_size=1, kind='U',
            item_index=7, current_production_hash=19, formation=0)])
        with patch.object(explicit_production_operation, 'apply') as execute:
            receipt, observation = xp2_lan_production.apply(
                None, action, {}, (snapshot, [action]), expected_head=old)
        execute.assert_not_called()
        self.assertEqual(receipt['reason'], 'native_production_state_changed')
        self.assertIsNone(observation)

    def test_production_archive_refuses_foreign_city_wrong_item_and_append(self):
        choice = dict(kind='unit', player_id=1, city_id=65544, operation=739199558, hash=299201842)
        wire = [0x7ce9adc2, 0x20001, 65544, 0, 0, 1, 0xffffffff, 299201842, 0,
                0xffffffff, 0xffffffff, 0, 0xffffd8f1, 0xffffd8f1, 0xb, 0, 0xffffffff]
        xp2_lan_production.require_archive(struct.pack('<17I', *wire), choice)
        for word, changed in ((1, 0x20000), (2, 65536), (7, 19), (14, 3), (15, 1)):
            with self.subTest(word=word):
                altered = wire.copy()
                altered[word] = changed
                with self.assertRaisesRegex(RuntimeError, 'archive differs'):
                    xp2_lan_production.require_archive(struct.pack('<17I', *altered), choice)

    def test_client_to_worker_secondary_opening_choices(self):
        f = PerspectiveFixture()
        self.addCleanup(f.close)
        f.enable_turn_fixture()
        f.enable_research_fixture()
        f.enable_foundation_fixture()
        f.enable_production_fixture()
        f.enable_city_control_fixture()
        f.saved.inputs.checkpoint = None
        f.saved.close = lambda: {'fixture': True}
        current = f.token.identity
        nonce = uuid4().hex
        turn = f.observation['turn']
        controls = dict(schema=turns.TURN_CONTROLS_SCHEMA, player_id=1, turn=turn,
            active=True, active_complete=True, can_unready=False, timer_elapsed=False)
        wake = dict(kind='unit_order', route='command', item_type='UNITCOMMAND_WAKE',
                    unit_id=28, hash=200562917)
        skip = dict(kind='unit_order', route='operation', item_type='UNITOPERATION_SKIP_TURN',
                    unit_id=28, hash=745019656)
        found = dict(kind='found_city', unit_id=29, x=4, y=0)
        builder = dict(kind='production', city_id=65544, category='unit', index=1,
                       hash=299201842, item_type='UNIT_BUILDER')
        append = dict(kind='queue_append', city_id=65544, category='unit', index=22,
                      hash=1558890441, item_type='UNIT_SLINGER', mode='append')
        swap = dict(kind='queue_swap', city_id=65544, source_position=0, destination_position=1)
        remove = dict(kind='queue_remove', city_id=65544, position=1)
        favor = dict(kind='city_focus', city_id=65544, yield_type='YIELD_PRODUCTION',
                     yield_index=1, favored=False, disfavored=False)
        disfavor = dict(favor, favored=True)
        lock = dict(kind='city_citizen', city_id=65544, plot_id=3, x=3, y=0, occupied=True,
                    locked=False, workers=None, capacity=None)
        f.next_offer['UNITCOMMAND_WAKE'] = (skip['item_type'], skip['hash'])
        orders = dict(player_id=1, turn=turn, units=[
            dict(unit_id=28, activity_type=99, fortify_turns=0, ready=True),
            dict(unit_id=29, activity_type=0, fortify_turns=0, ready=True)],
            offers=[dict(action=wake, legal=True)])
        def catalogue(sequence, state, unit_orders, availability, *, tech=None, civic=None,
                      founded=False, entries=(), focus_state=(False, False), qualified_city_controls=True):
            current_choices = None if turns.is_waiting(state) else {
                name: dict(current_index=index,
                    choices=[dict(index=i, hash=h) for i, h in f.choice_layout[name][2]])
                for name, index in [('research', tech), ('civic', civic)]
            }
            production, queues = None, None
            if not turns.is_waiting(state):
                production = dict(current=[], actions=[])
                queues = []
                if founded:
                    head = dict(city_id=65544, queue_size=len(entries), kind='N',
                                item_index=None, hash=0, formation=None)
                    if entries:
                        index, hashed = f.production_items[entries[0]]
                        head.update(kind='U', item_index=index, hash=hashed, formation=0)
                    production['current'] = [head]
                    production['actions'] = [builder]
                    rows = [dict(position=i, category='unit', index=f.production_items[item][0],
                                 hash=f.production_items[item][1], formation=0,
                                 formation_display=dict(is_corps=False, is_army=False))
                            for i, item in enumerate(entries)]
                    offers = [append] + [dict(remove, position=i) for i in range(len(entries))]
                    offers += [dict(swap, source_position=i, destination_position=j)
                               for i in range(len(entries)) for j in range(len(entries)) if i != j]
                    queues.append(dict(schema=QUEUE_SCHEMA, player_id=1, turn=turn, city_id=65544,
                                       enabled=True, entries=rows, offers=offers))
            founders = None if turns.is_waiting(state) else [] if founded else [found]
            focus_values = citizen_values = None
            if qualified_city_controls and production is not None:
                focus_values, citizen_values = [], []
                if founded:
                    yields = [dict(yield_type=name, index=index,
                                   favored=index == 1 and focus_state[0], disfavored=index == 1 and focus_state[1])
                              for index, name in enumerate(focus.YIELDS)]
                    focus_values.append(dict(schema=focus.SCHEMA, player_id=1, turn=turn, city_id=65544,
                                             yields=yields))
                    plot = {key: val for key, val in lock.items() if key in citizens.PLOT_FIELDS}
                    citizen_values.append(dict(schema=citizens.SCHEMA, player_id=1, turn=turn,
                                               city_id=65544, plots=[plot]))
            schema = (turns.CAPABILITY_SECONDARY_CITY_CONTROLS_SCHEMA if qualified_city_controls
                      else turns.CAPABILITY_SECONDARY_QUEUE_SCHEMA)
            return turns.secondary_unit_catalogue(current, sequence, turn, 1, state, unit_orders,
                schema=schema, turn_availability=availability, city_focus_catalogs=focus_values,
                citizen_catalogs=citizen_values,
                research_choices=current_choices, founders=founders, production_choices=production,
                production_queues=queues)

        active = dict(end_turn=True, force_end_turn=True, unready_turn=False)
        waiting = dict(end_turn=False, force_end_turn=True, unready_turn=True)
        decision = catalogue(1, controls, orders, active)
        next_orders = dict(orders, units=[dict(orders['units'][0], activity_type=100), orders['units'][1]],
                           offers=[dict(action=skip, legal=True)])
        next_decision = catalogue(2, controls, next_orders, active)
        skipped_orders = dict(next_orders, units=[dict(orders['units'][0], activity_type=101), orders['units'][1]])
        turn_decision = catalogue(3, controls, skipped_orders, active)
        ready_controls = dict(controls, active=False, can_unready=True)
        waiting_decision = catalogue(4, ready_controls, None, waiting)
        forced_decision = catalogue(5, ready_controls, None, waiting)
        unready_decision = catalogue(6, controls, skipped_orders, active)
        research_decision = catalogue(7, controls, skipped_orders, active, tech=3)
        civic_decision = catalogue(8, controls, skipped_orders, active, tech=3, civic=4)
        foundation_decision = catalogue(9, controls, skipped_orders, active, tech=3, civic=4)
        post_foundation_orders = dict(skipped_orders, units=skipped_orders['units'][:1])
        after_foundation = catalogue(10, controls, post_foundation_orders, active,
                                     tech=3, civic=4, founded=True)
        after_builder = catalogue(11, controls, post_foundation_orders, active,
                                  tech=3, civic=4, founded=True, entries=('UNIT_BUILDER',))
        after_append = catalogue(12, controls, post_foundation_orders, active,
                                  tech=3, civic=4, founded=True, entries=('UNIT_BUILDER', 'UNIT_SLINGER'))
        after_swap = catalogue(13, controls, post_foundation_orders, active,
                                tech=3, civic=4, founded=True, entries=('UNIT_SLINGER', 'UNIT_BUILDER'))
        city_options = dict(tech=3, civic=4, founded=True, entries=('UNIT_SLINGER',))
        after_remove = catalogue(14, controls, post_foundation_orders, active, **city_options)
        after_favor = catalogue(15, controls, post_foundation_orders, active,
                                focus_state=(True, False), **city_options)
        after_disfavor = catalogue(16, controls, post_foundation_orders, active,
                                   focus_state=(False, True), **city_options)
        tech_choice = dict(kind='research', index=3, hash=2080815322)
        civic_choice = dict(kind='civic', index=4, hash=4228356462)
        old = turns.secondary_unit_catalogue(current, 1, turn, 1, controls, orders,
                                              schema=turns.CAPABILITY_SECONDARY_UNIT_SCHEMA)
        self.assertEqual(turns.validate_catalogue(old, current, 1, turn, player_id=1), old)
        older_turns = turns.secondary_unit_catalogue(
            current, 1, turn, 1, controls, orders, schema=turns.CAPABILITY_SECONDARY_TURN_SCHEMA,
            turn_availability=active)
        self.assertEqual(turns.validate_catalogue(older_turns, current, 1, turn, player_id=1),
                         older_turns)
        previous = turns.secondary_unit_catalogue(
            current, 1, turn, 1, controls, orders, schema=turns.CAPABILITY_SECONDARY_RESEARCH_SCHEMA,
            turn_availability=active, research_choices=decision['research_choices'])
        self.assertEqual(turns.validate_catalogue(previous, current, 1, turn, player_id=1), previous)
        v5 = turns.secondary_unit_catalogue(
            current, 1, turn, 1, controls, orders, schema=turns.CAPABILITY_SECONDARY_FOUNDERS_SCHEMA,
            turn_availability=active, research_choices=decision['research_choices'], founders=[found])
        self.assertEqual(turns.validate_catalogue(v5, current, 1, turn, player_id=1), v5)
        v6 = turns.secondary_unit_catalogue(
            current, 1, turn, 1, controls, orders, schema=turns.CAPABILITY_SECONDARY_PRODUCTION_SCHEMA,
            turn_availability=active, research_choices=decision['research_choices'],
            founders=[found], production_choices=decision['production_choices'])
        self.assertEqual(turns.validate_catalogue(v6, current, 1, turn, player_id=1), v6)
        v7 = catalogue(14, controls, post_foundation_orders, active, qualified_city_controls=False,
                       **city_options)
        self.assertEqual(turns.validate_catalogue(v7, current, 14, turn, player_id=1), v7)
        with self.assertRaisesRegex(ValueError, 'own-unit observation'):
            turns.secondary_unit_catalogue(
                current, 1, turn, 1, controls, orders, schema=turns.CAPABILITY_SECONDARY_FOUNDERS_SCHEMA,
                observation=f.observations[1], founders=[dict(found, x=3)])
        with self.assertRaisesRegex(ValueError, 'Skip-turn order'):
            turns.secondary_unit_catalogue(current, 2, turn, 1, controls, next_orders,
                                           schema=turns.CAPABILITY_SECONDARY_UNIT_SCHEMA)

        def envelope(op, seq, actor):
            return dict(schema=SCHEMA, nonce=nonce, episode_id=current.episode_id,
                game_generation=current.game_generation, sequence=seq, operation=op, player_id=actor)

        observe, act = envelope('observe', 1, 1), envelope('act', 2, 1)
        skip_request, close = envelope('act', 3, 1), envelope('close', 18, 0)
        act['selection'] = dict(decision_id=decision['decision_id'], candidate_id=turns.digest(wake))
        skip_request['selection'] = dict(decision_id=next_decision['decision_id'],
                                         candidate_id=turns.digest(skip))
        def select(sequence, decisions, action):
            return dict(envelope('act', sequence, 1), selection=dict(
                decision_id=decisions['decision_id'], candidate_id=turns.digest(action)))

        commands = [observe, act, skip_request, select(4, turn_decision, dict(kind='end_turn')),
                    select(5, waiting_decision, dict(kind='force_end_turn')),
                    select(6, forced_decision, dict(kind='unready_turn')),
                    select(7, unready_decision, tech_choice), select(8, research_decision, civic_choice),
                    select(9, civic_decision, tech_choice), select(10, foundation_decision, found),
                    select(11, after_foundation, builder), select(12, after_builder, append),
                    select(13, after_append, swap), select(14, after_swap, remove),
                    select(15, after_remove, favor), select(16, after_favor, disfavor),
                    select(17, after_disfavor, lock), close]
        incoming = BytesIO(b'go\n' + b''.join(json.dumps(cmd).encode() + b'\n' for cmd in commands))
        from civ6_host.runtime import xp1_session_view

        def read_primary(saved, pid, sequence, *, actions_closed, **_):
            self.assertEqual((saved, pid, f.player), (f.saved, 0, 0))
            observation = deepcopy(f.token.observation)
            session = dict(game_mode='LAN', turn_phase='TURNPHASE_SIMULTANEOUS', turn=turn,
                local_player_id=0, human_player_ids=[0, 1], active_human_player_ids=[0, 1])
            choices = dict(schema=turns.CAPABILITY_SCHEMA, episode_id=current.episode_id,
                game_generation=current.game_generation, sequence=sequence, player_id=0, turn=turn,
                turn_controls=dict(controls, player_id=0), candidates=[],
                families={'found_city': {'status': 'unqualified', 'reason': 'fixture_primary'}},
                family_inventory_complete=False, complete_action_space=False)
            choices['decision_id'] = turns.digest(choices)
            return session, observation, choices

        with tempfile.TemporaryDirectory() as name:
            directory = Path(name).resolve()
            closure_path = directory / 'closure.json'
            instance = NativeNetworkSession.__new__(NativeNetworkSession)
            instance.public_view_players = (0, 1)
            closure = dict(schema=CLOSURE_SCHEMA, input_profile='xp2-lan', nonce=nonce,
                execution_image=identity(_PROFILE), initial_turn=turn, lifetime_seconds=120,
                rounds=2, stdout_limit_bytes=64 * 1024**2,
                official_bundle=dict(path='fixture.json', sha256='a'*64), pins={},
                secondary_unit_commands=True)
            instance._configure_public_views(closure)
            for module in (turns, xp1_choice_queries, xp2_lan_research, xp2_lan_unit_commands,
                           xp2_lan_production, explicit_production_operation,
                           xp1_action_transport, xp1_production_queue, xp2_lan_production_queue,
                           xp2_lan_city_controls, xp2_lan_world_input, xp2_lan_unit_development,
                           xp2_promotions, xp2_unit_upgrades, xp2_lan_unit_attacks, native_saved_combat,
                           captured_city, captured_city_session, native_saved_captured_city,
                           city_ranged, xp2_lan_ranged_shots, native_saved_city_shot, native_saved_district_shot,
                           plot_purchases, xp2_plot_purchases, native_plot_purchases, native_saved_purchases,
                           xp2_lan_government, xp2_government, xp2_policies, xp2_policy_unlock, native_policy_actions,
                           capability_policies, government, policies, policy_unlock,
                           city_state_levies, envoys, xp1_city_state_levies, xp2_city_state_levies,
                           xp2_envoys, xp2_lan_city_states, work_contract, unit_work_info, unit_work_state,
                           work_info_contract, work_state_contract, xp2_lan_unit_work, native_saved_unit_work):
                path = Path(module.__file__).resolve()
                closure['pins'][str(path)] = file_sha256(path)
            closure_path.write_text(json.dumps(closure), encoding='utf-8')
            stdout = StringIO()
            with (patch.object(native_probe, 'Windows'),
                  patch.object(native_checkpoint_stream, 'terminate_worker', side_effect=SupervisedStop) as stop,
                  patch.object(worker, 'BaseException', Exception, create=True),
                  patch.object(worker.sys, 'stdin', SimpleNamespace(buffer=incoming)),
                  patch.object(worker, '_open_xp1', return_value=(f.saved, None)),
                  patch.object(worker, '_emit_native_load_profile'),
                  patch.object(xp1_session_view, 'read', side_effect=read_primary),
                  patch('civ6_host.runtime.xp2_end_turn_readback.read', return_value={}),
                  patch.object(network_timer, 'read', return_value=False),
                  redirect_stdout(stdout),
                  self.assertRaises(SupervisedStop)):
                worker.main(str(closure_path))
            stop.assert_called_once_with(90)
            rows = [json.loads(line) for line in stdout.getvalue().splitlines()]
            replies = [row for row in rows if row['stage'] == 'official_session_response']
            views = [row for row in rows if row['stage'] == 'host_public_player_views']
            self.assertEqual(len(views), 18)

        class Backend:
            controllable_player_ids = (0, 1)
            session_operations_player_id = 0

            def reset(self):
                return deepcopy(replies[0])

            def request(self, request):
                offset = request['sequence'] - 1
                self.assertion(request, commands[offset])
                return deepcopy(replies[offset + 1])

            def abort(self, reason):
                raise AssertionError(reason)

        backend = Backend()
        backend.assertion = self.assertEqual
        client = SessionClient(backend)
        client.reset()
        second = client.observe(1)
        self.assertEqual(second['observation']['player_id'], 1)
        with self.assertRaisesRegex(ProtocolError, 'poll and close'):
            client.poll(1)
        applied = client.act(1, second['decisions']['decision_id'], turns.digest(wake))
        self.assertEqual(applied['applied_action'], wake)
        self.assertEqual(replies[2]['outcome']['native_victory']['player_id'], 1)
        skipped = client.act(1, applied['decisions']['decision_id'], turns.digest(skip))
        self.assertEqual(skipped['applied_action'], skip)
        self.assertEqual(skipped['observation']['turn'], turn)
        self.assertEqual(f.unit_activity, {0: 0, 1: 101})
        ended = client.act(1, skipped['decisions']['decision_id'], turns.digest(dict(kind='end_turn')))
        self.assertEqual(ended['applied_action'], dict(kind='end_turn'))
        self.assertEqual(client.session_state['active_human_player_ids'], [0])
        self.assertIsNone(ended['decisions']['research_choices'])
        self.assertIsNone(ended['decisions']['founders'])
        self.assertIsNone(ended['decisions']['city_focus_catalogs'])
        self.assertIsNone(ended['decisions']['citizen_catalogs'])
        forced = client.act(1, ended['decisions']['decision_id'], turns.digest(dict(kind='force_end_turn')))
        self.assertEqual(client.command_result['status'], 'submitted')
        self.assertIsNone(forced['applied_action'])
        unready = client.act(1, forced['decisions']['decision_id'], turns.digest(dict(kind='unready_turn')))
        self.assertEqual(unready['applied_action'], dict(kind='unready_turn'))
        self.assertEqual(client.session_state['active_human_player_ids'], [0, 1])
        self.assertEqual(f.turn_requests, [('end_turn', 1), ('force_end_turn', 1), ('unready_turn', 1)])
        researched = client.act(1, unready['decisions']['decision_id'], turns.digest(tech_choice))
        self.assertEqual(researched['applied_action'], tech_choice)
        self.assertEqual(researched['decisions']['research_choices']['research']['current_index'], 3)
        civics = client.act(1, researched['decisions']['decision_id'], turns.digest(civic_choice))
        self.assertEqual(civics['applied_action'], civic_choice)
        self.assertEqual(civics['decisions']['research_choices']['civic']['current_index'], 4)
        repeated = client.act(1, civics['decisions']['decision_id'], turns.digest(tech_choice))
        self.assertIsNone(repeated['applied_action'])
        self.assertEqual(client.command_result['status'], 'submitted')
        self.assertEqual(f.current_research, {0: dict(research=9, civic=6), 1: dict(research=3, civic=4)})
        self.assertEqual(f.research_requests, [(1, 'research', 3), (1, 'civic', 4), (1, 'research', 3)])
        founded = client.act(1, repeated['decisions']['decision_id'], turns.digest(found))
        self.assertEqual(founded['applied_action'], found)
        self.assertEqual(founded['decisions']['founders'], [])
        self.assertEqual([row['id'] for row in founded['observation']['units']], [28])
        city = founded['observation']['cities'][0]
        self.assertEqual((city['id'], city['owner'], city['x'], city['y']), (65544, 1, 4, 0))
        self.assertEqual(f.token.observation['cities'], [])
        selected = client.act(1, founded['decisions']['decision_id'], turns.digest(builder))
        self.assertEqual(selected['applied_action'], builder)
        self.assertEqual(selected['decisions']['production_choices']['current'], [
            dict(city_id=65544, queue_size=1, kind='U', item_index=1, hash=299201842, formation=0)])
        queued = client.act(1, selected['decisions']['decision_id'], turns.digest(append))
        self.assertEqual(queued['applied_action'], append)
        self.assertEqual([row['index'] for row in queued['decisions']['production_queues'][0]['entries']],
                         [1, 22])
        reordered = client.act(1, queued['decisions']['decision_id'], turns.digest(swap))
        self.assertEqual(reordered['applied_action'], swap)
        self.assertEqual([row['index'] for row in reordered['decisions']['production_queues'][0]['entries']],
                         [22, 1])
        removed = client.act(1, reordered['decisions']['decision_id'], turns.digest(remove))
        self.assertEqual(removed['applied_action'], remove)
        self.assertEqual([row['index'] for row in removed['decisions']['production_queues'][0]['entries']],
                         [22])
        self.assertEqual(f.production_queue, ['UNIT_SLINGER'])
        favored = client.act(1, removed['decisions']['decision_id'], turns.digest(favor))
        self.assertEqual(favored['applied_action'], favor)
        disfavored = client.act(1, favored['decisions']['decision_id'], turns.digest(disfavor))
        self.assertEqual(disfavored['applied_action'], disfavor)
        self.assertTrue(disfavored['decisions']['city_focus_catalogs'][0]['yields'][1]['disfavored'])
        locked = client.act(1, disfavored['decisions']['decision_id'], turns.digest(lock))
        self.assertEqual(locked['applied_action'], lock)
        self.assertTrue(locked['decisions']['citizen_catalogs'][0]['plots'][0]['locked'])
        self.assertEqual(f.focus_flags[1], (False, True))
        self.assertEqual((f.token.sequence, f.player, f.token.observation['cities']), (16, 0, []))
        client.close()
        self.assertEqual(replies[-1]['outcome']['native_victory']['player_id'], 0)
