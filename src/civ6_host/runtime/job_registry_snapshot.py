"""Shared strict read-only registry walker, extracted without relaxing checks.

Caller must authenticate its native executable, layout and exclusive owner entry.
It returns actual structures, never host/profile identities or success claims.
"""
import struct
UINT64_MAX = (1 << 64) - 1
GROUP_MAGIC = 4848501265015980593
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

def capture_registry(read, addresses, current_thread_id, *, max_items=4096, max_groups=4096):
    _positive_int(current_thread_id, 'actual Win32 thread ID', 4294967295)
    _positive_int(max_items, 'max_items', 65536)
    _positive_int(max_groups, 'max_groups', 65536)
    expected={'free_head','slots','active_head','lock','runtime_thread','spawn_active','groups','submission_sequence'}
    if type(addresses) is not dict or set(addresses)!=expected:
        raise ValueError('Exact registry address map required')
    for name,address in addresses.items():
        _positive_int(address,name)
    observed = {}

    def take(address, size):
        raw = _read_exact(read, address, size)
        key = (address, size)
        if key in observed and observed[key] != raw:
            raise ValueError('Host job memory changed during capture')
        observed[key] = raw
        return raw

    def glob(name, code):
        return struct.unpack(code, take(addresses[name], struct.calcsize(code)))[0]
    native_thread = glob('runtime_thread', '<I')
    if native_thread != current_thread_id:
        raise ValueError('Checkpoint caller is not the native job owner thread')
    if glob('spawn_active', '<I') != 0 or glob('lock', '<Q') != 0:
        raise ValueError('Host jobs are executing or registry lock is not admitted')
    free_head, active_head = (glob('free_head', '<Q'), glob('active_head', '<Q'))
    group_head = glob('groups', '<Q')
    submission_sequence = glob('submission_sequence', '<Q')
    table = addresses['slots']
    raw_slots = take(table, 64 * 32)
    slots = [struct.unpack_from('<QQQB7x', raw_slots, i * 32) for i in range(64)]

    def slot_index(pointer):
        if not table <= pointer < table + 64 * 32 or (pointer - table) % 32:
            raise ValueError('List chain points outside the real64 slots')
        return (pointer - table) // 32
    membership = set()
    for head, occupied in ((active_head, 1), (free_head, 0)):
        pointer = head
        while pointer:
            index = slot_index(pointer)
            if index in membership or slots[index][3] != occupied:
                raise ValueError('Cyclic/duplicate or inconsistent active/free list')
            membership.add(index)
            pointer = slots[index][2]
    if len(membership) != 64:
        raise ValueError('Active/free chains do not cover all64 slots')
    groups, owners = ({}, {})
    pointer = group_head
    while pointer:
        if pointer % 8 or pointer in groups or len(groups) >= max_groups:
            raise ValueError('Invalid, cyclic or over-budget owned job group')
        next_group, magic, owner, pending = struct.unpack('<4Q', take(pointer, 32))
        if magic != GROUP_MAGIC or not owner or owner % 8 or (owner in owners):
            raise ValueError('Invalid or duplicate owned job group identity')
        if pending > max_items:
            raise ValueError('Group pending count exceeds diagnostic item budget')
        groups[pointer] = dict(pointer=pointer, owner=owner, pending=pending)
        owners[owner] = pointer
        pointer = next_group
    items_seen, sequences, jobs, counts = (set(), set(), set(), {p: 0 for p in groups})
    output = []
    for index, (head, tail, next_slot, occupied) in enumerate(slots):
        if occupied not in (0, 1) or (not occupied and head):
            raise ValueError('Invalid occupancy or pending jobs in a free slot')
        items, pointer, last = ([], head, table + index * 32)
        while pointer:
            if pointer % 8 or pointer in items_seen or len(items_seen) >= max_items:
                raise ValueError('Invalid, cyclic, shared or over-budget job node')
            items_seen.add(pointer)
            node_next, job, job_set, descriptor0, descriptor1, execute, seq = struct.unpack('<7Q', take(pointer, 56))
            if not job or not execute or job in jobs or (job_set not in owners) or (not 1 <= seq <= submission_sequence) or (seq in sequences):
                raise ValueError('Invalid or duplicate queued job identity/sequence')
            jobs.add(job)
            sequences.add(seq)
            counts[owners[job_set]] += 1
            items.append(dict(node=pointer, job=job, job_set=job_set, descriptor_words=[descriptor0, descriptor1], execute=execute, submission_sequence=seq))
            last, pointer = (pointer, node_next)
        if tail != last:
            raise ValueError('Slot tail is not the address of the final next field')
        output.append(dict(handle=index + 1, occupied=bool(occupied), count=len(items), items=items))
    if any((counts[p] != item['pending'] for p, item in groups.items())):
        raise ValueError('Group pending counts disagree with all64 queues')
    for (address, size), expected in observed.items():
        if _read_exact(read, address, size) != expected:
            raise ValueError('Host job memory changed before snapshot completion')
    return dict(owner_thread_id=native_thread, spawn_active=0, registry_lock_raw=0, submission_sequence=submission_sequence, slots=output, groups=list(groups.values()), pending_items=len(items_seen), stable_read=True, concurrent_scheduler_supported=False, memory_modified=False, native_methods_called=False)


def validate_empty_transition_data(before,after):
    if before.get('stable_read') is not True or after.get('stable_read') is not True:
        raise ValueError('Both scheduler observations must be stable')
    if before['submission_sequence'] != after['submission_sequence']:
        raise ValueError('Submission sequence changed; job execution is outside this profile')
    if before.get('groups') != after.get('groups'):
        raise ValueError('Job-group identity changed; group lifecycle is outside this profile')
    if len(before['slots']) != 64 or len(after['slots']) != 64:
        raise ValueError('Expected all64 scheduler slots')
    observed_creates = []
    for i, (old, new) in enumerate(zip(before['slots'], after['slots'], strict=True), 1):
        if old.get('handle') != i or new.get('handle') != i:
            raise ValueError('Slot identity/order is malformed')
        if old.get('count') != 0 or new.get('count') != 0 or old.get('items') != [] or (new.get('items') != []):
            raise ValueError('Only empty scheduler slots are admitted')
        old_occ, new_occ = (old.get('occupied'), new.get('occupied'))
        if type(old_occ) is not bool or type(new_occ) is not bool:
            raise ValueError('Slot occupancy is malformed')
        if old_occ is False and new_occ is True:
            observed_creates.append(i)
        elif old_occ != new_occ:
            raise ValueError('Slot was freed or changed occupancy outside the first profile')
    return dict(snapshot_structural_candidate=True,ledger_reconciled=False,
                created_empty_handles_candidate=sorted(observed_creates),
                submission_sequence_unchanged=True,groups_unchanged=True,
                before_and_after_independently_quiescent=True,
                slot_pointer_identity_compared=False,native_load_success_claimed=False)
