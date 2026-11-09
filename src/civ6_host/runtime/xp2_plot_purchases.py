"""Bind ordinary tile, unit and building purchases to the exact XP2 route."""

from pathlib import Path
import struct

from .configuration_profiles import XP2_CORE_SHA256
from .native import native_district_completion as district
from .native import native_plot_purchases as plots
from .native import native_saved_purchases as purchases
from .native.native_source_cache import load_pinned_json
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('work/host-extensions/xp2-plot-purchase-source.json',
          'adafe0a6a1cb095aef64ba2d14b197f8c31d14a594a626f354cad331e202a77e')
CITY_SOURCE = ('work/host-extensions/xp2-city-purchase-source.json',
               'e597f80555b658a93e28c6d1c5ea904b91109a64e76fc8a0ce729e055422a65f')


def _source():
    path = resolve_path(resource_root() / SOURCE[0])
    proof = load_pinned_json(path, SOURCE[1])
    if (proof['schema'] != 'civ6-host.xp2-plot-purchase-source.v1'
            or proof['image']['sha256'] != XP2_CORE_SHA256
            or proof['parameter_value'] != plots.verify_source()['contract']['parameter_value']
            or proof['parsed_purchase_mode'] != 4):
        raise ValueError('XP2 plot purchase source identity changed')
    return path, proof


def _city_source():
    path = resolve_path(resource_root() / CITY_SOURCE[0])
    proof = load_pinned_json(path, CITY_SOURCE[1])
    if (proof['schema'] != 'civ6-host.xp2-city-purchase-source.v1'
            or proof['native_execution'] is not False
            or proof['image']['sha256'] != XP2_CORE_SHA256
            or proof['parent']['sha256'] != SOURCE[1]):
        raise ValueError('XP2 city purchase source identity changed')
    return path, proof


def source_dependencies(*, execution_image=None):
    path, proof = _source()
    city_path, city_proof = _city_source()
    refs = {
        path: SOURCE[1],
        city_path: CITY_SOURCE[1],
        plots.ROOT / plots.SOURCE_PATH: plots.SOURCE_SHA256,
        purchases.ROOT / 'work/purchases931/source.json': purchases.SOURCE_SHA,
        district.ROOT / 'evidence/native-district-completion' / (district.PROOF_SHA256 + '.json'):
            district.PROOF_SHA256,
    }
    refs.update({Path(row['path']): row['sha256'] for row in (*proof['ui_sources'], *city_proof['official_ui'])})
    pins = {str(resolve_path(path).resolve()): digest for path, digest in refs.items()}
    from .runtime_source_dependencies import materialize_runtime_source_pins
    return materialize_runtime_source_pins(pins, execution_image=execution_image)


def _bind(saved, *, active):
    if active:
        saved._check_active()
    else:
        saved._check_query()
    owner = saved.backend
    core = owner.core
    base = core._handle
    if owner.load_abi.core_sha256 != XP2_CORE_SHA256 or type(base) is not int or base <= 0:
        raise ValueError('Plot purchase requires the live XP2 owner')
    lifetime = (core, saved.prefix)
    if getattr(saved, '_xp2_plot_purchase_lifetime', None) == lifetime:
        return
    read = owner.runtime.read
    _, proof = _source()
    _, city_proof = _city_source()
    for source in (proof, city_proof):
        for body in source['bodies'].values():
            for fragment in body['fragments']:
                expected = bytes.fromhex(fragment['raw_hex'])
                if read(base + int(fragment['start_rva'], 16), len(expected)) != expected:
                    raise ValueError('Live XP2 purchase body differs')
        for key, binding in source['bindings'].items():
            registration = bytes.fromhex(binding['bytes_hex'])
            literal = binding.get('name', key).encode('ascii') + b'\0'
            if (read(base + binding['registration_rva'], len(registration)) != registration
                    or read(base + binding['name_rva'], len(literal)) != literal):
                raise ValueError('Live XP2 purchase registration differs')
    for table, slot, target in proof['tables'].values():
        if read(base + table + slot, 8) != struct.pack('<Q', base + target):
            raise ValueError('Live XP2 plot purchase vtable slot differs')
    saved._xp2_plot_purchase_lifetime = lifetime


def catalogue(saved, observation, *, allow_faith=False):
    if type(allow_faith) is not bool:
        raise ValueError('Explicit faith purchase catalogue flag required')
    _bind(saved, active=False)
    prefix = saved.prefix
    turn, player_id = observation['turn'], observation['player_id']
    plot_rows, city_rows = [], []
    for city in sorted(observation['cities'], key=lambda row: row['id']):
        plot_rows.append(plots.catalog(prefix, city['id'], turn, player_id=player_id))
        quote = purchases.catalog(prefix, city['id'], turn, player_id=player_id)
        if not allow_faith:
            quote['offers'] = [row for row in quote['offers'] if row['action']['currency'] == 'YIELD_GOLD']
        city_rows.append(quote)
    return plot_rows, city_rows


def apply(saved, action, observation, *, allow_faith=False):
    _bind(saved, active=True)
    from civ6_host.contracts.plot_purchases import validate_purchase_action
    validate_purchase_action(action, allow_faith=allow_faith)
    provider = plots if 'plot_id' in action else purchases
    return provider.apply(saved, saved.prefix, action, observation['turn'], observation,
                          player_id=observation['player_id'])
