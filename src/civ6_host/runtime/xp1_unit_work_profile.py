"""Source admission for the stock Rise and Fall UnitPanel terrain actions."""

from pathlib import Path

from .configuration_profiles import _source
from .execution_images import _XP1_PROFILE, identity
from .paths import resource_root
from .xp1_saved_load import REFERENCE

SOURCE = ('evidence/host-xp1-unit-work-panel-source.json',
          '2b4a7edb4a7375344eebc292b2ee315df05a77cc65d7c3451b30b72936045f3b')


def supports(reference, image):
    return reference == REFERENCE and image is _XP1_PROFILE


def _proof(image):
    if image is not _XP1_PROFILE:
        raise ValueError('Unit work requires the registered Rise and Fall execution image')
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp1-unit-work-panel.source.v1'
            or proof['engine'] != identity(image)
            or proof['native_execution'] is not False):
        raise ValueError('Rise and Fall UnitPanel source differs')
    return proof


def source_dependencies(image):
    proof = _proof(image)
    root = resource_root()
    game = Path(image.path).parents[4]
    return {
        str((root / SOURCE[0]).resolve()): SOURCE[1],
        str(Path(image.path).resolve()): image.image_sha256,
        **{str((root / entry['path']).resolve()): entry['sha256'] for entry in proof['upstream']},
        **{str((game / path).resolve()): digest for path, digest in proof['ui_sources'].items()},
    }


def verify_live(core, read):
    proof = _proof(getattr(core, '_civ6_host_execution_image', None))
    for name, row in proof['bindings'].items():
        expected = bytes.fromhex(row['raw_hex'])
        literal = name.rpartition('.')[2].encode('ascii') + b'\0'
        if (read(core._handle + row['rva'], len(expected)) != expected
                or read(core._handle + row['literal_rva'], len(literal)) != literal):
            raise ValueError('Rise and Fall UnitPanel binding differs: ' + name)


def bind(saved):
    core = saved.backend.core
    if not supports(saved.inputs.official_bundle, getattr(core, '_civ6_host_execution_image', None)):
        raise ValueError('Unit work requires the exact Rise and Fall bundle and engine')
    if saved.continuation.owner is not saved.backend:
        raise ValueError('Unit work requires its live Rise and Fall session owner')
    verify_live(core, saved.backend.runtime.read)
    saved._xp1_unit_work_core = core


def require_owner(saved):
    core = saved.backend.core
    if core is None or getattr(saved, '_xp1_unit_work_core', None) is not core:
        raise ValueError('Unit work requires its verified Rise and Fall UnitPanel bindings')
