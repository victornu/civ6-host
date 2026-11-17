"""Source admission and retained owner for the current XP2 occupation choices."""

import hashlib
from pathlib import Path

from .a0_policy_unlock_current import CURRENT_CORE_SHA256, _require_image
from .captured_city_session import BINDINGS
from .configuration_profiles import _source
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = ('evidence/host-xp2-captured-city-source.json',
          '22f1e528c29113dc29d9eeb9fdb72d207890933c2da8dc1b05e93e6e2c25a4b7')


def source(image):
    _require_image(image)
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-captured-city-source.v1'
            or proof['image']['profile_id'] != image.id
            or proof['image']['sha256'] != image.image_sha256
            or resolve_path(Path(proof['image']['path'])).resolve() != Path(image.path).resolve()
            or frozenset(proof['bindings']) != BINDINGS
            or {name: row['value'] for name, row in proof['directives'].items()} !=
                dict(LIBERATE_FOUNDER=0, LIBERATE_PREVIOUS_OWNER=1, KEEP=2, RAZE=3)
            or proof['popup'] != dict(
                xp2_override='OnOpen', inherits_base_button_handlers=True,
                button_gate='CityManager.CanStartCommand', button_command='CityManager.RequestCommand',
                command='CityCommandTypes.DESTROY', parameter_key='UnitOperationTypes.PARAM_FLAGS',
                city_selector='Players[localPlayer]:GetCities():GetNextCapturedCity()',
                bbg_manifest_mentions_popup=False, unsupported_directives=('REJECT',))):
        raise ValueError('Current XP2 captured-city source differs')
    return proof


def supports_stock(reference, execution_image):
    from .execution_images import ExecutionImageProfile
    from .xp2_bundle_inputs import REFERENCE

    return (reference == REFERENCE and type(execution_image) is ExecutionImageProfile
            and execution_image.image_sha256 == CURRENT_CORE_SHA256)


def source_dependencies(*, execution_image, stock=False):
    proof = source(execution_image)
    keys = ('image', 'base_popup', 'xp2_popup', 'expansion2_manifest')
    if not stock:
        keys += ('bbg_manifest',)
    refs = (proof[key] for key in keys)
    pins = {resolve_path(Path(row['path'])).resolve(): row['sha256'] for row in refs}
    pins[resource_root() / SOURCE[0]] = SOURCE[1]
    return pins


def bind(saved):
    from .captured_session_profile import require_bbg_capture

    continuation = saved.continuation
    continuation.check(active=False)
    core = saved.backend.core
    image = core._civ6_host_execution_image
    if getattr(continuation, 'captured_city_core', None) is not None:
        raise ValueError('XP2 captured-city choices already have a retained Core')
    reference = saved.inputs.official_bundle
    if not (saved.standard_trade is True and supports_stock(reference, image)):
        if saved.trade_diagnostic is not True or continuation.trade_feedback is None:
            raise ValueError('XP2 captured-city choices require an admitted stock or BBG session')
        require_bbg_capture(reference, execution_image=image)
    proof = source(image)
    spans = [proof['enum_registration']]
    for binding in proof['bindings'].values():
        spans.extend((binding['registrar_window'], binding['entry_pdata_fragment']))
    for span in spans:
        address = core._handle + int(span['start_rva'], 16)
        raw = saved.backend.runtime.read(address, span['bytes'])
        if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live XP2 captured-city binding differs at ' + span['start_rva'])
    continuation.captured_city_core = core
