"""Administrative LAN checkpoints over the existing native Save/Load path.

The original official capture remains the authority for engine, databases and
content. A checkpoint changes only the hash-bound native component pair and
explicit host UI state. It is never a replacement capture or a player action.
"""
from __future__ import annotations

import copy
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from functools import partial
from pathlib import Path

SCHEMA = 'civ6-host.network-checkpoint.v1'
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
MAX_DEPTH = 64


def _profile_engine(name):
    from .capture_profiles import LAN_PROFILE
    from .xp1_bundle_inputs import XP1_LAN_PROFILE
    from .xp2_bundle_inputs import XP2_LAN_PROFILE
    from .configuration_profiles import BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256
    profiles = {LAN_PROFILE.name: BASE_CORE_SHA256, XP1_LAN_PROFILE.name: XP1_CORE_SHA256,
                XP2_LAN_PROFILE.name: XP2_CORE_SHA256}
    if name not in profiles:
        raise ValueError('Unsupported network checkpoint engine/profile')
    return profiles[name]


def _capture_mode(name):
    from .capture_profiles import LAN_PROFILE
    from .xp1_bundle_inputs import XP1_LAN_PROFILE
    from .xp2_bundle_inputs import XP2_LAN_PROFILE
    return {LAN_PROFILE.name: 'lan', XP1_LAN_PROFILE.name: 'xp1-lan',
            XP2_LAN_PROFILE.name: 'xp2-lan'}[name]


def _root():
    from .provenance import resource_root
    return resource_root()


def _path(value):
    from .resource_resolution import resolve_path
    p = resolve_path(_root() / value).resolve()
    if not p.is_relative_to(_root() / 'work'):
        raise ValueError('LAN checkpoint must remain in private work resources')
    return p


def reference(path):
    path = _path(str(path))
    data = path.read_bytes()
    return dict(path=path.relative_to(_root()).as_posix(), bytes=len(data),
                sha256=hashlib.sha256(data).hexdigest())


def normalize(value):
    if (type(value) is not dict or set(value) not in ({'path','sha256'}, {'path','sha256','bytes'})
            or type(value['path']) is not str or type(value['sha256']) is not str
            or len(value['sha256']) != 64 or any(c not in '0123456789abcdef' for c in value['sha256'])):
        raise ValueError('LAN checkpoint needs an exact path and SHA256')
    p = _path(value['path'])
    if not 1 <= p.stat().st_size <= MAX_MANIFEST_BYTES:
        raise ValueError('LAN checkpoint manifest exceeds its bound')
    if 'bytes' in value and (type(value['bytes']) is not int or value['bytes'] != p.stat().st_size):
        raise ValueError('LAN checkpoint manifest size differs')
    return (p.relative_to(_root()).as_posix(), value['sha256'])


def _checked(row):
    from .native.native_session_resume import checked_file
    return checked_file(row)


def _read(reference_pair):
    from .native.native_source_cache import load_pinned_json
    from .native.native_session_resume import plain
    value = plain(load_pinned_json(_path(reference_pair[0]), reference_pair[1]))
    if (value.get('schema') != SCHEMA
            or value.get('core_sha256') != _profile_engine(value.get('input_profile'))
            or value.get('native_save_status') != 0 or value.get('stream_closed') is not True
            or value.get('jobs_quiescent_unchanged') is not True
            or value.get('full_civ6save_container') is not False
            or type(value.get('lineage_depth')) is not int
            or not 0 <= value['lineage_depth'] <= MAX_DEPTH):
        raise ValueError('Unsupported LAN checkpoint provenance')
    if (type(value.get('observed_game_turn')) is not int or not 1 <= value['observed_game_turn'] <= 100000
            or value.get('player_id') != 0 or value['observation']['player_id'] != 0
            or value['decisions']['player_id'] != 0
            or value['observation']['turn'] != value['observed_game_turn']
            or value['decisions']['turn'] != value['observed_game_turn']
            or value['network_boundary']['session']['turn'] != value['observed_game_turn']):
        raise ValueError('LAN checkpoint public identity differs')
    if _capture_mode(value['input_profile']) == 'xp2-lan':
        from .xp1_checkpoint_profile import provider_proof
        receipt=value.get('configuration_receipt',{})
        component=value['components'].get('application_configuration',{})
        if (type(value.get('native_save_status')) is not int
                or value.get('game_version_prefix') != '05000000'
                or receipt.get('operation') != 'serialize'
                or receipt.get('core_sha256') != value['core_sha256']
                or receipt.get('proof_sha256') != provider_proof(value['core_sha256'])
                or receipt.get('sha256') != component.get('sha256')
                or receipt.get('bytes') != component.get('bytes')
                or receipt.get('identity_checked_before_after') is not True
                or receipt.get('native_return_interpreted') is not False):
            raise ValueError('XP2 checkpoint lost its exact native B/Game serialization receipts')
    return value


def manifest(ref, *, official_bundle=None, reviewed_producers=None):
    """Validate component ancestry and producing runs.

    An explicit reviewed_producers map is for read-only retained-evidence review
    only. Normal Load never supplies it. Each correction is reauthenticated from
    its original supervisor, exact archived sources and actual native close
    receipts; success fields in a caller-supplied dictionary are insufficient.
    """
    return _validate_lineage(ref, official_bundle=official_bundle,
                             reviewed_producers=reviewed_producers)


def verify_resume_head(ref, *, official_bundle, core_sha256):
    """Check the requested head at construction; closure admission walks its ancestry."""
    from .native.native_official_bundle import normalize_reference

    head = _read(ref)
    if (head['core_sha256'] != core_sha256
            or normalize_reference(head['source_official_bundle']) != official_bundle):
        raise ValueError('LAN checkpoint head belongs to another engine or official capture')


def _validate_lineage(ref, *, official_bundle, reviewed_producers=None, collected_pins=None,
                      head_payload=None):
    # One background verifier per walk. It reads only the current ancestor's
    # private database bytes while the calling thread authenticates its close.
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix='checkpoint-database') as verifier:
        return _walk_lineage(ref, official_bundle=official_bundle, reviewed_producers=reviewed_producers,
                             collected_pins=collected_pins, head_payload=head_payload, verifier=verifier)


def _verify_database_bytes(rows):
    from .resource_resolution import resolve_path

    for row in rows:
        path = resolve_path(Path(row['path'])).resolve()
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != row['sha256']:
            raise ValueError('LAN checkpoint database changed after Save')


def _walk_lineage(ref, *, official_bundle, reviewed_producers, collected_pins, head_payload, verifier):
    if reviewed_producers is not None and type(reviewed_producers) is not dict:
        raise ValueError('Reviewed checkpoint producers require an explicit map')
    reviewed_producers={} if reviewed_producers is None else reviewed_producers
    reviewed=set()
    if type(ref) is dict:
        ref = normalize(ref)
    if type(ref) is not tuple or len(ref) != 2:
        raise ValueError('Expected canonical LAN checkpoint reference')
    from .native.native_official_bundle import normalize_reference
    from .resource_resolution import recorded_path, resolve_path
    origin = normalize_reference(official_bundle) if type(official_bundle) is dict else official_bundle
    first = None
    seen = set()
    # Ancestors share static source proofs. Reuse only exact pins within this
    # walk; private databases, component pairs and producer receipts are separate.
    checked_proofs = set()
    previous = None
    previous_fixture = None
    for _ in range(MAX_DEPTH + 1):
        if ref in seen:
            raise ValueError('LAN checkpoint ancestry cycle')
        seen.add(ref)
        m = _read(ref)
        current_origin = normalize_reference(m['source_official_bundle'])
        if origin is None:
            origin = current_origin
        if current_origin != origin:
            raise ValueError('LAN checkpoint belongs to another official bundle')
        is_head = first is None
        if is_head:
            first = m
        if previous is not None:
            if (previous['lineage_depth'] != m['lineage_depth'] + 1
                    or previous['input_profile'] != m['input_profile']
                    or previous['core_sha256'] != m['core_sha256']
                    or previous['input_components_sha256'] != {k:v['sha256'] for k,v in m['components'].items()}):
                raise ValueError('LAN checkpoint ancestry components differ')
        if set(m['components']) != {'gamecore','application_configuration'}:
            raise ValueError('Incomplete LAN checkpoint component pair')
        parent = _path(ref[0]).parent
        head_components = {} if is_head and head_payload is not None else None
        for role, row in m['components'].items():
            if _path(row['path']).parent != parent or not 4 <= row['bytes'] <= 32*1024*1024:
                raise ValueError('LAN checkpoint component escaped its pair')
            raw = _checked(row)
            if head_components is not None:
                head_components[role] = raw
        closure = json.loads(_checked(m['session_closure']))
        fixture = json.loads(_checked(m['fixture']))
        if head_components is not None:
            verified_head = dict(components=head_components, fixture=fixture)
        if (closure.get('input_profile') != _capture_mode(m['input_profile']) or closure.get('checkpoint_on_close') is not True
                or normalize_reference(closure['official_bundle']) != origin
                or closure.get('database_profile') != m['database_profile']
                or _path(closure['fixture']) != _path(m['fixture']['path'])):
            raise ValueError('LAN checkpoint producer closure differs')
        closure_path = _path(m['session_closure']['path'])
        recorded_closure = recorded_path(closure_path)
        supervisor_path = _path(recorded_closure.with_name('supervisor.json'))
        supervisor_raw=supervisor_path.read_bytes()
        supervisor = json.loads(supervisor_raw)
        if str(supervisor_path) in reviewed_producers:
            import zipfile
            from .native.network_session import xp1_loaded_close_evidence
            proof=reviewed_producers[str(supervisor_path)]
            original_reference=dict(path=str(supervisor_path),bytes=len(supervisor_raw),
                                    sha256=hashlib.sha256(supervisor_raw).hexdigest())
            if (type(proof) is not dict
                    or proof.get('schema')!='civ6-host.retained-xp1-stdout-close-correction.v1'
                    or proof.get('original_supervisor')!=original_reference
                    or proof.get('projection_only') is not True
                    or proof.get('original_files_modified') is not False
                    or proof.get('native_calls_during_review') is not False
                    or supervisor.get('error')!="JSONDecodeError('Expecting value: line 1 column 1 (char 0)')"
                    or supervisor.get('stop_reason')!='xp1_loaded_close_unverified'
                    or supervisor.get('normal_destroy_called') is not False
                    or not supervisor.get('stdout_native_records')):
                raise ValueError('Checkpoint producer review is not its exact retained parser refusal')
            pins=dict(closure['pins']);pins[str(supervisor_path.parent/'closure.json')]=m['session_closure']['sha256']
            projection=copy.deepcopy(supervisor);projection.update(error=None,stop_reason=None)
            actual=xp1_loaded_close_evidence(supervisor_path.parent,projection,pins)
            if proof.get('native_lifetime')!=actual or proof.get('normal_destroy_authenticated') is not True:
                raise ValueError('Reviewed producer differs from its actual native close receipts')
            archive=proof.get('executed_sources_archive')
            if type(archive) is not dict or set(archive)!={'path','bytes','sha256'}:
                raise ValueError('Reviewed producer lacks its exact executed source archive')
            archive_path=Path(archive['path']);archive_raw=archive_path.read_bytes()
            if (not archive_path.is_absolute() or len(archive_raw)!=archive['bytes']
                    or hashlib.sha256(archive_raw).hexdigest()!=archive['sha256']):
                raise ValueError('Reviewed producer source archive changed')
            host=Path(__file__).resolve().parents[3]
            sources={Path(p).relative_to(host).as_posix():sha for p,sha in closure['pins'].items()
                     if Path(p).is_relative_to(host) and Path(p).suffix=='.py'}
            if not sources or proof.get('executed_host_python_sources')!=sources:
                raise ValueError('Reviewed producer source inventory differs from its executed closure')
            with zipfile.ZipFile(archive_path) as saved:
                names=saved.namelist()
                if len(names)!=len(set(names)) or any(name not in names
                        or saved.getinfo(name).file_size>4*1024*1024
                        or hashlib.sha256(saved.read(name)).hexdigest()!=sha for name,sha in sources.items()):
                    raise ValueError('Reviewed producer archive differs from its executed source pins')
            projection.update(normal_destroy_called=True,native_lifetime=actual)
            supervisor=projection;reviewed.add(str(supervisor_path))
        if (supervisor.get('reaped') is not True or supervisor.get('exit_code') != 90
                or supervisor.get('timed_out') is not False or supervisor.get('error') is not None
                or not supervisor.get('source_unchanged') or not all(supervisor['source_unchanged'].values())):
            raise ValueError('LAN checkpoint producing process did not finish successfully')
        xp2 = _capture_mode(m['input_profile']) == 'xp2-lan'
        if xp2:
            from .native.network_session import xp1_loaded_close_evidence
            from .xp2_checkpoint_source import SOURCE, SUPPLEMENT, RULES
            if (_path(m['session_closure']['path']) != parent.parent/'closure.json'
                    or not _path(m['fixture']['path']).is_relative_to(parent.parent)):
                raise ValueError('XP2 checkpoint pair has a foreign producing closure or fixture')
            proof_pins={row['path']:row['sha256'] for row in m['source_proofs']}
            if any(proof_pins.get(path)!=digest for path,digest in (SOURCE,SUPPLEMENT,RULES)):
                raise ValueError('XP2 checkpoint lacks its exact Save source proofs')
            pins=dict(closure['pins'])
            pins[str(recorded_closure)]=m['session_closure']['sha256']
            if set(fixture['databases']) != {'configuration','gameplay','localization'}:
                raise ValueError('XP2 checkpoint requires its three captured databases')
            if previous_fixture is not None:
                if ({k:v['sha256'] for k,v in previous_fixture['databases'].items()}
                        != {k:v['sha256'] for k,v in fixture['databases'].items()}
                        or {resolve_path(Path(v['path'])).resolve() for v in previous_fixture['databases'].values()}
                        & {resolve_path(Path(v['path'])).resolve() for v in fixture['databases'].values()}):
                    raise ValueError('XP2 checkpoint ancestry changed or reused its private databases')
        for row in m['source_proofs']:
            proof = (row['path'], row['bytes'], row['sha256'])
            if proof not in checked_proofs:
                _checked(row)
                checked_proofs.add(proof)
        if xp2:
            databases = verifier.submit(_verify_database_bytes, tuple(fixture['databases'].values()))
            close_evidence = xp1_loaded_close_evidence(supervisor_path.parent,supervisor,pins,
                                                      core_sha256=_profile_engine(m['input_profile']))
            if recorded_closure != closure_path and supervisor.get('native_lifetime') != close_evidence:
                raise ValueError('Relocated LAN checkpoint close differs from the original supervisor receipt')
            databases.result()
        else:
            _verify_database_bytes(fixture['databases'].values())
        if collected_pins is not None:
            rows = [*m['components'].values(), *m['source_proofs'],
                    m['session_closure'], m['fixture'], *fixture['databases'].values()]
            collected_pins.update((row['path'], row['sha256']) for row in rows)
            collected_pins[ref[0]] = ref[1]
            supervisor_key = supervisor_path.relative_to(_root()).as_posix()
            collected_pins[supervisor_key] = hashlib.sha256(supervisor_raw).hexdigest()
        parent_ref = m.get('parent_checkpoint')
        if parent_ref is None:
            if m['lineage_depth'] != 0 or closure.get('network_checkpoint') is not None:
                raise ValueError('LAN checkpoint root is not an original captured session')
            from .native.native_official_bundle import read_bundle
            if _capture_mode(m['input_profile']) == 'xp1-lan':
                from .xp1_saved_load import consume_input_handoff
                original=consume_input_handoff(closure['prepared_capture'])
                if original.reference != origin:
                    raise ValueError('XP1 checkpoint origin differs from its prepared capture')
            elif _capture_mode(m['input_profile']) == 'xp2-lan':
                from .xp2_bundle_inputs import consume_input_handoff
                prepared = closure['prepared_capture']
                if recorded_closure != closure_path:
                    if type(prepared) is not dict or type(prepared.get('path')) is not str:
                        raise ValueError('Relocated LAN checkpoint lacks its prepared capture path')
                    prepared = {**prepared, 'path': str(resolve_path(Path(prepared['path'])))}
                original=consume_input_handoff(prepared)
                if original.reference != origin:
                    raise ValueError('XP2 checkpoint origin differs from its prepared capture')
                expected = original.fixture['databases']
                if (set(fixture['databases']) != set(expected)
                        or any(fixture['databases'][key]['sha256'] != row['sha256']
                            for key,row in expected.items())):
                    raise ValueError('XP2 checkpoint root changed its exact captured databases')
            else:
                original=read_bundle(dict(path=origin[0],sha256=origin[1]),input_profile='lan')
            if m['input_components_sha256'] != dict(gamecore=hashlib.sha256(original.inputs.game).hexdigest(),
                    application_configuration=hashlib.sha256(original.inputs.configuration).hexdigest()):
                raise ValueError('LAN checkpoint lineage root differs from official components')
            break
        if closure.get('network_checkpoint') != {'path':parent_ref['path'],'sha256':parent_ref['sha256']}:
            raise ValueError('LAN checkpoint parent differs from loaded component pair')
        previous_fixture = fixture
        previous, ref = m, normalize(parent_ref)
    else:
        raise ValueError('LAN checkpoint ancestry exceeds bound')
    if reviewed!=set(reviewed_producers):
        raise ValueError('A reviewed checkpoint producer was not in the actual ancestry')
    if head_payload is not None:
        head_payload.update(verified_head)
    return first


def validate_boundary(owner):
    from .a0_natural_wonder import require_checkpoint_quiescent
    require_checkpoint_quiescent(owner)
    from .network_owner import state
    from .network_turns import controls
    session = state(owner)
    pid = session['local_player_id']
    control = controls(owner, session, pid)
    if (session['human_player_ids'] != [0] or session['active_human_player_ids'] != [0]
            or pid != 0 or control['active'] is not True or control['active_complete'] is not True
            or control['can_unready'] is not False or control['timer_elapsed'] is not False
            or getattr(owner, 'turn_continuation', None) is not None
            or any(getattr(owner, 'world_input_prompts', {}).values())
            or any(row['active'] for key,row in owner.network_turn_rows.items() if key != pid)):
        raise ValueError('LAN checkpoint requires a quiescent active, untimed human boundary')
    owner.control(empty=True)
    return dict(session=session, controls=control)


def checkpoint_boundary(owner):
    from .native.native_saved_actions import boundary
    from .capture_profiles import LAN_PROFILE
    if owner.inputs.profile is LAN_PROFILE:
        return boundary(owner,player_id=0,player_ids=owner.network_reference['major_player_ids'])
    return boundary(owner)


def _validate_closure_fields(closure):
    from .native.native_official_bundle import DATABASE_PROFILE, normalize_reference
    if (closure.get('input_profile') not in ('lan', 'xp1-lan', 'xp2-lan')
            or closure.get('database_profile') != DATABASE_PROFILE
            or closure.get('official_bundle') is None or closure.get('resume_checkpoint') is not None
            or type(closure.get('checkpoint_on_close',False)) is not bool
            or type(closure.get('initial_turn')) is not int or not 1 <= closure['initial_turn'] <= 100000):
        raise ValueError('Unsupported LAN checkpoint closure')
    normalize_reference(closure['official_bundle'])


def validate_closure(closure, *, head_payload=None):
    _validate_closure_fields(closure)
    m = None
    if closure.get('network_checkpoint') is not None:
        m = _validate_lineage(normalize(closure['network_checkpoint']),
                              official_bundle=closure['official_bundle'], head_payload=head_payload)
        if closure['initial_turn'] != m['observed_game_turn']:
            raise ValueError('LAN checkpoint closure turn differs')
    if closure['input_profile'] == 'xp2-lan':
        from .configuration_profiles import XP2_CORE_SHA256
        from .xp1_checkpoint_profile import verify_source
        verify_source(XP2_CORE_SHA256)
    return m


def save_provenance(inputs, closure):
    from .native.native_official_bundle import normalize_reference
    origin = normalize_reference(closure['official_bundle'])
    if inputs.official_bundle != origin:
        raise ValueError('LAN Save origin differs from loaded official bundle')
    parent = inputs.checkpoint
    depth = 0
    if parent is not None:
        prior = manifest(parent, official_bundle=origin)
        depth = prior['lineage_depth'] + 1
        if closure.get('network_checkpoint') != dict(path=parent[0],sha256=parent[1]):
            raise ValueError('LAN Save parent differs from restored checkpoint')
    elif closure.get('network_checkpoint') is not None:
        raise ValueError('Original LAN Save has a false checkpoint parent')
    if depth > MAX_DEPTH:
        raise ValueError('LAN checkpoint lineage exceeds bound')
    return dict(schema=SCHEMA, source_official_bundle=dict(path=origin[0],sha256=origin[1]),
                lineage_depth=depth, parent_checkpoint=None if parent is None else dict(path=parent[0],sha256=parent[1]))


def finalize_manifest(backend, value):
    from .native.native_official_bundle import _manifest
    origin = _manifest(backend.inputs.official_bundle)[1]
    value['origin_official_save_sha256'] = origin['save']['source']['sha256']
    value['network_boundary'] = copy.deepcopy(backend.network_boundary)
    state_owner = getattr(backend, 'host_state_owner', backend.owner)
    value['host_world_selection'] = getattr(state_owner,'world_input_selections',{}).get(0)
    return value


def validate_inputs(inputs):
    """Validate the pair and return its manifest for this synchronous caller.

    This is not a cache: each call still checks the complete ancestry and files.
    """
    m = manifest(inputs.checkpoint, official_bundle=inputs.official_bundle)
    _validate_component_pair(inputs, m)
    return m


def _validate_component_pair(inputs, m):
    from .capture_profiles import LAN_PROFILE
    from .xp1_bundle_inputs import XP1_LAN_PROFILE
    from .xp2_bundle_inputs import XP2_LAN_PROFILE
    if (not any(inputs.profile is p for p in (LAN_PROFILE, XP1_LAN_PROFILE, XP2_LAN_PROFILE))
            or inputs.checkpoint is None or inputs.official_bundle is None):
        raise ValueError('LAN checkpoint requires its retained profile and capture')
    if m['input_profile'] != inputs.profile.name:
        raise ValueError('Checkpoint component engine/profile differs')
    for key, raw in (('gamecore', inputs.game), ('application_configuration', inputs.configuration)):
        row = m['components'][key]
        if (type(raw) is not bytes or len(raw) != row['bytes']
                or hashlib.sha256(raw).hexdigest() != row['sha256']):
            raise ValueError('LAN restored component differs from checkpoint')


def resume_bundle(bundle, closure):
    from .resource_resolution import resolve_path

    ref = normalize(closure['network_checkpoint'])
    payload = {}
    mode = _capture_mode(bundle.inputs.profile.name)
    if mode in ('xp1-lan', 'xp2-lan'):
        from .native.native_official_bundle import normalize_reference
        if (closure.get('input_profile') != mode
                or normalize_reference(closure['official_bundle']) != bundle.reference):
            raise ValueError('LAN resume closure differs from its prepared engine or capture')
        m = validate_closure(closure, head_payload=payload)
    else:
        m = _validate_lineage(ref, official_bundle=bundle.reference, head_payload=payload)
    from .native.official_configuration import compare_provider_roundtrip
    configuration = payload['components']['application_configuration']
    game = payload['components']['gamecore']
    if mode == 'xp2-lan':
        from .configuration_roundtrip import compare_provider_roundtrip as selected_compare
        selected_compare(bundle.inputs.configuration, configuration,
                         core_sha256=_profile_engine(bundle.inputs.profile.name))
    else:
        compare_provider_roundtrip(bundle.inputs.configuration, configuration)
    if game[:4] != b'\x05\x00\x00\x00':
        raise ValueError('LAN checkpoint native stream version differs')
    if m['lineage_depth'] == 0 and m['input_components_sha256'] != dict(
            gamecore=hashlib.sha256(bundle.inputs.game).hexdigest(),
            application_configuration=hashlib.sha256(bundle.inputs.configuration).hexdigest()):
        raise ValueError('LAN checkpoint root does not descend from the exact capture')
    old = payload['fixture']
    current = json.loads(Path(closure['fixture']).read_bytes())
    if set(old['databases']) != set(current['databases']):
        raise ValueError('LAN checkpoint database set differs')
    for key,row in current['databases'].items():
        if (row['sha256'] != old['databases'][key]['sha256']
                or resolve_path(Path(row['path'])).resolve() == resolve_path(Path(old['databases'][key]['path'])).resolve()):
            raise ValueError('LAN checkpoint requires distinct, identical private databases')
    inputs = replace(bundle.inputs,configuration=configuration,game=game,checkpoint=ref)
    _validate_component_pair(inputs, m)
    o = m['observation']
    own = dict(turn=o['turn'],width=o['width'],height=o['height'],player_id=o['player_id'],
        gold=o['economy']['gold'],city_count=len(o['cities']),
        units=sorted([{k:u[k] for k in ['id','type','x','y','damage','moves']} for u in o['units']],key=lambda u:u['id']))
    resumed = replace(bundle,inputs=inputs,initial_turn=o['turn'],expected_readback=own)
    if mode in ('xp1-lan', 'xp2-lan'):
        from .xp1_session_checkpoint import admit_resumed_bundle
        admit_resumed_bundle(bundle, resumed, m)
    return resumed


def configure_closure(closure, ref, *, validate_fields=False):
    if ref is None:
        if validate_fields:
            validate_closure(closure)
        return
    pins = {}
    m = _validate_lineage(ref, official_bundle=closure['official_bundle'], collected_pins=pins)
    fields = dict(network_checkpoint=dict(path=ref[0], sha256=ref[1]),
                  initial_turn=m['observed_game_turn'])
    if validate_fields:
        _validate_closure_fields({**closure, **fields})
    closure['pins'].update(pins)
    closure.update(fields)


def prepare_owner(owner, initial):
    m = manifest(owner.inputs.checkpoint,official_bundle=owner.inputs.official_bundle)
    if initial != m['observation']:
        raise ValueError('Restored LAN public observation differs from checkpoint')
    from .native.native_session_resume import restore_placement_choice
    xp1 = _capture_mode(owner.inputs.profile.name) in ('xp1-lan', 'xp2-lan')
    tracking = {}
    rows = m['host_placement_tracking']
    if type(rows) is not list or len(rows) > 256:
        raise ValueError('Restored LAN placement tracking exceeds bound')
    for row in rows:
        if (type(row) is not dict or set(row) != {'key','choice'}
                or type(row['key']) is not list or len(row['key']) != (3 if xp1 else 2)
                or any(type(item) is not int for item in row['key'])):
            raise ValueError('Restored LAN placement identity differs')
        key=tuple(row['key']);choice=restore_placement_choice(row['choice'])
        expected_key = ((choice['player_id'],choice['city_id'],choice['plot_id']) if xp1
                        else (choice['city_id'],choice['plot_id']))
        if key != expected_key or choice['player_id'] != 0 or key in tracking:
            raise ValueError('Restored LAN placement identity differs')
        tracking[key] = choice
    state_owner = owner.continuation if xp1 else owner
    if xp1:
        from .xp1_session_checkpoint import boundary
        current = boundary(owner)
    else:
        current = validate_boundary(owner)
    if current != m['network_boundary']:
        raise ValueError('Restored LAN readiness/session boundary differs')
    # Publish host-only tracking only after every identity and native boundary
    # check succeeds. A refused restore must not leave a partial host state.
    state_owner.explicit_placements=tracking
    state_owner.world_input_selections={0:m['host_world_selection']}
    # The initial reply belongs to this same loaded owner and validated
    # checkpoint. Keep the comparison local to that startup sequence.
    return partial(_compare_decisions, owner, m)


def compare_decisions(owner, observation, decisions):
    m = manifest(owner.inputs.checkpoint,official_bundle=owner.inputs.official_bundle)
    return _compare_decisions(owner, m, observation, decisions)


def _compare_decisions(owner, m, observation, decisions):
    from .native.native_session_resume import semantic_decisions
    from civ6_host.contracts import network_turn
    evidence=getattr(owner,'production_administrative_by_player',{}).get(observation['player_id'])
    combat=getattr(owner,'combat_administrative_by_player',{}).get(observation['player_id'])
    from .configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256
    from .xp1_unit_attack_profile import PUBLIC_PRECISION_SOURCE, READINESS_SOURCE, source_reference, precision_reference, verify_source, verify_readiness_source
    core_sha256=None;precision=PUBLIC_PRECISION_SOURCE[1]
    schema = decisions.get('schema')
    if schema in network_turn.ATTACK_CAPABILITY_SCHEMAS:
        core_sha256=_profile_engine(owner.inputs.profile.name)
        if core_sha256!=m['core_sha256']:
            raise ValueError('Checkpoint combat comparison selects another saved engine')
        if core_sha256==BASE_CORE_SHA256 or owner.backend.load_abi.core_sha256!=core_sha256:
            raise ValueError('Checkpoint combat comparison selects another live engine')
        precision=precision_reference(core_sha256)[1]
    readiness_source=None
    if (schema in network_turn.COMBAT_READINESS_CAPABILITY_SCHEMAS
            and schema != network_turn.CAPABILITY_CITY_CONTROLS_SCHEMA
            and m['decisions'].get('schema') not in network_turn.COMBAT_READINESS_CAPABILITY_SCHEMAS):
        if core_sha256==XP1_CORE_SHA256:
            verify_source();verify_readiness_source()
        else:
            verify_source(core_sha256);verify_readiness_source(core_sha256)
        readiness_source=(READINESS_SOURCE[1] if core_sha256==XP1_CORE_SHA256 else source_reference(core_sha256)[1])
    comparable, transition = network_turn.checkpoint_catalogue(decisions,m['decisions'],observation,production_evidence=evidence,
        combat_evidence=combat,combat_source_sha256=precision,
        combat_readiness_source_sha256=readiness_source,core_sha256=core_sha256)
    if observation != m['observation'] or semantic_decisions(comparable) != semantic_decisions(m['decisions']):
        raise ValueError('Restored LAN public decision catalogue differs')
    owner.emit('official_lan_checkpoint_reloaded',checkpoint=owner.inputs.checkpoint,
        turn=observation['turn'],public_observation_equal=True,public_decisions_equal=transition is None,
        saved_decision_fields_equal=True,catalogue_transition=transition,
        identity_rebound=True,complete_state_compared=False,strategic_training_ready=False)


def save(owner, observation, decisions, closure, closure_path):
    from .native.native_session_checkpoint import SessionSaveBackend, run_sequence
    from .native.native_checkpoint_retained_save import MAX_CALLS, MAX_BYTES
    boundary = validate_boundary(owner)
    backend=SessionSaveBackend(owner,observation,decisions,closure,closure_path)
    # A resumed boundary can have no private events at all: HostEvents creates
    # this ring lazily in both producers (or the ordinary drain). Preserve None
    # in every Save snapshot; never create/drain a queue to satisfy admission.
    backend.allow_uninitialized_private=True
    backend.stream_call_limit=max(MAX_CALLS,len(owner.inputs.game)*2)
    owner.emit('official_lan_checkpoint_stream_budget',input_bytes=len(owner.inputs.game),
        max_calls=backend.stream_call_limit,max_bytes=MAX_BYTES,strategic_training_ready=False)
    backend.network_boundary=boundary
    original_state=backend.state
    def checked_state():
        if validate_boundary(owner) != boundary:
            raise ValueError('LAN Save changed readiness or session boundary')
        return original_state()
    backend.state=checked_state
    return run_sequence(backend,owner.emit)
