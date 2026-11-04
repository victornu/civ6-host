"""Check native job lifecycle witnesses without treating them as game turns."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from collections import Counter

def validate_job_lifecycle(events):
    pending = {}
    submitted = set()
    completed = set()
    active = None
    spawn = None
    spawn_count = 0
    counts = Counter()
    for event in events:
        stage = event.get('stage')
        if stage == 'native_job_queued':
            sequence = event.get('submission_sequence')
            if type(sequence) is not int or sequence != len(submitted) + 1:
                raise ValueError('Missing or reused job submission sequence')
            if spawn is not None:
                raise ValueError('Recursive submission outside the serial diagnostic profile')
            pending[sequence] = (event['handle'], event['job'], event['execute_rva'])
            submitted.add(sequence)
        elif stage == 'native_job_spawn_requested':
            if spawn is not None or active is not None:
                raise ValueError('Overlapping native Spawn calls')
            spawn = (event['handle'], 0)
        elif stage == 'before_native_job_execute':
            sequence = event.get('submission_sequence')
            identity = (event['handle'], event['job'], event['execute_rva'])
            if spawn is None or spawn[0] != event['handle'] or active is not None or (pending.get(sequence) != identity):
                raise ValueError('Native execution has no matching queued job and Spawn')
            if event.get('thread_index') != 0:
                raise ValueError('Worker index outside the explicit diagnostic profile')
            active = sequence
        elif stage == 'native_job_executed':
            sequence = event.get('submission_sequence')
            identity = (event['handle'], event['job'], event['execute_rva'])
            if sequence is None or active != sequence or pending.get(sequence) != identity or (event.get('callback_returned') is not True):
                raise ValueError('Missing, duplicated, or mismatched native callback return')
            if event['execute_rva'] == '0x3d75b0' and event.get('victory_completion_checked') is not True:
                raise ValueError('Victory callback completion byte was not checked')
            del pending[sequence]
            completed.add(sequence)
            counts[event['execute_rva']] += 1
            spawn = (spawn[0], spawn[1] + 1)
            active = None
        elif stage == 'native_job_spawn_completed':
            if spawn is None or active is not None or spawn[0] != event['handle'] or (spawn[1] != event['native_jobs_executed']):
                raise ValueError('Spawn completion disagrees with its native callback returns')
            spawn = None
            spawn_count += 1
    return {'submitted_jobs': len(submitted), 'returned_native_callbacks': len(completed), 'completed_spawn_calls': spawn_count, 'execute_rva_counts': dict(sorted(counts.items())), 'pending_submission_sequences': sorted(pending), 'in_flight_submission_sequence': active, 'spawn_still_active': spawn is not None, 'all_submitted_jobs_returned': bool(submitted) and (not pending) and (active is None) and (spawn is None), 'native_thread_schedule_equivalence_validated': False, 'played_turns_proven_by_this_check': 0, 'eligible_for_training': False}
