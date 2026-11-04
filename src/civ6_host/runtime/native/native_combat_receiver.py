"""Combat row with its required map-release post-hook and zero subscribers.

This row is deliberately separate from the generic empty receiver table.
Profiling and the complete EXE frame schedule remain outside this adapter.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import struct
from civ6_host.runtime.native.native_source_cache import load_pinned_json
PROOF_SHA256 = '200aecee4ba3ad1f5d26f02027cf65190dd0087a6a24d60acf183ad0f662be92'
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_combat_receiver.py')))).resolve().parents[1]
PADDING_POLICY = 'zero-unread-combat-payload-gaps-post-release-only'
BASE_STATE = {'observer_registered': False, 'state_pointer_nonnull': True, 'pre_hook': None, 'post_hook': None, 'subscriber_count': 0, 'state_flags': 0}

def verify_source_evidence():
    proof = load_pinned_json(ROOT / 'evidence/native-combat-receiver-f8' / (PROOF_SHA256 + '.json'), PROOF_SHA256)
    row, life = (proof['receiver'], proof['token_lifecycle'])
    if proof['schema'] != 'civ6rl.native_combat_receiver_f8.static.v1' or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or row['record_type'] != 248 or (row['row_va'] != '0x1412c9730') or (row['handler_va'] != '0x1400dbdd0') or (row['common_subscriber_dispatch_va'] != '0x1400dc0d0') or (row['event_name']['text'] != 'GameCoreEvent::Combat') or (life['cleanup_hook_slot_va'] != '0x1412c9738') or (life['installer_va'] != '0x1401538b0') or (life['pair_store_va'] != '0x14011d6a0') or (life['release_by_id_va'] != '0x1401cc3e0') or (life['f8_call_arguments']['rdx_points_to_stack_pair'] != ('0x14014aa40', '0x14059cfd0')) or (life['f8_cleanup_adapter_window']['raw_hex'] != '488bc1488bca48ffe0'):
        raise RuntimeError('Combat post-hook receiver source changed')
    calls = {i['va']: i['text'] for i in life['dispatcher_post_hook_instructions']}
    if calls.get('0x1400dc188') != 'call qword ptr [rax + 8]' or calls.get('0x1400dc18b') != 'and byte ptr [rbx + 0x30], 0xfe':
        raise RuntimeError('Combat post-hook order changed')
    return proof

def validate_receiver_profile(base_state):
    verify_source_evidence()
    if type(base_state) is not dict or set(base_state) != set(BASE_STATE) or any((type(base_state[k]) is not type(v) or base_state[k] != v for k, v in BASE_STATE.items())):
        raise ValueError('Combat requires no additional observer, hook or subscriber')

class CombatReceiver:

    def __init__(self):
        verify_source_evidence()
        self.dispatching = False
        self.poisoned = False

    def consume(self, record, registry, base_state):
        validate_receiver_profile(base_state)
        if self.dispatching or self.poisoned:
            raise RuntimeError('Combat receiver is reentrant or poisoned')
        if type(record) is not bytes or len(record) != 128:
            raise ValueError('Combat receiver requires its exact source record size')
        size, kind, sequence, metadata = struct.unpack_from('<IIII', record)
        token = struct.unpack_from('<I', record, 120)[0]
        if size != 128 or kind != 248 or (not sequence) or (metadata != 0) or (not token) or (struct.unpack_from('<I', record, 80)[0] != sequence) or (record[84:88] != bytes(4)) or (record[124:128] != bytes(4)):
            raise ValueError('Combat record is outside the post-release-only profile')
        owner = registry.lookup(token)
        if owner is None or owner.closed or owner.poisoned:
            raise ValueError('Combat record has no live owned snapshot')
        self.dispatching = True
        try:
            remaining = registry.release(token)
            if remaining != 0 or registry.lookup(token) is not None or (not owner.closed):
                raise RuntimeError('Combat post-hook did not release its sole native map owner')
        except BaseException:
            self.poisoned = True
            raise
        else:
            self.dispatching = False
        return {'record_type': 248, 'record_size': len(record), 'token': token, 'post_hook_reproduced': True, 'native_map_destructor_returned': True, 'registry_live_maps': len(registry.entries), 'source_proof_sha256': PROOF_SHA256, 'subscribers_invoked': 0, 'full_exe_frame_schedule_reproduced': False, 'eligible_for_training': False}
