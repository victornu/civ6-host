"""Official plot-tooltip park getters on the current owned expansion view."""

from pathlib import Path

from civ6_host.contracts import national_parks as contract

from . import expansion_city_growth
from .a0_family_source import verify_pinned_files
from .configuration_profiles import _source
from .execution_images import identity
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp2_bbg_inputs import REFERENCE as BBG_REFERENCE

SOURCE = ('evidence/host-expansion-national-parks-ui-source.json',
          'cfbecc528632bb5ebf3e62497363dc585ad2e24cc6c46dca6018d38a87d9ea01')
CAPACITY = 4 * 1024 * 1024


def _profile(reference, image):
    known = expansion_city_growth.CAPTURES.get(reference)
    if known is None or known[0] is not image:
        raise ValueError('National park labels require an admitted expansion capture and image')
    proof = _source(SOURCE)
    original = proof['scope_proof']
    selected = proof['engines'][image.id]
    if (proof['schema'] != 'civ6-host.expansion-national-parks-ui-source.v1'
            or (original['path'], original['sha256']) != expansion_city_growth.SOURCE
            or selected['image'] != identity(image) or reference not in proof['exact_captures']
            or proof['read_gate'] != 'IsRevealed' or proof['bbg_replaces_ui'] is not False
            or proof['visibility_event_admitted'] is not False):
        raise ValueError('Expansion national park source differs')
    return proof, selected


def source_dependencies(reference, image):
    proof, _ = _profile(reference, image)
    root = resource_root()
    files = (*proof['inherited_ui'], *proof['manifests'][:2])
    if reference == BBG_REFERENCE:
        files = (*files, proof['manifests'][2])
    pins = {str(Path(image.path).resolve()): image.image_sha256}
    for name, digest in (SOURCE, expansion_city_growth.SOURCE, reference,
                         *((row['path'], row['sha256']) for row in files)):
        path = str(resolve_path(root / name).resolve(strict=True))
        if pins.setdefault(path, digest) != digest:
            raise ValueError('Conflicting national park source pin')
    verify_pinned_files(pins)
    return pins


def verify_live(selected, base, read):
    bindings = selected['bindings']
    expected = ('IsNationalPark', 'GetNationalParkName')
    if set(bindings) != set(expected) or any(len(bindings[name]) != 2 for name in expected):
        raise ValueError('National park binding inventory differs')
    for index in range(2):
        pair = {'bindings': {name: bindings[name][index] for name in expected}}
        expansion_city_growth.verify_bindings(pair, base, read)


def bind(saved):
    lifetime = expansion_city_growth._owner(saved)
    core = lifetime[0]
    _, selected = _profile(lifetime[-1], getattr(core, '_civ6_host_execution_image', None))
    verify_live(selected, core._handle, saved.backend.runtime.read)
    saved._expansion_national_parks = lifetime


def build_source(player_id, turn):
    if type(player_id) is not int or not 0 <= player_id < 64 or type(turn) is not int or not 0 <= turn < 2**31:
        raise ValueError('Invalid national park viewpoint')
    return (f'local pid,turn={player_id},{turn}\n'
            f'local maxPlots,maxName,capacity={contract.MAP_CELL_LIMIT},{contract.MAX_NAME_BYTES},{CAPACITY}\n'
            ).encode('ascii') + _READ


_READ = br'''
local function context()
    assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,
        'foreign or stale national park observation')
end
context()
local visibility=assert(PlayersVisibility[pid])
local width,height=Map.GetGridSize()
local count=Map.GetPlotCount()
assert(type(width)=='number' and type(height)=='number' and width%1==0 and height%1==0
    and width>0 and height>0 and width*height==count and count<=maxPlots,'invalid national park map extent')
local lines={string.format('national-parks-v1|%d|%d|%d|%d',pid,turn,width,height)}
local size=#lines[1]
for index=0,count-1 do
    local revealed=visibility:IsRevealed(index)
    assert(type(revealed)=='boolean','invalid national park reveal state')
    if revealed then
        local plot=assert(Map.GetPlotByIndex(index))
        local isPark=plot:IsNationalPark()
        assert(type(isPark)=='boolean','invalid native park flag')
        if isPark then
            local name=plot:GetNationalParkName()
            assert(type(name)=='string' and #name<=maxName and not string.find(name,'\0',1,true),
                'invalid native national park label')
            local encoded=string.gsub(name,'.',function(c) return string.format('%02x',string.byte(c)) end)
            local line=string.format('%d|%s',index,encoded)
            size=size+1+#line
            assert(size<=capacity,'national park readback limit')
            lines[#lines+1]=line
        end
    end
end
context()
return table.concat(lines,'\n')
'''


def parse(raw, observation):
    if type(raw) is not bytes or len(raw) > CAPACITY:
        raise ValueError('Unbounded national park frame')
    player_id, turn, width, height = (observation[key] for key in ('player_id', 'turn', 'width', 'height'))
    header, *lines = raw.decode('ascii').split('\n')
    if header != f'national-parks-v1|{player_id}|{turn}|{width}|{height}':
        raise ValueError('Foreign national park frame')
    visible = {plot['index'] for plot in observation['plots'] if plot['visible'] is True}
    rows = []
    for line in lines:
        number, token = line.split('|')
        index = int(number)
        label = bytes.fromhex(token)
        if number != str(index) or label.hex() != token:
            raise ValueError('Invalid national park frame row')
        rows.append(dict(plot_id=index, name=label.decode('utf-8') if label else None,
                         visible=index in visible))
    value = dict(schema=contract.SCHEMA, player_id=player_id, turn=turn, width=width, height=height, plots=rows)
    return contract.validate(value, player_id, turn, observation=observation)


def read(saved, observation):
    saved._check_query()
    if expansion_city_growth._owner(saved) != saved._expansion_national_parks:
        raise ValueError('National park Lua lifetime changed')
    prefix = saved.prefix
    payload = build_source(observation['player_id'], observation['turn'])
    raw = prefix.runtime.evaluate_text(prefix.ui_child, payload, b'@expansion_national_parks', capacity=CAPACITY + 1)
    return parse(raw, observation)
