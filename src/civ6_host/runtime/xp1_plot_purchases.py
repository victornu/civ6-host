"""Stock Rise and Fall tile quotes and purchase through the native city command."""

from hashlib import sha256
from pathlib import Path
from struct import unpack

from civ6_host.contracts.plot_purchases import validate_action
from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE
from .native import native_district_completion as district
from .native import native_plot_purchases as plots
from .native import native_saved_purchases as purchases
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


SOURCE = ('work/x1trade/xp1-plot-purchase-source.json',
          'a23e5b7ba57b0f602f520342a3f182cad4f1d8f9030b13d2a267f2eeb91f8422')
OVERRIDES = ('work/x1trade/xp1-plot-purchase-overrides-source.json',
             '1e0964dd4270cab2bee0316dac90aed668a2e05e15335c9999dcc0f6dc5b9e87')
_MESSAGE_TYPE = 0x346b0a13
_CALLBACKS = {
    'CityManager.CanStartCommand': 0x5ac950,
    'CityManager.GetCommandTargets': 0x5acfe0,
    'CityManager.RequestCommand': 0x5ad420,
    'City.GetGold': 0x5a6430,
    'CityGold.GetPlotPurchaseCost': 0x5aacf0,
}


def supports(reference, image):
    return reference == REFERENCE and image is _XP1_PROFILE


def verify_source():
    proof = _source(SOURCE)
    image, route, packet = (proof[k] for k in ('image', 'route', 'packet'))
    if (proof['schema'] != 'civ6-host.xp1-plot-purchase.static.v1'
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or proof['native_rules_reimplemented'] is not False
            or (image['profile_id'], image['sha256'], image['reference_core_sha256']) !=
               (_XP1_PROFILE.id, _XP1_PROFILE.image_sha256, XP1_CORE_SHA256)
            or (route['purchase_command_hash'], route['plot_flag_value'], route['parsed_purchase_mode']) !=
               (0x58dbb288, -780910418, 4)
            or route['plot_flag_value_is_not_read'] is not True
            or (packet['message_type'], packet['format'], packet['length'], packet['parameter_type_literal']) !=
               (_MESSAGE_TYPE, '<IHH9I', 44, 1)
            or any(proof['bindings'][name]['callback_rva'] != value for name,value in _CALLBACKS.items())):
        raise ValueError('Rise and Fall plot purchase source differs')
    return proof


def verify_overrides():
    proof = _source(OVERRIDES)
    parent, packet = proof['parent'], proof['packet']
    if (proof['schema'] != 'civ6-host.xp1-plot-purchase-overrides.static.v1'
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or (parent['path'], parent['sha256']) != SOURCE
            or proof['image']['sha256'] != _XP1_PROFILE.image_sha256
            or proof['registration']['runtime_command_slot'] != 0
            or (packet['format'], packet['byte_length'], packet['parameter_type']) != ('<IHH9I', 44, 1)
            or proof['tables']['xp1_purchase_command']['rva'] != 0x8d7000
            or proof['tables']['xp1_purchase_parameters']['rva'] != 0x8d6fd0):
        raise ValueError('Rise and Fall plot purchase override source differs')
    return proof


def source_dependencies(image):
    if image is not _XP1_PROFILE:
        raise ValueError('Plot purchase sources require the installed Rise and Fall image')
    proof = verify_source()
    override = verify_overrides()
    plots.verify_source()
    purchases.verify_source()
    district.verify_source()
    refs = [dict(path=SOURCE[0],sha256=SOURCE[1]), dict(path=REFERENCE[0],sha256=REFERENCE[1]),
            dict(path=OVERRIDES[0],sha256=OVERRIDES[1]),
            proof['image'], proof['executable'], *proof['ui_sources'].values()]
    refs.extend(row['trace'] for row in override['native_xp1_common_header_witnesses'].values())
    refs.extend(row.get('artifact',row.get('trace',row)) for row in proof['witnesses'].values())
    refs.extend((
        dict(path=plots.ROOT / plots.SOURCE_PATH,sha256=plots.SOURCE_SHA256),
        dict(path=purchases.ROOT / 'work/purchases931/source.json',sha256=purchases.SOURCE_SHA),
        dict(path=district.ROOT / 'evidence/native-district-completion' / (district.PROOF_SHA256+'.json'),
             sha256=district.PROOF_SHA256),
    ))
    pins = {}
    for row in refs:
        path = Path(row['path'])
        path = resolve_path(path if path.is_absolute() else resource_root() / path)
        if pins.setdefault(str(path.resolve()),row['sha256']) != row['sha256']:
            raise ValueError('Conflicting Rise and Fall plot purchase pins')
    verify_pinned_files(pins)
    return pins


def _bind(saved, *, active):
    if active:
        saved._check_active()
    else:
        saved._check_query()
    backend = saved.backend
    core = backend.core
    if (getattr(saved, 'xp1_plot_purchase', False) is not True
            or backend.load_abi.core_sha256 != XP1_CORE_SHA256
            or not supports(backend.captured_bundle.reference,getattr(core,'_civ6_host_execution_image',None))):
        raise ValueError('Plot purchase requires the exact Rise and Fall owner')
    lifetime = (core,saved.prefix)
    if getattr(saved,'_xp1_plot_purchase_lifetime',None) == lifetime:
        return
    proof = verify_source()
    override = verify_overrides()
    base = core._handle
    read = backend.runtime.read
    for row in (*proof['core_bodies'], *override['core_bodies']):
        raw = bytes.fromhex(row['raw_hex'])
        if (len(raw) != row['bytes'] or sha256(raw).hexdigest() != row['sha256']
                or read(base+row['rva'],len(raw)) != raw):
            raise ValueError('Live Rise and Fall purchase body differs: ' + row['name'])
    for row in proof['bindings'].values():
        register = bytes.fromhex(row['bytes_hex'])
        name = row['name'].encode('ascii')+b'\0'
        if (read(base+row['registration_rva'],len(register)) != register
                or read(base+row['name_rva'],len(name)) != name):
            raise ValueError('Live Rise and Fall purchase registration differs')
    for table in (*proof['tables'].values(), *override['tables'].values()):
        for slot in table['slots']:
            pointer = base + slot['target_rva']
            if read(base+table['rva']+slot['offset'],8) != pointer.to_bytes(8,'little'):
                raise ValueError('Live Rise and Fall purchase vtable differs')
    saved._xp1_plot_purchase_lifetime = lifetime


def catalogue(saved, observation):
    _bind(saved,active=False)
    turn, actor = observation['turn'],observation['player_id']
    return [plots.catalog(saved.prefix,city['id'],turn,player_id=actor,core_sha256=XP1_CORE_SHA256)
            for city in sorted(observation['cities'],key=lambda row:row['id'])]


def validate_archive(payload, actor, action):
    validate_action(action)
    if type(actor) is not int or not 0 <= actor <= 63 or type(payload) is not bytes or len(payload) != 44:
        raise ValueError('Invalid Rise and Fall plot purchase archive size or actor')
    # Only the retained ordinary purchase route is admitted. The first XP1
    # command must independently confirm the registry and auxiliary fields.
    fields = unpack('<IHH9I',payload)
    if fields != (_MESSAGE_TYPE,actor,2,action['city_id'],0,0,1,0,4,0xffffffff,action['x'],action['y']):
        raise ValueError('Rise and Fall plot purchase archive differs from the admitted city command')
    return sha256(payload).hexdigest()


def apply(saved, action, observation):
    _bind(saved,active=True)
    validate_action(action)
    return plots.apply(saved,saved.prefix,action,observation['turn'],observation,
        player_id=observation['player_id'],core_sha256=XP1_CORE_SHA256,
        archive_validator=validate_archive)
