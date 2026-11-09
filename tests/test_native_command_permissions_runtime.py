"""Actual permission-query Lua with replaced engine methods; no native execution."""
from types import SimpleNamespace as NS
import unittest
from lupa.lua51 import LuaRuntime
from civ6_host.runtime.xp1_session_view import _read_command_permissions


class CommandPermissionRuntimeTests(unittest.TestCase):
    def fixture(self, strategic=True, tactical=True, change_turn=False):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.globals().strategic = strategic
        lua.globals().tactical = tactical
        lua.globals().changeTurn = change_turn
        lua.execute('''
            currentTurn=61
            Game={GetLocalPlayer=function()return 0 end,
              GetLocalObserver=function()return 0 end,
              GetCurrentGameTurn=function()return currentTurn end,
              IsAllowStrategicCommands=function(pid)assert(pid==0);return strategic end,
              IsAllowTacticalCommands=function(pid)
                assert(pid==0);if changeTurn then currentTurn=62 end;return tactical
              end}
        ''')
        calls = []
        child = object()
        def evaluate(actual, source, label, **kwargs):
            self.assertIs(actual, child)
            self.assertEqual(label, b'@native_command_permissions')
            self.assertEqual(kwargs, {'capacity': 32})
            calls.append(source)
            return lua.execute(source.decode('ascii')).encode('ascii')
        saved = NS(prefix=NS(runtime=NS(evaluate_text=evaluate), ui_child=child))
        return saved, calls

    def test_gates_are_independent_and_keep_real_observation_identity(self):
        for strategic in (False, True):
            for tactical in (False, True):
                with self.subTest(strategic=strategic, tactical=tactical):
                    saved, calls = self.fixture(strategic, tactical)
                    value = _read_command_permissions(saved, 0, 61, 5)
                    self.assertEqual(value, dict(player_id=0, turn=61, sequence=5,
                        allow_strategic=strategic, allow_tactical=tactical))
                    self.assertEqual(len(calls), 1)

    def test_nonboolean_native_predicates_and_scope_changes_refuse(self):
        for args in ((1, True, False), (True, None, False), (True, True, True)):
            with self.subTest(args=args):
                saved, _ = self.fixture(*args)
                with self.assertRaises(Exception):
                    _read_command_permissions(saved, 0, 61, 5)

    def test_foreign_perspective_refuses_in_real_query(self):
        saved, _ = self.fixture()
        with self.assertRaisesRegex(Exception, 'perspective'):
            _read_command_permissions(saved, 1, 61, 5)

    def test_malformed_result_or_invalid_identity_cannot_become_permission(self):
        saved, calls = self.fixture()
        with self.assertRaises(ValueError):
            _read_command_permissions(saved, True, 61, 5)
        self.assertFalse(calls)
        saved.prefix.runtime.evaluate_text = lambda *a, **kw: b'0,0,0'
        with self.assertRaisesRegex(ValueError, 'Malformed'):
            _read_command_permissions(saved, 0, 61, 5)
