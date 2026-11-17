"""Exact stock Rise and Fall Culture bindings and policy request validation."""

from hashlib import sha256
from pathlib import Path

from .a0_family_source import verify_pinned_files
from .configuration_profiles import XP1_CORE_SHA256, _source
from .execution_images import _XP1_PROFILE
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp1_saved_load import REFERENCE


def supports(reference, image):
    return reference == REFERENCE and image is _XP1_PROFILE


SOURCE = ('work/x1trade/xp1-government-policy-source.json',
          '17cfb8393997cc96360bf5cc8e693eb2e3b290f0ad6f40e7958a7f1e62155f6e')
_CULTURE_RVA = 0x5c7200
_CHANGE_MESSAGE = 0xe57882af
_XP1_CALLBACKS = {
    'CanChangeGovernment': 0x5c7d60, 'CanChangeGovernmentAtAll': 0x5c7dd0,
    'GetCurrentGovernment': 0x5c8640, 'GetAnarchyTurns': 0x5c8090,
    'IsGovernmentUnlocked': 0x5c9470, 'GovernmentChangeMade': 0x5c9270,
    'GovernmentChangeConsidered': 0x5c9220, 'SetGovernmentChangeConsidered': 0x5c9de0,
    'RequestChangeGovernment': 0x5c96d0, 'RequestPolicyChanges': 0x5c9860,
    'GetCostToUnlockPolicies': 0x5c84f0, 'PolicyChangeMade': 0x5c9680,
}


def verify_source():
    proof = _source(SOURCE)
    image = proof['image']
    callbacks = {name: row for family in ('government', 'policies')
                 for name, row in proof['callbacks'][family].items()}
    packet = proof['packet']
    if (proof['schema'] != 'civ6-host.xp1-government-policy.static.v1'
            or proof['native_execution'] is not False or proof['process_memory_read'] is not False
            or (image['profile_id'], image['sha256'], image['reference_core_sha256']) !=
               (_XP1_PROFILE.id, _XP1_PROFILE.image_sha256, XP1_CORE_SHA256)
            or any((callbacks[name]['callback_rva'], callbacks[name]['registrar_rva']) != (rva, _CULTURE_RVA)
                   for name, rva in _XP1_CALLBACKS.items())
            or (packet['message_type'], packet['byte_order'], packet['word_bytes']) !=
               (_CHANGE_MESSAGE, 'little-endian', 4)
            or packet['subtype1']['words'] !=
               ('message_type', 'player_id', 1, 'selected_government_index', 0xffffffff, 0, 0)
            or packet['subtype3']['words'] !=
               ('message_type', 'player_id', 3, 0xffffffff, 0xffffffff, 'Nclear',
                'clear_slot_0..Nclear-1', 'Nadd', '(policy_hash_u32,slot) repeated Nadd')
            or proof['notifications']['government_changed']['queue_type'] != 203
            or proof['notifications']['slot_policy_changed']['queue_type'] != 206
            or proof['notifications']['policy_batch']['registered_callback'] is not False):
        raise ValueError('Rise and Fall government and policy source differs')
    return proof


def source_dependencies(image):
    if image is not _XP1_PROFILE:
        raise ValueError('Government sources require the installed Rise and Fall image')
    from .native import native_government_actions as government
    from .native import native_government_consideration as consideration

    government.verify_source()
    consideration.verify_source()
    proof = verify_source()
    refs = [dict(path=SOURCE[0], sha256=SOURCE[1]), dict(path=REFERENCE[0], sha256=REFERENCE[1])]
    refs.extend(proof[key] for key in ('image', 'executable', 'ui', 'expansion_ui', 'expansion_modinfo'))
    refs.extend(row.get('artifact', row) for row in proof['witnesses'].values())
    pins = {}
    for row in refs:
        path = Path(row['path'])
        path = resolve_path(path if path.is_absolute() else resource_root() / path)
        if pins.setdefault(str(path.resolve()), row['sha256']) != row['sha256']:
            raise ValueError('Conflicting Rise and Fall government source pins')
    for path, digest in (
            (government._PROOF, government.PINNED_EVIDENCE_SHA256),
            (government._CURRENT_GOVERNMENT_PROOF, government._CURRENT_GOVERNMENT_PIN),
            (government._TRANSPORT_PROOF, government.TRANSPORT_PROOF_SHA256),
            (consideration._PROOF, consideration.PINNED_EVIDENCE_SHA256)):
        pins[str(resolve_path(path).resolve())] = digest
    verify_pinned_files(pins)
    return pins


def bind_owner(saved):
    backend = saved.backend
    backend.check_thread()
    image = getattr(backend.core, '_civ6_host_execution_image', None)
    if (getattr(saved, 'xp1_government', False) is not True
            or backend.load_abi.core_sha256 != XP1_CORE_SHA256
            or not supports(backend.captured_bundle.reference, image)):
        raise ValueError('Government and policies require the exact Rise and Fall saved owner')
    base = backend.core._handle
    identity = (base, SOURCE[1])
    previous = getattr(backend, '_xp1_government_policy_source', None)
    if previous is not None:
        if previous != identity:
            raise ValueError('Rise and Fall government source owner changed')
        return
    proof = verify_source()
    for body in proof['core_bodies']:
        raw = bytes.fromhex(body['raw_hex'])
        if (len(raw) != body['bytes'] or sha256(raw).hexdigest() != body['sha256']
                or backend.runtime.read(base + body['rva'], len(raw)) != raw):
            raise ValueError('Live Rise and Fall Culture binding differs: ' + body['name'])
    packet = proof['packet']
    table = base + packet['vtable_rva']
    for target in packet['vtable_targets']:
        ptr = base + target['target_rva']
        if backend.runtime.read(table + 8 * target['slot'], 8) != ptr.to_bytes(8, 'little'):
            raise ValueError('Live Rise and Fall Culture packet vtable differs')
    backend._xp1_government_policy_source = identity


def validate_policy_archive(payload, choice):
    from .native.native_policy_actions import validate_assignment_archive
    return validate_assignment_archive(payload, choice)
