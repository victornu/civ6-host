"""Stock Rise and Fall unit and building purchases via CityManager."""

from hashlib import sha256
from pathlib import Path
from struct import pack

from civ6_host.contracts.plot_purchases import validate_city_action
from . import xp1_plot_purchases as plots
from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE
from .native import native_saved_purchases as purchases
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('work/x1trade/xp1-city-gold-purchases-source.json',
          '3cc4aab7e4de494f7632608ed44cc99d1ff5b2aedf6c0cca59257ffc79889517')
FAITH_SOURCE = ('work/x1trade/xp1-faith-purchase-source.json',
                '4e1f758a69da2cd9123226474218899cbc99fe09f42ec2b1da5bb7190caeb58e')
_CURRENCY_INDEX = {'YIELD_GOLD': 2, 'YIELD_FAITH': 5}
_CALLBACKS = {
    'CityGold.GetPurchaseCost': 0x5aada0, 'City.GetBuildings': 0x5a62a0,
    'CityBuildings.HasBuilding': 0x5a9400, 'PlayerTreasury.CanAfford': 0x5d21c0,
}
_FAITH_CALLBACKS = {
    'CityGold.IsUnitFaithPurchaseEnabled': 0x5aaf10,
    'CityGold.IsBuildingFaithPurchaseEnabled': 0x5aaea0,
    'Player.GetReligion': 0x5c5950,
    'PlayerReligion.CanAfford': 0x5ceea0,
}


def verify_source():
    proof = _source(SOURCE)
    packet = proof['packet']
    if (proof['schema'] != 'civ6-host.xp1-city-gold-purchases.static.v1'
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or proof['native_rules_reimplemented'] is not False
            or (proof['image']['profile_id'], proof['image']['sha256']) !=
               (_XP1_PROFILE.id, _XP1_PROFILE.image_sha256)
            or (proof['parents']['plot']['path'], proof['parents']['plot']['sha256']) != plots.SOURCE
            or (proof['parents']['overrides']['path'], proof['parents']['overrides']['sha256']) != plots.OVERRIDES
            or (packet['message_type'], packet['unit']['length'], packet['building']['length']) != (0x346b0a13, 52, 48)
            or (packet['unit']['mode'], packet['building']['mode'], packet['unit']['formation']) != (0, 1, 0xffffffff)
            or packet['required_constants'] != dict(city_type=2, command_slot=0, aux_flags=0, parameter_type=1,
                parameter_metadata=0, gold_yield_index=2, x=0xffffd8f1, y=0xffffd8f1)
            or any(proof['bindings'][name]['callback_rva'] != rva for name, rva in _CALLBACKS.items())):
        raise ValueError('Rise and Fall city purchase source differs')
    return proof


def verify_faith_source():
    proof = _source(FAITH_SOURCE)
    image, packet = proof['image'], proof['packet']
    gold = proof['parents']['city_gold']
    if (proof['schema'] != 'civ6-host.xp1-faith-purchase.static.v1'
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or proof['gameplay_rules_reimplemented'] is not False
            or (image['profile_id'], image['sha256'], image['reference_core_sha256']) !=
               (_XP1_PROFILE.id, _XP1_PROFILE.image_sha256, XP1_CORE_SHA256)
            or (gold['path'], gold['sha256']) != SOURCE
            or (packet['message_type'], packet['unit_length'], packet['building_length']) != (0x346b0a13, 52, 48)
            or (packet['unit_yield_offset'], packet['building_yield_offset']) != (40, 36)
            or packet['currency_indices'] != _CURRENCY_INDEX
            or proof['effects']['requires_observed_exact_debit'] is not True
            or {name: row['callback_rva'] for name, row in proof['bindings'].items()} != _FAITH_CALLBACKS):
        raise ValueError('Rise and Fall faith purchase source differs')
    return proof


def source_dependencies(image, *, allow_faith=False):
    if image is not _XP1_PROFILE:
        raise ValueError('City purchase sources require the installed Rise and Fall image')
    proof = verify_source()
    witnesses = proof['witnesses']
    rows = [dict(path=SOURCE[0], sha256=SOURCE[1]), proof['image'], proof['executable'],
            *proof['parents'].values(), *proof['ui_sources'].values(),
            witnesses['xp2_native_city_gold_receipt'], witnesses['xp1_native_plot_save_reload'],
            witnesses['xp1_captured_gameplay_db'], witnesses['checkpoint']['artifact'],
            *witnesses['xp1_existing_notification_traces']]
    rows.extend(row['trace'] for row in witnesses['xp2_archives_and_effects'].values())
    if allow_faith:
        faith = verify_faith_source()
        rows.extend([dict(path=FAITH_SOURCE[0], sha256=FAITH_SOURCE[1]), *faith['parents'].values(),
                     *faith['ui_sources'].values(), faith['captured_rules']['database']])
    pins = {}
    for row in rows:
        path = Path(row['path'])
        path = resolve_path(path if path.is_absolute() else resource_root() / path)
        if pins.setdefault(str(path.resolve()), row['sha256']) != row['sha256']:
            raise ValueError('Conflicting Rise and Fall city purchase pins')
    verify_pinned_files(pins)
    return pins


def _bind(saved, *, active):
    plots._bind(saved, active=active)
    if getattr(saved, 'xp1_city_purchase', False) is not True:
        raise ValueError('City item purchase requires the admitted Rise and Fall owner')
    backend, prefix = saved.backend, saved.prefix
    lifetime = (backend.core, prefix)
    if getattr(saved, '_xp1_city_purchase_lifetime', None) == lifetime:
        return
    base = backend.core._handle
    read = backend.runtime.read
    proofs = [verify_source()]
    if getattr(saved, 'xp1_faith_purchase', False):
        proofs.append(verify_faith_source())
    for proof in proofs:
        for row in proof['core_bodies']:
            raw = bytes.fromhex(row['raw_hex'])
            if (len(raw) != row['bytes'] or sha256(raw).hexdigest() != row['sha256']
                    or read(base + row['rva'], len(raw)) != raw):
                raise ValueError('Live Rise and Fall city purchase body differs: ' + row['name'])
        for row in proof['bindings'].values():
            registration = bytes.fromhex(row['bytes_hex'])
            name = row['name'].encode('ascii') + b'\0'
            if (read(base + row['registration_rva'], len(registration)) != registration
                    or read(base + row['name_rva'], len(name)) != name):
                raise ValueError('Live Rise and Fall city purchase registration differs: ' + row['name'])
    saved._xp1_city_purchase_lifetime = lifetime


def catalogue(saved, observation):
    _bind(saved, active=False)
    turn, actor = observation['turn'], observation['player_id']
    allow_faith = getattr(saved, 'xp1_faith_purchase', False) is True
    return [purchases.catalog(saved.prefix, city['id'], turn, player_id=actor, gold_only=not allow_faith)
            for city in sorted(observation['cities'], key=lambda row: row['id'])]


def validate_archive(payload, actor, action, *, allow_faith=False):
    validate_city_action(action, allow_faith=allow_faith)
    if type(actor) is not int or not 0 <= actor <= 63 or type(payload) is not bytes:
        raise ValueError('Invalid Rise and Fall city purchase archive or actor')
    head = pack('<IHH5I', 0x346b0a13, actor, 2, action['city_id'], 0, 0, 1, 0)
    index = action['index']
    currency = _CURRENCY_INDEX[action['currency']]
    tail = (pack('<IIiIii', 0, index, -1, currency, -9999, -9999) if action['category'] == 'unit'
            else pack('<IIIii', 1, index, currency, -9999, -9999))
    if payload != head + tail:
        raise ValueError('Rise and Fall city purchase archive differs from the selected item')
    return sha256(payload).hexdigest()


def apply(saved, action, observation):
    _bind(saved, active=True)
    allow_faith = getattr(saved, 'xp1_faith_purchase', False) is True
    validate_city_action(action, allow_faith=allow_faith)
    if action['currency'] == 'YIELD_FAITH':
        turn, pid = observation['turn'], observation['player_id']
        prefix = saved.prefix
        query = purchases.preamble(pid, action['city_id'], turn) + b"""
local gold = assert(GameInfo.Yields.YIELD_GOLD, 'gold index missing')
local faith = assert(GameInfo.Yields.YIELD_FAITH, 'faith index missing')
return n(gold.Index)..'|'..n(faith.Index)
"""
        if prefix.runtime.evaluate_text(prefix.ui_child, query, b'@xp1_purchase_yields', capacity=32) != b'2|5':
            raise ValueError('Live Rise and Fall purchase currency indices differ')
    def archive(payload, pid, selected):
        return validate_archive(payload, pid, selected, allow_faith=allow_faith)

    return purchases.apply(saved, saved.prefix, action, observation['turn'], observation,
        player_id=observation['player_id'], archive_validator=archive, allow_faith=allow_faith)
