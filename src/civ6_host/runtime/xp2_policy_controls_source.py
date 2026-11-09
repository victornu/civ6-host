"""Pinned wallet/slot queries and the official empty-map policy operation."""
from .configuration_profiles import XP2_CORE_SHA256, _source

SOURCE = ('work/host-extensions/xp2-policy-controls/source-profile.json',
          '3a055ef6fbfe1eff22682fc0e27bc182113af8bdd5cceb4ed9cc1ee94ff48a4b')
UNLOCK_POLICIES = 0xbd51f5f4
CALLBACKS = {
    'Player.GetReligion': 6987488, 'Player.GetTreasury': 6988416,
    'Treasury.GetGoldBalance': 7039184, 'Religion.GetFaithBalance': 7026016,
    'Culture.GetSlotType': 7000672,
}


def source():
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-policy-controls.static.v1'
            or proof['image']['sha256'] != XP2_CORE_SHA256
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or proof['ui']['sha256'] != '6420eba96b686d36b75cabb5ae3320c281f1c565f5489f63a4ddc5e8b2c8f314'
            or proof['enum']['name'] != 'PlayerOperationTypes.UNLOCK_POLICIES'
            or proof['enum']['u32_value'] != UNLOCK_POLICIES
            or proof['enum']['site_rva'] != 0x5b1e15
            or {key: row['callback_rva'] for key, row in proof['callbacks'].items()} != CALLBACKS):
        raise ValueError('XP2 policy controls source differs')
    return proof


def source_dependencies(*, execution_image=None):
    from .a0_family_source import verify_pinned_files
    from .execution_images import runtime_source_pins
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .xp2_policy_source import source_dependencies as policy_dependencies
    from .xp1_research_profile import source_dependencies as operation_dependencies
    proof = source()
    pins = dict(policy_dependencies(execution_image=execution_image))
    pins.update(operation_dependencies(XP2_CORE_SHA256, execution_image=execution_image))
    from .a0_policy_unlock import source_dependencies as event_dependencies
    pins.update(event_dependencies(execution_image=execution_image))
    rows = (dict(path=SOURCE[0], sha256=SOURCE[1]), proof['image'], proof['ui'], *proof['references'])
    own_pins = {str(resolve_path(resource_root() / row['path']).resolve()): row['sha256'] for row in rows}
    pins.update(runtime_source_pins(own_pins, execution_image=execution_image))
    verify_pinned_files(pins)
    return pins


def bind_owner(saved):
    from .xp2_policy_source import bind_owner as bind_policy
    from .xp1_research_profile import bind_owner as bind_operation
    backend = saved.backend
    backend.check_thread()
    if backend.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Policy unlock requires the exact XP2 engine')
    identity = (backend.core._handle, SOURCE[1])
    existing = getattr(backend, '_xp2_policy_controls_source', None)
    if existing is not None:
        if existing != identity:
            raise ValueError('Policy controls source belongs to another owner')
        return
    bind_policy(saved)
    bind_operation(backend, backend.core, backend.runtime.read)
    proof = source()
    for body in proof['functions'].values():
        for fragment in body['fragments']:
            raw = bytes.fromhex(fragment['raw_hex'])
            rva = int(fragment['start_rva'], 16)
            for offset in range(0, len(raw), 4096):
                block = raw[offset:offset+4096]
                if backend.runtime.read(backend.core._handle+rva+offset, len(block)) != block:
                    raise ValueError('Live XP2 policy controls differ from their source')
    backend._xp2_policy_controls_source = identity
