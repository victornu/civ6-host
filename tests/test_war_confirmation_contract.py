"""Public wire validation only; no GameCore requests or XP2 admission."""
from hashlib import sha256
import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest

from civ6_host.contracts import war_confirmation as war


class WarConfirmationContractTests(unittest.TestCase):
    def fixture(self):
        return dict(schema=war.DISPLAY_SCHEMA, player_id=0, turn=12,
            defender_player_ids=[1], war_type=1133958949,
            targets=[dict(player_id=1, display_name='Cible publique', icon_name='ICON_TEST')],
            message='Confirmer la guerre ?', warmonger_text='Information publique',
            buttons=[dict(accept=False, text='Annuler'), dict(accept=True, text='Confirmer')],
            static_text=dict(title='Guerre', warmonger_heading='Conséquences'),
            source_sha256='a' * 64)

    def parse(self, value):
        return war.parse_display(json.dumps(value).encode('utf-8'), 0, 12, [1], 1133958949,
                                 expected_source_sha256='a' * 64)

    def test_public_wire_and_both_explicit_boolean_responses(self):
        value = self.fixture()
        self.assertEqual(self.parse(value), value)
        prompt = dict(attacking_player=0, defending_player=1, war_type=1133958949)
        self.assertEqual(war.actions(prompt, 0), [
            dict(kind='world_war_response', accept=False),
            dict(kind='world_war_response', accept=True)])
        for action in war.actions(prompt, 0):
            self.assertIs(war.validate_action(action), action)
        for accept in (0, 1, 'true', None):
            with self.subTest(accept=accept), self.assertRaises(ValueError):
                war.validate_action(dict(kind='world_war_response', accept=accept))
        with self.assertRaises(ValueError):
            war.validate_prompt(dict(prompt, defending_player=0), 0)

    def test_foreign_identity_private_fields_and_missing_buttons_refuse(self):
        mutations = [dict(player_id=1), dict(turn=13), dict(war_type=True),
                     dict(defender_player_ids=[2]), dict(source_sha256='b' * 64),
                     dict(admin_state={'hidden_score': 42}), dict(buttons=self.fixture()['buttons'][:1])]
        for changes in mutations:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.parse(dict(self.fixture(), **changes))

    def test_duplicate_keys_nonfinite_bad_unicode_and_bounds_refuse(self):
        encoded = json.dumps(self.fixture()).encode('ascii')
        for raw in (b'{"turn":12,' + encoded[1:], encoded.replace(b'"turn": 12', b'"turn": NaN'),
                    b' ' * (war.MAX_BYTES + 1)):
            with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                war.parse_display(raw, 0, 12, [1], 1133958949, expected_source_sha256='a' * 64)
        for text in ('x' * (war.MAX_TEXT_BYTES + 1), '\ud800', 'a\x00b'):
            with self.subTest(length=len(text)), self.assertRaises(ValueError):
                self.parse(dict(self.fixture(), message=text))

    def test_client_codec_imports_no_runtime_and_needs_no_game_resources(self):
        code = '''import importlib.abc, json, sys
class NoRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('civ6_host.runtime'):
            raise RuntimeError('wire codec imported native runtime')
sys.meta_path.insert(0, NoRuntime())
from civ6_host.contracts.war_confirmation import parse_display
value=json.load(sys.stdin)
assert parse_display(json.dumps(value).encode(),0,12,[1],1133958949,
    expected_source_sha256='a'*64)==value
'''
        env = dict(os.environ)
        env.pop('CIV6_HOST_RESOURCE_ROOT', None)
        env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1] / 'src')
        result = subprocess.run([sys.executable, '-P', '-c', code], env=env,
            input=json.dumps(self.fixture()), text=True, capture_output=True, timeout=15,
            **({'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_retained_base_displays_match_archived_parser(self):
        lab = Path(os.environ.get('CIV6_HOST_RESOURCE_ROOT', Path(__file__).resolve().parents[2] / 'civ6-rl-lab'))
        original_sha = '3bfe020b1ceca398cb9f4ac10258ef5e6c3e10dbd7f1b3a47ac3a6b2433b1cc0'
        original = lab / 'work/bbg751-turn-source-scope/war-confirmation/before' / original_sha / 'native_world_war_display.py'
        proof = lab / 'evidence/phase1-native-war-confirmation.json'
        if not original.is_file() or not proof.is_file():
            self.skipTest('Local hash-pinned Base witnesses and original parser required')
        source = original.read_bytes()
        self.assertEqual(sha256(source).hexdigest(), original_sha)
        receipt = json.loads(proof.read_bytes())
        ref = receipt['explicit_trace']['events.jsonl']
        events = (lab / ref['path']).read_bytes()
        self.assertEqual(sha256(events).hexdigest(), ref['sha256'])
        displays = [row['display'] for line in events.splitlines()
                    if line.startswith(b'{') and (row := json.loads(line)).get('stage') == 'official_world_war_display']
        self.assertTrue(displays)
        namespace = dict(json=json, re=re, MAX_BYTES=war.MAX_BYTES, MAX_TEXT_BYTES=war.MAX_TEXT_BYTES,
                         SCHEMA=war.DISPLAY_SCHEMA, _PLAYER_MAX=63, _WAR_MAX=0xffffffff)
        functions = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef)
                     and n.name in ('_int', '_war_int', '_text', 'parse_display')]
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(original), 'exec'), namespace)
        wrapper_path = Path(__file__).resolve().parents[1] / 'src/civ6_host/runtime/native/native_world_war_display.py'
        wrapper_node = next(n for n in ast.parse(wrapper_path.read_bytes()).body
                            if isinstance(n, ast.FunctionDef) and n.name == 'parse_display')
        wrapper_namespace = {}
        exec(compile(ast.Module(body=[wrapper_node], type_ignores=[]), str(wrapper_path), 'exec'), wrapper_namespace)
        for value in displays:
            namespace['_projection_sha256'] = lambda: value['source_sha256']
            wrapper_namespace['_projection_sha256'] = lambda: value['source_sha256']
            args = (value['player_id'], value['turn'], value['defender_player_ids'], value['war_type'])
            raw = json.dumps(value).encode('utf-8')
            expected = namespace['parse_display'](raw, *args)
            self.assertEqual(war.parse_display(raw, *args,
                expected_source_sha256=value['source_sha256']), expected)
            self.assertEqual(wrapper_namespace['parse_display'](raw, *args), expected)
            for changes in (dict(player_id=True), dict(buttons=value['buttons'][::-1]),
                            dict(privileged_snapshot={}), dict(source_sha256='0' * 64)):
                bad = json.dumps(dict(value, **changes)).encode('utf-8')
                with self.assertRaises(ValueError):
                    namespace['parse_display'](bad, *args)
                with self.assertRaises(ValueError):
                    war.parse_display(bad, *args, expected_source_sha256=value['source_sha256'])


if __name__ == '__main__':
    unittest.main()
