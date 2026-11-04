"""Bounded Base-LAN capability-status projection for official restoration.

This is not Steam/Epic entitlement handling. The existing closed Base catalogue
and installed-file checks still run first. Only their absent-numeric-entry case
is projected. Present, restricted and unknown entries remain errors.

For that case EDI is 1 throughout the official callback. In LAN, the mode
predicate excludes its other-mode branch. With the captured session's read-only
getter types and empty record vectors, the intervening tests have no simulation
effects: both Boolean outcomes converge on EAX=1. Their values need not be
replayed, and separate live reads are not treated as an atomic snapshot.

The profile does not admit networking, command delivery or simultaneous play.
"""
from __future__ import annotations

import struct
from hashlib import sha256

LAN = 0x0138409A
EXE_SHA = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
SOURCE_PINS = {
    'call_closure': ('work/host-simultaneous/ownership-static/call-closure.json',
                     '9d6b28a9d5ce8f31c42b2b3c6be53af67b9bb647ecf3a890e123365fa47ee1b3'),
    'static': ('work/host-simultaneous/ownership-static/targeted-functions.json',
               'ae97dd5f060648b3ba93dd5c86d1db34f4ad8d1cc44d20e39cb5b5550b79df83'),
    'records': ('work/host-simultaneous/ownership-static/live-read-session-final.json',
                'bf33e17b00d7bc502314950cad52a12f3a1e8fe8b51bd3f83d3e84ecf299f7c0'),
    'leaves': ('work/host-simultaneous/ownership-static/live-read-leaf.json',
               'f130ec4ad676043e89ad3069205e1e7ecc4b4ea0438972d3656193002c3d490a'),
}


def validate_record_shape(vector):
    """Check the structural premise; pointer values never become runtime input."""
    raw = bytes.fromhex(vector['records_bytes_hex'])
    if (vector['status'] != 'exact_64_record_span_verified'
            or len(raw) != 64 * 0x40
            or sha256(raw).hexdigest() != vector['records_sha256']):
        raise ValueError('LAN record-array source identity differs')
    for player in range(64):
        if struct.unpack_from('<I', raw, player * 64)[0] != player:
            raise ValueError('LAN source record index differs')
        if struct.unpack_from('<QQQ', raw, player * 64 + 0x20) != (0, 0, 0):
            raise ValueError('LAN record vector requires its real copy/cleanup service')
        if not struct.unpack_from('<Q', raw, player * 64 + 0x18)[0]:
            raise ValueError('LAN source player provider is null')


def verify_source():
    from .native import native_host_capability_status as abi
    from .native.native_source_cache import load_pinned_json
    from .native.native_application_property_copy import verify_source as property_source

    callback = abi.verify_source()
    sources = {name: load_pinned_json(abi.ROOT / path, digest)
               for name, (path, digest) in SOURCE_PINS.items()}
    static, records, leaves = (sources[n] for n in ('static', 'records', 'leaves'))
    if (static['exe_sha256_actual'] != EXE_SHA or records['exe_sha256'] != EXE_SHA
            or leaves['exe_sha256'] != EXE_SHA
            or records['process_identity'] != leaves['process_identity']
            or records['status'] != 'captured_read_only_no_calls'
            or records['refusals']):
        raise ValueError('LAN read-only source profile differs')
    validate_record_shape(records['application']['player_vector'])
    if records['application']['provider_slot_68']['target_va'] != '0x1407a56b0':
        raise ValueError('LAN application getter source differs')
    slots = records['application']['player_vector']['slots']
    if (len(slots) != 64 or any(row['slot'] != player
            or row['status'] != 'captured'
            or row['receiver_slot_68']['target_va'] != '0x1407a56b0'
            for player, row in enumerate(slots))):
        raise ValueError('LAN player getter source differs')
    network = leaves['pointer_chain']
    status_map = records['status_map_type_2']
    fields = network['session_vtable_plus_270_simple_getter_result']
    if (status_map['lookup_key_u32'] != 2 or status_map['bucket_count'] <= 0
            or status_map['returned_pointer'] != network['network_manager_plus_8']
            or status_map['returned_vtable_slot_1c8']['target_va'] != '0x14083fa70'
            or fields['fields_0_4_8_hex'] != '020000000000000000000000'
            or sources['call_closure']['exe_sha256'] != EXE_SHA):
        raise ValueError('LAN session type/lookup source differs')
    expected_leaves = {
        'session_vtable_plus_1c8': ('0x14083fa70', '37f0797d48624be047793550ba72eeb59fb6fa0fe8dcac458ecd100f40417929'),
        'session_vtable_plus_270': ('0x14080f9b0', 'c0151d9feab268cccf5281f8b14121f2c8f7d02892d3177cc3efa49b031e22ec'),
    }
    for name, (target, digest) in expected_leaves.items():
        row = leaves['target_code'][name]
        if (row['target_va'] != target or row['body']['code_sha256'] != digest
                or row['status'] != 'bounded_body_verified_against_live_bytes'):
            raise ValueError('LAN network getter source differs')
    # Both providers implement the already verified scalar-property lookup.
    # Neither the session flag nor the player slot value is used as a permission.
    property_source()
    if callback['callback_contract']['entry_absent_status'] != 1:
        raise ValueError('LAN absent-entry status contract differs')
    return sources


class ClosedLanBranch:
    """Fixed source contract, fresh native provider checks on each request."""

    def __init__(self, application, captured_bundle, *, candidate_backend=None):
        self.candidate_backend = candidate_backend
        from .lan_load import reference_state
        self.sources = verify_source()
        if candidate_backend is None:
            state = reference_state(captured_bundle)['state']
            if (state['game_mode_u32'] != LAN or state['player_id'] != 0
                    or state['observer_id'] != 0):
                raise ValueError('LAN restoration identity is outside the witnessed profile')
        else:
            from .xp1_load_capability import validate_lan_candidate
            self.candidate_projection = validate_lan_candidate(application, captured_bundle, candidate_backend)
        self.application = application
        self.bundle_reference = captured_bundle.reference
        self.players = tuple(self._provider(player) for player in range(64))
        if len(set(self.players)) != 64:
            raise ValueError('LAN native player providers alias')

    def _provider(self, player):
        from .native import native_configuration_finalization as config
        row = (self.application.player(player, candidate_backend=self.candidate_backend)
               if self.candidate_backend is not None else self.application.player(player))
        table = self.application.base + config.CONFIG_VTABLE
        getter_rva = 7626176
        if getattr(self, 'candidate_backend', None) is not None:
            from .xp1_load_capability import source_profile
            proof, _ = source_profile(self.candidate_backend)
            table = self.application.base + proof['configuration_vtable_rva']
            getter_rva = proof['slots']['0x68']['target_rva']
        read = self.application.read
        if (config._qword(read, row['pointer']) != table
                or config._qword(read, table + 0x68) != self.application.base + getter_rva):
            raise ValueError('LAN player scalar getter is outside the verified native type')
        return row['pointer']

    def details(self, player):
        if type(player) is not int or not (0 <= player < 64 or player == 0xFFFFFFFF):
            raise ValueError('LAN capability player is outside the native record domain')
        if player != 0xFFFFFFFF and self._provider(player) != self.players[player]:
            raise ValueError('LAN player provider identity changed')
        return {
            'category': 3,
            'branch': ('captured_xp1_lan_absent_numeric_entry_read_only_projection' if getattr(self, 'candidate_backend', None) is not None else 'closed_base_lan_absent_numeric_entry_read_only_projection'),
            'mode_branch_proof_sha256': SOURCE_PINS['static'][1],
            'lan_record_source_sha256': SOURCE_PINS['records'][1] if getattr(self, 'candidate_backend', None) is None else None,
            **(dict(historical_base_record_source_sha256=SOURCE_PINS['records'][1], **self.candidate_projection)
               if getattr(self, 'candidate_backend', None) is not None else {}),
            'lan_leaf_source_sha256': SOURCE_PINS['leaves'][1],
            'atomic_live_callback_claimed': False,
            'network_session_qualified': False,
            'steam_or_epic_entitlement_queried': False,
        }
