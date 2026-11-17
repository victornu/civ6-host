"""Exact Rise and Fall Great Work command and shared notification evidence."""

from pathlib import Path

from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import _source
from .execution_images import _XP1_PROFILE
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


SOURCE = ('evidence/host-xp1-great-work-move-source.json',
          'd2c27707e709c3528888af390b72116b153d4bf827d06af4cad1cc7fc004704d')


def source(image):
    from . import xp2_great_work, xp2_great_work_commands

    if image is not _XP1_PROFILE:
        raise ValueError('Great Work move requires the registered Rise and Fall image')
    proof = _source(SOURCE)
    shared = xp2_great_work.moved_source()
    if (proof['schema'] != 'civ6-host.xp1-great-work-move.source.v1'
            or (proof['image_id'], proof['image_sha256']) != (image.id, image.image_sha256)
            or (proof['official_capture']['path'], proof['official_capture']['sha256']) != REFERENCE
            or (proof['shared_receiver']['path'], proof['shared_receiver']['sha256']) != xp2_great_work.MOVED_SOURCE
            or proof['matched_exe'] != shared['images']['exe']
            or set(proof['matched_exe_spans']) != shared['exe_spans'].keys()
            or proof['operation'] != xp2_great_work_commands.OPERATION
            or tuple(proof['parameters']) != xp2_great_work_commands._PARAMETERS
            or proof['full_dual_city_bytes_identical'] is not True
            or any(row['same_instructions_except_relative_addresses'] is not True
                   for row in proof['core_comparison'].values())):
        raise ValueError('Rise and Fall Great Work move route differs')
    return proof


def source_dependencies(image):
    proof = source(image)
    shared = proof['shared_receiver']
    pins = {str(_path(SOURCE[0]).resolve()): SOURCE[1],
            str(_path(shared['path']).resolve()): shared['sha256'],
            str(resolve_path(Path(image.path)).resolve()): image.image_sha256}
    for row in (proof['matched_exe'], proof['ui']):
        pins[str(resolve_path(Path(row['path'])).resolve())] = row['sha256']
    verify_pinned_files(pins)
    return pins
