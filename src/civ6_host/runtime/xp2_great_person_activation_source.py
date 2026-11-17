"""Gathering Storm binding for the shared, parameterless activation command."""

from hashlib import sha256

from . import xp2_bbg_inputs, xp2_bundle_inputs, xp2_great_work, xp2_unit_orders_source
from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP2_CORE_SHA256, _source
from .execution_images import _PROFILE
from .paths import resource_root
from .resource_resolution import resolve_path


SOURCE = (
    'work/xp2-workmove/activation-b86b059811544c9d655585e517c2b830455348a7013817bbad9488528a97ca83.json',
    'b86b059811544c9d655585e517c2b830455348a7013817bbad9488528a97ca83',
)
COMPLETION_SOURCE = SOURCE
WORK_SOURCE = xp2_great_work.SOURCE
_CAPTURES = {xp2_bundle_inputs.REFERENCE: 'stock', xp2_bbg_inputs.REFERENCE: 'bbg751'}
_EVENTS = {
    0x0379681d: 77, 0x981a9186: 73, 0xc1300ee7: 36, 0x9c3482f5: 76,
    0xfc7db95e: 72, 0xe992f3cd: 26, 0xc50d66d6: 25, 0x1a71e9f0: 220,
}


def supports(reference, image):
    return image is _PROFILE and type(reference) is tuple and reference in _CAPTURES


def require_actions(image, *, reference):
    if not supports(reference, image):
        raise ValueError('Great Person activation requires the exact Gathering Storm capture and image')
    proof = _source(SOURCE)
    command = proof['command']
    completion = proof['completion']
    capture = proof['selected_captures'][_CAPTURES[reference]]
    if (proof['schema'] != 'civ6-host.xp2-great-person-activation-static.v1'
            or (proof['image_profile'], proof['image']['sha256'], proof['reference_abi']) !=
               (image.id, image.image_sha256, XP2_CORE_SHA256)
            or proof['native_execution'] is not False
            or (command['type'], command['hash'], command['archive']) !=
               ('UNITCOMMAND_ACTIVATE_GREAT_PERSON', 0x165502d8, 0x493830af)
            or (command['ui_can_start'], command['ui_request'], command['shared_transport_spans'])
               != (0x6c0060, 0x6c2e90, 71)
            or command['table_target_rvas'][2:7] !=
               ('0x6549c0', '0x3fa120', '0x655560', '0x3e330', '0x13230')
            or (completion['work_event'], completion['marker_event']) != (0x1a71e9f0, 0xfc7db95e)
            or (capture['command_hash'], capture['visible'], capture['interface_mode'])
               != (0x165502d8, True, None)):
        raise ValueError('Gathering Storm Great Person activation source differs')
    return proof


def source_dependencies(image, *, reference):
    proof = require_actions(image, reference=reference)
    rules = _CAPTURES[reference]
    capture = proof['selected_captures'][rules]
    ui = proof['panel_source']
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), dict(path=reference[0], sha256=reference[1]),
            proof['image'], capture['capture'], capture['database'], *ui['scripts'][1:]]
    if rules == 'bbg751':
        refs.extend((ui['modinfo'], ui['scripts'][0], proof['dependencies']['balanced_profile']))
    pins = xp2_great_work.source_dependencies(execution_image=image)
    for path, digest in xp2_unit_orders_source.source_dependencies(execution_image=image).items():
        if pins.setdefault(path, digest) != digest:
            raise ValueError('Great Person activation transport source conflict')
    for row in refs:
        path = str(resolve_path(resource_root()/row['path']).resolve(strict=True))
        if pins.setdefault(path, row['sha256']) != row['sha256']:
            raise ValueError('Great Person activation source dependency conflict')
    verify_pinned_files(pins)
    return pins


def verify_live(base, read, *, reference, image):
    proof = require_actions(image, reference=reference)
    if type(base) is not int or base <= 0 or not callable(read):
        raise ValueError('Great Person activation requires an owned module reader')
    command = proof['command']
    bodies = [command[key] for key in ('registration', 'normalized', 'empty_parameter_factory',
                                      'native_hash_member', 'native_legality', 'application')]
    bodies.extend(proof['completion'][key] for key in ('created_work', 'command_marker'))
    bodies.extend(row['callback'] for row in proof['reads'].values())
    spans = [span for body in bodies for span in body['fragments']]
    spans.extend(row[key] for row in proof['reads'].values() for key in ('registrar_window', 'name'))
    for span in spans:
        rva, length = int(span['rva'], 16), span['bytes']
        raw = b''.join(read(base+rva+offset, min(4096, length-offset)) for offset in range(0, length, 4096))
        if len(raw) != length or sha256(raw).hexdigest() != span['sha256']:
            raise ValueError('Live Gathering Storm activation bytes differ at ' + span['rva'])
    table = command['descriptor_table']
    entries = b''.join((base+int(target, 16)).to_bytes(8, 'little') for target in command['table_target_rvas'])
    if read(base+int(table['rva'], 16), len(entries)) != entries:
        raise ValueError('Live Gathering Storm activation command table differs')
    xp2_unit_orders_source.verify_live(base, read)


def bind_prefix(prefix, *, action=False):
    from .core_script_services import check_bound
    from .saved_load_services import SavedLoadServices

    if type(prefix) is not SavedLoadServices:
        raise ValueError('Great Person activation requires its actual saved service owner')
    prefix.check()
    backend = prefix.backend
    backend.check_thread()
    core = backend.core
    reference = backend.captured_bundle.reference
    image = getattr(core, '_civ6_host_execution_image', None)
    if (not supports(reference, image) or prefix is not backend.prefix or prefix.core is not core
            or prefix.context != backend.context or prefix.runtime.service_owner is not prefix.host
            or prefix.core_sha256 != XP2_CORE_SHA256 or backend.load_abi.core_sha256 != XP2_CORE_SHA256):
        raise ValueError('Great Person activation lost its exact Gathering Storm saved owner')
    prefix.runtime.registry.validate(prefix.ui_child)
    check_bound(prefix.runtime, prefix.context, core)
    transport = prefix.actions
    transport.check()
    if action:
        args = prefix.event_arguments
        consumer = args.consumer
        if (consumer is None or consumer.arguments is not args or consumer.deferred is not prefix.deferred_events
                or consumer._foundation_backend is not backend):
            raise ValueError('Great Person activation lost its native event owner')
        for kind, record in _EVENTS.items():
            if not consumer.handles_kind(kind) or not consumer.handles_record(record):
                raise ValueError('Unqualified Gathering Storm activation event ' + hex(kind))
        transport.require_transition()
    lifetime = (prefix, core, core._handle, prefix.runtime, reference)
    previous = getattr(prefix, '_xp2_great_person_activation_lifetime', None)
    if previous is None:
        verify_live(core._handle, backend.runtime.read, reference=reference, image=image)
        xp2_great_work.verify_live(core, backend.runtime.read)
        prefix._xp2_great_person_activation_lifetime = lifetime
    elif previous != lifetime:
        raise ValueError('Great Person activation source belongs to another saved lifetime')
