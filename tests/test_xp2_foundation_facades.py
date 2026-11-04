import hashlib
import ast
from pathlib import Path
import ctypes as C
import struct
import types
from types import SimpleNamespace
import unittest

from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from civ6_host.runtime.saved_load_profiles import XP2_CORE_SHA256
from civ6_host.runtime import foundation_facade_profiles as facades


class XP2FoundationFacadeTests(unittest.TestCase):
    def test_exact_tables_and_native_operation_abis(self):
        abi = facades.query_abi(XP2_CORE_SHA256, None)
        self.assertEqual(abi.tables['outer'][0], 0xA101E8)
        self.assertEqual({slot: abi.tables['outer'][1][slot] for slot in (0x90, 0xA8, 0xB8, 0x100)},
                         {0x90: 0x5901A0, 0xA8: 0x590300, 0xB8: 0x590360, 0x100: 0x590140})
        self.assertEqual(abi.tables['map'][0], 0xA11698)
        self.assertEqual({slot: abi.tables['map'][1][slot] for slot in (8, 0x40, 0x68, 0x88)},
                         {8: 0x59A8D0, 0x40: 0x59B1F0, 0x68: 0x59B440, 0x88: 0x59ACC0})
        self.assertEqual(abi.tables['player'][0], 0xA11A80)
        self.assertEqual({slot: abi.tables['player'][1][slot] for slot in (8, 0x18, 0x110, 0x130)},
                         {8: 0x59C8C0, 0x18: 0x59CE50, 0x110: 0x59D310, 0x130: 0x59CDD0})
        self.assertEqual(abi.tables['plot'][0], 0xA12490)
        self.assertEqual({slot: abi.tables['plot'][1][slot] for slot in
                          (8, 0x20, 0x30, 0x60, 0x148, 0x178, 0x180)},
                         {8: 0x5A0FD0, 0x20: 0x5A13C0, 0x30: 0x5A1070, 0x60: 0x5A12A0,
                          0x148: 0x5A1620, 0x178: 0x5A0FF0, 0x180: 0x5A1050})
        self.assertEqual(abi.tables['type_service'][0], 0xA106F0)
        self.assertEqual(dict(abi.tables['type_service'][1]),
                         {8: 0x5919A0, 0xC8: 0x5934E0, 0xE0: 0x593480})
        self.assertEqual((abi.service_bytes, abi.service_secondary_vtable), (16, 0xA10CA8))
        self.assertEqual(abi.rva('service_player_type_hash'), 0x5934E0)
        self.assertEqual(abi.rva('player_type'), 0x59CE50)
        self.assertEqual(abi.rva('plot_owner'), 0x5A13C0)
        self.assertEqual(abi.rva('plot_value'), 0x5A1070)
        self.assertEqual(abi.rva('outer_map'), 0x590300)
        self.assertEqual((abi.slot('plot_owner'), abi.slot('plot_value')), (0x20, 0x30))
        self.assertEqual((len(abi.operations), len(abi.tables)), (35, 14))
        self.assertEqual(abi.source_sha256, facades.XP2_QUERY_SOURCE[1])

    def test_selector_preserves_xp1_and_refuses_unqualified_operations(self):
        retained = {'player': (0x111, {8: 4421040, 0x18: 4422464})}
        selected = facades.select_tables(XP2_CORE_SHA256, retained)
        self.assertEqual(selected, {'player': (0xA11A80, {8: 0x59C8C0, 0x18: 0x59CE50})})
        self.assertIs(facades.select_tables('d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3', retained), retained)
        from civ6_host.runtime.paths import resource_root
        self.assertEqual(facades.query_abi(XP1_CORE_SHA256, resource_root()).core_sha256, XP1_CORE_SHA256)
        self.assertRaises(ValueError, facades.query_abi, '0' * 64, None)
        self.assertRaises(ValueError, facades.select_specs, XP2_CORE_SHA256,
            {'unqualified': (0, object, ())})
        retained = {'plot': (0x777, ((8, 4435728), (32, 4436736), (48, 4435888)))}
        selected = facades.select_tables(XP2_CORE_SHA256, retained)
        self.assertEqual(selected['plot'], (0xA12490, ((8, 0x5A0FD0), (0x20, 0x5A13C0),
                                                        (0x30, 0x5A1070))))
        from civ6_host.runtime.paths import resource_root
        self.assertEqual(facades.select_tables(XP1_CORE_SHA256, retained, resource_root())['plot'][1],
                         ((8, facades.query_abi(XP1_CORE_SHA256, resource_root()).rva('release_plot')),
                          (32, facades.query_abi(XP1_CORE_SHA256, resource_root()).rva('plot_owner')),
                          (48, facades.query_abi(XP1_CORE_SHA256, resource_root()).rva('plot_value'))))

    def test_dependencies_pin_source_and_exact_references(self):
        pins = facades.source_dependencies(core_sha256=XP2_CORE_SHA256)
        from civ6_host.runtime.paths import resource_root
        from civ6_host.runtime.resource_resolution import resolve_path
        source_path = str(resolve_path(resource_root()/facades.XP2_QUERY_SOURCE[0]).resolve())
        self.assertEqual(pins[source_path], facades.XP2_QUERY_SOURCE[1])
        self.assertTrue(any(path.endswith('capture_query_facades_v3.py') for path in pins))
        self.assertTrue(any(path.replace('\\', '/').endswith('native-event-f4fe1b62/d579004ffcb9cebad2235aebd41f430a24bbbff2fca66386c90e9a08d032cc11.json')
                            for path in pins))
        self.assertTrue(any(path.replace('\\', '/').endswith('native-event-359703a2/c0154cc9f7b6a0844ce352dbde95040bbaa2afbbffdf37c990644c7e0e7665a5.json')
                            for path in pins))
        for path, digest in pins.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest)

    def test_plot_owner_and_value_follow_retained_exe_slots_and_xp1_bodies(self):
        from civ6_host.runtime import xp2_foundation_query_source as source
        from civ6_host.runtime.paths import resource_root
        from civ6_host.runtime.configuration_profiles import _source
        profile = source.source()
        abi = facades.query_abi(XP2_CORE_SHA256, resource_root())
        evidence = profile['semantic_evidence']
        self.assertEqual((abi.slot('plot_owner'), abi.rva('plot_owner')), (0x20, 0x5A13C0))
        self.assertEqual((abi.slot('plot_value'), abi.rva('plot_value')), (0x30, 0x5A1070))
        owner = evidence['plot_owner']
        value = evidence['plot_value']
        self.assertEqual((owner['caller']['bytes'], owner['consumer']['bytes']), ('ff5020', '8944242c'))
        self.assertEqual([row['bytes'] for row in value['callers']], ['ff5030', 'ff5030'])
        self.assertEqual(value['consumer']['bytes'], '8945cc')
        xp1_ref = next(row for row in profile['inputs'] if row.get('role') == 'cross-engine semantic body comparison')
        xp1 = _source((xp1_ref['path'], xp1_ref['sha256']))
        def bytes_from_rows(body):
            if 'fragments' in body:
                return b''.join(bytes.fromhex(row['bytes']) for fragment in body['fragments']
                                for row in fragment['instructions'])
            return b''.join(bytes.fromhex(row['bytes']) for row in body['instructions'])
        self.assertEqual(bytes_from_rows(profile['functions']['0x5a13c0']),
                         bytes_from_rows(xp1['functions'][hex(xp1['operations']['plot_owner']['rva'])]['body']))
        self.assertEqual(bytes_from_rows(profile['functions']['0x5a1070']),
                         bytes_from_rows(xp1['functions'][hex(xp1['operations']['plot_value']['rva'])]['body']))
        rejected = value['old_v2_slot_0x60_rejected_as_value']
        self.assertEqual((rejected['target_rva'], rejected['body_sha256']),
                         ('0x5a12a0', profile['functions']['0x5a12a0']['sha256']))
        self.assertIn('allocates an 0x18-byte wrapper', rejected['reason'])

    def test_installed_foundation_callers_are_covered_by_all_35_xp2_operations(self):
        from civ6_host.runtime.paths import resource_root
        native_dir = Path(__file__).resolve().parents[1] / 'src/civ6_host/runtime/native'
        abi = facades.query_abi(XP2_CORE_SHA256, resource_root())
        operation_requests, table_requests, slot_requests = set(), set(), set()
        aliases = {'collection': 'district_collection', 'item': 'district'}
        caller_count = 0
        for path in native_dir.glob('native_*.py'):
            text = path.read_text(encoding='utf-8')
            tree = ast.parse(text)
            query_names = set()
            for node in ast.walk(tree):
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                value = node.value
                if value is None:
                    continue
                if not any(isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
                           and call.func.id == 'query_abi' for call in ast.walk(value)):
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                query_names.update(target.id for target in targets if isinstance(target, ast.Name))
            if not query_names:
                continue
            caller_count += 1
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                    continue
                owner = node.func.value
                if not isinstance(owner, ast.Name) or owner.id not in query_names:
                    continue
                if node.func.attr in ('rva', 'slot', 'table') and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        {'rva': operation_requests, 'slot': slot_requests,
                         'table': table_requests}[node.func.attr].add(arg.value)
            for node in tree.body:
                if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if not any(isinstance(target, ast.Name) and target.id == '_TABLES' for target in targets):
                    continue
                try:
                    table_defs = ast.literal_eval(node.value)
                except (ValueError, TypeError):
                    continue
                if not isinstance(table_defs, dict):
                    continue
                for label, row in table_defs.items():
                    table_name = aliases.get(label, label)
                    if table_name not in abi.tables:
                        continue
                    table_requests.add(table_name)
                    for slot, target in row[1]:
                        slot = int(slot)
                        slot_requests.add((table_name, slot))
                        candidates = [(op_name, spec) for op_name, spec in facades._BASE_OPERATIONS.items()
                                      if spec.get('table') == table_name and spec.get('slot') == slot
                                      and spec.get('rva') == target]
                        if len(candidates) == 1:
                            op_name = candidates[0][0]
                            selected_op = abi.operations[op_name]
                            self.assertEqual(abi.tables[table_name][1][selected_op['slot']], selected_op['rva'])
                        else:
                            self.fail(f'{path.name} has an unqualified retained table slot {table_name}+{slot:#x}')
        self.assertGreater(caller_count, 0)
        self.assertTrue(operation_requests)
        for name in operation_requests:
            self.assertIn(name, abi.operations, name)
        for name in table_requests:
            self.assertIn(name, abi.tables, name)
        for name in slot_requests:
            if isinstance(name, tuple):
                table, slot = name
                self.assertIn(slot, abi.tables[table][1], f'{table}+{slot:#x}')
            else:
                self.assertIn(name, abi.operations, name)
                op = abi.operations[name]
                if 'table' in op:
                    self.assertEqual(abi.tables[op['table']][1][op['slot']], op['rva'])
        lab = Path(__file__).resolve().parents[2] / 'civ6-rl-lab'
        from extraction_foundation_facades import transform
        for module_name, operation in (('native_event_359703a2', 'plot_value'),
                                       ('native_event_f4fe1b62', 'plot_owner')):
            original = (lab / 'civ6rl' / f'{module_name}.py').read_text(encoding='utf-8')
            transformed = transform(f'civ6rl.{module_name}', original)
            self.assertIn(f"PLOT_VALUE_SLOT = _foundation_abi.slot('{operation}')", transformed)
        from extraction_foundation_queries import transform as transform_queries
        for module_name in ('native_event_c3183902', 'native_event_28d6ebbe'):
            original = (lab / 'civ6rl' / f'{module_name}.py').read_text(encoding='utf-8')
            transformed = transform_queries(f'civ6rl.{module_name}', original)
            self.assertIn('_TABLES = select_tables(core_sha256, _TABLES, resource_root())', transformed)
            self.assertNotIn('_foundation_abi.tables[_aliases.get(label,label)][1][slot]', transformed)
        hardcoded_slot_owners = {
            'native_plot_ui_query.py': {
                'OUTER_POSITION_GETTER_SLOT': 'outer_game',
                'GAME_FACADE_RELEASE_SLOT': 'release_game',
                'GAME_FACADE_POSITION_QUERY_SLOT': 'position_service',
                'POSITION_FACADE_RELEASE_SLOT': 'release_position',
                'POSITION_VALUE_SLOT': 'position_value', 'POSITION_FLAG_SLOT': 'position_flag'},
            'native_feature_visibility_event.py': {
                'OUTER_MAP_SLOT': 'outer_map', 'PLOT_SNAPSHOT_SLOT': 'plot_snapshot180'},
        }
        for filename, names in hardcoded_slot_owners.items():
            tree = ast.parse((native_dir / filename).read_text(encoding='utf-8'))
            constants = {}
            for node in tree.body:
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and type(node.value.value) is int:
                            constants[target.id] = node.value.value
                elif isinstance(node, ast.Assign) and isinstance(node.value, (ast.Tuple, ast.List)):
                    try:
                        values = ast.literal_eval(node.value)
                        target = node.targets[0]
                        if isinstance(target, (ast.Tuple, ast.List)):
                            for name_node, value in zip(target.elts, values):
                                if isinstance(name_node, ast.Name) and type(value) is int:
                                    constants[name_node.id] = value
                        elif isinstance(target, ast.Name) and len(values) == 1 and type(values[0]) is int:
                            constants[target.id] = values[0]
                    except (ValueError, TypeError):
                        pass
            for constant, operation in names.items():
                self.assertEqual(constants[constant], abi.slot(operation),
                                 f'{filename}:{constant} must match XP2 {operation} slot')

    def test_live_source_verifier_covers_every_facade_body_and_table_slot(self):
        from civ6_host.runtime import xp2_foundation_query_source as source
        profile = source.source()
        base = 0x180000000
        memory = {}

        def write(address, raw):
            memory.update((address + index, byte) for index, byte in enumerate(raw))

        def read(address, size):
            return bytes(memory[address + index] for index in range(size))

        for table in profile['tables'].values():
            table_rva = int(table['vtable_rva'], 16)
            for slot, target in table['slots'].items():
                write(base + table_rva + int(slot, 16), (base + int(target, 16)).to_bytes(8, 'little'))
        for body in profile['functions'].values():
            for fragment in body['fragments']:
                write(base + int(fragment['start_rva'], 16), bytes.fromhex(fragment['raw_hex']))
        result = source.verify_live(base, read)
        self.assertEqual((result['operations_checked'], result['functions_checked']), (35, 39))
        self.assertEqual(result['table_slots_checked'],
                         sum(len(row['slots']) for row in profile['tables'].values()))
        table = profile['tables']['plot']
        slot = int('0x180', 16)
        address = base + int(table['vtable_rva'], 16) + slot
        original = read(address, 8)
        write(address, b'\x00' * 8)
        with self.assertRaisesRegex(ValueError, 'vtable slot'):
            source.verify_live(base, read)
        write(address, original)

    def test_shared_foundation_plot_query_uses_the_selected_xp2_tables_and_slots(self):
        from civ6_host.runtime import xp2_turn_notification_source as xp2
        from extraction_civilization_getter import transform as transform_civilization
        from extraction_foundation_facades import transform as transform_facades
        from extraction_foundation_queries import transform as transform_queries

        lab = Path(__file__).resolve().parents[2] / 'civ6-rl-lab'
        source_text = (lab / 'civ6rl' / 'native_event_fa5b1159.py').read_text(encoding='utf-8')
        source_text = transform_facades('civ6rl.native_event_fa5b1159', source_text)
        source_text = transform_queries('civ6rl.native_event_fa5b1159', source_text)
        source_text = transform_civilization('civ6rl.native_event_fa5b1159', source_text)
        event = types.ModuleType('civ6_host.runtime.native.native_event_fa5b1159')
        event.__file__ = str(lab / 'civ6rl' / 'native_event_fa5b1159.py')
        event.__package__ = 'civ6_host.runtime.native'
        exec(compile(source_text, event.__file__, 'exec'), event.__dict__)

        values = {}
        memory = SimpleNamespace(base=0x10000000)

        def put(address, raw):
            values.update((address + i, byte) for i, byte in enumerate(raw))

        def read(address, size):
            return bytes(values[address + i] for i in range(size))

        memory.put, memory.read = put, read
        from civ6_host.runtime import xp2_foundation_query_source as facade_source
        facade_profile = facade_source.source()
        for row in facade_profile['tables'].values():
            table = int(row['vtable_rva'], 16)
            for slot, target in row['slots'].items():
                put(memory.base + table + int(slot, 16),
                    struct.pack('<Q', memory.base + int(target, 16)))
        for body in xp2.bodies():
            for fragment in body['fragments']:
                put(memory.base + int(fragment['start_rva'], 16), bytes.fromhex(fragment['raw_hex']))
        from civ6_host.runtime import xp2_foundation_optional_source as optional_source
        optional = optional_source.source()
        put(memory.base + optional_source.TABLE_RVA + optional_source.SLOT,
            (memory.base + optional_source.TARGET_RVA).to_bytes(8, 'little'))
        for fragment in optional['function']['fragments']:
            put(memory.base + int(fragment['start_rva'], 16), bytes.fromhex(fragment['raw_hex']))

        from civ6_host.runtime.foundation_facade_profiles import query_abi
        abi = query_abi(XP2_CORE_SHA256, None)
        context, map_pointer, plot_pointer = 0x700000, 0x700100, 0x700200
        put(context, struct.pack('<Q', memory.base + abi.table('outer')))
        put(map_pointer, struct.pack('<Q', memory.base + abi.table('map')))
        put(plot_pointer, struct.pack('<Q', memory.base + abi.table('plot')))
        calls = []
        native_api = {
            'outer_map': lambda value: calls.append(('outer_map', value)) or map_pointer,
            'release_map': lambda value: calls.append(('release_map', value)),
            'get_plot': lambda value, x, y: calls.append(('get_plot', value, x, y)) or plot_pointer,
            'release_plot': lambda value: calls.append(('release_plot', value)),
            'get_value': lambda value: calls.append(('plot_owner', value)) or 7,
        }
        fields = event.EventFields(struct.pack('<HHI', 2, 0, 11), 2, 11,
                                   struct.pack('<ii', 3, 4), 3, 4, 0)
        result = event._query_plot_owner(SimpleNamespace(_handle=memory.base), context,
                                         fields, read=read, native_api=native_api,
                                         core_sha256=XP2_CORE_SHA256)
        self.assertEqual(result, 7)
        self.assertEqual([call[0] for call in calls],
                         ['outer_map', 'get_plot', 'release_map', 'plot_owner', 'release_plot'])
        self.assertEqual(calls[2][1], map_pointer)
        self.assertEqual(calls[-1][1], plot_pointer)

    def test_shared_positive_index_query_uses_xp2_map_plus_68_and_releases(self):
        from civ6_host.runtime import xp2_turn_notification_source as xp2
        from civ6_host.runtime import xp2_foundation_optional_source as optional_source
        from extraction_foundation_facades import transform as transform_facades

        lab = Path(__file__).resolve().parents[2] / 'civ6-rl-lab'
        source_text = (lab / 'civ6rl' / 'native_event_827289e6.py').read_text(encoding='utf-8')
        source_text = transform_facades('civ6rl.native_event_827289e6', source_text)
        event = types.ModuleType('civ6_host.runtime.native.native_event_827289e6')
        event.__file__ = str(lab / 'civ6rl' / 'native_event_827289e6.py')
        event.__package__ = 'civ6_host.runtime.native'
        exec(compile(source_text, event.__file__, 'exec'), event.__dict__)

        values = {}
        base = 0x10000000

        def put(address, raw):
            values.update((address + i, byte) for i, byte in enumerate(raw))

        def read(address, size):
            return bytes(values[address + i] for i in range(size))

        for table, slots in xp2.TABLES.values():
            for slot, target in slots.items():
                put(base + table + slot, struct.pack('<Q', base + target))
        for body in xp2.bodies():
            for fragment in body['fragments']:
                put(base + int(fragment['start_rva'], 16), bytes.fromhex(fragment['raw_hex']))
        optional = optional_source.source()
        put(base + optional_source.TABLE_RVA + optional_source.SLOT,
            (base + optional_source.TARGET_RVA).to_bytes(8, 'little'))
        for fragment in optional['function']['fragments']:
            put(base + int(fragment['start_rva'], 16), bytes.fromhex(fragment['raw_hex']))

        outer = base + 0x100000
        facade = base + 0x101000
        owner = base + 0x102000
        put(outer, (base + 0xA101E8).to_bytes(8, 'little'))
        put(facade, (base + 0xA11698).to_bytes(8, 'little'))
        put(facade + 8, owner.to_bytes(8, 'little'))
        put(owner + 40, struct.pack('<i', 16))
        put(owner + 48, struct.pack('<i', 256))
        calls = []

        def lookup_index(map_object, output, index):
            calls.append(('lookup', map_object, index))
            C.memmove(output, struct.pack('<ii', 7, 9), 8)
            return output

        result = event.query_optional_position(
            SimpleNamespace(_handle=base), outer, 23, read=read,
            native_api={
                'get_map': lambda context: calls.append(('get_map', context)) or facade,
                'lookup_index': lookup_index,
                'release_map': lambda value: calls.append(('release_map', value)),
            }, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(result, struct.pack('<ii', 7, 9))
        self.assertEqual([row[0] for row in calls], ['get_map', 'lookup', 'release_map'])
        self.assertEqual(calls[1][2], 23)
        self.assertEqual(calls[-1][1], facade)


if __name__ == '__main__':
    unittest.main()
