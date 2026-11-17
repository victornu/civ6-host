"""Installed-source and retained-public-state checks for Gathering Storm activation."""

import ast
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import pefile

from civ6_host import SessionClient
from civ6_host.contracts import great_person_activation as public, information, network_turn
from civ6_host.runtime import xp1_great_person_activation as activation, xp2_great_person_activation_source as source
from civ6_host.runtime import network_checkpoint
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.execution_images import _PROFILE
from civ6_host.runtime.native import native_event_great_work
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.workers import network_worker
from civ6_host.runtime.xp1_continuation import SavedContinuation


def checked_json(path, expected):
    assert 0 < path.stat().st_size <= 1024**2
    raw = path.read_bytes()
    assert sha256(raw).hexdigest() == expected
    return json.loads(raw.decode('utf-8'))


def seal(value):
    value.pop('decision_id', None)
    value['decision_id'] = network_turn.digest(value)


def checked_event(root, reference, line_number):
    path = root / reference['path']
    assert path.stat().st_size == reference['bytes'] <= 8 * 1024**2
    checksum = sha256()
    selected = None
    with path.open('rb') as stream:
        for number, line in enumerate(stream, 1):
            checksum.update(line)
            if number == line_number:
                selected = line
    assert checksum.hexdigest() == reference['sha256'] and selected is not None
    return json.loads(selected.decode('utf-8'))


class GatheringStormActivationTests(unittest.TestCase):
    def test_wrapped_catalogue_preserves_native_parameterized_choices(self):
        root = resource_root()
        congress = checked_json(root/'evidence/host-xp2-congress-ballot-result-save-native.json',
                                '6107a4ec2e1a670b2409d0d4c9fae3388e31006a3433be768eeae900fe315db9')
        dedication = checked_json(root/'evidence/host-xp2-stock-dedications-confirmation-native.json',
                                   'c91ca23d3655c31d1801f1689728ef160d2e6fcb08444cdcd705ad9e640a8e41')
        catalogue_ref = dedication['catalogue_native']
        catalogue = checked_json(root/catalogue_ref['path'], catalogue_ref['sha256'])
        congress_request = checked_event(root, congress['commands'], 3)
        congress_reply = checked_event(root, congress['events'], 7457)
        dedication_reply = checked_event(root, catalogue['events'], 4729)
        cases = ((congress_reply, congress_request['selection'], 'congress_confirm_ballot'),
                 (dedication_reply, dedication['public']['command']['selection'], 'confirm_dedications'))

        for reply, selection, kind in cases:
            with self.subTest(kind=kind):
                obs, base = reply['observation'], reply['decisions']
                published, = (row for row in base['candidates'] if row['action']['kind'] == kind)
                self.assertEqual(published['candidate_id'], selection['candidate_id'])
                historical = dict(selection, decision_id=base['decision_id'])
                expected = network_turn.select_capability(base, historical)
                new = deepcopy(base)
                state = None if network_turn.family_query_unavailable(new, public.KIND) else dict(
                    schema=public.SCHEMA, player_id=obs['player_id'], turn=obs['turn'],
                    operation=public.OPERATION, units=[])
                network_turn.add_xp2_great_person_activation(new, state)
                seal(new)
                self.validate(obs, new)
                with self.assertRaisesRegex(ValueError, 'stale'):
                    network_turn.select_capability(new, historical)
                selection = dict(selection, decision_id=new['decision_id'])
                self.assertEqual(network_turn.select_capability(new, selection), expected)
                self.assertEqual(network_turn.congress_action_read_only(new, 'government'),
                                 network_turn.congress_action_read_only(base, 'government'))

    def test_offered_action_reaches_native_transition_only_when_enabled(self):
        observation, _, state = self.fixture()
        action, = public.actions(state)
        owner = SimpleNamespace(load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256))
        continuation = SimpleNamespace(owner=owner, observation=observation,
                                       world_input_prompts={}, _transition=Mock())
        session = SimpleNamespace(backend=owner, xp2_great_person_activation=True)

        SavedContinuation.execute(continuation, action, session=session)
        continuation._transition.assert_called_once_with(action, session=session, pump=False)

        continuation._transition.reset_mock()
        session.xp2_great_person_activation = False
        with self.assertRaisesRegex(ValueError, 'activation requires its explicit expansion group'):
            SavedContinuation.execute(continuation, action, session=session)
        continuation._transition.assert_not_called()

    def test_real_reset_reply_passes_the_composed_client(self):
        run = resource_root()/'work/xp2-workmove/stock-writer/native-runs/run-59f1539157f14da286bd9e1c1fb43f07'
        path = run/'events.jsonl'
        self.assertLess(path.stat().st_size, 3*1024**2)
        raw = path.read_bytes()
        self.assertEqual(sha256(raw).hexdigest(), '649cef3fd68b1d2a34af1250b7b57b2bc8a3f4fdac0fbad45d1306fa158eedf5')
        response = json.loads(raw.splitlines()[5440].decode('utf-8'))
        client = SessionClient(SimpleNamespace(reset=lambda: response, abort=Mock()))
        view = client.reset()
        self.assertEqual(view['observation']['turn'], 111)
        state = client.information('great_person_activation')['data']
        self.assertEqual(state['units'], [dict(unit_id=851972, x=39, y=14, individual_index=58,
                                             class_index=0, charges=0, visible=True, available=True)])
        self.assertIn(public.actions(state)[0], [row['action'] for row in view['decisions']['candidates']])
        self.assertEqual(client.information('city_buildings')['data'], view['decisions']['city_buildings'])
        self.assertEqual(client.information('combat')['data'],
                         information.project('combat', view['observation'], view['decisions']))

    def test_worker_dependency_check_preserves_the_run_manifest_path(self):
        filename = Path(network_worker.__file__)
        syntax = ast.parse(filename.read_text(encoding='utf-8'))
        opener = next(node for node in syntax.body if isinstance(node, ast.FunctionDef) and node.name=='_open_xp1')
        guard = next(node for node in opener.body if isinstance(node, ast.If)
                     and isinstance(node.test, ast.Name) and node.test.id=='xp2_great_person_activation')
        module = ast.fix_missing_locations(ast.Module(body=[guard], type_ignores=[]))
        reference = next(iter(source._CAPTURES))
        pins = source.source_dependencies(_PROFILE, reference=reference)
        manifest = Path('private-run/closure.json')
        ctx = dict(path=manifest, xp2_great_person_activation=True, occupation_image=_PROFILE,
                   selected=SimpleNamespace(reference=reference), closure={'pins': pins})
        runner = compile(module, str(filename), 'exec')
        exec(runner, ctx)
        self.assertIs(ctx['path'], manifest)
        ctx['closure'] = {'pins': {}}
        with self.assertRaisesRegex(ValueError, 'outside the Gathering Storm worker closure'):
            exec(runner, ctx)

    def test_source_dependency_membership_and_installed_bytes(self):
        pe = pefile.PE(str(_PROFILE.path))
        base = pe.OPTIONAL_HEADER.ImageBase
        for reference in source._CAPTURES:
            with self.subTest(reference=reference):
                self.assertIn(reference[1], source.source_dependencies(_PROFILE, reference=reference).values())
                source.verify_live(base, lambda address, size: pe.get_data(address-base, size),
                                   reference=reference, image=_PROFILE)
        with self.assertRaises(ValueError):
            source.require_actions(_PROFILE, reference=('other', '0'*64))
        corrupt = lambda address, size: bytes(size) if address == base+0xa256a0 else pe.get_data(address-base, size)
        with self.assertRaisesRegex(ValueError, 'command table differs'):
            source.verify_live(base, corrupt, reference=next(iter(source._CAPTURES)), image=_PROFILE)

    def fixture(self):
        root = resource_root()
        proof = checked_json(root/'evidence/host-xp2-stock-great-work-slots-empty-t111-native.json',
                             '09499a90b1fedfedfbf390f73bfdc771fca11e8b321fc7c695182730881d1d9c')
        ref = proof['checkpoint']
        manifest = checked_json(root/ref['path'], ref['sha256'])
        obs, old = manifest['observation'], manifest['decisions']
        unit = obs['units'][0]
        state = dict(schema=public.SCHEMA, player_id=obs['player_id'], turn=obs['turn'],
                     operation=public.OPERATION, units=[dict(
                         unit_id=unit['id'], x=unit['x'], y=unit['y'], individual_index=8,
                         class_index=6, charges=0, visible=True, available=True)])
        return obs, old, state

    def validate(self, obs, view):
        identity = SimpleNamespace(episode_id=view['episode_id'], game_generation=view['game_generation'])
        return network_turn.validate_capability_catalogue(
            view, identity, view['sequence'], obs['turn'], player_id=obs['player_id'], observation=obs)

    def test_additive_choice_validates_own_units_and_preserves_previous_fields(self):
        obs, old, state = self.fixture()
        view = deepcopy(old)
        network_turn.add_xp2_great_person_activation(view, state)
        seal(view)
        self.assertIs(self.validate(obs, view), view)
        self.assertEqual(information.project('great_person_activation', obs, view), state)
        for group in ('city_buildings', 'city_religion', 'native_command_permissions', 'production'):
            self.assertEqual(information.project(group, obs, view), information.project(group, obs, old))
        projected, proof = network_turn.checkpoint_catalogue(view, old, obs, core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, old)
        self.assertEqual(proof['added_action_families'], [public.KIND])
        origin = dict(schema=network_checkpoint.SCHEMA_V2, core_sha256=XP2_CORE_SHA256,
                      observation=obs, decisions=old)
        owner = SimpleNamespace(emit=Mock(),
            backend=SimpleNamespace(load_abi=SimpleNamespace(core_sha256=XP2_CORE_SHA256)),
            inputs=SimpleNamespace(checkpoint=('private/checkpoint.json', 'a'*64),
                                   profile=SimpleNamespace(name='xp2-lan-official-capture-inputs')))
        network_checkpoint._compare_decisions(owner, origin, obs, view)
        stage, = owner.emit.call_args.args
        self.assertEqual(stage, 'official_lan_checkpoint_reloaded')
        self.assertTrue(owner.emit.call_args.kwargs['saved_decision_fields_equal'])
        self.assertEqual(view['candidates'][-1]['action'], public.actions(state)[0])
        for modify in ('foreign', 'dropped', 'forged', 'closed'):
            with self.subTest(modify=modify), self.assertRaises(ValueError):
                candidate = deepcopy(view)
                if modify == 'foreign':
                    candidate['great_person_activation']['units'][0]['unit_id'] = 0xffffffff
                elif modify == 'dropped':
                    candidate['candidates'].pop()
                elif modify == 'forged':
                    candidate['candidates'][-1]['action']['x'] = True
                else:
                    candidate['native_command_permissions']['allow_strategic'] = False
                seal(candidate)
                self.validate(obs, candidate)

    def test_receipt_requires_selected_image_and_receiving_city(self):
        owner, uid, city = 0, 135, 65536
        raw = native_event_great_work.encode_record(
            9, dict(position_bytes=struct.pack('<ii', 39, 14), x=39, y=14,
                    selector=0, source_value=2, descriptor_tail=0),
            struct.pack('<HHI', owner, 1, uid), dict(owner=owner, city_id=city, district_id=0))
        receipt = dict(deferred_start_sequence=8, post_command_sequence=10,
                       completion_source_sha256=source.COMPLETION_SOURCE[1], great_work_records=[
                           dict(record_hex=raw.hex(), record_sha256=sha256(raw).hexdigest(),
                                source_sha256=source.WORK_SOURCE[1])])
        args = dict(pid=owner, unit_id=uid, cities=[dict(owner=owner, id=city, x=39, y=14)],
                    charges_before=0, charges_after=0, unit_consumed=False)
        self.assertEqual(activation.confirmation(receipt, profile=source, **args), 'great_work_created')
        with self.assertRaisesRegex(RuntimeError, 'interval or source'):
            activation.confirmation(receipt, **args)
        with self.assertRaisesRegex(RuntimeError, 'interval or owned unit'):
            activation.confirmation(receipt, profile=source, **dict(args, cities=[]))


if __name__ == '__main__':
    unittest.main()
