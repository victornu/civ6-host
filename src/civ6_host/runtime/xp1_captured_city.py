"""Source admission for the installed Rise and Fall occupation menu."""

import hashlib
from pathlib import Path
import struct

from .captured_city_session import BINDINGS
from .configuration_profiles import _source
from .execution_images import _XP1_PROFILE
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


SOURCE = ('evidence/host-xp1-installed-occupation-bindings-preparation.json',
          'ff3305a6116fc1d412895c78c335a43366bd4a1ec8355fc1a4514b34a93cf2df')


def supports(reference, image):
    return reference == REFERENCE and image is _XP1_PROFILE


def source(image):
    if image is not _XP1_PROFILE:
        raise ValueError('Occupation requires the registered Rise and Fall image')
    proof = _source(SOURCE)
    origin = proof['official_capture']
    if (proof['schema'] != 'civ6-host.xp1-installed-occupation-bindings.preparation.v1'
            or proof['image']['sha256'] != image.image_sha256
            or resolve_path(Path(proof['image']['path'])).resolve() != Path(image.path).resolve()
            or (Path(origin['path']).as_posix(), origin['sha256']) != REFERENCE
            or set(proof['bindings']) != BINDINGS
            or {name: row['value'] for name, row in proof['enums'].items()}
               != dict(LIBERATE_FOUNDER=0, LIBERATE_PREVIOUS_OWNER=1, KEEP=2, RAZE=3, REJECT=4)
            or proof['popup_route'] != dict(selector='PlayerCities.GetNextCapturedCity',
                native_gate='CityManager.CanStartCommand', native_command='CityManager.RequestCommand',
                command='CityCommandTypes.DESTROY', parameter='UnitOperationTypes.PARAM_FLAGS',
                not_offered_by_popup=('REJECT',))):
        raise ValueError('Rise and Fall captured-city source differs')
    return proof


def source_dependencies(image):
    proof = source(image)
    rows = (proof['image'], proof['base_popup'], proof['expansion1_manifest'])
    pins = {resolve_path(Path(row['path'])).resolve(): row['sha256'] for row in rows}
    pins[(resource_root() / SOURCE[0]).resolve()] = SOURCE[1]
    return pins


def bind(saved):
    continuation = saved.continuation
    continuation.check(active=False)
    core = saved.backend.core
    image = getattr(core, '_civ6_host_execution_image', None)
    if not supports(saved.inputs.official_bundle, image) or getattr(continuation, 'captured_city_core', None) is not None:
        raise ValueError('Rise and Fall occupation requires its original unbound session')
    proof = source(image)
    read = saved.backend.runtime.read
    spans = [proof['enum_registration'], *(row['numeric_source'] for row in proof['enums'].values())]
    for row in proof['bindings'].values():
        spans.extend((row['registration_span'], row['entry_pdata_fragment']))
    namespaces = proof['namespace_sources']
    spans.extend(row for key, row in namespaces.items() if key != 'city_manager_vtable_entry')
    for span in spans:
        raw = read(core._handle + span['rva'], span['bytes'])
        if type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != span['sha256']:
            raise ValueError(f"Live Rise and Fall occupation binding differs at {span['rva']:#x}")
    slot = namespaces['city_manager_vtable_entry']
    registrar = proof['bindings']['CityManager.RequestCommand']['registrar_rva']
    if slot['bytes'] != 8 or read(core._handle + slot['rva'], 8) != struct.pack('<Q', core._handle + registrar):
        raise ValueError('Live Rise and Fall CityManager occupation registrar differs')
    continuation.captured_city_core = core
