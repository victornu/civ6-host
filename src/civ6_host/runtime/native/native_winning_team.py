"""Read the native victory result without inferring an episode termination."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import re
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PIN = '8c4f82ac7181b3474826d13b051dc978b332d7aa138a314be54bf356c8cf2081'
PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_winning_team.py')))).resolve().parents[1] / 'evidence/native-winning-team' / f'{PIN}.json'

def source(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    if core_sha256 == 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
        proof = load_pinned_json(PROOF, PIN)
        if proof['schema'] != 'civ6rl.native_winning_team.static.v1' or proof['callback_rva'] != '0x523ed0' or proof['core_sha256'] != 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3':
            raise RuntimeError('Native winning-team source identity changed')
    else:
        from civ6_host.runtime.xp1_session_result import verify_reader_source
        verify_reader_source(core_sha256)
    return b"assert(Game and type(Game.GetWinningTeam)=='function','native winner getter unavailable')\nlocal function encode(...)\n local count=select('#',...)\n if count==0 then return 'none' end\n assert(count==2,'native winner getter returned unexpected result count')\n local team,victory=...\n assert(type(team)=='number' and team%1==0 and team>=-2147483648 and team<=2147483647\n        and team~=-1,'invalid native winning team')\n assert(type(victory)=='number' and victory%1==0 and victory>=-2147483648 and victory<=2147483647,\n        'invalid native victory type')\n return string.format('%d,%d',team,victory)\nend\nreturn encode(Game.GetWinningTeam())\n"

def parse(payload):
    if type(payload) is not bytes or len(payload) > 48:
        raise ValueError('Invalid native winning-team payload')
    if payload == b'none':
        return {'winner_present': False, 'winning_team': None, 'victory_type': None}
    if not re.fullmatch(b'-?[0-9]{1,10},-?[0-9]{1,10}', payload):
        raise ValueError('Malformed native winning-team result')
    team, victory = map(int, payload.split(b','))
    if not -2 ** 31 <= team < 2 ** 31 or team == -1 or (not -2 ** 31 <= victory < 2 ** 31):
        raise ValueError('Native winning-team result outside source contract')
    if payload != f'{team},{victory}'.encode('ascii'):
        raise ValueError('Noncanonical native winning-team result')
    return {'winner_present': True, 'winning_team': team, 'victory_type': victory}

def guard_case(*, core_sha256='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'):
    return b"local mode='none'\nlocal Game={GetWinningTeam=function()\n if mode=='none' then return end\n if mode=='winner' then return 1,-123 end\n if mode=='partial' then return 1 end\n if mode=='extra' then return 1,2,3 end\n if mode=='invalid' then return -1,2 end\n return 0,0.5\nend}\nlocal function collect()\n" + source(core_sha256=core_sha256) + b"end\nassert(collect()=='none')\nmode='winner';assert(collect()=='1,-123')\nfor _,bad in ipairs({'partial','extra','invalid','fraction'}) do\n mode=bad;assert(not pcall(collect),'malformed native victory result accepted')\nend\nreturn 'winning-team-guards-ok'\n"
