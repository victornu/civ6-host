"""Retained source-selected inventory receipts; no engine calls or alternate parser."""
import hashlib
import json
from pathlib import Path

from civ6_host.contracts.placement_inventory import validate as validate_inventory, SCOPE
from civ6_host.runtime.native.native_session_resume import semantic_decisions


def _source_reference(core_sha256=None):
    from civ6_host.runtime.placement_inventory_profile import SOURCE
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
    if core_sha256==XP2_CORE_SHA256:
        from civ6_host.runtime.xp2_placement_inventory_source import SOURCE
    elif core_sha256 not in (None,XP1_CORE_SHA256):
        raise ValueError('Inventory review requires an exact qualified Core identity')
    from civ6_host.runtime.paths import resource_root
    from civ6_host.runtime.resource_resolution import resolve_path
    return str(resolve_path(resource_root() / SOURCE[0]).resolve()), SOURCE[1]


def _pin(path):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest)


def _closing_inventory_boundary(run, closure, public_views, previous_responses, closing_responses, core_sha256):
    """Authenticate a real close response without inventing a client public view."""
    from civ6_host.runtime.native.network_session import xp1_loaded_close_evidence
    from civ6_host.runtime.network_protocol import NetworkProtocol, validate_network_response
    from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
    if len(previous_responses)!=1 or len(closing_responses)!=1:
        raise ValueError('Closing inventory requires one preceding response and one unique native close')
    previous_line, _, previous = previous_responses[0]
    close_line, close_raw, closing = closing_responses[0]
    last_path, last = public_views[max(public_views)]
    sequence=max(public_views)+1
    if (type(closing.get('sequence')) is not int or closing['sequence']!=sequence
            or type(previous.get('sequence')) is not int
            or previous.get('schema')!=NetworkProtocol.schema
            or previous.get('operation') not in ('reset','observe','act','poll')
            or any(previous.get(k)!=last[k] for k in
                   ('episode_id','game_generation','sequence','observation','decisions','applied_action'))
            or previous.get('nonce')!=closure['nonce']
            or closing.get('observation')!=last['observation']
            or type(closing.get('decisions')) is not dict
            or closing['decisions'].get('schema')!=last['decisions']['schema']
            or closing['decisions'].get('placement_inventory')!=last['decisions']['placement_inventory']):
        raise ValueError('Closing inventory response differs from its last actual public boundary')
    report=json.loads((run/'supervisor.json').read_bytes())
    pins=dict(closure['pins']);pins[str((run/'closure.json').resolve())]=_pin(run/'closure.json')['sha256']
    lifetime=xp1_loaded_close_evidence(run,report,pins,core_sha256=core_sha256)
    lines=lifetime['ordered_marker_lines']
    if (close_line!=lines[-2] or not previous_line<lines[0]<close_line
            or report.get('last_sequence')!=sequence):
        raise ValueError('Closing inventory is outside its authenticated native close interval')
    identity=DiagnosticEpisodeIdentity(last['episode_id'],last['game_generation'])
    protocol=NetworkProtocol(identity,closure['nonce'],closure['rounds'],
        initial_turn=closure['initial_turn'],core_sha256=core_sha256)
    protocol.accept_response(previous)
    request={k:closing.get(k) for k in ('schema','nonce','episode_id','game_generation','sequence','operation')}
    request['player_id']=last['observation']['player_id']
    validate_network_response(closing,protocol,'close',request=request)
    return closing, dict(sequence=sequence,operation='close',response_line=close_line,
        response_bytes=len(close_raw),response_sha256=hashlib.sha256(close_raw).hexdigest(),
        transcript=_pin(run/'events.jsonl'),preceding_public=_pin(last_path),
        preceding_native_response_line=previous_line,close_begin_line=lines[0],
        native_lifetime_evidence=lifetime,network_protocol_validated=True,
        unchanged_observation=True,unchanged_inventory=True,client_public_view_fabricated=False)


def validate_inventory_readback(run, public_views, *, core_sha256=None, allow_authenticated_closing=False):
    """Join every native read to its actual public revision; repeat reads may agree."""
    run = Path(run)
    source_path, source_sha = _source_reference(core_sha256)
    closure = json.loads((run / 'closure.json').read_bytes())
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
    if (type(allow_authenticated_closing) is not bool or allow_authenticated_closing
            and (core_sha256!=XP2_CORE_SHA256 or closure.get('input_profile')!='xp2-lan')):
        raise ValueError('Closing inventory review requires its explicit XP2 checkpoint scope')
    if core_sha256 is not None:
        from civ6_host.runtime.captured_session_profile import for_family
        if for_family(closure.get('input_profile')).candidate.core_sha256!=core_sha256:
            raise ValueError('Inventory read selects another captured engine')
        if _pin(source_path)['sha256']!=source_sha:
            raise ValueError('Inventory review source differs from its selected profile')
    if closure['pins'].get(source_path) != source_sha:
        raise ValueError('Inventory source is absent from the actual native closure')
    if not public_views or any(type(s) is not int or s < 0 for s in public_views):
        raise ValueError('Inventory review needs actual public revisions')
    fields = {'stage', 'episode_id', 'game_generation', 'sequence', 'player_id',
              'turn', 'inventory', 'source_proof_sha256', 'host_tracking_used',
              'native_gameplay_mutated'}
    records = {}
    closing_reads=[];previous_responses=[];closing_responses=[]
    event_count = 0
    from civ6_host.runtime.stdout_transport_profiles import session_records
    for line, raw, event in session_records(run):
        if allow_authenticated_closing and event.get('stage')=='official_session_response':
            if event.get('operation')=='close':closing_responses.append((line,raw,event))
            elif event.get('sequence')==max(public_views):previous_responses.append((line,raw,event))
        if event.get('stage') != 'native_placement_inventory_readback':
            continue
        seq = event.get('sequence')
        if (set(event) != fields or type(seq) is not int or seq < 0
                or event['source_proof_sha256'] != source_sha
                or event['host_tracking_used'] is not False
                or event['native_gameplay_mutated'] is not False):
            raise ValueError('Inventory read has an unmatched revision, source or scope')
        if seq not in public_views:
            if not allow_authenticated_closing or seq!=max(public_views)+1:
                raise ValueError('Inventory read has an unmatched revision, source or scope')
            closing_reads.append((line,event));event_count+=1
            continue
        path, view = public_views[seq]
        obs = view['observation']
        if (view['sequence'] != seq
                or any(event[k] != view[k] for k in ('episode_id', 'game_generation'))
                or type(event['player_id']) is not int or event['player_id'] != obs['player_id']
                or type(event['turn']) is not int or event['turn'] != obs['turn']):
            raise ValueError('Inventory read identity differs from its public boundary')
        inventory = event['inventory']
        if inventory is None or inventory != view['decisions']['placement_inventory']:
            raise ValueError('Inventory native result differs from its public copy')
        validate_inventory(inventory, obs['player_id'], obs['turn'], observation=obs)
        payload = {key: event[key] for key in fields - {'stage'}}
        if seq in records:
            if records[seq]['native'] != payload:
                raise ValueError('Repeated inventory reads diverge at the same revision')
            records[seq]['lines'].append(line)
        else:
            records[seq] = dict(sequence=seq, native=payload, lines=[line], public=_pin(path))
        event_count += 1
    if set(records) != set(public_views):
        raise ValueError('A public inventory has no native readback receipt')
    if (allow_authenticated_closing and not closing_reads
            and not (len(closing_responses)==1 and closing_responses[0][2].get('sequence') in public_views)):
        raise ValueError('Native close inventory lacks its distinct readback receipt')
    result=dict(scope=SCOPE, source_proof_sha256=source_sha, event_count=event_count,
                public_revision_count=len(records), records=[records[k] for k in sorted(records)],
                host_tracking_used=False, native_gameplay_mutated=False,
                native_tracking_empty_witness=False)
    if closing_reads:
        closing,evidence=_closing_inventory_boundary(run,closure,public_views,previous_responses,
                                                     closing_responses,core_sha256)
        obs=closing['observation'];payload=None;lines=[]
        for line,event in closing_reads:
            if (not evidence['preceding_native_response_line']<line<evidence['close_begin_line']
                    or any(event[k]!=closing[k] for k in ('episode_id','game_generation','sequence'))
                    or type(event['player_id']) is not int or event['player_id']!=obs['player_id']
                    or type(event['turn']) is not int or event['turn']!=obs['turn']
                    or event['inventory'] is None or event['inventory']!=closing['decisions']['placement_inventory']):
                raise ValueError('Closing inventory read differs from its authenticated close response')
            validate_inventory(event['inventory'],obs['player_id'],obs['turn'],observation=obs)
            copied={key:event[key] for key in fields-{'stage'}}
            if payload is not None and copied!=payload:
                raise ValueError('Repeated closing inventory reads diverge at the same revision')
            payload=copied;lines.append(line)
        result.update(closing_revision_count=1,closing_event_count=len(closing_reads),
            closing_records=[dict(sequence=closing['sequence'],native=payload,lines=lines,
                                 closing_response=evidence)])
    return result


def _inventory_rows(view):
    inv = view['decisions']['placement_inventory']
    if inv is None or inv != view['placement_inventory']:
        raise ValueError('Inventory group lost its complete public inventory copy')
    obs = view['observation']
    validate_inventory(inv, obs['player_id'], obs['turn'], observation=obs)
    return {(r['city_id'], r['category'], r['plot_id']): r for r in inv['rows']}


def _public_by_sequence(row):
    values = row['public']
    if (not values or any(type(v['sequence']) is not int or v['sequence'] < 0 for v in values)
            or len({v['sequence'] for v in values}) != len(values)
            or values[0]['sequence'] != 0):
        raise ValueError('Inventory public revisions are missing or duplicated')
    result = {v['sequence']: v for v in values}
    receipt = row['inventory_receipts']
    if (receipt['scope'] != SCOPE or receipt['host_tracking_used'] is not False
            or receipt['native_gameplay_mutated'] is not False
            or receipt['native_tracking_empty_witness'] is not False
            or receipt['public_revision_count'] != len(result)):
        raise ValueError('Inventory group lacks source-qualified native readbacks')
    seen = set()
    for record in receipt['records']:
        seq = record['sequence']
        if type(seq) is not int or seq not in result or seq in seen:
            raise ValueError('Inventory readbacks do not cover exact public revisions')
        seen.add(seq)
        v = result[seq]
        native = record['native']
        if (native['sequence'] != seq or native['episode_id'] != v['episode_id']
                or native['game_generation'] != v['generation']
                or native['player_id'] != v['observation']['player_id'] or native['turn'] != v['turn']
                or native['inventory'] != v['placement_inventory']
                or native['source_proof_sha256'] != receipt['source_proof_sha256']
                or native['host_tracking_used'] is not False or native['native_gameplay_mutated'] is not False):
            raise ValueError('Inventory group readback differs from its public identity or value')
        _inventory_rows(v)
    if seen != set(result):
        raise ValueError('Inventory readbacks omit a public revision')
    return result


def validate_inventory_group(acceptance, rows):
    """Consume the main reviewer's authenticated command, Save and lifetime rows."""
    if acceptance['status'] != 'native_placement_inventory_checkpoint_reset_verified':
        raise ValueError('Inventory acceptance did not complete its exact client group')
    group = acceptance['inventory_group']
    prep = group['preparation']
    if (len(rows) != 3 or len({r['run'] for r in rows}) != 3
            or [len(r['ledger']['commands']) for r in rows] != [2, 1, 0]
            or any(r['ledger']['updates'] for r in rows)
            or ['checkpoint' in r['ledger'] for r in rows] != [True, False, False]
            or [r['checkpoint_on_close'] for r in rows] != [True, False, False]
            or any(r['normal_native_destroy_authenticated'] is not True
                   or r['all_source_pins_unchanged'] is not True for r in rows)
            or type(group['poll_calls']) is not int or group['poll_calls'] != 0
            or group['native_tracking_empty_witness'] is not False
            or len(prep['steps']) != 2 or type(prep['poll_calls']) is not int or prep['poll_calls'] != 0
            or prep['observation_scope'] != 'host_tracked'
            or any(prep[k] is not False for k in ('completion_witnessed', 'other_category_qualified',
                                                'unobserved_placement_inventory_complete'))):
        raise ValueError('Inventory cycle lacks three clean lifetimes, one Save and zero polls')
    a, b, c = rows
    maps = [_public_by_sequence(r) for r in rows]
    pa, pb, pc = maps
    first, resumed, reset = pa[0], pb[0], pc[0]
    placed, switched = a['ledger']['commands']
    resume = b['ledger']['commands'][0]
    all_commands = [placed, switched, resume]
    if (acceptance['commands'] != [r['command_result'] for r in all_commands]
            or [r['action']['kind'] for r in all_commands] != ['production_placement', 'production', 'production_resume']
            or type(group['turn']) is not int or group['turn'] != first['turn']
            or prep['initial_turn'] != group['turn'] or prep['final_turn'] != group['turn']
            or any(v['turn'] != group['turn'] for mapping in maps for v in mapping.values())
            or any(r['turn_before'] != group['turn'] or r['turn_after'] != group['turn'] for r in all_commands)):
        raise ValueError('Inventory cycle changes its actual commands or native turn')
    action = placed['action']
    key = (action['city_id'], action['category'], action['plot_id'])
    if (action['category'] not in ('district', 'building')
            or any(prep[k] != action[k] for k in ('city_id', 'category', 'plot_id', 'item_type'))
            or group['resume_action'] != resume['action'] or type(group['resume_sequence']) is not int
            or group['resume_sequence'] != resume['protocol_sequence']
            or any(resume['action'][k] != action[k] for k in ('city_id', 'category', 'index', 'hash', 'item_type'))
            or switched['action']['city_id'] != action['city_id'] or switched['action']['hash'] == action['hash']):
        raise ValueError('Inventory cycle does not resume the placed item after actual replacement')
    def state(view):
        return dict(production=next(r for r in view['choice_state']['production'] if r['city_id'] == key[0]),
                    placements=view['placements'], production_queues=view['production_queues'])
    for command, mapping in ((placed, pa), (switched, pa), (resume, pb)):
        seq = command['protocol_sequence']
        if type(seq) is not int or seq not in mapping or not any(s < seq for s in mapping):
            raise ValueError('Inventory command lacks its exact public boundary')
        before = mapping[max(s for s in mapping if s < seq)]
        if (command['command_result']['status'] != 'completed' or command['command_result']['reason'] is not None
                or command['command_result']['requested_action'] != command['action']
                or not any(r['action'] == command['action'] for r in before['candidates'])):
            raise ValueError('Inventory command was not offered and completed natively')
    for step, command in zip(prep['steps'], (placed, switched)):
        seq = command['protocol_sequence']; before = pa[max(s for s in pa if s < seq)]
        if (type(step['sequence']) is not int or step['sequence'] != seq
                or step['action'] != command['action'] or step['command_result'] != command['command_result']
                or step['before'] != state(before) or step['after'] != state(pa[seq])):
            raise ValueError('Inventory preparation differs from the retained public transitions')
    placed_view = pa[placed['protocol_sequence']]
    saved = pa[switched['protocol_sequence']]
    initial_rows, new_rows = _inventory_rows(first), _inventory_rows(placed_view)
    native_row = new_rows.get(key)
    if (key in initial_rows or set(new_rows) != set(initial_rows) | {key}
            or any(new_rows[k] != v for k, v in initial_rows.items()) or native_row is None
            or native_row['complete'] is not False
            or any(native_row[k] != action[k] for k in ('city_id', 'category', 'index', 'hash', 'item_type', 'plot_id', 'x', 'y'))
            or group['native_row'] != native_row
            or any(_inventory_rows(v) != new_rows for v in (saved, resumed, reset, pb[resume['protocol_sequence']]))):
        raise ValueError('Native inventory did not discover and preserve the exact unfinished placement')
    checkpoint = a['ledger']['checkpoint']['phase_receipt']
    reference = checkpoint['manifest_reference']
    if (group['checkpoint'] != reference or acceptance['checkpoints'] != [reference]
            or checkpoint['observed_game_turn'] != group['turn']
            or type(checkpoint['native_save_status']) is not int or checkpoint['native_save_status'] != 0
            or any(checkpoint[k] is not True for k in ('stream_closed', 'public_state_unchanged', 'continuation_not_advanced'))
            or checkpoint['native_load_of_pair_claimed'] is not False):
        raise ValueError('Inventory checkpoint differs from the authenticated native Save')
    expected_ref = {k: reference[k] for k in ('path', 'sha256')}
    for row, public, episode in ((b, resumed, group['resumed_episode']), (c, reset, group['reset_episode'])):
        marker = row['checkpoint_reloaded']
        if (public['episode_id'] != episode or row['checkpoint_input'] != expected_ref
                or public['observation'] != saved['observation']
                or semantic_decisions(public['decisions']) != semantic_decisions(saved['decisions'])
                or type(marker) is not dict or marker.get('checkpoint') != [reference['path'], reference['sha256']]
                or marker.get('turn') != group['turn']
                or any(marker.get(k) is not True for k in ('public_observation_equal', 'public_decisions_equal',
                        'saved_decision_fields_equal', 'identity_rebound'))
                or marker.get('catalogue_transition') is not None
                or marker.get('complete_state_compared') is not False or marker.get('strategic_training_ready') is not False):
            raise ValueError('Inventory Load/reset differs from its actual saved public boundary')
    if (len({v['episode_id'] for v in (first, resumed, reset)}) != 3
            or len({v['generation'] for v in (first, resumed, reset)}) != 3):
        raise ValueError('Inventory Load/reset reused a native lifetime identity')
    p, r = placed['ledger']['phase_receipt'], resume['ledger']['phase_receipt']
    if (p.get('placement_status') != 'completed' or p['effect']['new_placement_verified'] is not True
            or switched['ledger']['phase_receipt'].get('explicit_choice_applied') is not True
            or r.get('placement_status') != 'completed' or r['kind'] != 'production_resume'
            or type(r['progress_before']) is not int or not 0 <= r['progress_before'] <= 0x7fffffff
            or r['progress_before'] != r['progress_after']):
        raise ValueError('Inventory cycle lacks native placement and retained-progress resumption')
    return dict(category=key[1], city_id=key[0], plot_id=key[2], item_type=action['item_type'],
                checkpoint=reference, command_count=3, save_count=1, independent_loads=2, native_lifetimes=3,
                native_inventory_survives_load_and_reset=True, native_tracking_empty_witness=False,
                host_tracking_preserved=True, host_tracking_used_by_inventory=False,
                retained_progress=r['progress_after'], positive_retained_progress_witnessed=r['progress_after'] > 0,
                unfinished_district_witnessed=key[1] == 'district', unfinished_building_witnessed=key[1] == 'building',
                observation_scope=SCOPE, poll_calls=0, turn=group['turn'], completion_qualified=False,
                wonder_qualified=False, complete_hidden_state_compared=False, complete_gameplay_qualified=False)
