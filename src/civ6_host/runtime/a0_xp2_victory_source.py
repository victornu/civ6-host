"""Verify the live XP2 producer before reusing the Base notification codec."""

import hashlib
from .configuration_profiles import XP2_CORE_SHA256, _source
from .native.native_victory_notifications import PROOF_SHA256

SOURCE = ('evidence/host-xp2-victory-notification-producer.json',
          '1b41f60cd0d6e3773b883cefc5b8b5f291b9b6ebc84372b48645a97337e27843')
COMPARISON = ('evidence/host-xp2-victory-notification-codec-comparison.json',
              '31230a6874ac16340229f4c68a987f19695acd86dde82a245e70921282b58654')


def verify_xp2_producer(kind, base, read):
    proof = _source(SOURCE)
    comparison = _source(COMPARISON)
    if (proof['core_sha256'] != XP2_CORE_SHA256
            or proof['reference_base_consumer_sha256'] != PROOF_SHA256
            or comparison['xp2_core_sha256'] != XP2_CORE_SHA256
            or comparison['base_proof_sha256'] != PROOF_SHA256):
        raise ValueError('Foreign XP2 victory notification source')
    event, = (row for row in proof['events'] if row['kind'] == kind)
    producer = proof['shared_producer']
    rva = int(producer['rva'], 16)
    size = int(producer['end_rva_exclusive'], 16) - rva
    raw = read(base + rva, size)
    if type(raw) is not bytes or len(raw) != size or hashlib.sha256(raw).hexdigest() != producer['sha256']:
        raise ValueError('Live XP2 victory notification producer differs')
    call = bytes.fromhex(event['call_bytes'])
    if (read(base + int(event['call_rva'], 16), len(call)) != call
            or read(base + int(event['kind_immediate_rva'], 16), 4) != kind.to_bytes(4, 'little')):
        raise ValueError('Live XP2 victory notification callsite differs')
