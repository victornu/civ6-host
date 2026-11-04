"""Narrow pure contract for validating empty Host41 scheduler changes at Load.

This is a bounded diagnostic contract. It does not read process memory, mutate Host41,
or establish that a native Load succeeded. Its inputs must be two independently
captured snapshots and the exact intervening Host41 job-export ledger.
"""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import hashlib
import json
import math
from pathlib import Path
from civ6_host.runtime.native import native_checkpoint_jobs as jobs
NOOP_WAIT = ('empty_job_set_waited', 'EXP_JobManager_Wait')
NOOP_NULL_FREE = ('null_job_list_freed', 'EXP_JobManager_FreeJobList')
CREATE_LIST = ('job_list_created', 'EXP_JobManager_CreateJobList')
HOST_SOURCE_PATH = 'work/native-script-services-host41/gamecore_python_host.c'
HOST_SOURCE_SHA256 = '377e91581b4c13db986446084607d1b269a39e5284e163c1e7d0866a64d68d64'
HOST_AUDIT_SHA256 = 'c9c6d6cd508daeae619aa1e6cbc17fef2e636c6abbfbacd2414f399bb0f38907'
HOST_SOURCE_COPIES = ('work/native-script-services-host41/gamecore_python_host.c',)
PROBE_SOURCE_PATHS = {'ee3a6af9231643f3fe069b2cf37df90bc4be64052e40627235e9ce58beff516e': 'work/native-postload-jobs-probe368.py', '3ac2f5c65c3bb737c398374ed29cb9b0500f23694645262af7177831012aaaca': 'work/native-postload-jobs-probe369.py', 'a313f755da07600ce91d3e137e65883a8049c9a5f9e30167080f70ccb8203867': 'work/native-postload-jobs-probe370.py', 'f9989186f1fe8e01a96ecc809525790b34305ee9bb105b612b40a833d62e5c18': 'work/native-postload-jobs-probe371.py', '836dec1ffd00aa0e284d4d226e528698dca1736869cdf2c27a85d9770800f64c': 'work/native-postload-jobs-probe372.py', '931e5ac145078b9c371de9f81a2c8083586f0cc0f20fda668c43592ddc96304d': 'work/native-postload-jobs-probe376.py', 'eeb5b15aa73bd5acbe520d4882b90b0765ec14ab28e11684b5c26b8576bbd603': 'work/native-postload-jobs-probe377.py', '471e3fea022291a60921bd711ec954d7e4a9aad109e435a38decea79f56d4f1e': 'work/native-postload-jobs-probe378.py', 'facea0f968370b926c45f96f53d8d5708880e163f6e78ef2c9671c333f1c21a1': 'work/native-postload-jobs-probe379.py', 'c0c723e75490d379bbaada7a4a9e23ff018f96508214b86de2a3eb2f69806710': 'work/native-postload-jobs-probe380.py', '180c563672533bf24aeb0dd950318839a95f26ae4accf0b58b2c4e4d0b5fee3b': 'work/native-postload-jobs-probe381.py', '89aa725a928a30eded2c75bc1a48fc5a07be79878109801a459e94a33050e1fc': 'work/native-postload-jobs-probe382.py', '80ef0d3d0c1f49179f6be5c3a3b88fef5da43f92c2e914ee604d3254707b7eec': 'work/native-postload-jobs-probe383.py', '6c71a7fe6a44db399b49371b2d7cef24fc66ff62ca7de136696ffc5c2a6d47af': 'work/native-postload-jobs-probe385.py', 'ccb2afbd9b4fe613cc65fbf5b54de8069774677d5f183394cf22721f10be2764': 'work/native-postload-jobs-probe386.py', 'fc191993363a1d258493624fd31ded0f48de1da5f6fe574db1fc10e9bfcf7c82': 'work/native-postload-jobs-probe387.py', '398252b25191170eafb6ed44cab7d7a8a8aa7a5e74aa843ae46d3117082ff7d1': 'work/native-postload-jobs-probe389.py', 'eecc0056c32cdee49c40f6b5c3fbb9b455a923d6aa3232bcc1174fc9fcc28fbc': 'work/native-postload-jobs-probe390.py', 'a8743bad70b7c769051fbe7f5154221ddd97f57554c210c061d2fe1bcf41db0f': 'work/native-postload-jobs-probe392.py', '37d1b99511e102092cc878a94f1a42cef0b600b113f958f3b57c699d32fb8979': 'work/native-postload-jobs-probe393.py', '418c2316b11f6230a3b379588c8e496ef8332059dcfee26bd10b5ae2135615bb': 'work/native-postload-jobs-probe394.py', '1c21baf4c1fabc9641719357e64a36e0712c367edd1101fce771e6d78f7d40d4': 'work/native-postload-jobs-probe395.py', 'd136bd71679d43258008f8a664ec56f66139edbf70ff7218e8486454a590219b': 'work/native-postload-jobs-probe397.py', 'bdc0c65f1da14933b9250b111a7db7324cd251525ff8429fb1c49499f237c91e': 'work/native-postload-jobs-probe399.py', '61249945f8598d333f1820bae0d15fdf56f5c2a68c448d369ce8a835cdffb544': 'work/native-postload-jobs-probe400.py', '5f800786cc64d53957b9b4e04b25c4b86adb787cdb69601755e0348407d5ced3': 'work/native-postload-jobs-probe401.py', 'b220981e1d81484cf86905ffc71684bf58f6ce3ade33595acd73bb2717beeb92': 'work/native-postload-jobs-probe402.py', '914221fd26e2bf13d8275280ad7883c2df82b5a235d169a1b3add1403611c55b': 'work/native-postload-jobs-probe403.py', 'e7cda800cb0723867128b809086e4145a5f24f181e7e4cfb86a138e6500ec383': 'work/native-postload-jobs-probe405.py', 'ad38a197568c57f1379f7e5afc6b7f6dd908331a3d9747f3a42ed48bf22c0f24': 'work/native-retained150-long-stage628/native_probe-v1.py', 'aca73cc2369e3c19aad3ffcd472d151a912848444fb51d65d38d0d3c97d2b299': 'work/native-postload-jobs-probe406.py', '77f45b83d1481bf0a403a8375dd4c772a20ebc97d0e594cfaa9f31ad3a160e62': 'work/native-postload-jobs-probe407.py', '4aa90d6cc8dfa2bd4a82d0991f1b6f11c99dfff73dc0f86391c52e271cdd980c': 'work/native-postload-jobs-probe408.py', '99baab5a333ab4995f2ac411f0b57bb6bb10b7504bb0c6ed070b433e3f29419c': 'work/native-postload-jobs-probe409.py', '8b4e8aacbae08c6417b122122994ae746a32e96164003fd84d2f3aaa32b776a9': 'work/native-postload-jobs-probe410.py', '3e38f148a1fe0834ae594aa129ceb2d417b150b7fd2dbaed6439d70e5cd0671d': 'work/native-postload-jobs-probe411.py', '5c16a29d883e9c5e8670f883abcf9c5e1eb89321dec2c563e3fb196d5c6c928f': 'work/native-postload-jobs-probe413.py', 'c728c17a456116d2c61c351034af0f07bafe1cf8ef84ba6c6bf66710bd7e4946': 'work/native-postload-jobs-probe414.py', '5fb49a2c619895c3eda5d86b501faa18c23307c98be291206b63efcf8fbb1a28': 'civ6rl/native_probe.py'}
PROBE_MODE = 'trace-checkpoint-load-only'
PROBE_MODES = ('trace-checkpoint-resume-previctory12-one-round', PROBE_MODE, 'trace-checkpoint-load-facades', 'trace-checkpoint-load-post160', 'trace-checkpoint-load-retained121-post160', 'trace-checkpoint-load-retained150-post160', 'trace-checkpoint-load-retained150-owned-state', 'trace-checkpoint-resume-retained121-one-round', 'trace-checkpoint-resume-retained150-one-round', 'trace-checkpoint-resume-retained182-one-round', 'trace-checkpoint-resume-one-round', 'trace-checkpoint-resume-late114-one-round', 'trace-checkpoint-resume-late114-bounded-rounds', 'trace-checkpoint-resume-late114-save118', 'trace-checkpoint-resume-retained118-save121', 'trace-checkpoint-resume-retained118-one-round', 'trace-checkpoint-resume-retained118-bounded-rounds', 'trace-checkpoint-resume-retained118-long-bounded-rounds', 'trace-checkpoint-resume-retained118-save150', 'trace-checkpoint-resume-retained150-long-bounded-rounds', 'trace-checkpoint-resume-retained150-save182')
REPORT_SCHEMA = 'civ6rl.native-host-probe.v1'
SNAPSHOT_SCHEMA = 'civ6rl.native_checkpoint_host41_job_snapshot.v1'
SNAPSHOT_KEYS = frozenset(('schema', 'source_proof_sha256', 'host_sha256', 'profile', 'owner_thread_id', 'spawn_active', 'registry_lock_raw', 'submission_sequence', 'slots', 'groups', 'pending_items', 'stable_read', 'concurrent_scheduler_supported', 'memory_modified', 'native_methods_called', 'current_executable'))
EXE_KEYS = frozenset(('host_base', 'executable_path', 'os_thread_id'))
SLOT_KEYS = frozenset(('handle', 'occupied', 'count', 'items'))
GROUP_KEYS = frozenset(('pointer', 'owner', 'pending'))
EVENT_ENVELOPE_KEYS = frozenset(('seconds', 'monotonic_seconds', 'pid', 'memory'))
EVENT_KEYS = {NOOP_WAIT: frozenset(('stage', 'export', 'first_argument_raw', 'member8', 'contract')), NOOP_NULL_FREE: frozenset(('stage', 'export', 'handle', 'contract')), CREATE_LIST: frozenset(('stage', 'export', 'handle'))}

def verify_source_contract():
    """Bind this proposal to the already-pinned Host41 source and PE evidence."""
    proof = jobs.verify_source()
    if proof.get('source', {}).get('sha256') != HOST_SOURCE_SHA256:
        raise RuntimeError('Host41 scheduler source hash differs from source343 proof')
    if proof.get('source', {}).get('path', '').replace('\\', '/').endswith('/work/native-script-services-host41/gamecore_python_host.c') is False:
        raise RuntimeError('Host41 scheduler source path differs from source343 proof')
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_module_file(jobs)))).resolve().parents[1]
    for relative in HOST_SOURCE_COPIES:
        source_path = root / relative
        if not _resolve_resource_path(source_path).is_file() or hashlib.sha256(_resolve_resource_path(source_path).read_bytes()).hexdigest() != HOST_SOURCE_SHA256:
            raise RuntimeError(f'Host41 C source copy changed: {relative}')
    audit_path = root / 'work/native-checkpoint-job-snapshot-audit343.json'
    if not _resolve_resource_path(audit_path).is_file() or hashlib.sha256(_resolve_resource_path(audit_path).read_bytes()).hexdigest() != HOST_AUDIT_SHA256:
        raise RuntimeError('Host41 source343 audit changed or is missing')
    return proof

def _exact_int(value, name, *, low=0, high=(1 << 64) - 1):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f'{name} is outside its exact integer domain')
    return value

def _identity(snapshot, label):
    proof = verify_source_contract()
    if type(snapshot) is not dict:
        raise ValueError(f'{label} snapshot must be an object')
    if set(snapshot) != SNAPSHOT_KEYS:
        raise ValueError(f'{label} snapshot has missing or unknown fields')
    if snapshot.get('host_sha256') != proof['host']['sha256']:
        raise ValueError(f'{label} Host41 image pin differs from source proof')
    if snapshot.get('source_proof_sha256') != jobs.PROOF_SHA256:
        raise ValueError(f'{label} job snapshot source pin differs')
    for key, expected in (('spawn_active', 0), ('registry_lock_raw', 0), ('stable_read', True), ('concurrent_scheduler_supported', False), ('memory_modified', False), ('native_methods_called', False)):
        if type(snapshot.get(key)) is not type(expected) or snapshot[key] != expected:
            raise ValueError(f'{label} snapshot {key} is outside the strict idle profile')
    if type(snapshot.get('pending_items')) is not int or snapshot['pending_items'] != 0:
        raise ValueError(f'{label} pending item count is not exactly zero')
    _exact_int(snapshot['submission_sequence'], f'{label} submission sequence')
    if type(snapshot.get('owner_thread_id')) is not int or not 1 <= snapshot['owner_thread_id'] <= 4294967295:
        raise ValueError(f'{label} owner thread is malformed')
    exe = snapshot.get('current_executable')
    if type(exe) is not dict or set(exe) != {'host_base', 'executable_path', 'os_thread_id'}:
        raise ValueError(f'{label} live executable identity is incomplete')
    _exact_int(exe['host_base'], f'{label} executable base', low=1)
    if type(exe['executable_path']) is not str or not exe['executable_path']:
        raise ValueError(f'{label} executable path is malformed')
    root = _resolve_resource_path(_resolve_resource_path(Path(_historical_module_file(jobs)))).resolve().parents[1]
    expected_exe = _resolve_resource_path(root / 'work/native-script-services-host41/civ6rl-native-python.exe').resolve()
    if _resolve_resource_path(_resolve_resource_path(Path(exe['executable_path']))).resolve() != expected_exe:
        raise ValueError(f'{label} executable path is not the pinned Host41')
    _exact_int(exe['os_thread_id'], f'{label} OS thread', low=1, high=4294967295)
    if exe['os_thread_id'] != snapshot['owner_thread_id']:
        raise ValueError(f'{label} executable and snapshot thread differ')
    if type(snapshot.get('groups')) is not list or type(snapshot.get('slots')) is not list:
        raise ValueError(f'{label} scheduler collections are malformed')
    if len(snapshot['slots']) != 64 or len(snapshot['groups']) > 4096:
        raise ValueError(f'{label} scheduler collection count is outside bounds')
    group_ptrs, group_owners = (set(), set())
    for group in snapshot['groups']:
        if type(group) is not dict or set(group) != GROUP_KEYS:
            raise ValueError(f'{label} group record has wrong shape')
        pointer = _exact_int(group['pointer'], f'{label} group pointer', low=8)
        owner = _exact_int(group['owner'], f'{label} group owner', low=8)
        pending = _exact_int(group['pending'], f'{label} group pending', high=65536)
        if pointer % 8 or owner % 8 or pointer == owner or (pending != 0) or (pointer in group_ptrs) or (owner in group_owners):
            raise ValueError(f'{label} group identity/pending state is malformed')
        group_ptrs.add(pointer)
        group_owners.add(owner)
    for index, slot in enumerate(snapshot['slots'], 1):
        if type(slot) is not dict or set(slot) != SLOT_KEYS:
            raise ValueError(f'{label} slot record has wrong shape')
        if type(slot['handle']) is not int or slot['handle'] != index:
            raise ValueError(f'{label} slot identity/order is malformed')
        if type(slot['occupied']) is not bool:
            raise ValueError(f'{label} slot occupancy is malformed')
        if type(slot['count']) is not int or slot['count'] != 0 or type(slot['items']) is not list or slot['items']:
            raise ValueError(f'{label} slot is not structurally empty')
    jobs.require_quiescent(snapshot)
    return exe

def _ledger_event(event):
    if type(event) is not dict or type(event.get('stage')) is not str:
        raise ValueError('Malformed Host41 job event')
    stage = event['stage']
    export = event.get('export')
    key = (stage, export)
    if key not in EVENT_KEYS:
        raise ValueError('Load interval contains unknown/non-admitted job export')
    expected = EVENT_KEYS[key]
    if set(event) != expected:
        raise ValueError('Host41 job event has missing or unknown fields')
    if (stage, export) == NOOP_WAIT:
        if event.get('contract') != 'null_second_member_only' or type(event.get('member8')) is not int or event['member8'] != 0 or (type(event.get('first_argument_raw')) is not int) or (not 1 <= event['first_argument_raw'] <= jobs.UINT64_MAX):
            raise ValueError('Wait event is not the proven no-op null-second-member path')
        return ('noop', None)
    if (stage, export) == NOOP_NULL_FREE:
        if type(event.get('handle')) is not int or event['handle'] != 0 or event.get('contract') != 'zero_handle_only':
            raise ValueError('FreeJobList event is not the proven null-handle no-op')
        return ('noop', None)
    if (stage, export) == CREATE_LIST:
        handle = _exact_int(event.get('handle'), 'created job-list handle', low=1, high=64)
        return ('create', handle)
    raise ValueError('Load interval contains a job transition outside the narrow empty-list profile')

def validate_quiescent_snapshot_transition(before, after):
    """Validate the live-safe structural subset, without claiming ledger proof.

    Host41 writes C-export diagnostics to stdout; those records may only be
    available to the supervising process after the worker exits. Therefore this
    function does not synthesize an event ledger from snapshot differences.
    """
    before_exe = _identity(before, 'before')
    after_exe = _identity(after, 'after')
    for name in ('schema', 'source_proof_sha256', 'host_sha256', 'profile', 'owner_thread_id'):
        if before.get(name) != after.get(name):
            raise ValueError(f'Host41 {name} changed across Load')
    if before_exe != after_exe:
        raise ValueError('Host41 process identity changed across Load')
    from civ6_host.runtime.job_registry_snapshot import validate_empty_transition_data
    data = validate_empty_transition_data(before, after)
    return dict(data, schema='civ6rl.native_checkpoint_postload_empty_jobs_transition.v1', source_proof_sha256=jobs.PROOF_SHA256, host_source_sha256=HOST_SOURCE_SHA256)

def reconcile_empty_list_ledger(candidate, events):
    """Post-run reconcile the real ordered C stdout ledger with a candidate.

    This phase is separate because the child may not be able to consume its own
    C stdout records during synchronous Load. A candidate alone is not admission.
    """
    candidate_keys = frozenset(('schema', 'snapshot_structural_candidate', 'ledger_reconciled', 'created_empty_handles_candidate', 'submission_sequence_unchanged', 'groups_unchanged', 'before_and_after_independently_quiescent', 'slot_pointer_identity_compared', 'native_load_success_claimed', 'source_proof_sha256', 'host_source_sha256'))
    if type(candidate) is not dict or set(candidate) != candidate_keys or candidate.get('schema') != 'civ6rl.native_checkpoint_postload_empty_jobs_transition.v1' or (candidate.get('snapshot_structural_candidate') is not True) or (candidate.get('ledger_reconciled') is not False):
        raise ValueError('Expected a fresh structural snapshot candidate')
    if candidate.get('submission_sequence_unchanged') is not True or candidate.get('groups_unchanged') is not True or candidate.get('before_and_after_independently_quiescent') is not True or (candidate.get('slot_pointer_identity_compared') is not False) or (candidate.get('native_load_success_claimed') is not False) or (candidate.get('source_proof_sha256') != jobs.PROOF_SHA256) or (candidate.get('host_source_sha256') != HOST_SOURCE_SHA256):
        raise ValueError('Candidate proof flags or source identity are inconsistent')
    handles = candidate.get('created_empty_handles_candidate')
    if type(handles) is not list or any((type(handle) is not int or not 1 <= handle <= 64 for handle in handles)) or len(handles) != len(set(handles)):
        raise ValueError('Candidate handle list is malformed')
    if type(events) not in (list, tuple) or len(events) > 4096:
        raise ValueError('Host41 event ledger must be a bounded sequence')
    operations = [_ledger_event(event) for event in events]
    creates = [handle for kind, handle in operations if kind == 'create']
    if len(creates) != len(set(creates)):
        raise ValueError('A list handle was created more than once in the interval')
    if sorted(candidate['created_empty_handles_candidate']) != sorted(creates):
        raise ValueError('Empty-list slot changes do not match the Host41 creation ledger')
    return dict(candidate, ledger_reconciled=True, created_empty_handles=sorted(creates), noop_wait_count=sum((1 for event in events if (event.get('stage'), event.get('export')) == NOOP_WAIT)), noop_null_free_count=sum((1 for event in events if (event.get('stage'), event.get('export')) == NOOP_NULL_FREE)), ledger_events_match_snapshot=True, admission_complete=False, ledger_provenance_checked_by_this_function=False, required_ledger_scope='ordered child stdout bounded by Load markers')

def compare_empty_load_transition(before, after, events):
    """Post-run evidence composition, not an admission decision.

    The caller/supervisor must authenticate the ordered stdout interval and
    separately decide whether continuation is permitted.
    """
    return reconcile_empty_list_ledger(validate_quiescent_snapshot_transition(before, after), events)

def _finite_number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f'{name} must be a finite number')
    return float(value)
STDOUT_TRANSPORT_REQUIRED_PROBE_SHA256S = frozenset(('1c21baf4c1fabc9641719357e64a36e0712c367edd1101fce771e6d78f7d40d4', 'd136bd71679d43258008f8a664ec56f66139edbf70ff7218e8486454a590219b', 'bdc0c65f1da14933b9250b111a7db7324cd251525ff8429fb1c49499f237c91e', '61249945f8598d333f1820bae0d15fdf56f5c2a68c448d369ce8a835cdffb544', '5f800786cc64d53957b9b4e04b25c4b86adb787cdb69601755e0348407d5ced3', 'b220981e1d81484cf86905ffc71684bf58f6ce3ade33595acd73bb2717beeb92', '914221fd26e2bf13d8275280ad7883c2df82b5a235d169a1b3add1403611c55b', 'e7cda800cb0723867128b809086e4145a5f24f181e7e4cfb86a138e6500ec383', 'ad38a197568c57f1379f7e5afc6b7f6dd908331a3d9747f3a42ed48bf22c0f24', 'aca73cc2369e3c19aad3ffcd472d151a912848444fb51d65d38d0d3c97d2b299', '77f45b83d1481bf0a403a8375dd4c772a20ebc97d0e594cfaa9f31ad3a160e62', '4aa90d6cc8dfa2bd4a82d0991f1b6f11c99dfff73dc0f86391c52e271cdd980c', '99baab5a333ab4995f2ac411f0b57bb6bb10b7504bb0c6ed070b433e3f29419c', '8b4e8aacbae08c6417b122122994ae746a32e96164003fd84d2f3aaa32b776a9', '3e38f148a1fe0834ae594aa129ceb2d417b150b7fd2dbaed6439d70e5cd0671d', '5c16a29d883e9c5e8670f883abcf9c5e1eb89321dec2c563e3fb196d5c6c928f', 'c728c17a456116d2c61c351034af0f07bafe1cf8ef84ba6c6bf66710bd7e4946', '5fb49a2c619895c3eda5d86b501faa18c23307c98be291206b63efcf8fbb1a28'))

def _validate_stdout_transport_admission(report, trial):
    required = report.get('probe_source_sha256') in STDOUT_TRANSPORT_REQUIRED_PROBE_SHA256S
    if not required and 'stdout_transport' not in trial:
        return
    from civ6_host.runtime.native import native_stdout_transport as transport
    if report.get('native_stdout_transport_evidence_sha256') != transport.SOURCE_SHA256 or report.get('native_stdout_transport_source_sha256') != hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(_historical_module_file(transport)))).read_bytes()).hexdigest():
        raise ValueError('Prospective stdout decoder source pins differ')
    transport.validate_trial_collection(trial)

def _validate_report_size_admission(report, byte_count):
    if type(byte_count) is not int or not 0 < byte_count <= 128 * 1024 * 1024:
        raise ValueError('Probe report is outside the absolute128MiB bound')
    if byte_count <= 64 * 1024 * 1024:
        return
    if type(report) is not dict:
        raise ValueError('Only prospectively collected retained long-round or Save150 reports may exceed64MiB')
    mode = report.get('mode')
    probe_sha = report.get('probe_source_sha256')
    if mode == 'trace-checkpoint-resume-retained150-long-bounded-rounds':
        admitted = probe_sha in ('aca73cc2369e3c19aad3ffcd472d151a912848444fb51d65d38d0d3c97d2b299', '77f45b83d1481bf0a403a8375dd4c772a20ebc97d0e594cfaa9f31ad3a160e62', '4aa90d6cc8dfa2bd4a82d0991f1b6f11c99dfff73dc0f86391c52e271cdd980c', '99baab5a333ab4995f2ac411f0b57bb6bb10b7504bb0c6ed070b433e3f29419c', '8b4e8aacbae08c6417b122122994ae746a32e96164003fd84d2f3aaa32b776a9', '3e38f148a1fe0834ae594aa129ceb2d417b150b7fd2dbaed6439d70e5cd0671d', '5c16a29d883e9c5e8670f883abcf9c5e1eb89321dec2c563e3fb196d5c6c928f', 'c728c17a456116d2c61c351034af0f07bafe1cf8ef84ba6c6bf66710bd7e4946', '5fb49a2c619895c3eda5d86b501faa18c23307c98be291206b63efcf8fbb1a28')
    elif mode == 'trace-checkpoint-resume-retained150-save182':
        admitted = probe_sha in ('77f45b83d1481bf0a403a8375dd4c772a20ebc97d0e594cfaa9f31ad3a160e62', '4aa90d6cc8dfa2bd4a82d0991f1b6f11c99dfff73dc0f86391c52e271cdd980c', '99baab5a333ab4995f2ac411f0b57bb6bb10b7504bb0c6ed070b433e3f29419c', '8b4e8aacbae08c6417b122122994ae746a32e96164003fd84d2f3aaa32b776a9', '3e38f148a1fe0834ae594aa129ceb2d417b150b7fd2dbaed6439d70e5cd0671d', '5c16a29d883e9c5e8670f883abcf9c5e1eb89321dec2c563e3fb196d5c6c928f', 'c728c17a456116d2c61c351034af0f07bafe1cf8ef84ba6c6bf66710bd7e4946', '5fb49a2c619895c3eda5d86b501faa18c23307c98be291206b63efcf8fbb1a28')
    else:
        admitted = mode in ('trace-checkpoint-resume-retained118-long-bounded-rounds', 'trace-checkpoint-resume-retained118-save150') and probe_sha in STDOUT_TRANSPORT_REQUIRED_PROBE_SHA256S
    if not admitted:
        raise ValueError('Only prospectively collected retained long-round or Save150 reports may exceed64MiB')

def _report_event_limit(mode):
    return 400000 if mode in ('trace-checkpoint-resume-retained150-long-bounded-rounds', 'trace-checkpoint-resume-retained118-save150', 'trace-checkpoint-resume-retained150-save182') else 200000

def validate_postrun_report(report_path, *, expected_report_sha256=None):
    """Authenticate the bounded child-output interval before ledger reconciliation.

    This validates report provenance and the diagnostic receipt; it does not
    turn the native status into proof of successful restore or a playable game.
    """
    path = _resolve_resource_path(Path(report_path))
    if not _resolve_resource_path(path).is_file() or _resolve_resource_path(path).stat().st_size > 128 * 1024 * 1024:
        raise ValueError('Probe report is missing or exceeds the absolute128MiB bound')
    raw = _resolve_resource_path(path).read_bytes()
    report_sha = hashlib.sha256(raw).hexdigest()
    if expected_report_sha256 is not None and report_sha != expected_report_sha256:
        raise ValueError('Probe report hash differs from caller pin')
    report = json.loads(raw)
    _validate_report_size_admission(report, len(raw))
    if type(report) is not dict or report.get('schema') != REPORT_SCHEMA or report.get('mode') not in PROBE_MODES:
        raise ValueError('Unexpected checkpoint-load probe report schema/mode')
    if report.get('host_executable_sha256') != jobs.HOST_SHA256:
        raise ValueError('Probe report executable hash is not the pinned Host41 image')
    host_path = report.get('host_executable')
    if type(host_path) is not str or _resolve_resource_path(Path(host_path)).name.lower() != 'civ6rl-native-python.exe':
        raise ValueError('Probe report executable path is not the expected host')
    expected_host = _resolve_resource_path(_resolve_resource_path(Path(_historical_module_file(jobs)))).resolve().parents[1] / 'work/native-script-services-host41/civ6rl-native-python.exe'
    actual_host = _resolve_resource_path(Path(host_path))
    if not _resolve_resource_path(actual_host).is_file() or _resolve_resource_path(actual_host).resolve() != _resolve_resource_path(expected_host).resolve() or hashlib.sha256(_resolve_resource_path(actual_host).read_bytes()).hexdigest() != jobs.HOST_SHA256:
        raise ValueError('Probe report executable path/file does not match pinned Host41')
    probe_sha = report.get('probe_source_sha256')
    if type(probe_sha) is not str or probe_sha not in PROBE_SOURCE_PATHS:
        raise ValueError('Probe source does not match a reviewed report source pin')
    probe_path = _resolve_resource_path(_resolve_resource_path(Path(_historical_module_file(jobs)))).resolve().parents[1] / PROBE_SOURCE_PATHS[probe_sha]
    if not _resolve_resource_path(probe_path).is_file() or hashlib.sha256(_resolve_resource_path(probe_path).read_bytes()).hexdigest() != probe_sha:
        raise ValueError('Probe source does not match the report source pin')
    batches = report.get('batches')
    if type(batches) is not list or len(batches) != 1 or type(batches[0]) is not dict:
        raise ValueError('Expected exactly one supervised batch')
    trials = batches[0].get('trials')
    if type(trials) is not list or len(trials) != 1 or type(trials[0]) is not dict:
        raise ValueError('Expected exactly one supervised child trial')
    trial = trials[0]
    _validate_stdout_transport_admission(report, trial)
    if trial.get('mode') != report['mode'] or trial.get('timed_out') is not False or trial.get('reaped') is not True:
        raise ValueError('Child was not a completed, reaped checkpoint-load-only process')
    if trial.get('supervisor_error') is not None or trial.get('success') is not False:
        raise ValueError('Trial is not the expected controlled diagnostic stop')
    if trial.get('stdout_other') != []:
        raise ValueError('Supervised child produced unparsed stdout records')
    pid = _exact_int(trial.get('pid'), 'child PID', low=1, high=4294967295)
    if type(trial.get('exit_code')) is not int:
        raise ValueError('Child exit code is malformed')
    if trial['exit_code'] not in (89, 90):
        raise ValueError('Trial exit code is outside the source-reviewed Load diagnostics')
    start = _finite_number(trial.get('started_monotonic_seconds'), 'child start')
    end = _finite_number(trial.get('ended_monotonic_seconds'), 'child end')
    if end < start:
        raise ValueError('Child monotonic interval is reversed')
    events = trial.get('events')
    event_limit = _report_event_limit(report.get('mode'))
    if type(events) is not list or len(events) > event_limit:
        raise ValueError('Child event stream is malformed or over budget')
    markers = {}
    marker_indices = {}
    for index, event in enumerate(events):
        if type(event) is not dict:
            raise ValueError('Child event is not an object')
        stage = event.get('stage')
        if stage in ('before_native_checkpoint_load', 'native_checkpoint_load_returned_diagnostic'):
            if stage in markers:
                raise ValueError('Duplicate checkpoint-load boundary marker')
            if event.get('pid') != pid or type(event.get('pid')) is not int:
                raise ValueError('Boundary marker PID differs from the supervised child')
            stamp = _finite_number(event.get('monotonic_seconds'), 'marker timestamp')
            if not start <= stamp <= end:
                raise ValueError('Boundary marker lies outside the child interval')
            markers[stage] = event
            marker_indices[stage] = index
    before_key, after_key = ('before_native_checkpoint_load', 'native_checkpoint_load_returned_diagnostic')
    if set(markers) != {before_key, after_key} or marker_indices[before_key] >= marker_indices[after_key]:
        raise ValueError('Checkpoint-load markers are missing or out of order')
    if _finite_number(markers[before_key]['monotonic_seconds'], 'pre-load marker time') > _finite_number(markers[after_key]['monotonic_seconds'], 'returned marker time'):
        raise ValueError('Checkpoint-load marker timestamps are reversed')
    interval = events[marker_indices[before_key] + 1:marker_indices[after_key]]
    ledger_events = []
    known_exports = {NOOP_WAIT[1], NOOP_NULL_FREE[1], CREATE_LIST[1]}
    job_prefixes = ('job_list_', 'native_job_', 'empty_job_set', 'null_job_list', 'unsupported_executable_export')
    for event in interval:
        stage, export = (event.get('stage'), event.get('export'))
        is_job_event = export is not None or (type(stage) is str and stage.startswith(job_prefixes))
        if not is_job_event:
            continue
        if export not in known_exports:
            raise ValueError('Checkpoint-load interval contains an export outside the narrow Host41 job profile')
        if 'pid' in event or 'monotonic_seconds' in event:
            raise ValueError('Raw Host41 C job records must not carry synthesized PID/time metadata')
        ledger_events.append(event)
    if 'jobs_before' not in markers[after_key] or 'jobs_after' not in markers[after_key]:
        raise ValueError('Returned diagnostic marker lacks both scheduler snapshots')
    before_jobs, after_jobs = (markers[after_key]['jobs_before'], markers[after_key]['jobs_after'])
    if type(markers[after_key].get('jobs_identical')) is not bool or markers[after_key]['jobs_identical'] != (before_jobs == after_jobs) or markers[after_key].get('validation_completed') is not False or (markers[after_key].get('eligible_for_training') is not False):
        raise ValueError('Returned diagnostic job identity/training flags are inconsistent')
    candidate = compare_empty_load_transition(before_jobs, after_jobs, ledger_events)
    if type(markers[after_key].get('native_status')) is not int or markers[after_key]['native_status'] != 0:
        raise ValueError('Native diagnostic status was not zero')
    return dict(schema='civ6rl.native_checkpoint_postload_report_validation.v1', report_sha256=report_sha, pid=pid, mode=report['mode'], host_executable_sha256=jobs.HOST_SHA256, probe_source_sha256=report['probe_source_sha256'], start_monotonic_seconds=start, end_monotonic_seconds=end, marker_order=[before_key, after_key], child_reaped=True, timed_out=False, supervisor_error=None, native_status=0, ledger_order_basis='supervised-child-stdout-order', raw_job_event_timestamps_claimed=False, load_diagnostic_return_observed=True, native_load_success_claimed=False, game_load_or_restore_validated=False, admission_complete=False, transition=candidate)
