"""Authenticate shared unit attack receipts; no native calls or combat rules."""


def replay_reset_combat_information(run, sidecar):
    """Reconstruct a cached client query from the retained native reset only.

    This is a replay of the public Python API, never a third live query or a
    new native response. The caller first authenticates the complete lifetime.
    """
    import copy
    import hashlib
    import json
    from pathlib import Path
    from types import SimpleNamespace
    from civ6_host import SessionClient
    from civ6_host.runtime.information_store import InformationStore
    from civ6_host.runtime.stdout_transport_profiles import session_records
    from civ6_host.runtime.xp1_unit_attack_profile import precision_reference
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
    from unit_attack_preparation import combat_information_snapshot
    run=Path(run);records=list(session_records(run))
    resets=[(line,raw,event) for line,raw,event in records
            if event.get('stage')=='official_session_response' and event.get('operation')=='reset']
    witnesses=[(line,raw,event) for line,raw,event in records
               if event.get('stage')=='native_combat_administrative_readback' and event.get('sequence')==0]
    if (len(resets)!=1 or len(witnesses)!=1 or witnesses[0][2]!=sidecar
            or witnesses[0][0]>=resets[0][0] or resets[0][2]['sequence']!=0):
        raise ValueError('Combat information replay lacks its unique retained native reset/sidecar0')
    line,raw,response=resets[0];source=precision_reference(XP2_CORE_SHA256)[1]
    store=InformationStore({'combat':source});calls=[]
    def reset():
        if calls:raise ValueError('Combat boundary replay cannot reset twice')
        calls.append('retained_reset');store.ingest(sidecar);store.ingest(response)
        return copy.deepcopy(response)
    def administrative(group,boundary):
        calls.append('cached_administrative_read')
        if group!='combat':raise ValueError('Combat boundary replay does not expose another group')
        return store.read(group,boundary)
    def refuse(*args):raise ValueError('Combat information replay cannot execute a native request')
    client=SessionClient(SimpleNamespace(reset=reset,read_administrative=administrative,
                                        request=refuse,abort=refuse),allow_administrative=True)
    view=client.reset();public_path=run/'public-0000.json'
    if view!=json.loads(public_path.read_bytes()):
        raise ValueError('Combat information replay differs from the retained public reset')
    query=combat_information_snapshot(client,view)
    if calls!=['retained_reset','cached_administrative_read']:
        raise ValueError('Combat boundary replay performed an unexpected operation')
    def reference(path):
        data=path.read_bytes();return dict(path=str(path.resolve()),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
    return dict(classification='reconstructed_client_information_query_from_retained_native_reset',
        query=query,live_query_executed=False,native_calls_during_replay=False,
        native_response_fabricated=False,original_files_modified=False,
        client_api='SessionClient.information',administrative_store='InformationStore',
        public_reset=reference(public_path),transcript=reference(run/'events.jsonl'),
        reset_response_line=line,reset_response_record_sha256=hashlib.sha256(raw).hexdigest(),
        sidecar_line=witnesses[0][0],sidecar_record_sha256=hashlib.sha256(witnesses[0][1]).hexdigest(),
        core_sha256=XP2_CORE_SHA256,source_sha256=source,operations=calls)


def combat_readbacks(run,public_views,*,core_sha256=None):
    """Authenticate raw sidecars against public projection at each revision."""
    from pathlib import Path
    import json
    from civ6_host.contracts.information import validate_administrative
    from civ6_host.runtime.xp1_unit_attack_profile import precision_reference
    from civ6_host.runtime.paths import resource_root
    from civ6_host.runtime.resource_resolution import resolve_path
    run=Path(run);closure=json.loads((run/'closure.json').read_bytes())
    from civ6_host.runtime.captured_session_profile import for_family
    selected=for_family(closure['input_profile']).candidate.core_sha256
    if core_sha256 is not None and selected!=core_sha256:
        raise ValueError('Combat readback closure selects another engine')
    PUBLIC_PRECISION_SOURCE=precision_reference(selected)
    source=str(resolve_path(resource_root()/PUBLIC_PRECISION_SOURCE[0]).resolve())
    if closure['pins'].get(source)!=PUBLIC_PRECISION_SOURCE[1]:
        raise ValueError('Combat precision source is not pinned in the native closure')
    seen={}
    from civ6_host.runtime.stdout_transport_profiles import session_records
    for line_number,raw,event in session_records(run):
        if event.get('stage')!='native_combat_administrative_readback':continue
        seq=event.get('sequence')
        if type(seq) is not int or seq not in public_views:
            raise ValueError('Combat sidecar has no matching public revision')
        view=public_views[seq][1]
        validate_administrative('combat',event,view,PUBLIC_PRECISION_SOURCE[1])
        if seq in seen and seen[seq]!=event:
            raise ValueError('Combat sidecars diverge at the same revision')
        seen[seq]=event
    expected={seq for seq,(_,v) in public_views.items() if v['decisions'].get('unit_attacks') is not None}
    if set(seen)!=expected:raise ValueError('Public combat projection lacks its exact raw native witness')
    return seen


def validate_native_attack(result,interval,loaded_jobs,*,transport,core_sha256=None):
    from civ6_host.runtime.native import native_saved_combat as combat
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
    from civ6_host.runtime.xp1_unit_attack_profile import source_reference, selected_queued_proof
    from civ6_host.runtime.xp1_action_job_ledger import reconcile_action_jobs
    from qualify_xp1_configuration import saved_load_review_profile
    core_sha256=XP1_CORE_SHA256 if core_sha256 is None else core_sha256
    selected=saved_load_review_profile(core_sha256);SOURCE=source_reference(core_sha256)
    action=result['action'];before=result['observation_before'];after=result['observation_after']
    combat.validate_action(action,before['width'],before['height'])
    effect=result['effect']
    if (result['jobs_before']!=loaded_jobs or result['game_update_called'] is not False
            or any(before[k]!=after[k] for k in ('player_id','turn','width','height'))
            or type(effect) is not dict or set(effect)!={'status','refusal_code','observation','receipt'}
            or effect['status']!='completed' or effect['refusal_code'] is not None
            or effect['observation']!=after):
        raise ValueError('Unit attack lost its actual same-turn result boundary')
    receipt=effect['receipt'];rows=interval['commands']
    fields={'action','effect','observation_before','observation_after','automatic_choices_applied',
            'native_defender_selection','source_proof_sha256','city_target_source_sha256'}
    emitted=[r for r in rows if r['stage']=='official_explicit_unit_attack_effect']
    reads=[r for r in rows if r['stage']=='official_explicit_unit_attack_readback']
    if (type(receipt) is not dict or set(receipt)!=fields or len(emitted)!=1 or len(reads)!=1
            or emitted[0]!={'stage':'official_explicit_unit_attack_effect',**receipt}
            or receipt['action']!=action or receipt['observation_before']!=before
            or receipt['observation_after']!=after or receipt['automatic_choices_applied'] is not False
            or receipt['native_defender_selection'] is not True or receipt['source_proof_sha256']!=SOURCE[1]
            or receipt['city_target_source_sha256'] not in (None,SOURCE[1])):
        raise ValueError('Unit attack differs from its source-selected native effect')
    read=reads[0]
    QUEUED_SHA=selected_queued_proof('base-unused',core_sha256)
    if (read['action']!=action or read['observation_before']!=before or read['observation_after']!=after
            or read['queued_source_sha256']!=QUEUED_SHA
            or read['native_defender_selection'] is not True or read['effect_verified'] is not False):
        raise ValueError('Unit attack lost its independent native readbacks')
    combat.validate_relationships(read['relationships'],player_id=before['player_id'])
    expected=combat.effect(before,after,read['own_units_before'],read['own_units_after'],action,
        player_id=before['player_id'],cities_before=receipt['effect']['visible_cities_before'],
        cities_after=receipt['effect']['visible_cities_after'],queued_before=read['queued_before'],
        queued_after=read['queued_after'],core_sha256=core_sha256)
    if expected!=receipt['effect']:
        raise ValueError('Unit attack effect differs from its actual visible/own-unit readbacks')
    stages=['native_command_archive_queued','native_command_received_in_core_queue',
            'before_native_command_queue_drain','native_command_queue_drained',
            'official_explicit_unit_attack_readback','official_explicit_unit_attack_effect']
    if [r['stage'] for r in rows if r['stage'] in stages]!=stages:
        raise ValueError('Unit attack lost its single native archive and effect ordering')
    delivered=transport(rows,before['player_id'],core_sha256=core_sha256)
    if len(delivered['delivered_archives'])!=1 or delivered['completion_echo_archives']:
        raise ValueError('Unit attack did not deliver exactly one captured native archive')
    jobs=reconcile_action_jobs(result['jobs_before'],result['jobs_after'],interval['jobs'],
                               victory_execute_rva=selected['job']['execute_rva'])
    return dict(jobs=jobs,native_unit_attack_delivered=True,source_proof_sha256=SOURCE[1],
        archive_hex=delivered['delivered_archives'][0],action=action,effect=expected,
        selected_defender_claimed=False,death_or_capture_inferred_from_absence=False,
        same_save_official_transition_compared=False)


def validate_public_attack(result,previous,current,phase_receipt):
    action=result['action'];state=previous['decisions']['unit_attacks']
    if (previous['observation']!=result['observation_before']
            or current['observation']!=result['observation_after'] or state is None
            or action not in state['offers']
            or not any(r['action']==action for r in previous['decisions']['candidates'])
            or phase_receipt.get('native_unit_attack_delivered') is not True):
        raise ValueError('Unit attack lost its actual offered public input/result')
    receipt=result['effect']['receipt'];native=receipt['effect']
    if (native['actor_before'] not in state['units']
            or native['selected_defender_claimed'] is not False
            or native['death_or_capture_inferred_from_absence'] is not False):
        raise ValueError('Unit attack public state differs or infers a hidden defender/death')


def validate_information_query(query,view,*,core_sha256=None):
    from civ6_host.contracts.information import validate_administrative,project
    from civ6_host.runtime.xp1_unit_attack_profile import precision_reference
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
    public,admin=query['public'],query['administrative']
    response=dict(episode_id=view['episode_id'],game_generation=view['generation'],
        sequence=view['sequence'],observation=view['observation'],decisions=view['decisions'])
    expected=dict(episode_id=response['episode_id'],game_generation=response['game_generation'],
        player_id=view['observation']['player_id'],sequence=view['sequence'],turn=view['observation']['turn'],
        native_decision_id=view['decisions']['decision_id'])
    if (public['channel']!='public' or admin['channel']!='administrative'
            or public['group']!='combat' or admin['group']!='combat'
            or any(public[k]!=value or admin[k]!=value for k,value in expected.items())
            or public['source_contracts']!=admin['source_contracts']
            or public['data']!=project('combat',view['observation'],view['decisions'])):
        raise ValueError('Combat information query differs from its reviewed public response')
    selected=XP2_CORE_SHA256 if core_sha256 is None else core_sha256
    validate_administrative('combat',admin['data'],response,precision_reference(selected)[1])


def validate_attack_group(acceptance,rows,*,core_sha256=None,information_query_replay=None):
    query_provenance=None
    if (len(rows)!=2 or [len(r['ledger']['commands']) for r in rows]!=[1,0]
            or any(r['ledger']['updates'] for r in rows)):
        raise ValueError('Attack group requires one native attack and one fresh reset, without polls')
    first,fresh=rows[0]['public'][0],rows[1]['public'][0]
    command=rows[0]['ledger']['commands'][0]
    from civ6_host.runtime.native.native_session_resume import semantic_decisions
    if (command['action']['kind']!='unit_attack'
            or acceptance['commands']!=[command['command_result']]
            or command['command_result']['status']!='completed'
            or first['observation']!=fresh['observation']
            or semantic_decisions(first['decisions'])!=semantic_decisions(fresh['decisions'])):
        raise ValueError('Attack group lost its exact command or reset public state')
    if core_sha256 is not None:
        from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
        if core_sha256==XP2_CORE_SHA256:
            query_provenance=['recorded_live_client_query','recorded_live_client_query',
                'reconstructed_client_replay' if information_query_replay is not None else 'recorded_live_client_query']
            queries=acceptance.get('combat_information')
            expected=[rows[0]['public'][0],rows[0]['public'][-2],rows[1]['public'][0]]
            if type(queries) is not list or len(queries)!=3:
                raise ValueError('XP2 attack group requires both combat information channels')
            for query,view in zip(queries,expected):
                validate_information_query(query,view,core_sha256=core_sha256)
                run=rows[1] if view is expected[-1] else rows[0]
                if query['administrative']['data']!=run['combat_readbacks'].get(view['sequence']):
                    raise ValueError('Combat query raw data differs from its actual native sidecar')
            if information_query_replay is not None:
                if (information_query_replay.get('classification')!='reconstructed_client_information_query_from_retained_native_reset'
                        or information_query_replay.get('live_query_executed') is not False
                        or information_query_replay.get('native_calls_during_replay') is not False
                        or information_query_replay.get('native_response_fabricated') is not False
                        or information_query_replay.get('original_files_modified') is not False
                        or information_query_replay.get('core_sha256')!=core_sha256
                        or information_query_replay.get('query')!=queries[2]
                        or information_query_replay.get('public_reset')!=fresh['reference']):
                    raise ValueError('Combat reset information replay lost its explicit provenance')
    effect=command['ledger']['phase_receipt']['effect']
    result=dict(action=command['action'],command_count=1,poll_calls=0,
        observable_native_change=effect['observable_native_change'],
        visible_damage_increased=effect['target_visible_damage_increased'],
        queued_move_to_selected_plot=effect['queued_move_to_selected_plot'],
        native_defender_selection=True,death_or_capture_inferred_from_absence=False,
        reset_public_equal=True,full_combat_qualified=False)
    if query_provenance is not None:
        result.update(combat_information_query_provenance=query_provenance,
                      reset_combat_information_live_qualified=information_query_replay is None)
    elif information_query_replay is not None:
        raise ValueError('Combat information replay is limited to the explicitly reviewed XP2 group')
    return result
