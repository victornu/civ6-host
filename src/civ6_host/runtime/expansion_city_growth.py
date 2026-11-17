"""Read the loyalty-aware official city growth panel on pinned LAN captures."""

from hashlib import sha256
from pathlib import Path

from civ6_host.contracts import city_growth as contract

from . import city_growth, xp1_saved_load, xp2_bbg_inputs, xp2_bundle_inputs
from .a0_family_source import verify_pinned_files
from .configuration_profiles import _source
from .core_script_services import check_bound
from .execution_images import _PROFILE, _XP1_PROFILE, identity
from .paths import resource_root
from .resource_resolution import resolve_path
from .saved_load_services import SavedLoadServices

SOURCE = ('evidence/host-expansion-city-growth-ui-source.json',
          '3e7fd08a140746b04911d37e0d7946fe8c0997282c2e035aec03e960c4dabbd5')
CAPTURES = {
    xp1_saved_load.REFERENCE: (_XP1_PROFILE, 'xp1'),
    xp2_bundle_inputs.REFERENCE: (_PROFILE, 'xp2'),
    xp2_bbg_inputs.REFERENCE: (_PROFILE, 'bbg'),
}


def _profile(reference, image):
    known = CAPTURES.get(reference)
    if known is None or known[0] is not image:
        raise ValueError('City growth requires an admitted expansion capture and image')
    proof = _source(SOURCE)
    selected = proof['engines'][image.id]
    if (proof['schema'] != 'civ6-host.expansion-city-growth-ui-source.v1'
            or selected['image'] != identity(image)
            or (proof['base_panel_source']['path'], proof['base_panel_source']['sha256']) != city_growth.SOURCE
            or proof['captures'][known[1]] != reference
            or proof['bbg_panel_replaced'] is not False):
        raise ValueError('Expansion city growth source differs')
    return proof, selected


def source_dependencies(reference, image):
    proof, selected = _profile(reference, image)
    root = resource_root()
    files = [selected['overrides'], *selected['other_ui']]
    if reference == xp2_bbg_inputs.REFERENCE:
        files.append(proof['bbg_modinfo'])
    pins = {**city_growth.source_files(), str(Path(image.path).resolve()): image.image_sha256}
    for name, digest in (SOURCE, reference, *((row['path'], row['sha256']) for row in files)):
        path = str(resolve_path(root / name).resolve(strict=True))
        if pins.setdefault(path, digest) != digest:
            raise ValueError('Conflicting expansion city growth source pin')
    verify_pinned_files(pins)
    return pins


def verify_bindings(selected, base, read):
    for name, binding in selected['bindings'].items():
        literal = name.encode('ascii') + b'\0'
        if read(base + binding['name_rva'], len(literal)) != literal:
            raise ValueError(f'Expansion city growth binding name differs: {name}')
        for key in ('registration', 'callback'):
            span = binding[key]
            raw = read(base + span['rva'], span['bytes'])
            if len(raw) != span['bytes'] or sha256(raw).hexdigest() != span['sha256']:
                raise ValueError(f'Expansion city growth {key} differs: {name}')


def _owner(saved):
    backend, prefix = saved.backend, saved.prefix
    core = backend.core
    if (type(prefix) is not SavedLoadServices or prefix.closed or prefix.quarantined
            or backend.prefix is not prefix or prefix.core is not core
            or prefix.context != backend.context):
        raise ValueError('City growth requires its live saved expansion owner')
    runtime = prefix.runtime
    lease = check_bound(runtime, backend.context, core)
    runtime.registry.validate(prefix.ui_child)
    return (core, prefix, runtime, prefix.ui_child, lease, backend.captured_bundle.reference)


def bind(saved):
    lifetime = _owner(saved)
    core = lifetime[0]
    _, selected = _profile(lifetime[-1], getattr(core, '_civ6_host_execution_image', None))
    verify_bindings(selected, core._handle, saved.backend.runtime.read)
    path = resolve_path(Path(selected['overrides']['path']))
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != selected['overrides']['sha256']:
        raise ValueError('Expansion city growth panel changed')
    saved._expansion_city_growth = (lifetime, raw.decode('utf-8-sig').replace('\r\n', '\n'))


def read(saved, observation, *, borrowed=False):
    if borrowed:
        from .xp1_session_view import _borrowed_xp2_reference
        _borrowed_xp2_reference(saved, observation['player_id'])
    else:
        saved._check_query()
    lifetime, panel = saved._expansion_city_growth
    if _owner(saved) != lifetime:
        raise ValueError('City growth Lua lifetime changed')
    pid, turn = observation['player_id'], observation['turn']
    prefix = saved.prefix
    raw = prefix.runtime.evaluate_text(prefix.ui_child, city_growth.source(pid, turn, expansion_panel=panel),
                                      b'@expansion_city_growth', capacity=city_growth.CAPACITY + 1)
    public, _ = city_growth.parse(raw, pid, turn, expansion=True)
    return contract.validate(public, pid, turn, observation=observation)
