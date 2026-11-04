"""Pure reconciliation of one authentic XP1 action interval.

The caller authenticates transcript boundaries, source pins and supervision.
This helper never loads a DLL and does not turn a callback return into an action
effect or a scheduling-equivalence claim. Its C ledger format is the shared
source-pinned scheduler, not a list of permitted GameCore task subclasses.
"""
import re

from civ6_host.runtime.saved_load_job_observer import require_quiescent
from civ6_host.runtime.native.native_job_evidence import validate_job_lifecycle
from civ6_host.runtime.native.native_checkpoint_postload_jobs import _ledger_event

UINT64_MAX = (1 << 64) - 1
SERIAL = 'diagnostic_serial_native_callbacks'


def _int(value, label, low=0, high=UINT64_MAX):
    if type(value) is not int or not low <= value <= high:
        raise ValueError('Invalid ' + label)
    return value


def _fields(row, names):
    if set(row) != set(names.split()):
        raise ValueError('Unknown/missing fields in ' + str(row.get('stage')))


def _words(value, size):
    if type(value) is not list or len(value) != size:
        raise ValueError('Malformed native word vector')
    for word in value:
        _int(word, 'native word')


def _rva(value):
    if type(value) is not str or not re.fullmatch(r'0x[0-9a-f]+', value):
        raise ValueError('Malformed execute RVA')
    return _int(int(value, 16), 'execute RVA', 1)


def _canonical(value):
    return ((_int(value, 'raw handle', 1) - 1) & 0xffffffff) + 1


def reconcile_action_jobs(before, after, events, *, victory_execute_rva):
    """Reconcile actual snapshots plus the bounded C records BETWEEN them.

    ``victory_execute_rva`` must come from the selected engine's pinned source
    profile. It is a completion-byte assertion, never a callback allowlist.
    Absolute submission sequences are checked before a copied lifecycle stream
    is rebased for the existing validator; original evidence is left untouched.
    """
    require_quiescent(before)
    require_quiescent(after)
    mutable = {'submission_sequence', 'slots', 'groups'}
    if ({k: v for k, v in before.items() if k not in mutable}
            != {k: v for k, v in after.items() if k not in mutable}):
        raise ValueError('Scheduler owner/source/process identity changed')
    core = before.get('core_identity')
    exe = before.get('current_executable')
    build = before.get('source_build')
    if (type(core) is not dict or type(exe) is not dict or type(build) is not dict
            or before.get('host_sha256') != build.get('host_sha256')
            or before.get('owner_thread_id') != exe.get('os_thread_id')):
        raise ValueError('Incomplete scheduler source/process identity')
    core_base = _int(core.get('base'), 'Core base', 1)
    _int(before.get('owner_thread_id'), 'owner thread', 1, 0xffffffff)
    _int(victory_execute_rva, 'profile victory execute RVA', 1)
    start, end = before['submission_sequence'], after['submission_sequence']
    if end < start:
        raise ValueError('Native submission sequence regressed')
    if type(events) not in (list, tuple) or len(events) > 4096:
        raise ValueError('Expected bounded authentic interval job records')

    occupied = {s['handle'] for s in before['slots'] if s['occupied']}
    old_groups = {g['owner']: g['pointer'] for g in before['groups']}
    new_groups = {g['owner']: g['pointer'] for g in after['groups']}
    allocations = []
    group_observations = []
    group_count = len(old_groups)
    destroyed = waited = noops = observed_count = 0
    created = []
    freed = []
    queued = {}
    active = None
    spawn = None
    observed = None
    sequence = start
    normalized = []
    alias_count = 0

    for row in events:
        if type(row) is not dict or type(row.get('stage')) is not str:
            raise ValueError('Malformed native job record')
        stage = row['stage']
        # Push emits these two records synchronously, without a native callback.
        if observed is not None and stage != 'native_job_queued':
            raise ValueError('Native submission observation has no matching queue record')
        if stage == 'native_job_submission_observed':
            _fields(row, 'stage handle job job_set readable job_words vtable_slots set_words descriptor_words executed')
            if spawn is not None or row['readable'] is not True or row['executed'] is not False:
                raise ValueError('Unreadable/recursive native submission')
            handle = _canonical(row['handle'])
            if handle not in occupied:
                raise ValueError('Submission uses an inactive list')
            for key, length in (('job_words', 5), ('vtable_slots', 2), ('set_words', 2), ('descriptor_words', 2)):
                _words(row[key], length)
            for key in ('job', 'job_set'):
                _int(row[key], key, 1)
            first, second = row['set_words']
            if (row['job_words'][1:3] != [0, 0]
                    or (second and second != first)):
                raise ValueError('Submission is not the native unqueued ownership contract')
            observed = row
            observed_count += 1
            if first == 0:
                allocations.append(row['job_set'])
                group_count += 1
            else:
                group_observations.append((row['job_set'], first))
        elif stage == 'native_job_queued':
            _fields(row, 'stage handle job job_set execute_rva profile executed submission_sequence native_scheduling_cadence_verified')
            _int(row['handle'], 'canonical queue handle', 1, 64)
            _int(row['submission_sequence'], 'submission sequence', 1)
            if (observed is None or row['submission_sequence'] != sequence + 1
                    or row['submission_sequence'] > end or row['handle'] != _canonical(observed['handle'])
                    or row['job'] != observed['job'] or row['job_set'] != observed['job_set']
                    or row['profile'] != SERIAL or row['executed'] is not False
                    or row['native_scheduling_cadence_verified'] is not False
                    or core_base + _rva(row['execute_rva']) != observed['vtable_slots'][1]
                    or any(q['job'] == row['job'] for q in queued.values())):
                raise ValueError('Queue record differs from the actual submission/sequence/Core callback')
            sequence += 1
            queued[sequence] = row
            observed = None
            normalized.append(dict(row, submission_sequence=sequence-start))
        elif stage == 'native_job_spawn_requested':
            _fields(row, 'stage handle core_base stack_pointers executed')
            handle = _canonical(row['handle'])
            if (spawn is not None or handle not in occupied or row['core_base'] != core_base
                    or type(row['core_base']) is not int or row['executed'] is not False):
                raise ValueError('Overlapping/foreign native Spawn')
            if type(row['stack_pointers']) is not list or len(row['stack_pointers']) > 12:
                raise ValueError('Malformed Spawn stack')
            for p in row['stack_pointers']:
                _int(p, 'stack pointer', 1)
            spawn = handle
            alias_count += row['handle'] != handle
            normalized.append(dict(row, handle=handle))
        elif stage in ('before_native_job_execute', 'native_job_executed'):
            if stage == 'before_native_job_execute':
                _fields(row, 'stage handle execute_rva thread_index submission_sequence job')
                if type(row['thread_index']) is not int or row['thread_index'] != 0:
                    raise ValueError('Non-serial worker index')
            else:
                _fields(row, 'stage handle execute_rva callback_returned victory_completion_checked submission_sequence job profile eligible_for_training')
                if (row['callback_returned'] is not True or row['profile'] != SERIAL
                        or row['eligible_for_training'] is not False
                        or row['victory_completion_checked'] is not (_rva(row['execute_rva']) == victory_execute_rva)):
                    raise ValueError('Callback return/completion contract differs')
            seq = _int(row['submission_sequence'], 'execution sequence', start+1, end)
            _int(row['handle'], 'execution handle', 1, 64)
            _int(row['job'], 'execution job', 1)
            task = queued.get(seq)
            if task is None or spawn != row['handle'] or any(task[k] != row[k] for k in ('handle', 'job', 'execute_rva')):
                raise ValueError('Native execution has no matching outstanding submission')
            if stage == 'before_native_job_execute':
                if active is not None:
                    raise ValueError('Overlapping native execution')
                # C pops a list FIFO; the shared validator separately checks Spawn.
                if seq != min(k for k, q in queued.items() if q['handle'] == spawn):
                    raise ValueError('Native execution differs from list FIFO order')
                active = seq
            else:
                if active != seq:
                    raise ValueError('Native callback return lacks its invocation')
                del queued[seq]
                active = None
            normalized.append(dict(row, submission_sequence=seq-start))
        elif stage == 'native_job_spawn_completed':
            _fields(row, 'stage handle native_jobs_executed eligible_for_training')
            _int(row['handle'], 'completed Spawn handle', 1, 64)
            _int(row['native_jobs_executed'], 'completed Spawn count', 0, 1024)
            if (spawn != row['handle'] or active is not None or row['eligible_for_training'] is not False
                    or any(q['handle'] == spawn for q in queued.values())):
                raise ValueError('Spawn returned with pending work or another list')
            spawn = None
            normalized.append(dict(row))
        elif stage == 'job_list_created':
            _fields(row, 'stage export handle')
            _int(row['handle'], 'created handle', 0, 64)
            handle = row['handle']
            if (row['export'] != 'EXP_JobManager_CreateJobList' or spawn is not None
                    or (handle == 0 and len(occupied) != 64) or handle in occupied):
                raise ValueError('List creation disagrees with registry occupancy')
            if handle:
                occupied.add(handle)
                created.append(handle)
            else:
                noops += 1
        elif stage in ('job_list_freed', 'job_list_free_ignored'):
            if row.get('export') != 'EXP_JobManager_FreeJobList' or spawn is not None:
                raise ValueError('Wrong/recursive FreeJobList')
            handle = _canonical(row.get('handle'))
            if stage == 'job_list_freed':
                _fields(row, 'stage export handle canonical_handle queued_jobs')
                if (type(row['canonical_handle']) is not int or row['canonical_handle'] != handle
                        or handle not in occupied or type(row['queued_jobs']) is not int or row['queued_jobs'] != 0
                        or any(q['handle'] == handle for q in queued.values())):
                    raise ValueError('Freed list is inactive or has pending jobs')
                occupied.remove(handle)
                freed.append(handle)
            else:
                _fields(row, 'stage export handle reason')
                expected = 'out_of_range' if handle > 64 else 'inactive' if handle not in occupied else None
                if expected is None or row['reason'] != expected:
                    raise ValueError('Ignored free disagrees with actual slot')
                noops += 1
        elif stage in ('native_job_set_destroyed', 'native_job_set_wait_completed'):
            _fields(row, 'stage pending_jobs profile')
            if (spawn is not None or type(row['pending_jobs']) is not int or row['pending_jobs'] != 0
                    or row['profile'] != SERIAL or group_count <= 0):
                raise ValueError('Malformed/recursive owned group completion')
            if stage == 'native_job_set_destroyed':
                group_count -= 1
                destroyed += 1
            else:
                waited += 1
        elif stage == 'empty_job_set_destroyed':
            _fields(row, 'stage export first_argument_raw member0 member8 contract')
            _int(row['first_argument_raw'], 'empty job set address', 1)
            if (row['export'] != 'EXP_JobManager_DestroyJobSet' or row['contract'] != 'two_null_members_only'
                    or type(row['member0']) is not int or row['member0'] != 0
                    or type(row['member8']) is not int or row['member8'] != 0):
                raise ValueError('Malformed empty group destruction')
            noops += 1
        elif stage in ('null_job_list_freed', 'empty_job_set_waited'):
            if stage == 'null_job_list_freed' and spawn is not None:
                raise ValueError('Recursive FreeJobList')
            if _ledger_event(row)[0] != 'noop':
                raise ValueError('Non-noop in empty export contract')
            noops += 1
        else:
            raise ValueError('Unknown or refused job record: ' + stage)

    if observed is not None or queued or active is not None or spawn is not None or sequence != end:
        raise ValueError('Interval has missing/in-flight submissions or differs from final sequence')
    if occupied != {s['handle'] for s in after['slots'] if s['occupied']}:
        raise ValueError('List ledger differs from final occupied slots')
    if group_count != len(new_groups):
        raise ValueError('Group allocation/destruction count differs from final snapshot')
    # The existing C destruction records omit group identity. Preserve this
    # evidence limit instead of manufacturing exact per-pointer free receipts.
    allocated_owners = set(allocations)
    if (set(new_groups) - set(old_groups)) - allocated_owners:
        raise ValueError('Final group owner has no native allocation')
    for owner, pointer in new_groups.items():
        if owner in old_groups and owner not in allocated_owners and pointer != old_groups[owner]:
            raise ValueError('Existing group pointer changed without a native allocation')
    if len(set(old_groups) - set(new_groups)) > destroyed:
        raise ValueError('Removed groups lack native destruction records')
    for owner, pointer in group_observations:
        if owner not in allocated_owners and old_groups.get(owner) != pointer:
            raise ValueError('Observed reused group has no matching initial owner')

    lifecycle = validate_job_lifecycle(normalized)
    if (lifecycle['submitted_jobs'] != end-start or lifecycle['returned_native_callbacks'] != end-start
            or lifecycle['pending_submission_sequences'] or lifecycle['in_flight_submission_sequence'] is not None
            or lifecycle['spawn_still_active'] or (end > start and not lifecycle['all_submitted_jobs_returned'])):
        raise ValueError('Shared native job lifecycle is incomplete')
    return dict(schema='civ6_host.action_job_interval_reconciliation.v1',
        source_proof_sha256=before['source_proof_sha256'], source_build=build,
        core_identity=core, first_submission_sequence=start+1 if end>start else None,
        last_submission_sequence=end if end>start else None, submission_counter_before=start,
        submission_counter_after=end, submission_observation_count=observed_count,
        sequence_rebase_offset=start, lifecycle=lifecycle, no_submitted_jobs=end==start,
        before_and_after_independently_quiescent=True, ledger_events_match_snapshot=True,
        created_handles=created, freed_handles=freed, created_group_count=len(allocations),
        destroyed_group_count=destroyed, completed_group_waits=waited, noop_records=noops,
        canonicalized_spawn_alias_count=alias_count,
        group_pointer_history_authenticated=False,
        group_identity_limit='C wait/destruction records omit identities; counts and observed boundary owners are reconciled, not a per-pointer destruction ledger.',
        ledger_provenance_checked_by_this_function=False,
        native_thread_schedule_equivalence_validated=False, action_effect_validated=False,
        public_runtime_admitted=False, eligible_for_training=False)
