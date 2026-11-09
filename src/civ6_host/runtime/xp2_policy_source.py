"""Exact XP2 Culture callbacks used by the existing free policy adapter."""
from .configuration_profiles import XP2_CORE_SHA256, _source

SOURCE = ('work/host-extensions/xp2-policy-inputs/source-profile-v3.json',
          '3146fc224c13a690aead78bc2e5347d92951e09f7436e707863ef5f4e271e706')
CALLBACKS = {
    'GetNumPolicySlots': 0x6ad0f0, 'GetNumPolicySlotsOpen': 0x6ad140,
    'GetSlotPolicy': 0x6ad1e0, 'PolicyChangeMade': 0x6adc00,
    'GetCostToUnlockPolicies': 0x6aca70, 'CivicCompletedThisTurn': 0x6ac510,
    'IsPolicyUnlocked': 0x6adb90, 'IsPolicyObsolete': 0x6adb20,
    'CanSlotPolicy': 0x6ac400, 'RequestPolicyChanges': 0x6adde0,
}


def verify_source():
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-policy-inputs.static.v1'
            or proof['image']['sha256'] != XP2_CORE_SHA256 or proof['registrar_rva'] != 0x6ab780
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or {name: row['callback_rva'] for name, row in proof['callbacks'].items()} != CALLBACKS
            or proof['ui']['sha256'] != '6420eba96b686d36b75cabb5ae3320c281f1c565f5489f63a4ddc5e8b2c8f314'):
        raise ValueError('XP2 free policy source profile differs')
    return proof


def source_dependencies(*, execution_image=None):
    from .a0_family_source import verify_pinned_files
    from .execution_images import runtime_source_pins
    proof = verify_source()
    rows = (dict(path=SOURCE[0], sha256=SOURCE[1]), proof['image'], proof['ui'], *proof['references'])
    from .paths import resource_root
    from .resource_resolution import resolve_path
    pins = {str(resolve_path(resource_root() / row['path']).resolve()): row['sha256'] for row in rows}
    pins = runtime_source_pins(pins, execution_image=execution_image)
    verify_pinned_files(pins)
    return pins


def bind_owner(saved):
    backend = saved.backend
    backend.check_thread()
    if backend.load_abi.core_sha256 != XP2_CORE_SHA256:
        raise ValueError('Policy adapter requires the XP2 owner')
    identity = (backend.core._handle, SOURCE[1])
    bound = getattr(backend, '_xp2_policy_source', None)
    if bound is not None:
        if bound != identity:
            raise ValueError('XP2 policy source owner changed')
        return
    proof = verify_source()
    for body in proof['functions'].values():
        for fragment in body['fragments']:
            raw = bytes.fromhex(fragment['raw_hex'])
            rva = int(fragment['start_rva'], 16)
            for offset in range(0, len(raw), 4096):
                part = raw[offset:offset+4096]
                if backend.runtime.read(backend.core._handle+rva+offset, len(part)) != part:
                    raise ValueError('Live XP2 policy callback differs from its source')
    backend._xp2_policy_source = identity
