"""Read the XP2 game's end turn at an admitted local decision boundary."""
from .configuration_profiles import XP2_CORE_SHA256, _source


SOURCE = ('evidence/host-xp2-game-end-turn-source.json',
          '9ae6a6ec529f3455c50fd7276b0f2ad2a9dbc1561fbc2642a023b5848bfb66f0')

_READ = b'''
local function checked(...)
    assert(select('#', ...) == 1, 'unexpected end turn arity')
    local value = ...
    assert(type(value) == 'number' and value % 1 == 0
        and value >= -2147483648 and value <= 2147483647, 'invalid end turn')
    return value
end
local function context()
    assert(Game.GetCurrentGameTurn() == turn and Game.GetLocalPlayer() == player
        and Game.GetLocalObserver() == player, 'foreign end turn context')
end
context()
local value = checked(Game.GetGameEndTurn())
context()
return string.format('%d', value)
'''


def read(saved, player_id, turn):
    backend = saved.backend
    saved._check('commands', requested='unit_commands_candidate')
    if backend.load_abi.core_sha256 != XP2_CORE_SHA256 or saved.core is not backend.core:
        raise ValueError('End turn read requires its exact XP2 owner')
    if (type(player_id) is not int or not 0 <= player_id < 64
            or type(turn) is not int or not 0 <= turn <= 100000):
        raise ValueError('Invalid end turn observation identity')
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-game-end-turn.static.v1'
            or proof['core_sha256'] != XP2_CORE_SHA256 or proof['binding'] != 'Game.GetGameEndTurn'):
        raise ValueError('Unexpected XP2 end turn source')
    base = saved.core._handle
    for key in ('callback_load', 'name_load', 'callback', 'read_leaf'):
        raw = bytes.fromhex(proof[key + '_bytes'])
        if backend.runtime.read(base + int(proof[key + '_rva'], 16), len(raw)) != raw:
            raise ValueError('Live XP2 end turn binding bytes differ: ' + key)
    literal = b'GetGameEndTurn\0'
    if backend.runtime.read(base + int(proof['name_rva'], 16), len(literal)) != literal:
        raise ValueError('Live XP2 end turn binding name differs')
    prefix = saved.prefix
    with saved._attempt():
        saved.continuation.check(active=False)
        saved.continuation.transport.require_empty_native_queue()
        backend.control(empty=True)
        payload = prefix.runtime.evaluate_text(prefix.ui_child,
            f'local player, turn = {player_id}, {turn}\n'.encode('ascii') + _READ,
            b'@xp2_game_end_turn', capacity=32)
        value = int(payload)
        if str(value).encode('ascii') != payload or not -(2**31) <= value < 2**31:
            raise ValueError('Malformed XP2 native end turn')
        backend.control(empty=True)
    return value
