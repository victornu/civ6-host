"""XP2 public data contract; these fixtures do not qualify native war actions."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from civ6_host.contracts import xp2_war_confirmation as war


class WarConfirmationContractTests(unittest.TestCase):
    def fixture(self):
        return dict(schema=war.DISPLAY_SCHEMA, player_id=0, turn=25,
            defender_player_ids=[1], war_type=1133958949,
            targets=[dict(player_id=1, display_name='Défenseur', icon_name='ICON_CIV_TEST')],
            message='Confirmer la guerre ?', consequences='Conséquences visibles de Gathering Storm',
            buttons=[dict(accept=False, text='Annuler'), dict(accept=True, text='Confirmer')],
            static_text=dict(title='Guerre', warmonger_heading='Conséquences'), source_sha256='a'*64)

    def parse(self, value):
        return war.parse_display(json.dumps(value).encode(), 0, 25, [1], 1133958949,
                                 expected_source_sha256='a'*64)

    def test_distinct_public_schema_and_two_explicit_boolean_choices(self):
        value = self.fixture()
        self.assertEqual(self.parse(value), value)
        prompt = dict(attacking_player=0, defending_player=1, war_type=1133958949)
        self.assertEqual(war.actions(prompt, 0), [dict(kind='world_war_response', accept=False),
                                                dict(kind='world_war_response', accept=True)])
        old = dict(value, warmonger_text=value['consequences'])
        del old['consequences']
        with self.assertRaises(ValueError):
            self.parse(old)
        for accept in (0, 1, 'true'):
            with self.subTest(accept=accept), self.assertRaises(ValueError):
                war.validate_action(dict(kind='world_war_response', accept=accept))

    def test_identity_provenance_and_extra_private_fields_refused(self):
        for change in (dict(player_id=True), dict(turn=24), dict(war_type=False),
                       dict(defender_player_ids=[True]), dict(source_sha256='b'*64),
                       dict(schema='civ6rl.native_world_war_display.v2'),
                       dict(raw_grievances=100), dict(test_action_results={'hidden': 5})):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.parse(dict(self.fixture(), **change))
        for key, mutation in [('buttons', [dict(accept=True, text='Oui'), dict(accept=False, text='Non')]),
                              ('targets', [dict(player_id=True, display_name='X', icon_name='I')])]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.parse(dict(self.fixture(), **{key: mutation}))

    def test_strict_json_and_public_text_bounds(self):
        raw = json.dumps(self.fixture()).encode()
        for bad in (b'{"turn":25,'+raw[1:], raw.replace(b'"turn": 25', b'"turn": NaN'),
                    b' '*(war.MAX_BYTES+1), b'\xff', raw.decode().encode('utf-16')):
            with self.subTest(size=len(bad)), self.assertRaises(ValueError):
                war.parse_display(bad,0,25,[1],1133958949,expected_source_sha256='a'*64)
        for text in ('\ud800', 'x\0y', 'x'*(war.MAX_TEXT_BYTES+1)):
            with self.subTest(length=len(text)), self.assertRaises(ValueError):
                self.parse(dict(self.fixture(), consequences=text))

    def test_portable_parser_has_no_runtime_or_game_resource_dependency(self):
        script = """
import importlib.abc, json, sys
class NoRuntime(importlib.abc.MetaPathFinder):
 def find_spec(self, fullname, path=None, target=None):
  if fullname.startswith('civ6_host.runtime'): raise AssertionError(fullname)
sys.meta_path.insert(0, NoRuntime())
from civ6_host.contracts.xp2_war_confirmation import parse_display
v=json.loads(sys.stdin.read())
assert parse_display(json.dumps(v).encode(),0,25,[1],1133958949,expected_source_sha256='a'*64)==v
"""
        env = os.environ.copy()
        env.pop('CIV6_HOST_RESOURCE_ROOT', None)
        env['PYTHONPATH'] = str(Path(__file__).resolve().parents[1]/'src')
        run = subprocess.run([sys.executable, '-P', '-c', script], input=json.dumps(self.fixture()),
                             text=True, capture_output=True, env=env, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)


if __name__ == '__main__':
    unittest.main()
