"""Source-bound alert and automatic exploration on the shared unit-order route."""

from hashlib import sha256
from pathlib import Path
from struct import pack, unpack

from civ6_host.contracts.capability_unit_orders import EXTENDED_OPERATIONS
from .configuration_profiles import XP2_CORE_SHA256, _source
from .execution_images import _PROFILE
from .resource_resolution import resolve_path
from .paths import resource_root

SOURCE = ('evidence/host-xp2-extra-unit-orders-source.json',
          'f5e86992b728108656b2c5c3d0fadfac97a82f57aba01e6357e6067687cd880b')


def verify_source():
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-extra-unit-orders.source.v1'
            or proof['image']['sha256'] != _PROFILE.image_sha256
            or tuple(row['name'] for row in proof['operations']) != EXTENDED_OPERATIONS
            or proof['native_execution'] is not False
            or proof['contracts']['parameterless'] is not True
            or proof['contracts']['automatic_success'] is not False):
        raise ValueError('Extra unit-order source differs')
    return proof


def source_dependencies(reference, image):
    proof = verify_source()
    if image is not _PROFILE:
        raise ValueError('Extra unit orders require the installed Gathering Storm image')
    capture = next((row for row in proof['captures']
                    if (row['reference']['path'], row['reference']['sha256']) == reference), None)
    if capture is None:
        raise ValueError('Extra unit orders require the admitted stock or BBG capture')
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), proof['image'], proof['shared_source'],
            *proof['ui'], capture['reference'], capture['database']]
    pins = {}
    for row in refs:
        path = Path(row['path'])
        path = resolve_path(path if path.is_absolute() else resource_root()/path).resolve()
        if sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Extra unit-order input differs: '+str(path))
        pins[str(path)] = row['sha256']
    return pins


def bind(saved):
    from .expansion_city_growth import _owner

    lifetime = _owner(saved)
    core = lifetime[0]
    source_dependencies(lifetime[-1], getattr(core, '_civ6_host_execution_image', None))
    read = saved.backend.runtime.read
    for operation in verify_source()['operations']:
        for span in (*operation['constructor'], operation['table']):
            raw = read(core._handle + span['rva'], span['bytes'])
            if span is operation['table'] and type(raw) is bytes and len(raw) == span['bytes']:
                targets = unpack('<'+'Q'*(len(raw)//8), raw)
                if any(not 0 <= target-core._handle < 2**32 for target in targets):
                    raise ValueError('Extra unit-order table has a foreign native target')
                raw = pack('<'+'Q'*len(targets), *(target-core._handle+0x180000000 for target in targets))
            if type(raw) is not bytes or len(raw) != span['bytes'] or sha256(raw).hexdigest() != span['sha256']:
                raise ValueError('Live extra unit-order descriptor differs')
    saved._xp2_extra_unit_orders = lifetime


def enabled(saved):
    lifetime = getattr(saved, '_xp2_extra_unit_orders', None)
    if lifetime is None:
        return False
    from .expansion_city_growth import _owner

    if _owner(saved) != lifetime or saved.backend.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Extra unit orders lost their admitted lifetime')
    return True
