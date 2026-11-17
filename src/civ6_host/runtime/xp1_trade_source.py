"""Exact source boundary for stock Rise and Fall trade."""

from pathlib import Path

from .a0_family_source import verify_pinned_files
from .configuration_profiles import _source
from .execution_images import _XP1_PROFILE
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


SOURCE = ('work/trade-common-client/xp1-installed-stock-trade-operations.json',
          '4bda7665a7a6925fb19b21e9e28696caa806f4dae94603a229e1b34eb5641a27')
OPERATIONS = {
    'UNITOPERATION_MAKE_TRADE_ROUTE': -2089494188,
    'UNITOPERATION_TELEPORT_TO_CITY': 509098169,
}


def supports(reference, image):
    return reference == REFERENCE and image is _XP1_PROFILE


def source_dependencies(image):
    if image is not _XP1_PROFILE:
        raise ValueError('Trade sources require the installed Rise and Fall image')
    from .locale_text import source_files as locale_files
    from .native import native_saved_trade as routes, native_saved_trade_origin as origins
    from .native.native_locale_arguments import verified_files as locale_arguments_files

    proof = _source(SOURCE)
    provenance = proof['provenance']
    capture = provenance['official_capture']
    if (proof['schema'] != 'civ6-host.xp1-installed-stock-trade-operations.static.v1'
            or proof['images']['core']['sha256'] != image.image_sha256
            or (capture['path'], capture['sha256']) != REFERENCE
            or {row['type']: row['hash_signed'] for row in proof['operation_definitions']
                if row['visible_in_ui'] is True} != OPERATIONS):
        raise ValueError('Rise and Fall trade sources differ')

    route_source, origin_source = routes.verify_source(), origins.verify_source()
    sources = [
        dict(path=SOURCE[0], sha256=SOURCE[1]),
        capture, provenance['gameplay_database'], provenance['prior_bindings'],
        provenance['base_trade_source'], route_source['official_helper'],
        dict(path=origins.PROOF, sha256=origins.PROOF_SHA),
        *route_source['official_ui'].values(), *origin_source['official_ui'].values(),
    ]
    steam_root = Path(image.path).parents[4]
    sources.extend(dict(row, path=steam_root / row['path']) for row in provenance['ui'].values())
    pins = {}
    for row in sources:
        path = Path(row['path'])
        resolved = str(resolve_path(path if path.is_absolute() else resource_root() / path).resolve())
        if pins.setdefault(resolved, row['sha256']) != row['sha256']:
            raise ValueError('Conflicting Rise and Fall trade pins')
    verify_pinned_files(pins)
    pins.update((str(resolve_path(path).resolve()), digest)
                for path, digest in locale_arguments_files()[0].items())
    pins.update(locale_files(execution_image=image)[0])
    return pins
