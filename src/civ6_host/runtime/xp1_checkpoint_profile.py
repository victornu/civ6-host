"""Source selection for the existing bounded Save and checkpoint primitives.

This profile admits no new session or saved bundle. The shared caller retains
ownership, serializes the configuration and publishes the exact native pair.
"""
from dataclasses import dataclass
import struct
from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256, _source

SOURCE = ('work/host-extensions/xp1-checkpoint-static/save-source-v1.json',
          '4a5576a1540b40a691093cedee5ffdbb4e6729ec8dd1b9869554366c708270bb')
SUPPLEMENT = ('work/host-extensions/xp1-checkpoint-static/save-source-supplement-v1.json',
              'd610ce522db981fa45ee587917bf1e30eef9bb06c14d07dee0dc9c2c121cb052')


@dataclass(frozen=True)
class SaveABI:
    core_sha256: str
    outer_vtable_rva: int
    inner_vtable_rva: int
    outer_save_rva: int
    inner_save_rva: int
    initialized_rva: int


BASE = SaveABI(BASE_CORE_SHA256, 7987232, 0, 4387856, 250224, 4383648)
XP1 = SaveABI(XP1_CORE_SHA256, 0x8a8df0, 0x8d7168, 0x4be510, 0x3e220, 0x4bd4a0)


XP2 = SaveABI(XP2_CORE_SHA256, 0xa101e8, 0xa44f70, 0x5916e0, 0x472c0, 0x590660)

def verify_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_checkpoint_source import verify_source as selected
        return selected(core_sha256)[0]
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Checkpoint Save source requires its exact XP1 engine')
    p = _source(SOURCE)
    expected = {'outer_save_rva': XP1.outer_save_rva, 'inner_save_rva': XP1.inner_save_rva,
                'initialized_rva': XP1.initialized_rva, 'inner_game_offset': 0x60,
                'return_present_game': 0, 'return_absent_game': 7}
    if (p['schema'] != 'civ6_host.xp1_checkpoint_save.static.v1'
            or p['image']['sha256'] != core_sha256 or p['image']['base'] != '0x180000000'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['validation']['all_instruction_bytes_match_image'] is not True
            or p['validation']['conditional_branches_included'] is not True
            or p['source_version'] != {'rva': 0x865070, 'value': 5}
            or p['stream']['writer_slot'] != 0x28
            or any(p['contracts'].get(k) != v for k, v in expected.items())
            or p['tables'][str(XP1.outer_vtable_rva)] != {'56': XP1.initialized_rva, '360': XP1.outer_save_rva}
            or p['tables'][str(XP1.inner_vtable_rva)]['120'] != XP1.inner_save_rva):
        raise ValueError('XP1 Save source contract changed')
    for rva in (XP1.outer_save_rva, XP1.inner_save_rva, XP1.initialized_rva, 0x3d1f0):
        if not p['functions'][hex(rva)]['instructions']:
            raise ValueError('XP1 Save has an incomplete entry body')
    for reference in p['references']:
        _source((reference['path'], reference['sha256']))
    supplement = _source(SUPPLEMENT)
    if (supplement['schema'] != 'civ6_host.xp1_checkpoint_save.supplement.v1'
            or supplement['source']['sha256'] != SOURCE[1]
            or supplement['native_execution'] is not False
            or supplement['correction']['runtime_writer_unchanged'] is not True
            or supplement['correction']['corrected'] !=
                'Win64: RCX=this, RDX=const source bytes, R8=byte_length uint64; returns int32 status in EAX'):
        raise ValueError('XP1 Save writer ABI source join changed')
    for reference in supplement['references']:
        _source((reference['path'], reference['sha256']))
    return p


def save_abi(core_sha256):
    if core_sha256 == BASE_CORE_SHA256:
        return BASE
    verify_source(core_sha256)
    return XP2 if core_sha256 == XP2_CORE_SHA256 else XP1


def bind_source(session, read, *, core_sha256):
    """Return entry bodies in the shared binder's retained source format."""
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_checkpoint_source import bind_source as selected
        return selected(session, read, core_sha256=core_sha256)
    p = verify_source(core_sha256)
    from .saved_load_services import SavedLoadServices
    if (type(session) is not SavedLoadServices or session.backend.prefix is not session
            or session.backend.core is not session.core or session.backend.context != session.context
            or session.backend.load_abi.core_sha256 != core_sha256):
        raise ValueError('Save requires its exact XP1 saved owner')
    session.backend.check_thread(); session.check()
    base = session.core._handle
    q = lambda address: struct.unpack('<Q', read(address, 8))[0]
    inner = q(session.context + 8)
    if not inner or q(inner) != base + XP1.inner_vtable_rva:
        raise ValueError('Save has a foreign XP1 inner context')
    # The shared binder checks both Save bodies. Check the selected getter too;
    # no new native service, serialization or Update is performed here.
    for rva in (XP1.initialized_rva, 0x3d1f0):
        for row in p['functions'][hex(rva)]['instructions']:
            raw = bytes.fromhex(row['bytes'])
            if read(base + int(row['va'], 16) - 0x180000000, len(raw)) != raw:
                raise ValueError('XP1 initialized getter instructions changed')
    version = p['source_version']
    if read(base + version['rva'], 4) != struct.pack('<I', version['value']):
        raise ValueError('XP1 native Save version changed')
    return {'core_functions': {'save_outer': p['functions'][hex(XP1.outer_save_rva)],
                              'inner_save': p['functions'][hex(XP1.inner_save_rva)]}}


def control_boundary(session, read, *, allow_uninitialized_private=False, core_sha256):
    """Read the actual XP1 composition, without manufacturing Base owner fields."""
    verify_source(core_sha256)
    if type(allow_uninitialized_private) is not bool:
        raise TypeError('Checkpoint private-ring admission must be Boolean')
    from .saved_load_services import SavedLoadServices
    from .captured_saved_load import control_snapshot
    from .xp1_action_transport import SavedActionTransport
    from .action_transport_profiles import ActionTransportProfile
    if (type(session) is not SavedLoadServices or session.backend.prefix is not session
            or session.backend.load_abi.core_sha256 != core_sha256):
        raise ValueError('Checkpoint control requires its exact XP1 owner')
    control = control_snapshot(session.backend, empty=True)
    actions = session.actions
    if (type(actions) is not SavedActionTransport or actions.services is not session
            or type(actions.transport_abi) is not ActionTransportProfile
            or actions.transport_abi.core_sha256 != core_sha256):
        raise ValueError('Checkpoint requires its actual selected command transport')
    actions.require_empty_native_queue()
    a0 = session.host._a0_family_owner
    if a0.private_notification_profile is None:
        if not allow_uninitialized_private:
            raise RuntimeError('Checkpoint requires an initialized private bank')
        ring = None
    else:
        from .a0_private_notifications import get_ring
        ring = get_ring(a0)
        if ring.poisoned or ring.cursors[ring.selector & 1] != 0:
            raise RuntimeError('Checkpoint requires a drained active private bank')
    flags = read(session.core._handle + actions.transport_abi.processor_flags_rva, 4)
    if len(flags) != 4 or any(value not in (0, 1) for value in flags):
        raise RuntimeError('Checkpoint processor flags have an unknown representation')
    return dict(public_sequence=control['sequence'], consumed_count=control['consumed'],
                private_selector=None if ring is None else ring.selector,
                private_cursors=None if ring is None else list(ring.cursors),
                processor_flags=list(flags), notification_counter=control['notification_counter'],
                metadata_counter=control['metadata_counter'])


def provider_proof(core_sha256):
    from .configuration_profiles import configuration_abi
    if core_sha256 not in (BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256):
        raise ValueError('Checkpoint configuration engine is not qualified')
    return configuration_abi(core_sha256).codec_proof_sha256


def require_quiescent(snapshot, *, core_sha256):
    if core_sha256 == BASE_CORE_SHA256:
        from .native.native_checkpoint_jobs import require_quiescent as validate
    elif core_sha256 in (XP1_CORE_SHA256, XP2_CORE_SHA256):
        from .saved_load_job_observer import require_quiescent as validate
    else:
        raise ValueError('Checkpoint scheduler engine is not qualified')
    return validate(snapshot)


def source_dependencies(*, core_sha256=XP1_CORE_SHA256):
    if core_sha256 == XP2_CORE_SHA256:
        from .xp2_checkpoint_source import source_dependencies as selected
        return selected()
    if core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Unknown checkpoint dependency engine')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .action_transport_profiles import source_dependencies as transport
    from .saved_load_job_observer import SOURCE as jobs_source
    p = verify_source()
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), dict(path=SUPPLEMENT[0], sha256=SUPPLEMENT[1]),
            p['image'], *p['references'], *_source(SUPPLEMENT)['references'],
            dict(path=jobs_source[0], sha256=jobs_source[1])]
    result = {str(resolve_path(resource_root()/r['path']).resolve()): r['sha256'] for r in refs}
    for path, sha in transport().items():
        if path in result and result[path] != sha:
            raise ValueError('Conflicting checkpoint source pins')
        result[path] = sha
    return result
