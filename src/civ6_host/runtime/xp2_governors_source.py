"""Selected XP2/BBG governor bindings, with strict native owner admission.

Detailed disassemblies remain private source evidence. Only compact, exact byte
guards are parsed into the live process. Unknown request and event services keep
their existing refusal paths; these guards alone establish no gameplay effect.
"""
from functools import lru_cache
from hashlib import sha256
from pathlib import Path

from .configuration_profiles import XP2_CORE_SHA256, _source as pinned_source
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('work/bbg751-governors/runtime-source-v1.json', 'b4d670e82493a1c46d862780ee15fd355b09422ec6d4fbb8554ca050d835f7ea')
REQUEST_SOURCE = ('work/bbg751-governors/source/source-governors-query-request-v2.json', '9f68c18c455c5fd08ca51fe60bd055fa4894f2b1e2733e7dcff23f3f0d643e94')
UI_SOURCE = ('work/bbg751-governors/ui-source-v1.json', '45a3ceadf331b76421d99c6570192d3f6741a241f0763f3ee7b50c445906995e')
_REGISTRARS = {
    'Player.GetGovernors': 0x712840,
    **{'Governors.'+name: 0x70fb90 for name in (
        'GetGovernorPoints', 'GetGovernorPointsSpent', 'GetGovernorList',
        'CanPromoteGovernor', 'CanAssignGovernor', 'HasGovernor', 'GetTurnsToEstablish',
        'CanAppoint', 'CanEverAppointGovernor', 'CanEarnPromotion',
        'HasTitleBeenConsidered', 'SetTitleConsidered')},
    **{'Governor.'+name: 0x70ef50 for name in (
        'GetType', 'GetAssignedCity', 'IsEstablished', 'GetTurnsOnSite',
        'GetTurnsToEstablish', 'GetNeutralizedTurns', 'IsGovernCityState', 'HasPromotion')},
    'Governor.CanAssignToMajorCiv': 0x7415d0,
}
_CONSTANTS = {
    'APPOINT_GOVERNOR': 0xa68659ab, 'ASSIGN_GOVERNOR': 0xf97c278b,
    'PROMOTE_GOVERNOR': 0x7d3da99d, 'PARAM_GOVERNOR_TYPE': 0xaf5e1625,
    'PARAM_GOVERNOR_PROMOTION_TYPE': 0x6d4bd4ea,
    'PARAM_PLAYER_ONE': 0x0483191c, 'PARAM_CITY_DEST': 0xe5f2cf9b,
}


def source():
    if any(reference[1] is None for reference in (SOURCE, REQUEST_SOURCE, UI_SOURCE)):
        raise RuntimeError('Governor native source admission is not yet complete')
    value = pinned_source(SOURCE)
    if (value['schema'] != 'civ6-host.xp2-governors-runtime-source.v1'
            or value['image']['sha256'] != XP2_CORE_SHA256
            or set(value['bindings']) != set(_REGISTRARS)
            or value['native_execution'] is not False
            or value['complete_apply_cache_lifecycle_proven'] is not False):
        raise ValueError('Governor source identity or scope differs')
    for name, registrar in _REGISTRARS.items():
        row = value['bindings'][name]
        if (row['name'] != name.split('.')[1] or row['registrar_rva'] != registrar
                or row['helper_rva'] != 0xdab0):
            raise ValueError('Governor Lua method role differs: '+name)
    for name, expected in _CONSTANTS.items():
        if value['constants'][name]['unsigned32'] != expected:
            raise ValueError('Governor native operation or parameter identity differs: '+name)
    if (value['parents']['request']['path'], value['parents']['request']['sha256']) != REQUEST_SOURCE:
        raise ValueError('Governor request source parent differs')
    if (value['parents']['ui']['path'], value['parents']['ui']['sha256']) != UI_SOURCE:
        raise ValueError('Governor selected UI source parent differs')
    return value


def _file(reference):
    path = resolve_path(Path(reference['path']) if Path(reference['path']).is_absolute()
                        else resource_root()/reference['path']).resolve()
    if sha256(path.read_bytes()).hexdigest() != reference['sha256']:
        raise ValueError('Governor source dependency changed: '+str(path))
    return path


def source_dependencies(*, execution_image=None):
    from civ6_host.contracts import governors
    from . import xp2_governors, xp2_governors_query
    value, ui = source(), pinned_source(UI_SOURCE)
    image = value['image']
    rows = [dict(path=SOURCE[0], sha256=SOURCE[1]), value['generator'],
            *value['parents'].values(), *ui['source_files'], ui['profile']['gameplay_database'],
            ui['profile']['bbg_modinfo'],
            dict(path=ui['official_activation']['expansion2_modinfo'],
                 sha256=ui['official_activation']['expansion2_modinfo_sha256'])]
    result = {str(_file(row)): row['sha256'] for row in rows}
    if execution_image is None:
        result[str(_file(image))] = image['sha256']
    else:
        from .execution_images import runtime_source_pins
        image_path = resolve_path(Path(image['path'])).resolve()
        selected_path = Path(execution_image.path).resolve()
        if (image['sha256'] != execution_image.reference_core_sha256
                or image_path != selected_path):
            raise ValueError('Governor source image does not match the selected execution/reference pair')
        result.update(runtime_source_pins(
            {str(selected_path): image['sha256']}, execution_image=execution_image))
    for module in (governors, xp2_governors, xp2_governors_query):
        path = Path(module.__file__).resolve()
        result[str(path)] = sha256(path.read_bytes()).hexdigest()
    path = Path(__file__).resolve()
    result[str(path)] = sha256(path.read_bytes()).hexdigest()
    return result


@lru_cache(maxsize=1)
def support_source():
    source()
    ui = pinned_source(UI_SOURCE)
    matches = [row for row in ui['source_files'] if row['name'] == 'GovernorSupport.lua']
    if len(matches) != 1:
        raise ValueError('Selected official GovernorSupport module is ambiguous')
    path = _file(matches[0])
    return path.read_bytes()


def operation_parameters(action):
    from civ6_host.contracts.governors import validate_action
    validate_action(action)
    if action['kind'] == 'consider_governor_titles':
        raise ValueError('Title consideration has no native player-operation request')
    values = source()['constants']
    ids = {key: row['unsigned32'] for key, row in values.items()}
    parameters = {ids['PARAM_GOVERNOR_TYPE']: action['governor_index']}
    kind = action['kind']
    if kind == 'appoint_governor':
        operation = ids['APPOINT_GOVERNOR']
    elif kind == 'promote_governor':
        operation = ids['PROMOTE_GOVERNOR']
        parameters[ids['PARAM_GOVERNOR_PROMOTION_TYPE']] = action['promotion_index']
    elif kind == 'assign_governor':
        operation = ids['ASSIGN_GOVERNOR']
        parameters[ids['PARAM_PLAYER_ONE']] = action['city_owner']
        parameters[ids['PARAM_CITY_DEST']] = action['city_id']
    else:
        raise ValueError('Title consideration has no native player-operation request')
    return operation, parameters


def bind_owner(saved, *, active):
    from . import xp2_bbg_inputs
    if active:
        saved._check_active()
    else:
        saved._check_query()
    if (getattr(saved, 'governors_diagnostic', False) is not True
            or not xp2_bbg_inputs.is_reference(saved.inputs.official_bundle)):
        raise ValueError('Governors require the explicit exact BBG source profile')
    b, p = saved.backend, saved.prefix
    core, base = b.core, b.core._handle
    if b.load_abi.core_sha256 != XP2_CORE_SHA256 or type(base) is not int or base <= 0:
        raise ValueError('Governors require the selected live XP2 engine')
    lifetime = (core, p)
    if getattr(saved, '_xp2_governor_lifetime', None) == lifetime:
        return
    value = source()
    for block in value['blocks']:
        raw = bytes.fromhex(block['raw_hex'])
        if len(raw) != block['length'] or b.runtime.read(base+block['rva'], len(raw)) != raw:
            raise ValueError('Live governor callback or registrar body differs')
    for row in value['bindings'].values():
        raw = row['name'].encode('ascii')+b'\0'
        if b.runtime.read(base+row['name_rva'], len(raw)) != raw:
            raise ValueError('Live governor Lua method name differs')
    saved._xp2_governor_lifetime = lifetime
