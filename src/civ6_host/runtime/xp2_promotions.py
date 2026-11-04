"""Bind the shared native promotion adapter to the exact XP2 implementation."""
from pathlib import Path
import struct

from civ6_host.contracts.unit_promotions import validate_catalogue
from .configuration_profiles import XP2_CORE_SHA256
from .native import native_saved_promotions as promotions
from .native.native_source_cache import load_pinned_json
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('work/host-extensions/xp2-promotion-source.json',
          'bc29a267edeadbcf57e23b4c971e0ec0b93cb00f4d7126c598997823ce4fec38')


def _source():
    path = resolve_path(resource_root() / SOURCE[0])
    proof = load_pinned_json(path, SOURCE[1])
    if (proof['schema'] != 'civ6-host.xp2-unit-promotion-source.v1'
            or proof['image']['sha256'] != XP2_CORE_SHA256 or proof['native_execution'] is not False
            or proof['command'] != 0xb4edd43f or proof['promotions_result'] != 0x315247e7):
        raise ValueError('XP2 promotion source identity differs')
    return path, proof


def source_dependencies():
    path, proof = _source()
    promotions.verify_source()
    return {str(path.resolve()): SOURCE[1],
            str(resolve_path(promotions.PROOF_PATH).resolve()): promotions.PROOF_SHA,
            **{str(resolve_path(Path(row['path'])).resolve()): row['sha256']
               for row in proof['official_ui']}}


def _bind(saved, *, active):
    if active:
        saved._check_active()
    else:
        saved._check_query()
    owner = saved.backend
    core = owner.core
    base = core._handle
    if owner.load_abi.core_sha256 != XP2_CORE_SHA256 or type(base) is not int or base <= 0:
        raise ValueError('Unit promotions require the live XP2 owner')
    lifetime = (core, saved.prefix)
    if getattr(saved, '_xp2_promotion_lifetime', None) == lifetime:
        return
    _, proof = _source()
    read = owner.runtime.read
    for body in proof['functions'].values():
        for fragment in body['fragments']:
            expected = bytes.fromhex(fragment['raw_hex'])
            if read(base + int(fragment['start_rva'], 16), len(expected)) != expected:
                raise ValueError('Live XP2 promotion body differs')
    for name, binding in proof['bindings'].items():
        expected = bytes.fromhex(binding['bytes_hex'])
        literal = name.encode('ascii') + b'\0'
        if (read(base + binding['registration_rva'], len(expected)) != expected
                or read(base + binding['name_rva'], len(literal)) != literal):
            raise ValueError('Live XP2 promotion registration differs')
    table = proof['command_table']
    for offset, rva in table['slots'].items():
        if read(base + table['rva'] + int(offset), 8) != struct.pack('<Q', base + rva):
            raise ValueError('Live XP2 promotion command vtable differs')
    saved._xp2_promotion_lifetime = lifetime


def catalogue(saved, observation):
    _bind(saved, active=False)
    player_id, turn = observation['player_id'], observation['turn']
    raw = promotions.catalog(saved.prefix, turn, player_id=player_id)
    # The XP2 binding emits integer XP. Movement and damage are already in the
    # own-unit observation, so this catalogue omits the private adapter tokens.
    value = dict(player_id=player_id, turn=turn, offers=raw['offers'], units=[
        dict(unit_id=unit['unit_id'], experience_points=int(unit['experience_token']),
             promotions=unit['promotions']) for unit in raw['units']])
    validate_catalogue(value, player_id, turn, observation=observation)
    saved.explicit_promotions = raw
    return value


def apply(saved, action, observation):
    _bind(saved, active=True)
    return promotions.apply(saved, saved.prefix, action, observation['turn'], observation,
                            player_id=observation['player_id'])
