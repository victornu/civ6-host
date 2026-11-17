"""Source-bound building and player notifications on the XP1 capture path."""

import hashlib
from pathlib import Path

from . import foundation_facade_profiles as facades
from . import xp2_building_removal as building
from . import xp2_capture_notification_source as registered
from . import xp2_player_can_construct_event as player
from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE, identity
from .paths import resource_root


SOURCE = ('evidence/host-xp1-installed-capture-followup-notifications-source.json',
          '1978c1ef2f7b86c91fa0f1c0e921b7abdbabef708096d7aa116c606e7406ded4')
ROUTES = {
    'building_removed': (building.KIND, {(building.RECORD_TYPE, building.RECORD_SIZE)}),
    'player_availability': (player.KIND, {(kind, player.RECORD_SIZE) for kind in player.RECORD_TYPES}),
}
PLOT_OPERATIONS = ('outer_map', 'get_plot', 'release_map', 'release_plot',
                   'plot_snapshot178', 'plot_flag148')


def source(execution_image):
    if execution_image is not _XP1_PROFILE:
        raise ValueError('Capture notifications require the registered Rise and Fall image')
    proof = _source(SOURCE)
    abi = facades.query_abi(XP1_CORE_SHA256, resource_root())
    if (proof['schema'] != 'civ6-host.xp1-installed-capture-followup-notifications.source.v1'
            or proof['image'] != identity(execution_image)
            or proof['exe'] != registered.source()['images']['exe']
            or (proof['registered_source']['path'], proof['registered_source']['sha256']) != registered.SOURCE
            or (proof['facade_source']['path'], proof['facade_source']['sha256']) != facades.SOURCE
            or proof['plot_operations'] != {name: abi.operations[name] for name in PLOT_OPERATIONS}
            or set(proof['routes']) != set(ROUTES)):
        raise ValueError('Rise and Fall capture notification source differs')
    for name, (kind, records) in ROUTES.items():
        route = proof['routes'][name]
        if route['kind'] != kind or set(route['records']) != records:
            raise ValueError('Rise and Fall capture notification wire differs: ' + name)
        registered.route(name, kind, records)
    return proof


def source_dependencies(execution_image):
    proof = source(execution_image)
    pins = {
        str(_path(SOURCE[0]).resolve()): SOURCE[1],
        str(_path(registered.SOURCE[0]).resolve()): registered.SOURCE[1],
        str(_path(facades.SOURCE[0]).resolve()): facades.SOURCE[1],
        str(Path(execution_image.path).resolve()): execution_image.image_sha256,
        str(Path(proof['exe']['path']).resolve()): proof['exe']['sha256'],
    }
    verify_pinned_files(pins)
    return pins


def verify_live(core, read):
    proof = source(getattr(core, '_civ6_host_execution_image', None))
    for route in proof['routes'].values():
        for label, span in route['core_spans'].items():
            raw = read(core._handle + span['rva'], span['bytes'])
            if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != span['sha256']:
                raise ValueError('Live Rise and Fall capture notification differs: ' + label)


def dispatch_building(owner, fields):
    return building.dispatch_record(owner, fields, execution_image=_owned_image(owner),
                                    core_sha256=XP1_CORE_SHA256, proof_sha256=SOURCE[1])


def dispatch_player(owner, fields):
    return player.dispatch_record(owner, fields, execution_image=_owned_image(owner),
                                  proof_sha256=SOURCE[1])


def _owned_image(owner):
    from .a0_foundation_events import require_borrow

    backend = require_borrow(owner).owner
    image = getattr(backend.core, '_civ6_host_execution_image', None)
    if image is not _XP1_PROFILE:
        raise ValueError('Rise and Fall capture notification lost its registered Core')
    return image
