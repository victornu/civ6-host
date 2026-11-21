"""Exercise the saved owner boundary with current Core bytes and fixture calls."""

import ctypes as C
import json
import struct
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from zlib import crc32

import pefile

from civ6_host.runtime import xp2_human_perspective as perspective
from civ6_host.runtime import xp2_lan_research as lan_research
from civ6_host.runtime import xp2_local_player_changed as changed
from civ6_host.runtime import foundation_event_profile
from civ6_host.runtime import xp2_unit_orders_source as orders_source
from civ6_host.runtime.configuration_profiles import _source
from civ6_host.runtime.captured_session_profile import select as select_capture
from civ6_host.runtime.execution_images import known_path, select
from civ6_host.runtime.lan_load import _LAN_MODE, _SIMULTANEOUS_PHASE
from civ6_host.runtime.native import native_player_observation as observations
from civ6_host.runtime.native.native_saved_player_map import validate
from civ6_host.runtime.xp1_continuation import READY
from test_xp1_turn_a0 import scalar
import xp2_unit_attack_owner_fixture as fixture

_OBSERVE_PLAYER = observations.observe_player


class PerspectiveFixture(fixture.Fixture):
    production_items = {'UNIT_BUILDER': (1, 299201842), 'UNIT_SLINGER': (22, 1558890441)}
    choice_layout = {
        'research': (1848062833, 347601064, ((0, 952445125), (3, 2080815322))),
        'civic': (2678441256, 2786034420, ((0, 996177632), (4, 4228356462))),
    }

    def __init__(self):
        image_id = 'xp2-gamecore-current-4de40abf'
        image = select(image_id, core_path=known_path(image_id))
        pillage_source = foundation_event_profile.pillage_source
        original_graph = fixture.XP2ComposedNotifications.graph

        def current_graph(test):
            graph = original_graph(test)
            graph.backend.core._civ6_host_execution_image = image
            graph.backend.core._name = image.path
            return graph

        with (patch.object(foundation_event_profile, 'pillage_source',
                           lambda **_: pillage_source(execution_image=image)),
              patch.object(fixture.XP2ComposedNotifications, 'graph', current_graph)):
            super().__init__()
        self.saved._running = False
        bundle = self.backend.captured_bundle
        candidate = select_capture(self.saved._engine_sha256,
                                   official_bundle=bundle.reference).candidate
        self.saved.inputs.profile = candidate.profile
        self.saved.inputs.official_bundle = bundle.reference
        self.player = 0
        self.switches = []
        self.fail_target_read = False
        self.extra_revealed = {}
        self.ignore_setter = False
        self.changes_readiness = False
        self.restore_corrupts_view = False
        self.defeated_secondary = False
        self.command_archive_owner = None
        self.command_archive_unit = None
        self.command_archive_route = None
        self.operation_target = 0xffffffff
        self.command_effect = True
        self.turn_rows = {0: (1, 1, 0), 1: (1, 1, 0), 2: (1, 1, 0)}
        self.turn_requests = []
        self.completion_sender = None
        self.turn_blocked = False
        self.current_research = {0: dict(research=9, civic=6), 1: dict(research=None, civic=None)}
        self.research_requests = []
        self.research_queued = None
        self.research_wrong_parameter = False
        self.research_applies = True
        self.founder = None
        self.foundation_queued = False
        self.foundation_opcode = 14
        self.production_queue = []
        self.queue_command = None
        self.production_queued = False
        self.world_click_mode = None
        self.world_click_queued = None
        self.strategic_allowed = True
        self.development_queued = None
        self.acquired_promotions = []
        self.resource_stockpile = 15
        self.resource_cost = 5
        self.focus_flags = [(False, False)] * 6
        self.citizen_locked = False
        self.city_control_requests = []
        self.token.world_input_prompts = {}
        self.token.world_input_selections = {}
        self.token.trade_feedback = None
        self.saved.prefix.deferred_events.pending_diplomacy_statements = []
        self.unit_activity = {0: 0, 1: 99}
        self.destinations = {0: 8, 1: None}
        self.offers = {0: ('UNITCOMMAND_CANCEL', 533311341), 1: ('UNITCOMMAND_WAKE', 200562917)}
        self.next_offer = {}
        self.humans = b'0=1|1=1|2=0'
        self.observations = {0: deepcopy(self.observation), 1: deepcopy(self.observation)}
        other = self.observations[1]
        other['player_id'] = 1
        other['units'][0].update(id=28, owner=1, x=3)
        other['plots'][0].update(index=3, x=3, owner=1)
        other['visible_enemy_units'] = []
        self.saved.network_reference = dict(
            capture_manifest_sha256=self.backend.captured_bundle.reference[1],
            state=dict(player_id=0, observer_id=0, game_mode_u32=_LAN_MODE,
                       turn_phase_u32=_SIMULTANEOUS_PHASE),
            major_player_ids=(0, 1, 2), human_player_ids=(0, 1),
        )
        proof = _source(perspective.SOURCE)
        self.abi = proof['abi']
        with pefile.PE(image.path, fast_load=True) as installed:
            for span in proof['spans'].values():
                rva = int(span['rva'], 16)
                self.memory.put(self.memory.base + rva, installed.get_data(rva, span['bytes']))
            for rva, raw in changed.core_fragments():
                self.memory.put(self.memory.base + rva, installed.get_data(rva, len(raw)))
            for rva, raw in perspective._TURN_COMPLETION_SPANS:
                self.memory.put(self.memory.base + rva, installed.get_data(rva, len(bytes.fromhex(raw))))
            for rva, size, _ in lan_research._SPANS:
                self.memory.put(self.memory.base + rva, installed.get_data(rva, size))
            for slot, _ in lan_research._SLOTS:
                target, = struct.unpack('<Q', installed.get_data(slot, 8))
                self.memory.put(self.memory.base + slot,
                                struct.pack('<Q', target - installed.OPTIONAL_HEADER.ImageBase + self.memory.base))
            table, entries = orders_source.COMMAND_TABLE
            raw_table = installed.get_data(table, 8 * len(entries))
            relocated = [value - installed.OPTIONAL_HEADER.ImageBase + self.memory.base
                         for (value,) in struct.iter_unpack('<Q', raw_table)]
            self.memory.put(self.memory.base + table,
                            struct.pack('<' + 'Q' * len(relocated), *relocated))
        self.game, visibility = 0xd20000, 0xd21000
        self.global_owner = self.token.lease.identity['game']
        context, indices, slots = 0xd22000, 0xd23000, 0xd24000
        self.indices, self.slots = indices, slots
        a = self.abi
        for address, value in (
            (self.memory.base + a['game_global_rva'], self.game),
            (self.memory.base + a['owner_global_rva'], self.global_owner),
            (self.global_owner + a['owner_game_offset'], self.game),
            (self.global_owner + a['owner_visibility_offset'], visibility),
            (visibility + a['visibility_context_offset'], context),
            (context + a['visibility_slot_indices_offset'], indices),
            (context + a['visibility_slots_offset'], slots),
            (slots, 0xd25000), (slots + 8, 0xd26000),
        ):
            self.memory.put(address, struct.pack('<Q', value))
        self.memory.put(context + a['notification_suppressed_offset'], b'\0')
        self.memory.put(indices, struct.pack('<ii', 0, 1))
        self.set_perspective(0)
        self.arguments.reader.base = self.memory.base
        # The unrelated meeting and research machine callbacks are not used.
        with (patch('civ6_host.runtime.xp1_diplomacy_meet_source.verify_live'),
              patch('civ6_host.runtime.a0_notification_scope_source.verify_research_changed_live')):
            self.owner.enable_notification_scopes(script_hashes={'stock': changed.STOCK_SCRIPT})
        self.stack.enter_context(patch.object(observations, 'observe_player', _OBSERVE_PLAYER))

    def set_perspective(self, player):
        self.player = player
        for name in ('game_local_offset', 'game_observer_offset'):
            self.memory.put(self.game + self.abi[name], struct.pack('<i', player))

    def factory(self, result, *args):
        fallback = super().factory(result, *args)

        def bind(address):
            if not hasattr(self, 'abi') or address != self.memory.base + self.abi['call_rva']:
                return fallback(address)
            assert (result, args) == (C.c_uint8, (C.c_void_p, C.c_int32))

            def switch(game, player):
                assert game == self.game and self.backend.busy
                self.switches.append(player)
                if not self.ignore_setter:
                    self.set_perspective(player)
                if self.restore_corrupts_view and player == 0:
                    self.observations[0]['units'][0]['moves'] = 0
                # A real notification codec and shared FIFO consume the record
                # emitted by the machine fixture.
                fields = {0xA1E5A149: scalar(3, 0), 0xD6FCF3E4: scalar(2, player)}
                assert self.owner.dispatch(changed.KIND, fields, 0) == 0
                return 1

            return switch

        return bind

    def evaluate(self, child, source, name, **kw):
        if name in (b'@xp2_perspective_humans', b'@lan_session_humans'):
            assert child is self.token.game_child
            return self.humans
        if name == b'@xp2_perspective_living':
            assert child is self.token.game_child and b':IsAlive()' in source
            if self.defeated_secondary and b'ipairs({0,1})' in source:
                return b'defeated'
            return b'living'
        assert child is self.token.ui_child, name
        if name == b'@lan_turn_activity':
            rows = dict(self.turn_rows)
            if self.changes_readiness and self.player == 1:
                rows[1] = (1, 1, 1)
            activity = ';'.join(','.join(map(str, (pid, *state))) for pid, state in rows.items())
            return f'8|{self.player}|{self.player}|{activity}'.encode()
        if name == b'@xp1_human_turn_gates':
            assert f'local pid={self.player}\nlocal turn=8\n'.encode() in source
            active, complete, unready = self.turn_rows[self.player]
            blocker = '41' if self.turn_blocked else ''
            return (f'8|{self.player}|{blocker or 0}|0|{blocker}|'
                    f'1,{active},{complete},{unready},1,1,0,0,0|41,42,43').encode()
        if name in (b'@explicit_research_catalog', b'@explicit_current_research',
                    b'@native_research_revalidation', b'@native_research_after'):
            return self.evaluate_research(source, name)
        if name == b'@xp1_session_winner':
            return b'none'
        if name == b'@xp1_session_episode_facts':
            assert f'local pid,expectedTurn={self.player},8'.encode() in source
            return f'episode-facts-v1|{self.player}|8|{self.player}|1|1|0'.encode()
        obs = self.observations[self.player]
        if name == b'@native_found_city_catalog':
            assert f'local pid,expectedTurn={self.player},8'.encode() in source
            if self.founder is None or self.player != 1:
                return f'{self.player},8,0'.encode()
            return b'1,8,1;29,4,0'
        if name == b'@native_found_city_legality':
            assert b'local selectedID=29\nlocal pid=1' in source
            assert self.player == 1 and self.founder is not None
            return b'1,29,0,4,0'
        if name == b'@native_found_city_request':
            assert b'local pid,uid=1,29' in source
            assert self.player == 1 and self.founder is not None
            self.foundation_queued = True
            self.token.transport.pending.append(struct.pack('<IHHIIIII',
                0x8c0f3f36, 1, 1, 29, self.foundation_opcode, 0xffffffff, 0, 0))
            return b'submitted'
        if name == b'@native_found_city_effect':
            assert self.player == 1 and self.founder is None
            assert b"p=Players[1]" in source and obs['cities'][0]['id'] == 65544
            return b'65544,4,0,1'
        if name in (b'@explicit_queue_snapshot', b'@explicit_production_before',
                    b'@explicit_production_effect', b'@explicit_production_catalog',
                    b'@explicit_production_revalidation', b'@explicit_production_request'):
            return self.evaluate_production(source, name, obs)
        if name in (b'@explicit_production_queue', b'@explicit_production_queue_request'):
            return self.evaluate_queue(source, name)
        if name in (b'@explicit_city_focus_catalog1000', b'@explicit_city_focus_request1000',
                    b'@explicit_city_citizens_catalog', b'@explicit_city_citizens_request'):
            return self.evaluate_city_controls(source, name)
        if name in (b'@explicit_promotions_catalog', b'@explicit_promotion_request',
                    b'@xp2_explicit_unit_upgrades', b'@explicit_unit_upgrades',
                    b'@explicit_unit_upgrade_request', b'@xp2_upgrade_stockpile'):
            return self.evaluate_unit_development(name, obs)
        if name == b'@xp2_perspective_unit_permissions':
            return b'allow' if self.strategic_allowed else b'unavailable'
        if name == b'@explicit_unit_orders':
            if not obs['units']:
                return f'orders-v1|{self.player}|8'.encode()
            unit_id = obs['units'][0]['id']
            item, hashed = self.offers[self.player]
            route = 'command' if item.startswith('UNITCOMMAND_') else 'operation'
            founder = 'U|29|0|0|1\n' if self.player == 1 and self.founder is not None else ''
            return (f'orders-v1|{self.player}|8\n'
                    f'U|{unit_id}|{self.unit_activity[self.player]}|0|1\n'
                    f'{founder}'
                    f'A|{unit_id}|{route}|{item}|{hashed}|1\n').encode()
        if name == b'@explicit_unit_order_request':
            unit_id = obs['units'][0]['id']
            item, hashed = self.offers[self.player]
            route = 'command' if item.startswith('UNITCOMMAND_') else 'operation'
            assert f'{unit_id}|{route}|{item}|{hashed}'.encode() in source
            owner = self.player if self.command_archive_owner is None else self.command_archive_owner
            unit = unit_id if self.command_archive_unit is None else self.command_archive_unit
            if (self.command_archive_route or route) == 'operation':
                archive = struct.pack('<IHHIIIII', 0x8C0F3F36, owner, 1, unit, 36,
                                      self.operation_target, 0, 0)
            else:
                archive = struct.pack('<IHHIII', 0x493830AF, owner, 1, unit, 1, 0)
            self.token.transport.pending.append(archive)
            return b'submitted'
        if name == b'@explicit_own_queued_destination':
            destination = self.destinations[self.player]
            return b'none' if destination is None else str(destination).encode()
        if name == b'@world_input_own_units':
            return json.dumps([dict(unit_id=row['id'], ignore_moves=False)
                               for row in obs['units']]).encode()
        if name == b'@explicit_own_queued_orders':
            return json.dumps(dict(player_id=self.player, turn=obs['turn'], width=obs['width'],
                height=obs['height'], units=[dict(unit_id=row['id'], plot_id=self.destinations[self.player])
                                           for row in obs['units']])).encode()
        if name == b'@official_world_click':
            return self.evaluate_world_click(source, obs)
        if name == b'@native_player_observation':
            if self.fail_target_read and self.player == 1:
                raise RuntimeError('fixture could not read target public view')
            return json.dumps(obs).encode()
        if name == b'@native_revealed_plot_observation':
            plots = [{k: v for k, v in row.items() if k != 'visible'} for row in obs['plots']]
            plots.extend(self.extra_revealed.get(self.player, ()))
            return json.dumps(dict(schema='civ6rl-revealed-plot-observation-v1',
                player_id=self.player, observer_id=self.player, turn=8, width=74, height=46,
                plots=plots)).encode()
        return super().evaluate(child, source, name, **kw)

    def evaluate_research(self, source, name):
        header, identity, parameter_line, *_ = source.splitlines()
        kind = header.split(b'"')[1].decode('ascii')
        operation, key, choices = self.choice_layout[kind]
        if name == b'@explicit_research_catalog':
            assert identity == f'local pid,expectedTurn={self.player},8'.encode()
            offers = ','.join(f'{index}:{hashed}' for index, hashed in choices)
            return f'{kind},{self.player},8,{operation},{key},2888817673,2550048198,2,{offers}'.encode()
        if name == b'@native_research_revalidation':
            raw = identity.partition(b'=')[2]
            player, turn, index, hashed, opcode, param_key, insert, mode = map(int, raw.split(b','))
            assert (player, turn, opcode, param_key, insert, mode) == (
                self.player, 8, operation, key, 2888817673, 2550048198)
            assert (index, hashed) in choices
            return kind.encode() + b',' + raw
        assert identity == f'local pid={self.player}'.encode()
        expected = int(parameter_line.partition(b'=')[2])
        selected = self.current_research[self.player][kind]
        return f'{kind},{self.player},8,{-1 if selected is None else selected},{expected}'.encode()

    def evaluate_production(self, source, name, observation):
        if name in (b'@explicit_queue_snapshot', b'@explicit_production_before',
                    b'@explicit_production_effect'):
            city_lines = []
            for city in observation['cities']:
                current = '0,0,0,1,0,0,N,-1,-1,-1,-1'
                if self.production_queue:
                    item_index, item_hash = self.production_items[self.production_queue[0]]
                    current = f'{len(self.production_queue)},{item_hash},0,1,0,5,U,{item_index},25,0,0'
                city_lines.append(f"C,{city['id']},{self.player},{current}")
            city_lines.append(f'P1|{self.player}|8|{len(city_lines)}')
            return '\n'.join(city_lines).encode()
        assert b'local pid,cityID,expectedTurn=1,65544,8' in source
        if name == b'@explicit_production_request':
            self.production_queued = True
            self.token.transport.pending.append(struct.pack('<IHH15I',
                0x7ce9adc2, 1, 2, 65544, 0, 0, 1, 0xffffffff, 299201842,
                0, 0xffffffff, 0xffffffff, 0, 0xffffd8f1, 0xffffd8f1, 0x0b, 0, 0xffffffff))
            return b'submitted'
        return (b'production-v1|1|65544|8|catalog|4|739199558|2888817673|2912129934|'
                b'2688392346|2395106579|3040219410|2818811211|1605245423|1|unit:UNIT_BUILDER:1:299201842')

    def evaluate_queue(self, source, name):
        assert self.player == 1 and b'local pid,cityID,expectedTurn=1,65544,8' in source
        size = len(self.production_queue)
        if name == b'@explicit_production_queue':
            rows = [f'queue-v2|1|65544|8|1|{size}']
            for pos, item in enumerate(self.production_queue):
                index, hashed = self.production_items[item]
                rows.append(f'E|{pos}|unit|{index}|{hashed}|0|0|0')
            rows.append('A|unit|22|1558890441|UNIT_SLINGER|' + ('replace_tail' if size == 8 else 'append'))
            rows.extend(f'R|{pos}' for pos in range(size))
            rows.extend(f'S|{i}|{j}' for i in range(size) for j in range(size) if i != j)
            return '\n'.join(rows).encode()
        assert b'CityManager.RequestOperation(city,e.BUILD,chosen.args)' in source
        action = source.split(b'if c.wire=="', 1)[1].split(b'"', 1)[0].decode().split('|')
        self.queue_command = action
        none = 0xffffffff
        packet = [0x7ce9adc2, 0x20001, 65544, 0, 0, 1, none, none, none, none, none,
                  0, 0xffffd8f1, 0xffffd8f1, 0, none, none]
        if action[0] == 'A':
            packet[7] = int(action[3])
            packet[8] = 0
            packet[14:16] = [0xb, 7] if action[-1] == 'replace_tail' else [3, none]
        elif action[0] == 'R':
            packet[4], packet[14], packet[15] = 7, 7, int(action[1])
        elif action[0] == 'S':
            packet[4], packet[14] = 8, 9
            packet[15:17] = [int(action[2]), int(action[1])]
        else:
            raise AssertionError(action)
        self.token.transport.pending.append(struct.pack('<17I', *packet))
        return b'submitted'

    def evaluate_city_controls(self, source, name):
        import re
        from civ6_host.runtime.native import native_saved_city_focus1000 as focus

        assert self.player == 1 and b'local pid,cityID,turn=1,65544,8' in source
        if name == b'@explicit_city_focus_catalog1000':
            rows = ['city-focus1000-v1|1|8|65544']
            rows.extend(f'{yield_type}|{index}|{int(favored)}|{int(disfavored)}'
                        for index, (yield_type, (favored, disfavored))
                        in enumerate(zip(focus.YIELDS, self.focus_flags)))
            return '\n'.join(rows).encode()
        if name == b'@explicit_city_citizens_catalog':
            return f'city-citizens-v1|1|8|65544\n3|3|0|1|{int(self.citizen_locked)}|-|-'.encode()
        if name == b'@explicit_city_focus_request1000':
            index = int(re.search(rb'assert\(row.Index==(\d+)', source)[1])
            for flags, data in re.findall(rb'cc.PARAM_FLAGS\]=(\d+).*?cc.PARAM_DATA0\]=(\d+)', source):
                flags, data = int(flags), int(data)
                self.city_control_requests.append((index, flags, data))
                self.token.transport.pending.append(struct.pack('<IHH7IB', 0x346b0a13, 1, 2,
                    65544, 2, flags, 1, 0, flags, index, data))
        else:
            assert b'if row.id==3' in source
            self.city_control_requests.append(None)
            self.token.transport.pending.append(
                struct.pack('<IHH8I', 0x346b0a13, 1, 2, 65544, 3, 0, 1, 0, 5, 3, 0))
        return b'submitted'

    def evaluate_world_click(self, source, observation):
        from civ6_host.runtime.native.native_world_click import _SOURCE_HASH

        ident = source.splitlines()[0].split(b'=')[1].decode('ascii')
        pid, turn, uid, destination = map(int, ident.split(','))
        assert pid == self.player and turn == observation['turn']
        width, height = observation['width'], observation['height']
        if self.world_click_mode == 'unsupported':
            return f'unsupported,{ident},{width},{height},-,-,-,-,-,{_SOURCE_HASH}'.encode()
        assert self.world_click_mode in ('arrive', 'queue')
        x, y = destination % width, destination // width
        self.world_click_queued = (uid, destination)
        self.token.transport.pending.append(struct.pack('<IHH9I', 0x8c0f3f36, pid, 1,
            uid, 19, 0xffffffff, 0, 1, x, y, 16400, 0))
        params = f'modifiers:-1749939689=16400;y:1248610884={y};x:1400339205={x}'
        return f'request,{ident},{width},{height},MOVE_TO,1477390184,{params},-,-,{_SOURCE_HASH}'.encode()

    def evaluate_unit_development(self, name, observation):
        pid, turn = self.player, observation['turn']
        assert pid == 1
        if not observation['units']:
            if name == b'@explicit_promotions_catalog':
                return f'promotions-v1|{pid}|{turn}'.encode()
            if name in (b'@xp2_explicit_unit_upgrades', b'@explicit_unit_upgrades'):
                return f'upgrades-v1|{pid}|{turn}'.encode()
        unit = observation['units'][0]
        uid = unit['id']
        if name == b'@explicit_promotions_catalog':
            acquired = ','.join(str(index) for index in self.acquired_promotions)
            rows = [f'promotions-v1|{pid}|{turn}',
                    f"U|{uid}|15|{unit['moves']}|{unit['damage']}|{acquired}"]
            if not acquired:
                rows.append(f'P|{uid}|7|3461640876|PROMOTION_BATTLECRY')
            return '\n'.join(rows).encode()
        if name in (b'@xp2_explicit_unit_upgrades', b'@explicit_unit_upgrades'):
            rows = [f'upgrades-v1|{pid}|{turn}']
            if uid == 28:
                quote = f'{uid}|3544934848|36|75|1'
                if name == b'@xp2_explicit_unit_upgrades':
                    quote += f'|43|{self.resource_cost}'
                rows.append(quote)
            return '\n'.join(rows).encode()
        if name == b'@xp2_upgrade_stockpile':
            return f'{pid}|{turn}|43|{self.resource_stockpile}'.encode()
        if name == b'@explicit_promotion_request':
            self.development_queued = 'promote'
            archive = struct.pack('<IHH6I', 0x493830af, pid, 1, uid, 13, 0, 1, 0, 3461640876)
        else:
            assert name == b'@explicit_unit_upgrade_request'
            self.development_queued = 'upgrade'
            archive = struct.pack('<IHH7I', 0x493830af, pid, 1, uid, 15, 0, 1, 0xffffd8f1, 0xffffd8f1, 0)
        self.token.transport.pending.append(archive)
        return b'submitted'

    def virtual(self, core, pointer, slot, rva, result, *args):
        if rva == self.token.transport.transport_abi.drain_rva and self.development_queued is not None:
            def drain_unit_development(_):
                self.machine.append(('drain',))
                self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
                obs = self.observations[self.player]
                if self.development_queued == 'promote':
                    self.acquired_promotions.append(7)
                else:
                    unit = obs['units'][0]
                    unit.update(id=44, type=36)
                    obs['economy']['gold'] -= 75
                    self.resource_stockpile -= self.resource_cost
                    if self.token.trade_feedback is not None:
                        self.token.trade_feedback.events.append('upgrade')
                self.development_queued = None
            return drain_unit_development
        if rva == self.token.transport.transport_abi.drain_rva and self.world_click_queued is not None:
            def drain_world_click(_):
                self.machine.append(('drain',))
                self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
                uid, plot = self.world_click_queued
                obs = self.observations[self.player]
                unit = next(row for row in obs['units'] if row['id'] == uid)
                if self.world_click_mode == 'arrive':
                    unit.update(x=plot % obs['width'], y=plot // obs['width'], moves=0)
                    self.destinations[self.player] = None
                else:
                    self.destinations[self.player] = plot
                self.world_click_queued = None
            return drain_world_click
        if rva == self.token.transport.transport_abi.drain_rva and self.city_control_requests:
            def drain_city_control(_):
                self.machine.append(('drain',))
                self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
                command = self.city_control_requests.pop(0)
                if command is None:
                    self.citizen_locked = not self.citizen_locked
                else:
                    index, flags, data = command
                    current = list(self.focus_flags[index])
                    current[flags] = bool(data)
                    self.focus_flags[index] = tuple(current)
            return drain_city_control
        if rva == self.token.transport.transport_abi.drain_rva and self.queue_command is not None:
            def drain_queue(_):
                self.machine.append(('drain',))
                self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
                action = self.queue_command
                queue = self.production_queue
                if action[0] == 'S':
                    i, j = int(action[1]), int(action[2])
                    queue[i], queue[j] = queue[j], queue[i]
                elif action[0] == 'R':
                    queue.pop(int(action[1]))
                elif action[-1] == 'replace_tail':
                    queue[-1] = action[4]
                else:
                    queue.append(action[4])
                self.queue_command = None
            return drain_queue
        if rva == self.token.transport.transport_abi.drain_rva and self.production_queued:
            def drain_production(_):
                self.machine.append(('drain',))
                self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
                self.production_queue[:] = ['UNIT_BUILDER']
                self.production_queued = False
            return drain_production
        if rva == self.token.transport.transport_abi.drain_rva and self.foundation_queued:
            def drain_foundation(_):
                self.machine.append(('drain',))
                self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
                obs = self.observations[1]
                obs['units'].remove(self.founder)
                self.founder = None
                self.foundation_queued = False
                obs['plots'][1]['owner'] = 1
                obs['cities'].append(dict(id=65544, owner=1, x=4, y=0, population=1,
                    yields=dict(food=2, production=1, gold=0, science=1, culture=1, faith=0)))
            return drain_foundation
        if rva == self.token.transport.transport_abi.drain_rva and self.research_queued is not None:
            def drain_research(_):
                self.machine.append(('drain',))
                self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
                player, kind, index = self.research_queued
                if self.research_applies:
                    self.current_research[player][kind] = index
                self.research_queued = None
            return drain_research
        if (rva == self.token.transport.transport_abi.drain_rva
                and getattr(self.token.transport, '_expected_unit_order', None) is not None):
            def drain(_):
                self.machine.append(('drain',))
                self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
                if self.command_effect:
                    item = self.offers[self.player][0]
                    if item == 'UNITCOMMAND_CANCEL':
                        self.destinations[self.player] = None
                    else:
                        self.unit_activity[self.player] += 1
                    if item in self.next_offer:
                        self.offers[self.player] = self.next_offer[item]
            return drain
        if (rva == self.token.transport.transport_abi.drain_rva
                and self.turn_requests):
            def drain_turn(_):
                self.machine.append(('drain',))
                self.memory.put(self.sentinel, struct.pack('<QQ', self.sentinel, self.sentinel))
                kind, pid = struct.unpack('<II', self.read(0x78001000, 8))
                assert pid == self.player
                if kind == 0x1bdb4f5c:
                    return
                if kind == 0xe8a26b84:
                    self.turn_rows[pid] = (1, 1, 0)
                elif self.turn_rows[pid][0]:
                    self.turn_rows[pid] = (0, 1, 1)
                    if self.completion_sender is not None:
                        self.token.transport.pending.append(struct.pack('<II', 0x1bdb4f5c,
                                                                         self.completion_sender))
                        flags = self.token.transport.transport_abi.processor_flags_rva
                        self.memory.put(self.memory.base + flags, b'\x01\x01\0\0')
            return drain_turn
        return super().virtual(core, pointer, slot, rva, result, *args)

    def enable_foundation_fixture(self):
        obs = self.observations[1]
        self.founder = dict(obs['units'][0], id=29, type=0, x=4, y=0)
        obs['units'].append(self.founder)
        obs['plots'].append(dict(obs['plots'][0], index=4, x=4, y=0, owner=-1))

    def enable_research_fixture(self):
        from civ6_host.runtime import xp1_research_profile
        from civ6_host.runtime.native import native_player_operation_request as request
        self.stack.enter_context(patch.object(xp1_research_profile, 'bind_owner'))

        def submit(core, context, player, operation, parameters, *, read, core_sha256):
            assert core is self.backend.core and context == self.backend.context
            assert core_sha256 == self.saved._engine_sha256 and player == self.player == 1
            kind, (_, key, choices) = next((name, row) for name, row in self.choice_layout.items()
                                           if row[0] == operation)
            assert parameters[2888817673] == 2550048198
            index = next(i for i, hashed in choices if hashed == parameters[key])
            self.research_requests.append((player, kind, index))
            self.research_queued = (player, kind, index)
            payload = bytearray(struct.pack('<IIIIII', 0xc45de12f, player, operation, 0, 0x80000001, 2))
            for field, value in parameters.items():
                actual = value ^ 1 if field == key and self.research_wrong_parameter else value
                payload += struct.pack('<IH', field, 0) + bytes([2]) + bytes(11) + struct.pack('<I', actual)
            self.token.transport.pending.append(bytes(payload))
            return dict(can_start=True, request_invoked=True, player_id=player, operation=operation)

        self.stack.enter_context(patch.object(request, 'request_player_operation', side_effect=submit))

    def enable_production_fixture(self):
        from civ6_host.runtime import xp1_production_profile, xp1_production_queue_profile
        self.stack.enter_context(patch.object(xp1_production_profile, 'bind_owner'))
        self.stack.enter_context(patch.object(xp1_production_queue_profile, 'bind_owner'))
        self.stack.enter_context(patch.object(xp1_production_queue_profile, 'gate_admitted',
                                              return_value=True))

    def enable_city_control_fixture(self):
        from civ6_host.runtime import expansion_city_controls

        self.stack.enter_context(patch.object(expansion_city_controls, 'bind_owner'))
        expansion_city_controls.enable(self.saved, dict(
            city_focus_diagnostic=True, city_management_diagnostic=True))

    def enable_world_fixture(self):
        from civ6_host.runtime import xp1_world_input_profile

        self.saved._xp2_lan_world_input_enabled = True
        self.stack.enter_context(patch.object(xp1_world_input_profile, 'bind_owner'))

    def enable_unit_development_fixture(self):
        from civ6_host.runtime import xp2_promotions, xp2_unit_upgrades

        self.saved._xp2_lan_unit_development_enabled = True
        self.stack.enter_context(patch.object(xp2_promotions, '_bind'))
        self.stack.enter_context(patch.object(xp2_unit_upgrades, '_bind'))

    def enable_turn_fixture(self):
        from civ6_host.runtime import xp1_turn_ui_profile
        from civ6_host.runtime.native.native_forced_endturn import USER_FORCED_HASH
        from civ6_host.runtime.xp2_turn_source import ABI

        transport = self.token.transport
        transport._turn_abi = ABI  # Native byte and call guards have a separate transport suite.
        self.stack.enter_context(patch.object(xp1_turn_ui_profile, 'bind_owner'))
        self.stack.enter_context(patch.object(perspective.SavedTurnBoundary, 'reactivation_owner',
                                              return_value=None))

        def request(player, *, player_ids, user_forced):
            assert self.player == player and player_ids == (0, 1, 2)
            self.turn_requests.append(('force_end_turn' if user_forced else 'end_turn', player))
            transport.pending.append(struct.pack('<III', 3619694470, player,
                                                 USER_FORCED_HASH if user_forced else 3069842052))

        def unready(player, *, player_ids):
            assert self.player == player and player_ids == (0, 1, 2)
            self.turn_requests.append(('unready_turn', player))
            transport.pending.append(struct.pack('<II', 0xe8a26b84, player))
            return {'queued': True}

        self.stack.enter_context(patch.object(transport, 'request_end_turn', side_effect=request))
        self.stack.enter_context(patch.object(transport, 'request_unready_turn', side_effect=unready))


class XP2HumanPerspectiveTests(unittest.TestCase):
    def fixture(self):
        f = PerspectiveFixture()
        self.addCleanup(f.close)
        return f

    def test_checkpoint_restores_both_native_turn_rows_before_admitting_owner(self):
        from civ6_host.runtime import network_checkpoint, xp1_session_checkpoint

        f = self.fixture()
        saved, observation = f.saved, f.token.observation
        f.turn_rows[2] = (0, 0, 0)
        saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        with patch('civ6_host.runtime.network_timer.read', return_value=False):
            boundary = xp1_session_checkpoint.boundary(saved)
            self.assertEqual(boundary['session']['active_human_player_ids'], [0, 1])
            self.assertEqual(boundary['secondary_controls'], [dict(boundary['controls'], player_id=1)])
            manifest = dict(observation=deepcopy(observation), decisions={}, host_placement_tracking=[],
                            host_world_selection=None, network_boundary=boundary)
            with patch.object(network_checkpoint, 'manifest', return_value=manifest):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, observation)))
            # The same native city/unit observation with a different saved
            # secondary roster must still fail before changing host state.
            manifest['network_boundary'] = deepcopy(boundary)
            manifest['network_boundary']['secondary_controls'][0]['player_id'] = 2
            f.token.world_input_selections = {0: 7}
            with (patch.object(network_checkpoint, 'manifest', return_value=manifest),
                  self.assertRaisesRegex(ValueError, 'readiness/session boundary differs')):
                network_checkpoint.prepare_owner(saved, observation)
            self.assertEqual(f.token.world_input_selections, {0: 7})
            f.turn_rows[1] = (0, 1, 1)
            with self.assertRaisesRegex(ValueError, 'quiescent active untimed human boundary'):
                xp1_session_checkpoint.boundary(saved)
        self.assertEqual(f.machine, [])
        self.assertEqual((f.player, f.token.sequence), (0, 0))

    def test_checkpoint_rejects_changed_secondary_view_or_decisions_at_the_same_native_turn(self):
        from civ6_host.contracts.network_turn import digest
        from civ6_host.runtime import network_checkpoint, player_views, xp1_session_checkpoint, xp2_lan_unit_commands
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        from civ6_host.runtime.native.native_session_resume import semantic_decisions

        f = self.fixture()
        f.enable_turn_fixture()
        f.enable_research_fixture()
        f.enable_production_fixture()
        saved, observation = f.saved, f.token.observation
        f.turn_rows[2] = (0, 0, 0)
        saved.inputs.checkpoint = ('work/fixture/checkpoint.json', 'a' * 64)
        secondary = f.observations[1]
        fog = {key: val for key, val in secondary['plots'][0].items() if key != 'visible'}
        fog.update(index=5, x=5, y=0, owner=-1)
        f.extra_revealed[1] = [fog]
        with patch('civ6_host.runtime.network_timer.read', return_value=False):
            boundary = xp1_session_checkpoint.boundary(saved)
            closure = dict(public_view_players=[0, 1], secondary_unit_commands=True)
            scope = player_views.checkpoint_view_players(closure, boundary)
            self.assertEqual(scope, (0, 1))
            decision_scope = player_views.checkpoint_decision_players(closure, boundary, scope)
            views = player_views.checkpoint_view_digests(saved, boundary, scope, decision_players=decision_scope)
            self.assertEqual(views['schema'], player_views.CHECKPOINT_DECISIONS_SCHEMA)
            protocol = SimpleNamespace(core_sha256=XP2_CORE_SHA256, identity=f.token.identity,
                                       session=boundary['session'])
            request = dict(player_id=1, operation='observe', sequence=4)
            _, _, _, choices, _ = xp2_lan_unit_commands.read_reply(saved, protocol, request, scope)
            self.assertEqual(views['players'][1]['decisions_sha256'], digest(semantic_decisions(choices)))
            self.assertNotIn('decisions_sha256', views['players'][0])
            self.assertTrue(any(row['action']['kind'] == 'end_turn' for row in choices['candidates']))
            manifest = dict(observation=deepcopy(observation), decisions={}, host_placement_tracking=[],
                            host_world_selection=None, network_boundary=boundary, checkpoint_public_views=views)
            f.token.sequence += 1
            with patch.object(network_checkpoint, 'manifest', return_value=manifest):
                self.assertTrue(callable(network_checkpoint.prepare_owner(saved, observation)))
                self.assertIn(('official_lan_checkpoint_public_views_matched', dict(turn=8, player_ids=[0, 1])),
                              f.emitted)
                self.assertIn(('official_lan_checkpoint_public_decisions_matched', dict(turn=8, player_ids=[1])),
                              f.emitted)
                f.token.world_input_selections = {0: 7}
                f.extra_revealed[1] = []
                with self.assertRaisesRegex(ValueError, 'revealed map differs for player 1'):
                    network_checkpoint.prepare_owner(saved, observation)
                self.assertEqual(f.token.world_input_selections, {0: 7})
                f.extra_revealed[1] = [fog]
                secondary['economy']['gold'] += 1
                with self.assertRaisesRegex(ValueError, 'public observation differs for player 1'):
                    network_checkpoint.prepare_owner(saved, observation)
                secondary['economy']['gold'] -= 1
                f.turn_blocked = True
                with self.assertRaisesRegex(ValueError, 'public decision catalogue differs for player 1'):
                    network_checkpoint.prepare_owner(saved, observation)
        self.assertEqual(f.token.world_input_selections, {0: 7})
        self.assertEqual((f.player, f.token.sequence), (0, 1))
        self.assertNotIn('receive', [row[0] for row in f.machine])

    def test_borrowed_turn_completion_echo_uses_native_sender(self):
        f = self.fixture()
        f.enable_turn_fixture()
        f.turn_rows[0] = (0, 1, 1)
        f.completion_sender = 1
        with patch('civ6_host.runtime.network_timer.read', return_value=False):
            boundary = perspective.read_network_boundary(f.saved, 1, {'kind': 'force_end_turn'})
        state = boundary.state
        self.assertEqual(boundary.receipt['status'], 'completed')
        self.assertEqual((f.player, state['player'], state['flags']), (0, 0, (1, 1, 0, 0)))
        self.assertFalse(next(row for row in state['rows'] if row['player_id'] == 1)['active'])
        self.assertEqual(f.turn_requests, [('force_end_turn', 1)])
        self.assertIn(1, [row['player_id'] for stage, row in f.emitted
                          if stage == 'native_game_turn_complete_echo_verified'])
        self.assertEqual(f.token.transport.pending, [])

    def test_borrowed_turn_refuses_unavailable_or_foreign_echo(self):
        f = self.fixture()
        f.enable_turn_fixture()
        f.enable_research_fixture()
        f.enable_production_fixture()
        with patch('civ6_host.runtime.network_timer.read', return_value=False):
            f.turn_blocked = True
            boundary = perspective.read_network_boundary(f.saved, 1, {'kind': 'end_turn'})
            self.assertEqual(boundary.receipt['status'], 'refused')
            self.assertEqual(boundary.gates['turn_availability'],
                             dict(end_turn=False, force_end_turn=True, unready_turn=False))
            self.assertEqual(f.turn_requests, [])
            self.assertEqual(f.player, 0)
            f.turn_rows[0] = (0, 1, 1)
            f.completion_sender = 0
            with self.assertRaisesRegex(RuntimeError, 'expected local player'):
                perspective.read_network_boundary(f.saved, 1, {'kind': 'force_end_turn'})
        self.assertTrue(f.saved.poisoned)
        self.assertEqual(f.token.transport.pending, [struct.pack('<II', 0x1bdb4f5c, 0)])

    def test_borrowed_research_refuses_a_mismatched_parameter_before_delivery(self):
        f = self.fixture()
        f.enable_research_fixture()
        f.research_wrong_parameter = True
        with self.assertRaisesRegex(RuntimeError, 'native parameters'):
            perspective.read_network_boundary(f.saved, 1,
                dict(kind='research', index=3, hash=2080815322))
        self.assertTrue(f.saved.poisoned)
        self.assertNotIn('receive', [row[0] for row in f.machine])
        self.assertEqual(f.current_research[1], dict(research=None, civic=None))

    def test_borrowed_foundation_refuses_another_unit_operation_before_delivery(self):
        f = self.fixture()
        f.enable_foundation_fixture()
        f.foundation_opcode = 36
        with self.assertRaisesRegex(ValueError, 'opcode differs'):
            perspective.read_network_boundary(f.saved, 1, dict(kind='found_city', unit_id=29, x=4, y=0))
        self.assertTrue(f.saved.poisoned)
        self.assertNotIn('receive', [row[0] for row in f.machine])
        self.assertIsNotNone(f.founder)
        self.assertEqual(f.observations[1]['cities'], [])

    def test_second_human_view_drains_and_restores_without_a_command(self):
        f = self.fixture()
        bindings = tuple(f.host.vtable)
        before = deepcopy(f.token.observation)
        view = f.saved.read_xp2_human_view(1)
        self.assertEqual(view['observation']['units'][0]['id'], 28)
        self.assertEqual([p['index'] for p in view['player_map']['plots']], [3])
        validate(view['player_map'], 1, 8, visible=view['observation'])
        self.assertEqual(view['player_turn'], dict(active=True, turn_active_complete=True))
        self.assertEqual((f.switches, f.player, f.token.sequence), ([1, 0], 0, 0))
        self.assertEqual((f.deferred.pending, f.deferred.consumed_count), ([], 2))
        self.assertEqual(f.token.publication_count, 2)
        self.assertEqual(tuple(f.host.vtable), bindings)
        self.assertEqual((f.backend.stage, f.token.observation), (READY, before))
        self.assertEqual([row[0] for row in f.machine], ['ensure', 'publish', 'ensure', 'publish'])

    def held_dialogue_fixture(self, *, closes_on_return=False, statement_type='DECLARE_SURPRISE_WAR'):
        from civ6_host.runtime import xp2_diplomacy, xp2_statement_source
        from civ6_host.runtime.native.native_combat_map_owner import CombatMapRegistry
        from civ6_host.runtime.native.native_diplomacy_statement import StatementReceiver

        f = self.fixture()
        backend, owner, deferred = f.backend, f.owner, f.deferred
        owner.statement_event_profile = owner._statement_event_profile = xp2_statement_source.PROFILE
        owner._statement_producing = owner._statement_poisoned = False
        deferred.diplomacy_statement_receiver = deferred
        deferred.statement_consumer = StatementReceiver()
        deferred.combat_map_registry = CombatMapRegistry(limit=64, core_sha256=backend.load_abi.core_sha256)
        statement = dict(event_sequence=73,
            fields=dict(SessionID=9, FromPlayer=2, ToPlayer=0, ResponseType=0,
                        StatementType=crc32(statement_type.encode('ascii')) ^ 0xffffffff,
                        StatementSubType=crc32(b'NONE') ^ 0xffffffff))
        deferred.pending_diplomacy_statements.append(statement)
        f.open_checks = []
        evaluate = f.saved.prefix.runtime.evaluate_text

        def query(child, source, name, **options):
            if name != b'@xp2_saved_pending_dialogue':
                return evaluate(child, source, name, **options)
            self.assertEqual(f.player, 0)
            self.assertIn(b'DiplomacyManager.IsSessionIDOpen(sid)', source)
            f.open_checks.append(len(f.switches))
            active = not (closes_on_return and bool(f.switches))
            return f'0|9|2|0|{int(active)}|{statement_type}|NONE|'.encode('ascii')

        f.stack.enter_context(patch.object(f.saved.prefix.runtime, 'evaluate_text', side_effect=query))
        self.assertTrue(xp2_diplomacy.retain(f.saved))
        return f

    def test_public_view_publication_preserves_held_surprise_war(self):
        from civ6_host.runtime import player_views

        f = self.held_dialogue_fixture()
        f.turn_rows[2] = (0, 0, 0)
        retained = deepcopy(f.deferred.pending_diplomacy_statements)
        protocol = SimpleNamespace(ended=False, closed=False, identity=f.token.identity,
                                   sequence=f.token.sequence, nonce='f' * 32)
        with TemporaryDirectory() as tmp:
            path = Path(tmp)/'closure.json'
            path.write_text('{}', encoding='utf-8')
            player_views.publish_player_views(f.emit, f.saved, protocol, f.observations[0],
                {'public_view_players': [0, 1]}, path, lan_players=(0, 1))
            for pid, unit in ((0, f.observations[0]['units'][0]['id']), (1, 28)):
                raw = json.loads(player_views._path(path.parent, pid).read_bytes())
                self.assertEqual(raw['observation']['player_id'], pid)
                self.assertEqual(raw['observation']['units'][0]['id'], unit)
                self.assertNotIn('statement', raw)
                self.assertNotIn('dialogue', raw)
        self.assertEqual(f.deferred.pending_diplomacy_statements, retained)
        self.assertEqual(f.switches, [1, 0])
        self.assertEqual(f.open_checks, [0, 0, 2, 2, 2])
        self.assertEqual((f.player, f.token.sequence, f.backend.stage), (0, 0, READY))
        self.assertFalse(any(row[0] == 'receive' for row in f.machine))
        with self.assertRaisesRegex(RuntimeError, 'unanswered diplomacy statement'):
            f.saved.read_xp2_human_unit_commands(1)

    def test_public_wars_follow_each_viewer_at_a_new_same_turn_boundary(self):
        from civ6_host.runtime import player_views
        from civ6_host.player_view import WAR_STATUS_SCHEMA
        from test_xp2_diplomatic_relationships import LuaRuntime

        if LuaRuntime is None:
            self.skipTest('Lua fixture unavailable')
        f = self.fixture()
        f.saved.diplomacy_overview_diagnostic = True
        lua = LuaRuntime()
        lua.execute('''
Game={GetLocalPlayer=function() return viewer end, GetLocalObserver=function() return viewer end,
      GetCurrentGameTurn=function() return 8 end}
local function major(id)
 return {GetID=function() return id end, IsMajor=function() return true end,
   GetDiplomacy=function()
    assert(id==viewer)
    return {HasMet=function(_, target) return target<2 end,
      IsAtWarWith=function(_, target) assert(target==1-viewer); return atWar end}
   end}
end
Players={[0]=major(0), [1]=major(1), [2]=major(2)}
PlayerManager={GetAliveMajors=function() return {Players[2],Players[1],Players[0]} end}
''')
        evaluate = f.saved.prefix.runtime.evaluate_text

        def query(child, source, name, **options):
            if name != b'@xp2_public_diplomatic_wars':
                return evaluate(child, source, name, **options)
            lua.globals().viewer = f.player
            return lua.execute(source.decode('ascii')).encode('ascii')

        protocol = SimpleNamespace(ended=False, closed=False, identity=f.token.identity, nonce='a' * 32)
        closure = {'public_view_players': [0, 1], 'diplomacy_overview_diagnostic': True}
        with TemporaryDirectory() as tmp, patch.object(f.saved.prefix.runtime, 'evaluate_text', side_effect=query):
            path = Path(tmp) / 'closure.json'
            path.write_text('{}', encoding='utf-8')
            for sequence, at_war in enumerate((False, True)):
                protocol.sequence = f.token.sequence = sequence
                lua.globals().atWar = at_war
                player_views.publish_player_views(f.emit, f.saved, protocol, f.observations[0],
                                                   closure, path, lan_players=(0, 1))
                for pid in (0, 1):
                    raw = json.loads(player_views._path(path.parent, pid).read_bytes())
                    self.assertEqual((raw['schema'], raw['sequence'], raw['turn']), (WAR_STATUS_SCHEMA, sequence, 8))
                    self.assertEqual(raw['diplomatic_wars'], [dict(player_id=1 - pid, at_war=at_war)])
                self.assertEqual(f.player, 0)
                self.assertEqual(f.token.observation, f.observations[0])
        self.assertEqual(f.switches, [1, 0, 1, 0])
        self.assertFalse(any(row[0] == 'receive' for row in f.machine))

    def test_perspective_return_refuses_a_closed_dialogue(self):
        f = self.held_dialogue_fixture(closes_on_return=True)
        with self.assertRaisesRegex(RuntimeError, 'session is no longer open'):
            f.saved.read_xp2_human_view(1)
        self.assertEqual(f.switches, [1, 0])
        self.assertTrue(f.saved.poisoned)

    def test_view_never_borrows_with_an_unqualified_pending_dialogue(self):
        f = self.held_dialogue_fixture(statement_type='MAKE_DEAL')
        with self.assertRaisesRegex(ValueError, 'qualified pending-dialogue type'):
            f.saved.read_xp2_human_view(1)
        self.assertEqual(f.switches, [])

    def test_rejects_nonhuman_alias_and_fallback_visibility_before_setter(self):
        f = self.fixture()
        for seat in (False, 2, 64):
            with self.assertRaisesRegex(ValueError, 'captured human seat'):
                f.saved.read_xp2_human_view(seat)
        f.memory.put(f.indices + 4, struct.pack('<i', -1))
        with self.assertRaisesRegex(ValueError, 'no admitted native visibility'):
            f.saved.read_xp2_human_view(1)
        f.memory.put(f.indices + 4, struct.pack('<i', 0))
        with self.assertRaisesRegex(ValueError, 'slots alias'):
            f.saved.read_xp2_human_view(1)
        self.assertEqual((f.switches, f.backend.stage), ([], READY))

    def test_setter_success_without_boundary_change_is_refused(self):
        f = self.fixture()
        f.ignore_setter = True
        with self.assertRaisesRegex(RuntimeError, 'target or native turn state'):
            f.saved.read_xp2_human_view(1)
        self.assertEqual(f.switches, [1])
        self.assertTrue(f.saved.poisoned)

    def test_changed_turn_flags_poison_without_a_guessed_restore(self):
        f = self.fixture()
        f.changes_readiness = True
        with self.assertRaisesRegex(RuntimeError, 'target or native turn state'):
            f.saved.read_xp2_human_view(1)
        self.assertEqual(f.switches, [1])
        self.assertTrue(f.saved.poisoned)

    def test_target_read_failure_restores_only_with_verified_state(self):
        f = self.fixture()
        f.fail_target_read = True
        with self.assertRaisesRegex(RuntimeError, 'could not read target'):
            f.saved.read_xp2_human_view(1)
        self.assertEqual((f.switches, f.player), ([1, 0], 0))
        self.assertTrue(f.saved.poisoned)

    def test_restore_requires_the_exact_original_view(self):
        f = self.fixture()
        f.restore_corrupts_view = True
        with self.assertRaisesRegex(RuntimeError, 'failed to restore'):
            f.saved.read_xp2_human_view(1)
        self.assertEqual((f.switches, f.player), ([1, 0], 0))
        self.assertTrue(f.saved.poisoned)

    def test_both_seats_submit_their_own_unit_command_in_the_same_turn(self):
        f = self.fixture()
        before = f.saved.read_xp2_human_unit_commands(1)
        self.assertEqual(len(before['actions']), 1)
        self.assertEqual(before['actions'][0]['item_type'], 'UNITCOMMAND_WAKE')
        result = f.saved.execute_xp2_human_unit_command(1, before['decision'], before['actions'][0])
        self.assertEqual((result['status'], result['new_sequence']), ('completed', 1))
        self.assertEqual(result['unit_after']['unit_id'], 28)
        self.assertEqual(f.unit_activity, {0: 0, 1: 100})
        self.assertEqual(f.token.observation['player_id'], 0)
        self.assertEqual(result['observation']['turn'], f.token.observation['turn'])
        with self.assertRaisesRegex(ValueError, 'decision revision'):
            f.saved.execute_xp2_human_unit_command(1, before['decision'], before['actions'][0])
        primary = f.saved.read_xp2_human_unit_commands(0)
        self.assertEqual(primary['decision']['turn'], before['decision']['turn'])
        self.assertEqual(primary['actions'][0]['item_type'], 'UNITCOMMAND_CANCEL')
        next_result = f.saved.execute_xp2_human_unit_command(0, primary['decision'], primary['actions'][0])
        self.assertEqual((next_result['status'], next_result['new_sequence']), ('completed', 2))
        self.assertEqual(next_result['unit_after']['unit_id'], 17)
        self.assertEqual(next_result['unit_before'], next_result['unit_after'])
        self.assertEqual(next_result['queued_destination_before'], 8)
        self.assertIsNone(next_result['queued_destination_after'])
        self.assertEqual(f.unit_activity, {0: 0, 1: 100})
        self.assertEqual([row[0] for row in f.machine].count('drain'), 2)

    def test_rejects_wrong_native_archive_seat_or_unit_before_receive(self):
        for attr, value in (('command_archive_owner', 0), ('command_archive_unit', 17)):
            with self.subTest(attr=attr):
                f = self.fixture()
                try:
                    info = f.saved.read_xp2_human_unit_commands(1)
                    setattr(f, attr, value)
                    with self.assertRaisesRegex(ValueError, 'archive differs'):
                        f.saved.execute_xp2_human_unit_command(1, info['decision'], info['actions'][0])
                    self.assertTrue(f.saved.poisoned)
                    self.assertFalse(any(row[0] == 'receive' for row in f.machine))
                    self.assertEqual(f.token.sequence, 0)
                finally:
                    f.close()

    def test_fresh_unavailable_choice_is_refused_and_session_remains_usable(self):
        f = self.fixture()
        info = f.saved.read_xp2_human_unit_commands(1)
        f.offers[1] = ('UNITCOMMAND_CANCEL', 533311341)
        with self.assertRaisesRegex(ValueError, 'was not offered'):
            f.saved.execute_xp2_human_unit_command(1, info['decision'], info['actions'][0])
        self.assertEqual((f.backend.stage, f.token.sequence), (READY, 0))
        self.assertFalse(any(row[0] == 'receive' for row in f.machine))

    def test_delivered_archive_without_readback_effect_is_unresolved(self):
        f = self.fixture()
        info = f.saved.read_xp2_human_unit_commands(1)
        f.command_effect = False
        result = f.saved.execute_xp2_human_unit_command(1, info['decision'], info['actions'][0])
        self.assertEqual((result['status'], result['new_sequence']), ('submitted_effect_unresolved', 1))

    def test_parameterless_operation_refuses_a_command_archive_or_a_target(self):
        skip = dict(kind='unit_order', route='operation', item_type='UNITOPERATION_SKIP_TURN',
                    unit_id=28, hash=745019656)
        cases = [('command_archive_route', 'command', 'archive differs'),
                 ('operation_target', 3, 'target or parameter')]
        for attr, value, error in cases:
            with self.subTest(attr=attr):
                f = self.fixture()
                try:
                    f.offers[1] = (skip['item_type'], skip['hash'])
                    setattr(f, attr, value)
                    with self.assertRaisesRegex(ValueError, error):
                        perspective.read_network_boundary(f.saved, 1, skip)
                    self.assertTrue(f.saved.poisoned)
                    self.assertFalse(any(row[0] == 'receive' for row in f.machine))
                    self.assertEqual(f.token.sequence, 0)
                finally:
                    f.close()
