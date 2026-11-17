"""Source guard for the installed Rise and Fall dedication path."""

from pathlib import Path

from .a0_family_source import verify_pinned_files
from .configuration_profiles import _source
from .execution_images import _XP1_PROFILE, identity
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


SOURCE = ('evidence/host-xp1-installed-dedication-source.json',
          '06a9ab0ae4e412096a47a25bd4fd634cb48b44ac437960b4b8763c3bd3953e89')


def supports(reference, image):
    return reference == REFERENCE and image is _XP1_PROFILE


def source(execution_image):
    from .xp2_dedications import BLOCKER, OPERATION, PARAMETER, SOURCE as XP2_SOURCE

    if execution_image is not _XP1_PROFILE:
        raise ValueError('Dedications require the installed Rise and Fall image')
    proof = _source(SOURCE)
    reference = proof['stock_xp2_reference']
    if (proof['schema'] != 'civ6-host.xp1-installed-dedication-source.v1'
            or proof['image'] != identity(execution_image)
            or (reference['path'], reference['sha256']) != XP2_SOURCE
            or {key: row['value_u32'] for key, row in proof['enums'].items()} != {
                'ENDTURN_BLOCKING_COMMEMORATION_AVAILABLE': BLOCKER,
                'COMMEMORATE': OPERATION, 'PARAM_COMMEMORATION_TYPE': PARAMETER}
            or proof['player_boundary']['no_generic_can_start'] is not True):
        raise ValueError('Installed Rise and Fall dedication source differs')
    return proof


def source_dependencies(execution_image):
    proof = source(execution_image)
    refs = (dict(path=SOURCE[0], sha256=SOURCE[1]), proof['stock_xp2_reference'],
            proof['xp1_age_event_reference'], *proof['ui'].values())
    pins = {}
    for ref in refs:
        path = Path(ref['path'])
        resolved = resolve_path(path if path.is_absolute() else resource_root() / path)
        pins[str(resolved.resolve())] = ref['sha256']
    verify_pinned_files(pins)
    return pins
