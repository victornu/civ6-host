"""Read-only Host41 job snapshot draft; never loads or calls GameCore.

The caller supplies an exact safe reader and the real current Win32 thread ID.
This is restricted to the serialized host owner outside all native callbacks.
Double-read stability is not a concurrency primitive or an ABA guarantee.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
from pathlib import Path
import struct
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_checkpoint_jobs.py')))).resolve().parents[1]
PROOF_PATH = ROOT / 'work/native-checkpoint-job-state-source343.json'
PROOF_SHA256 = '4b035fe2b0dfb0b4be35ae46c24b8b8d42affd95e98f97363e2ef1bebbd855bd'
HOST_SHA256 = '2b938551555af92ef37bbda8631d0a90c585c3e89c9d7710d0758e85e2b01334'
PROFILE = 'owned-synchronous-host-idle-controller-v1'
RVA = dict(free_head=8726696, slots=8726704, active_head=8728752, lock=8728760, runtime_thread=8530044, spawn_active=8728768, groups=8728776, submission_sequence=8728784)
UINT64_MAX = (1 << 64) - 1
GROUP_MAGIC = 4848501265015980593

def verify_source():
    raw = _resolve_resource_path(PROOF_PATH).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PROOF_SHA256:
        raise RuntimeError('Host41 job source pin changed')
    proof = json.loads(raw)
    if proof['schema'] != 'civ6rl.native_checkpoint_host41_job_snapshot_source.v1' or proof['host']['sha256'] != HOST_SHA256 or proof['globals_rva'] != RVA or (proof['layout']['slot_count'] != 64) or (proof['layout']['slot_size'] != 32) or (proof['layout']['node_size'] != 56) or (proof['layout']['group_size'] != 32) or (proof['layout']['group_magic'] != GROUP_MAGIC):
        raise RuntimeError('Host41 job source contract changed')
    return proof

def _positive_int(value, label, maximum=UINT64_MAX):
    if type(value) is not int or not 1 <= value <= maximum:
        raise ValueError(label + ' must be a positive exact integer')
    return value

def _read_exact(read, address, size):
    _positive_int(address, 'read address')
    _positive_int(size, 'read length')
    if address > UINT64_MAX - size + 1:
        raise ValueError('Read range overflows uint64')
    value = read(address, size)
    if type(value) is not bytes or len(value) != size:
        raise ValueError('Safe reader returned incomplete or non-bytes memory')
    return value

def _fragments(proof):
    for body in proof['captures'].values():
        for fragment in body['fragments']:
            yield (int(fragment['start_va'], 16) - 5368709120, bytes.fromhex(''.join((ins['bytes'] for ins in fragment['instructions']))))

def verify_live_image(read, host_base, host_image_bytes):
    """Pin the on-disk host identity and all six actual export bodies."""
    proof = verify_source()
    _positive_int(host_base, 'actual host image base')
    if type(host_image_bytes) is not bytes or hashlib.sha256(host_image_bytes).hexdigest() != HOST_SHA256:
        raise ValueError('Actual executable must be the pinned Host41 image')
    for rva, expected in _fragments(proof):
        if _read_exact(read, host_base + rva, len(expected)) != expected:
            raise ValueError('Live Host41 job method bytes differ from pinned image')
    return proof

def capture_snapshot(read, host_base, host_image_bytes, current_thread_id, *, profile, exclusive_owner_entry, max_items=4096, max_groups=4096):
    """Capture real counts/items for all64 lists; pending is visible, not drained.

    Call require_quiescent on the result before Save. ``exclusive_owner_entry``
    is an explicit caller protocol assertion, never inferred from two reads.
    No job, lock, queue cursor, group or job-set field is written by this code.
    """
    if profile != PROFILE or exclusive_owner_entry is not True:
        raise ValueError('An explicit exclusive serial owner entry is required')
    _positive_int(current_thread_id, 'actual Win32 thread ID', 4294967295)
    _positive_int(max_items, 'max_items', 65536)
    _positive_int(max_groups, 'max_groups', 65536)
    verify_live_image(read, host_base, host_image_bytes)
    from civ6_host.runtime.job_registry_snapshot import capture_registry
    result = capture_registry(read, {name: host_base + rva for name, rva in RVA.items()}, current_thread_id, max_items=max_items, max_groups=max_groups)
    return dict(result, schema='civ6rl.native_checkpoint_host41_job_snapshot.v1', source_proof_sha256=PROOF_SHA256, host_sha256=HOST_SHA256, profile=profile)

def require_quiescent(snapshot):
    if type(snapshot) is not dict or snapshot.get('schema') != 'civ6rl.native_checkpoint_host41_job_snapshot.v1' or snapshot.get('source_proof_sha256') != PROOF_SHA256 or (snapshot.get('host_sha256') != HOST_SHA256) or (snapshot.get('profile') != PROFILE) or (snapshot.get('stable_read') is not True) or (type(snapshot.get('spawn_active')) is not int) or (snapshot['spawn_active'] != 0) or (type(snapshot.get('pending_items')) is not int) or (snapshot['pending_items'] != 0) or (len(snapshot.get('slots', ())) != 64):
        raise ValueError('No verified quiescent Host41 job snapshot')
    for index, slot in enumerate(snapshot['slots'], 1):
        if slot.get('handle') != index or type(slot.get('count')) is not int or slot['count'] != 0 or (slot.get('items') != []):
            raise ValueError('Host41 still has pending jobs')
    if any((type(g.get('pending')) is not int or g['pending'] != 0 for g in snapshot.get('groups', ()))):
        raise ValueError('Host41 still has pending groups')
    return snapshot
