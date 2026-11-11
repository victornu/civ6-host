"""XP2 end-turn effect marker from the retained public UI getter."""
import hashlib
from pathlib import Path

from .a0_policy_unlock_current import _require_image
from .configuration_profiles import XP2_CORE_SHA256, _source
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('work/trade-common-client/congress-turn-source/source.json', '73859bb176399dedfc7d3f464a83691043d097f07043f938406d0f4facd03922')


def source_dependencies(*, execution_image):
    _require_image(execution_image)
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-turn-segment-source.v1'
            or proof['image']['sha256'] != execution_image.image_sha256
            or tuple(proof['contract']['chain']) != ('0x69b030', '0x63d0c0', '0x5b320')
            or any(row['relocations'] for row in proof['spans'].values())):
        raise ValueError('XP2 public turn-segment getter source changed')
    module = Path(__file__).resolve()
    return {str(resolve_path(resource_root()/SOURCE[0]).resolve()): SOURCE[1],
            str(module): hashlib.sha256(module.read_bytes()).hexdigest()}


def read(saved, player_id, turn):
    """Return the native hash, preserving the absent marker as uint32 0xffffffff."""
    from .xp1_world_input import _owner
    from .xp1_session_view import _reference
    if (type(player_id) is not int or not 0 <= player_id <= 63
            or type(turn) is not int or not 0 <= turn <= 100000):
        raise ValueError('Invalid turn-segment perspective')
    b, c, p, identity = _owner(saved, active=True)
    _reference(saved, player_id)
    if (b.load_abi.core_sha256 != XP2_CORE_SHA256
            or (getattr(saved, 'world_congress_diagnostic', False) is not True
                and getattr(saved, 'stock_dedications', False) is not True)):
        raise ValueError('Turn-segment marker requires a source-qualified XP2 saved owner')
    image = getattr(b.core, '_civ6_host_execution_image', None)
    source_dependencies(execution_image=image)
    proof = _source(SOURCE)
    for row in proof['spans'].values():
        raw = b.runtime.read(b.core._handle + int(row['rva'], 16), row['bytes'])
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Live turn-segment getter differs at ' + row['rva'])
    revision, runtime, child = c.sequence, p.runtime, p.ui_child
    text = (f'local pid={player_id}; local turn={turn}\n'.encode('ascii') + b'''
local function identity()
 assert(Game.GetCurrentGameTurn()==turn and Game.GetLocalPlayer()==pid and
  Game.GetLocalObserver()==pid,'turn-segment perspective changed')
end
identity()
local value=Game.GetCurrentTurnSegment()
assert(type(value)=='number' and value%1==0 and value>=-2147483648 and
 value<=2147483647,'invalid native turn segment')
identity()
return string.format('%.0f',value%4294967296)
''')
    raw = runtime.evaluate_text(child, text, b'@xp2_turn_segment', capacity=64)
    actual = _owner(saved, active=True)
    if (any(a is not e for a, e in zip(actual, (b, c, p, identity)))
            or c.sequence != revision or p.runtime is not runtime or p.ui_child is not child):
        raise RuntimeError('Turn-segment owner changed during native read')
    if (type(raw) is not bytes or not 1 <= len(raw) <= 10 or not raw.isdigit()
            or str(int(raw)).encode('ascii') != raw or not 0 <= int(raw) <= 0xffffffff):
        raise ValueError('Malformed native turn-segment marker')
    return int(raw)
