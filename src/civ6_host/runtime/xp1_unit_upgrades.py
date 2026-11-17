"""Native unit upgrades for the installed stock Rise and Fall ruleset."""

from hashlib import sha256
from pathlib import Path
from struct import pack

from civ6_host.contracts import unit_upgrades
from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE
from .native import native_saved_unit_upgrade as upgrades
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


SOURCE = ('work/x1trade/xp1-unit-upgrade-source.json',
          'f8934e86c684c02cbcf13d14dca78aa7989c7e608d06a8bbb91f276f16571d52')
_ARCHIVE = 0x493830af
_REGISTRY_SLOT = 16
_DEFAULT_DESTINATION = 0xffffd8f1


def supports(reference, image):
    return reference == REFERENCE and image is _XP1_PROFILE


def verify_source():
    proof = _source(SOURCE)
    image, route, packet = proof['image'], proof['route'], proof['packet']
    constants = dict(entity_type=1, command_slot=_REGISTRY_SLOT, auxiliary_flags=0,
                     parameter_type=1, default_destination_x=_DEFAULT_DESTINATION,
                     default_destination_y=_DEFAULT_DESTINATION, ui_modifiers=0)
    if (proof['schema'] != 'civ6-host.xp1-unit-upgrade.static.v1'
            or proof['native_execution'] is not False
            or proof['process_memory_read'] is not False
            or proof['gameplay_rules_reimplemented'] is not False
            or (image['sha256'], image['reference_core_sha256']) !=
               (_XP1_PROFILE.image_sha256, XP1_CORE_SHA256)
            or (route['command'], route['result']) != (unit_upgrades.COMMAND, 0x3c0dec5b)
            or route['resources']['native_upgrade_stockpile_quote'] is not False
            or route['resources']['native_upgrade_stockpile_debit'] is not False
            or (packet['message_type'], packet['format'], packet['length']) != (_ARCHIVE, '<IHH7I', 36)
            or packet['expected_constants'] != constants):
        raise ValueError('Rise and Fall upgrade source differs')
    return proof


def source_dependencies(image):
    if image is not _XP1_PROFILE:
        raise ValueError('Upgrade sources require the installed Rise and Fall image')
    proof = verify_source()
    base = upgrades.verify_source()
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), dict(path=REFERENCE[0], sha256=REFERENCE[1]),
            proof['image'], proof['executable'], base['official_ui'],
            proof['parents']['shared_upgrade'], proof['ui_sources']['xp1_unit_panel']]
    pins = {}
    for row in refs:
        path = Path(row['path'])
        path = resolve_path(path if path.is_absolute() else resource_root() / path)
        if pins.setdefault(str(path.resolve()), row['sha256']) != row['sha256']:
            raise ValueError('Conflicting Rise and Fall upgrade source pins')
    verify_pinned_files(pins)
    return pins


def _bind(saved, *, active):
    if active:
        saved._check_active()
    else:
        saved._check_query()
    backend = saved.backend
    core = backend.core
    if (getattr(saved, 'xp1_unit_upgrades', False) is not True
            or backend.load_abi.core_sha256 != XP1_CORE_SHA256
            or not supports(backend.captured_bundle.reference, getattr(core, '_civ6_host_execution_image', None))):
        raise ValueError('Upgrade requires the exact Rise and Fall saved owner')
    lifetime = (core, saved.prefix)
    if getattr(saved, '_xp1_upgrade_lifetime', None) == lifetime:
        return
    proof = verify_source()
    base, read = core._handle, backend.runtime.read
    for span in (*proof['core_bodies'], *proof['enums'].values()):
        raw = bytes.fromhex(span['raw_hex'])
        if (not 0 < len(raw) <= 4096 or len(raw) != span['bytes']
                or sha256(raw).hexdigest() != span['sha256'] or read(base + span['rva'], len(raw)) != raw):
            raise ValueError('Live Rise and Fall upgrade code differs: '+str(span['rva']))
    for binding in proof['bindings'].values():
        raw = bytes.fromhex(binding['bytes_hex'])
        name = binding['name'].encode('ascii') + b'\0'
        if (sha256(raw).hexdigest() != binding['registration_sha256']
                or read(base + binding['registration_rva'], len(raw)) != raw
                or read(base + binding['name_rva'], len(name)) != name):
            raise ValueError('Live Rise and Fall upgrade registration differs: '+binding['name'])
    for table in proof['tables'].values():
        for slot in table['slots']:
            pointer = base + slot['target_rva']
            if read(base + table['rva'] + slot['offset'], 8) != pointer.to_bytes(8, 'little'):
                raise ValueError('Live Rise and Fall upgrade vtable differs')
    saved._xp1_upgrade_lifetime = lifetime


def catalogue(saved,observation):
    _bind(saved,active=False)
    pid,turn = observation['player_id'],observation['turn']
    base = upgrades.catalog(saved.prefix,turn,player_id=pid)
    result = dict(player_id=pid,turn=turn,offers=[
        dict(row,resource_type=None,resource_cost=None) for row in base['offers']])
    unit_upgrades.validate_catalogue(result,pid,turn,observation=observation)
    saved.explicit_unit_upgrades = base
    return result


def validate_archive(payload,actor,action):
    upgrades.validate_action(action)
    if (action['hash']!=unit_upgrades.COMMAND or type(payload) is not bytes
            or type(actor) is not int or not 0<=actor<=63):
        raise ValueError('Invalid Rise and Fall upgrade archive or actor')
    expected = pack('<IHH7I', _ARCHIVE, actor, 1, action['unit_id'], _REGISTRY_SLOT, 0, 1,
                    _DEFAULT_DESTINATION, _DEFAULT_DESTINATION, 0)
    if payload!=expected:
        raise ValueError('Rise and Fall upgrade archive differs from the selected unit')
    return sha256(payload).hexdigest()


def apply(saved,action,observation):
    _bind(saved,active=True)
    unit_upgrades.validate_action(action)
    if action['resource_type'] is not None:
        raise ValueError('Rise and Fall upgrade does not accept a stockpile quote')
    pid,turn = observation['player_id'],observation['turn']
    base = {key:action[key] for key in upgrades.FIELDS}
    digests=[]
    def verify_archive(payload, actor, selected):
        digests.append(validate_archive(payload,actor,selected))

    after = upgrades.apply(saved,saved.prefix,base,turn,observation,player_id=pid,
                           archive_validator=verify_archive)
    old_ids = {row['id'] for row in observation['units']}
    old = next(row for row in observation['units'] if row['id'] == action['unit_id'])
    replacement = [row for row in after['units']
                   if row['id'] not in old_ids and row['owner']==pid and row['type']==action['target_type']
                   and (row['x'], row['y']) == (old['x'], old['y'])]
    if len(replacement)!=1 or any(row['id']==action['unit_id'] for row in after['units']):
        raise RuntimeError('Rise and Fall upgrade did not replace the requested unit')
    debit = observation['economy']['gold']-after['economy']['gold']
    if debit!=action['cost']:
        raise RuntimeError('Rise and Fall upgrade gold debit differs from the native quote')
    digest, = digests
    receipt = dict(action=action,native_unit_replaced=True,exact_treasury_debit_verified=True,
                   replacement=replacement[0],gold_debit=debit,native_archive_sha256=digest)
    saved.emit('xp1_explicit_unit_upgrade_verified',receipt=receipt)
    return dict(observation=after,receipt=receipt)
