"""Explicit prepared capture inputs for the existing native Load implementation.

Preparation uses the original complete capture validator once. The immutable
package is then checked against its requested hash, installed validator code,
original capture identity and actual runtime files. Old capture evidence stays
separate; this does not qualify a different game profile or remove its guards.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re

ENV='CIV6_HOST_PREPARED_CAPTURE'
FIELD='prepared_capture'
XP2_LAUNCH_FIELD='xp2_prepared_launch'
_SETTING=object()
_UNSET=_SETTING

# Explicit artifact-reader compatibility, not a rewrite of producer identity.
# This producer admitted the retained capture and completed the installed native
# round-trip recorded by host-prepared-capture.json. Original validator sources
# must still match. Unknown producer versions remain refused.
_COMPATIBLE_PRODUCERS={
    'fb8f64fccfaab86e947eb3f9263a149854bf0a2e7f50cc52fc5ecc6f218993bd':{
        'preparation_evidence_sha256':'d42a36ae7ec2bad445742db44f016483ae5efffc099a1d0a738bca083bff0284',
        'origin_sha256':'28cc55ad4c2d56535db8c0a1351445125fd75800ab54eefd3b0b600b41717f1d',
        'origin_path':'work/official-capture/xp2-gs-lan-rows-20261102-04/manifest.json',
        'package_sha256':'6468bf13145fa712438bd276896273630789ca4afb6003d904b66a8aa29e2020',
        'private_input_profile':'xp2-lan',
        'native_session_qualified':False,
    },
    # Input preparation only; subsequent native wiring is not qualified here.
    '5317ec0a1c1b4054173d58cb10e95b3437d427e6dfd2eded8092425a6937e01a':{
        'preparation_evidence_sha256':'4ab8be2003321166e8cf7addc0cff6b1a9ffa731bc3c8a78bd471036124662bf',
        'origin_sha256':'475f74f15dc4921b3281c9eece768afadbff924c6384f0507d3ea92413c48fcf',
        'origin_path':'work/official-capture/xp1-lan-20261030/manifest.json',
        'private_input_profile':'xp1-lan',
        'native_session_qualified':False,
    },
    '2ced1dfd9a2297ab5c202d8981047013b612924a62a8385be4afc456ab174960':{
        'runtime_wheel_sha256':'25af15ca97cc064aae36ac5ba77bac31fc5d18c2f60d87efa287f11b0d73b657',
        'native_qualification_sha256':'6bd28ad02119b0eb1c32e1fd99382737b8042b4c8e0df27c5cb64892ea17d2b8',
    },
    # Exact LAN preparation from the original full validator. Subsequent
    # changes affect capability callbacks, roster readback and worker profile
    # selection, not capture admission. This is not a native-session receipt.
    '1fa9b5bc31d34d3cba213b6b1575485021faeef2d436f80a1b5e7c2248a8b1df':{
        'preparation_evidence_sha256':'5a9656998bc38fe7389ee9f4de220f1bc60ca5c0a0fc9380e77a5daf2acffd41',
        'native_session_qualified':False,
    },
}


def _sha(data):return hashlib.sha256(data).hexdigest()


def _reference(value):
    if type(value) is not dict or set(value)!={'path','sha256'}:
        raise ValueError('Prepared capture needs an exact path and SHA-256')
    path=Path(value['path']) if type(value['path']) is str else Path()
    if not path.is_absolute() or not path.is_file() or not re.fullmatch('[0-9a-f]{64}',str(value['sha256'])):
        raise ValueError('Invalid prepared capture reference')
    return dict(path=str(path.resolve()),sha256=value['sha256'])


def configured_reference():
    global _SETTING
    raw=os.environ.get(ENV)
    value=None if raw is None else _reference(json.loads(raw))
    if _SETTING is _UNSET:_SETTING=copy.deepcopy(value)
    if value!=_SETTING:raise RuntimeError('Prepared capture configuration changed; use a new process')
    return copy.deepcopy(value)


def configure(reference):
    previous=os.environ.get(ENV)
    value=None if reference is None else _reference(reference)
    if previous is not None and _reference(json.loads(previous))!=value:
        raise ValueError('Prepared capture environment differs from explicit backend configuration')
    if value is not None:os.environ[ENV]=json.dumps(value,sort_keys=True)
    if configured_reference()!=value:raise ValueError('Prepared capture configuration differs')


def validation_identity():
    from .provenance import installed_source_pins
    from .native import native_official_bundle as original
    package=Path(__file__).resolve().parents[1]
    sources={Path(p).relative_to(package).as_posix():v for p,v in installed_source_pins().items()}
    return dict(schema='civ6-host.capture-preparation-code.v1',runtime_sources=sources,
        original_validator_sources=original._prepared_bundle_validator_digests())


def admit_producer(producer,consumer):
    digest=_sha(json.dumps(producer,sort_keys=True,separators=(',',':')).encode())
    if producer==consumer:
        return dict(mode='same_runtime',producer_identity_sha256=digest)
    if (digest not in _COMPATIBLE_PRODUCERS or producer.get('schema')!=consumer.get('schema')
            or producer.get('original_validator_sources')!=consumer.get('original_validator_sources')):
        raise ValueError('Prepared capture producer is not compatible with this reader')
    mode=('retained_preparation_producer' if
          _COMPATIBLE_PRODUCERS[digest].get('native_session_qualified') is False
          else 'retained_qualified_producer')
    return dict(mode=mode,producer_identity_sha256=digest,
        **_COMPATIBLE_PRODUCERS[digest])


def _check_xp1_prepared_reader(producer,consumer,admission,manifest,package_reference=None):
    """Preserve input-parser identity while native initialization is integrated.

    The recorded producer is never relabelled as the current runtime. This
    permits rehashing prepared inputs, not opening a public game session.
    """
    if (admission.get('private_input_profile')!='xp1-lan'
            or admission.get('native_session_qualified') is not False
            or manifest['input_profile']!='xp1-lan'
            or manifest['origin']['sha256']!=admission.get('origin_sha256')
            or manifest['origin']['path']!=admission.get('origin_path')):
        raise ValueError('Prepared XP1 input producer lacks its exact private scope')
    from .xp1_bundle_inputs import reader_validator_digests
    package=Path(__file__).resolve().parents[1]
    validators={Path(p).relative_to(package).as_posix():v
                for p,v in reader_validator_digests().items()}
    # The lab-original digests in admit_producer do not authenticate their
    # installed transformations. Pin actual input parsers as well. Native Load
    # wiring is deliberately not part of this prepared-input compatibility set.
    installed_input_modules = (
        'runtime/capture_package.py',
        'runtime/native/official_save.py',
        'runtime/native/official_configuration.py',
        'runtime/native/database_capture_bundle993.py',
        'runtime/native/native_gameplay_source_capture.py',
        'runtime/native/native_localization_logical_export.py',
        'runtime/native/native_localization.py',
        'runtime/native/native_source_cache.py',
        'runtime/native/native_checkpoint_provider.py',
        'runtime/native/native_game_configuration.py',
    )
    for key in installed_input_modules:
        path=package/key
        if not path.is_file() or not 0<path.stat().st_size<=4*1024*1024:
            raise ValueError('Prepared XP1 input parser is missing or oversized')
        raw=path.read_bytes()
        if not 0<len(raw)<=4*1024*1024:
            raise ValueError('Prepared XP1 input parser exceeds its byte bound')
        validators[key]=_sha(raw)
    from .xp1_prepared_reader_transition import admit_retained_package, PRODUCER_IDENTITY_SHA256, PACKAGE_RELATIVE, PACKAGE_SHA256
    producer_digest=_sha(json.dumps(producer,sort_keys=True,separators=(',',':')).encode())
    if package_reference is not None or producer_digest == PRODUCER_IDENTITY_SHA256:
        if package_reference is None:
            from .paths import resource_root
            package_path=(resource_root()/PACKAGE_RELATIVE).resolve(strict=True)
            package_reference=dict(path=str(package_path),sha256=PACKAGE_SHA256)
        receipt=admit_retained_package(producer=producer,consumer=consumer,
            manifest=manifest,reference=package_reference,validator_digests=validators)
        return [receipt]
    transitions=[]
    for key,digest in validators.items():
        if consumer['runtime_sources'].get(key)!=digest:
            raise ValueError('Prepared XP1 current input validator changed')
        previous=producer['runtime_sources'].get(key)
        if previous==digest:continue
        # Complete source comparison against the retained executed module
        # proves that only these two non-parsing functions changed. The new
        # fingerprint additionally binds checkpoint ancestry; the closure
        # dispatcher selects its explicit XP1 administrative validator. Every
        # input parser, content check and raw-component reader is unchanged.
        # This exact pair is intentionally not a general version exemption.
        if (key,previous,digest)!=(
                'runtime/native/native_official_bundle.py',
                '0f9ad559341707cebd6ce0e9a76f27ccdc2dfecee6cc65ab2f385eaba93ce51b',
                '55c05c15c7dc08b776f9e52ba379d1f13e5a83bce83d41787f32c2bd9626a89a'):
            raise ValueError('Prepared XP1 input validator changed; raw revalidation required')
        transitions.append(dict(module=key,producer_sha256=previous,consumer_sha256=digest,
            transition='xp1_checkpoint_nonparser_join_v1',
            changed_functions=['_prepared_bundle_fingerprint','validate_closure_profile'],
            input_parsers_unchanged=True,producer_identity_substituted=False))
    return transitions


def _check_xp2_prepared_reader(producer,consumer,admission,manifest,reference):
    """Reuse the exact input package with unchanged original input decoders.

    Native callback additions are independently source-pinned by their caller;
    they cannot authorize a different input parser, capture or engine. The
    recorded producer stays intact and this admits no native game session.
    """
    if (admission.get('private_input_profile')!='xp2-lan'
            or admission.get('native_session_qualified') is not False
            or manifest['input_profile']!='xp2-lan'
            or manifest['origin']['path']!=admission.get('origin_path')
            or manifest['origin']['sha256']!=admission.get('origin_sha256')
            or reference.get('sha256')!=admission.get('package_sha256')):
        raise ValueError('Prepared XP2 producer lacks its exact qualified input-only scope')
    from .xp2_bundle_inputs import reader_validator_digests
    package=Path(__file__).resolve().parents[1]
    validators={Path(p).relative_to(package).as_posix():digest
                for p,digest in reader_validator_digests().items()}
    for key in (
        'runtime/capture_package.py', 'runtime/capture_candidates.py',
        'runtime/database_bulk_capture.py', 'runtime/database_row_stream.py',
        'runtime/localization_stream_bridge.py',
        'runtime/native/official_save.py', 'runtime/native/official_configuration.py',
        'runtime/native/official_saved_content.py',
        'runtime/native/database_capture_bundle993.py',
        'runtime/native/native_localization_logical_export.py',
        'runtime/native/native_localization.py', 'runtime/native/native_source_cache.py',
        'runtime/native/native_checkpoint_provider.py',
        'runtime/native/native_game_configuration.py',
    ):
        path=package/key
        if not path.is_file() or not 0<path.stat().st_size<=4*1024*1024:
            raise ValueError('Prepared XP2 input parser missing or oversized')
        validators[key]=_sha(path.read_bytes())
    reader_transitions=[]
    for key,digest in validators.items():
        if consumer['runtime_sources'].get(key)!=digest:
            raise ValueError('Prepared XP2 current input validator changed: '+key)
        previous=producer['runtime_sources'].get(key)
        if previous==digest:continue
        if (key,previous,digest)==(
                'runtime/capture_script_paths.py',
                'd1ed79521048d0d451714b4642267faa29f91656e9259d2cb5eefcb8fd982c87',
                '44763044232af82190a01dbd3f7b249184566285eeacd12cedec3f298d1ffc9c'):
            reader_transitions.append(dict(module=key,producer_sha256=previous,consumer_sha256=digest,
                transition='xp2_script_proof_physical_path_relocation_v1',
                logical_reference_preserved=True,proof_bytes_rechecked=True,
                producer_identity_substituted=False))
            continue
        # This exact source pair retains the original capture branch, all
        # component/map/mode/content/script validators and all other module
        # AST. Only authenticated, registered derived pairs enter the new
        # branch. The independent source comparison is retained by its hash;
        # this is not a general input-reader version exemption.
        if (key,previous,digest)!=(
                'runtime/xp2_bundle_inputs.py',
                '318301d09f21816c9540d21661753c2dae427da54b0f25b6aa3d2e588f8d910f',
                'd57b99c1e47a933a965009cb5f152309abacff3eef3b847df6eba6382ef1782c'):
            raise ValueError('Prepared XP2 input validator changed; raw revalidation required: '+key)
        reader_transitions.append(dict(module=key,producer_sha256=previous,consumer_sha256=digest,
            transition='xp2_checkpoint_registered_pair_join_v1',
            source_review_sha256='160acbf7a3a3c6ff2b10925b858d5989884a40c076ba30c5171ca22171eb3430',
            changed_function='validate_candidate_inputs',original_capture_branch_unchanged=True,
            original_input_parsers_unchanged=True,producer_identity_substituted=False))
    changed=sorted(key for key in set(producer['runtime_sources'])|set(consumer['runtime_sources'])
        if producer['runtime_sources'].get(key)!=consumer['runtime_sources'].get(key))
    return [dict(transition='xp2_exact_input_reader_identity_v1',
                 unchanged_input_modules=len(validators)-len(reader_transitions),
                 reviewed_input_transitions=reader_transitions,changed_runtime_modules=changed,
                 native_session_admitted=False,producer_identity_substituted=False)]


def _load(*, _xp1_candidate=False, _candidate_profile=None):
    from .capture_candidates import select_private_candidate
    candidate=select_private_candidate(xp1_candidate=_xp1_candidate,
                                       candidate_profile=_candidate_profile)
    reference=configured_reference()
    if reference is None:return None
    from .capture_package import read_package
    manifest,folder,files=read_package(reference, _xp1_candidate=_xp1_candidate,
                                      _candidate_profile=_candidate_profile)
    producer,consumer=manifest['validation_identity'],validation_identity()
    admission=admit_producer(producer,consumer)
    if candidate is not None and candidate.family=='xp1-lan' and producer != consumer:
        _check_xp1_prepared_reader(producer,consumer,admission,manifest,reference)
    if candidate is not None and candidate.family=='xp2-lan' and producer!=consumer:
        _check_xp2_prepared_reader(producer,consumer,admission,manifest,reference)
    from .native import native_official_bundle as original
    origin=manifest['origin'];normalized=original.normalize_reference(origin)
    raw=(original.ROOT/normalized[0]).read_bytes()
    if _sha(raw)!=normalized[1] or raw!=(folder/'origin-manifest.json').read_bytes():
        raise ValueError('Prepared capture differs from its original manifest')
    return reference,manifest,folder,files,json.loads(raw)


def _files(manifest,folder):
    result={}
    for role,row in manifest['files'].items():
        result[role]=dict(path=str((folder/row['path']).resolve()),sha256=row['sha256'],size_bytes=row['bytes'])
    return result


def _bootstrap(manifest,folder):
    bootstrap=copy.deepcopy(manifest['localization_bootstrap'])
    bootstrap['icu_data']['path']=str((folder/manifest['files']['icu_data']['path']).resolve())
    return bootstrap


def _same_origin(reference,manifest):
    from .native import native_official_bundle as original
    requested=reference if type(reference) is tuple else original.normalize_reference(reference)
    origin=(manifest['origin']['path'],manifest['origin']['sha256'])
    if requested!=origin:raise ValueError('Prepared capture belongs to another official capture')
    return origin


def _pin_original(row,dependencies):
    from .native import native_official_bundle as original
    raw=original._file(row,dependencies,maximum=128*1024**2)
    return raw


def _check_localization(manifest,folder,capture,dependencies):
    reference=capture['localization_exports']['after']
    report=json.loads(_pin_original(reference,dependencies))
    database=manifest['files']['database_localization']
    if database['sha256']!=report['database']['sha256'] or database['bytes']!=report['database']['bytes']:
        raise ValueError('Prepared Localization database differs from original materialization')
    bootstrap=manifest['localization_bootstrap'];expected=report['bootstrap']
    if (bootstrap['locale']!=expected['locale'] or bootstrap['dictionary_flag'] is not expected['dictionary_flag']
            or bootstrap['icu_data']['sha256']!=expected['icu_data']['sha256']
            or bootstrap.get('official_export')!=reference):
        raise ValueError('Prepared Localization settings differ from original capture')
    return _bootstrap(manifest,folder)


def try_bundle(reference,*,input_profile,_xp1_candidate=False,_candidate_profile=None):
    from .capture_candidates import select_private_candidate
    candidate=select_private_candidate(xp1_candidate=_xp1_candidate,
                                       candidate_profile=_candidate_profile)
    loaded=_load(_xp1_candidate=_xp1_candidate,_candidate_profile=_candidate_profile)
    if loaded is None:return None
    package_ref,manifest,folder,_,capture=loaded
    origin=_same_origin(reference,manifest)
    if manifest['input_profile']!=input_profile:raise ValueError('Prepared capture turn profile differs')
    from .native import native_official_bundle as original
    from .native.native_official_load import OfficialInputs
    from .capture_profiles import profile_for_capture
    if candidate is not None:
        if input_profile != candidate.family:raise ValueError('Candidate input family differs')
        profile=candidate.profile
    else:
        profile=profile_for_capture(input_profile)
    files=_files(manifest,folder)
    configuration=Path(files['configuration_stream']['path']).read_bytes()
    game=Path(files['gamecore_stream']['path']).read_bytes()
    _,maps=original.parse_configuration(configuration,profile.mode_name)
    if [list(x) for x in maps]!=manifest['map_values']:raise ValueError('Prepared map configuration differs')
    inputs=OfficialInputs(configuration,game,maps,profile,official_bundle=origin)
    # Retain the original save/provider/GameCore-section validation. This reads
    # the bounded official save, not the thousands of capture export fragments.
    original.validate_inputs(inputs, _input_only=candidate is not None)
    databases={role:files['database_'+role] for role in ('configuration','gameplay','localization')}
    content=copy.deepcopy(manifest['content_profile'])
    for role,row in databases.items():
        if content['final_databases'][role]!={k:row[k] for k in ('sha256','size_bytes')}:
            raise ValueError('Prepared database/content identity differs')
        if role in ('configuration','gameplay'):
            captured=capture['export_matches'][role]['copy']
            if row['sha256']!=captured['sha256'] or row['size_bytes']!=captured['bytes']:
                raise ValueError('Prepared final database differs from original capture')
    engine=manifest['engine']
    from .native.native_checkpoint_provider import CORE_SHA256
    if candidate is not None:
        CORE_SHA256=candidate.core_sha256
    if (content['engine']['gamecore_sha256']!=engine['sha256'] or engine['sha256']!=CORE_SHA256
            or capture['preflight']['process']['gamecore_module']['sha256']!=engine['sha256']):
        raise ValueError('Prepared engine/content identity differs')
    dependencies={str((folder/r['path']).resolve()):r['sha256'] for r in manifest['files'].values()}
    dependencies.update({package_ref['path']:package_ref['sha256'],str((original.ROOT/origin[0]).resolve()):origin[1],str(Path(engine['path']).resolve()):engine['sha256']})
    runtimes=[]
    for name in ('runtime-selections-before.json','runtime-selections-after.json'):
        runtimes.append(json.loads(_pin_original(capture['artifacts'][name],dependencies)))
    before=json.loads(_pin_original(capture['artifacts']['observation-before.json'],dependencies))
    after=json.loads(_pin_original(capture['artifacts']['observation-after.json'],dependencies))
    if before['turn']!=after['turn'] or before['observation']!=after['observation']:
        raise ValueError('Original capture decision boundary differs')
    state=before['observation'];fields=('id','type','x','y','damage','moves')
    expected=dict(turn=before['turn'],width=state['map']['width'],height=state['map']['height'],player_id=0,
        gold=state['economy']['gold'],city_count=len(state['cities']),
        units=sorted(({k:u[k] for k in fields} for u in state['units']),key=lambda u:u['id']))
    if manifest['initial_turn']!=before['turn'] or manifest['expected_readback']!=expected:
        raise ValueError('Prepared initial readback differs from original capture')
    scripts=json.loads(_pin_original(capture['selected_gameplay_sources']['manifest'],dependencies))
    if candidate is not None and candidate.family=='xp2-lan':
        from . import xp2_bundle_inputs as xp2
        from .native.native_gameplay_empty import stable_capture_identity
        identities=[]
        for runtime in runtimes:
            xp2.validate_selection_scope(runtime)
            identities.append(stable_capture_identity(runtime['gameplay_active_list']))
        if identities[0]!=identities[1]:
            raise ValueError('Prepared XP2 selected/active script state changed around save')
        xp2.validate_summary_scope(capture['runtime_selections'])
        xp2.validate_scripts(scripts,Path(capture['selected_gameplay_sources']['manifest']['path']).parent,
                             capture['preflight']['process'],dependencies)
    elif scripts['selected_paths'] or scripts['records'] or scripts['files']:
        raise ValueError('Nonempty gameplay script packages are not yet supported')
    save=(original.ROOT/capture['save']['extraction907']['manifest']).parent/'source.Civ6Save'
    _pin_original(dict(path=str(save),bytes=capture['save']['source']['bytes'],sha256=capture['save']['source']['sha256']),dependencies)
    bootstrap=_check_localization(manifest,folder,capture,dependencies)
    _verify_content_profile(content, capture['preflight']['process'], databases,
                            bootstrap, runtimes, scripts)
    fixture=dict(schema='civ6rl.native-fixture.v1',purpose='diagnostic exact prepared official capture',eligible_for_training=False,
        databases=databases,localization_bootstrap=bootstrap,official_bundle=dict(path=origin[0],sha256=origin[1]),input_profile=input_profile)
    bundle=original.PreparedBundle(origin,inputs,manifest['initial_turn'],Path(engine['path']),fixture,dependencies,
        copy.deepcopy(manifest['expected_readback']),content)
    if candidate is not None:
        candidate.validate_inputs(inputs,bundle)
    return original._remember_prepared_bundle(bundle,input_profile,original._prepared_bundle_validator_digests(),_token=original._PARENT_ADMISSION_TOKEN,_input_only=candidate is not None)


def _verify_content_profile(content, process, databases, bootstrap, runtimes, scripts):
    from .native import native_official_bundle as original
    from .workers.capture_phase1_bundle994 import (
        _content_semantics, _join_native_report, _selection_semantics,
    )

    for runtime in runtimes:
        report = runtime['content929']
        _join_native_report(report, process, 'civ6rl.official_resolved_content929.capture.v1')
        resolved = _content_semantics(report['snapshot'], process)
        selection = _selection_semantics(runtime['gameplay_selection994'], process, resolved)
        active = runtime['gameplay_active_list']
        expected = original.build_content_profile(
            process=process, databases=databases, localization_bootstrap=bootstrap,
            resolved_content=resolved, gameplay_selection=selection,
            active_state=dict(active_count=active['state']['active_count'],
                              selected_and_active_empty=active['selected_and_active_empty']),
            script_manifest=scripts)
        if content != expected:
            raise ValueError('Prepared content profile differs from pinned native runtime evidence')


def try_localization(capture,dependencies,*,reference=None):
    if configured_reference() is None:return None
    from .saved_load_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
    core=capture['preflight']['process']['gamecore_module']['sha256']
    candidate_profile={XP1_CORE_SHA256:'xp1-lan',XP2_CORE_SHA256:'xp2-lan'}.get(core)
    loaded=_load(_candidate_profile=candidate_profile)
    if loaded is None:return None
    _,manifest,folder,_,expected=loaded
    if capture!=expected:raise ValueError('Prepared Localization origin manifest differs')
    if reference is not None:_same_origin(reference,manifest)
    files=_files(manifest,folder)
    for role in ('database_localization','icu_data'):
        row=files[role];dependencies[row['path']]=row['sha256']
    return files['database_localization'],_check_localization(manifest,folder,capture,dependencies)


def _xp2_launch_binding(configuration, gamecore_sha256, initial_turn, readback):
    """Bind the original prepared input, before any checkpoint replacement."""
    from .captured_session_profile import configuration_geometry
    geometry = configuration_geometry(configuration, initial_turn, readback)
    for name in ('major_player_ids', 'taken_player_ids'):
        geometry[name] = list(geometry[name])
    return dict(schema='civ6-host.xp2-prepared-launch.v1',
                configuration_sha256=_sha(configuration), gamecore_sha256=gamecore_sha256,
                saved_geometry=geometry)


def configure_prepared_closure(closure,captured):
    reference=configured_reference()
    if reference is None:return False
    if captured is None:raise ValueError('Prepared capture cannot replace an uncaptured session')
    origin={'path':captured.reference[0],'sha256':captured.reference[1]}
    if closure.get('official_bundle')!=origin:raise ValueError('Prepared closure capture differs')
    if closure['pins'].get(reference['path'])!=reference['sha256']:
        raise ValueError('Prepared package must be pinned in the worker closure')
    if closure.get('input_profile') == 'xp2-lan':
        from .xp2_bundle_inputs import validate_candidate_inputs
        validate_candidate_inputs(captured.inputs, captured)
        closure[XP2_LAUNCH_FIELD] = _xp2_launch_binding(
            captured.inputs.configuration, _sha(captured.inputs.game),
            captured.initial_turn, captured.expected_readback)
    closure[FIELD]=reference
    return True


def consume_prepared_closure(closure,*,environment=None,_xp1_candidate=False,_candidate_profile=None):
    reference=configured_reference()
    if reference is None:
        if FIELD in closure or XP2_LAUNCH_FIELD in closure:
            raise ValueError('Prepared worker closure has no explicit package configuration')
        return None
    env=os.environ if environment is None else environment
    if closure.get(FIELD)!=reference or closure['pins'].get(reference['path'])!=reference['sha256']:
        raise ValueError('Prepared worker reference differs from pinned closure')
    if 'parent_localization_validation' in closure or env.get('CIV6RL_LOCALIZATION_HANDOFF_KEY') is not None:
        raise ValueError('Prepared capture cannot mix with legacy Localization handoff')
    from .capture_candidates import select_private_candidate
    candidate=select_private_candidate(xp1_candidate=_xp1_candidate,
                                       candidate_profile=_candidate_profile)
    _,manifest,_,files,_ = _load(_xp1_candidate=_xp1_candidate,_candidate_profile=_candidate_profile)
    _same_origin(closure['official_bundle'],manifest)
    if closure['input_profile']!=manifest['input_profile']:raise ValueError('Prepared worker profile differs')
    launch_binding = {}
    if XP2_LAUNCH_FIELD in closure:
        if candidate is None or candidate.family != 'xp2-lan':
            raise ValueError('XP2 launch binding requires the explicit XP2 prepared profile')
        with files['configuration_stream'].open('rb') as stream:
            raw = stream.read(4 * 1024**2 + 1)
        pin = manifest['files']['configuration_stream']
        if len(raw) > 4 * 1024**2 or len(raw) != pin['bytes'] or _sha(raw) != pin['sha256']:
            raise ValueError('Prepared configuration changed before launch')
        binding = _xp2_launch_binding(raw, manifest['files']['gamecore_stream']['sha256'],
                                      manifest['initial_turn'], manifest['expected_readback'])
        if json.dumps(closure[XP2_LAUNCH_FIELD], sort_keys=True) != json.dumps(binding, sort_keys=True):
            raise ValueError('XP2 launch binding differs from the verified prepared inputs')
        launch_binding[XP2_LAUNCH_FIELD] = binding
    consumer=validation_identity()
    producer=admit_producer(manifest['validation_identity'],consumer)
    transitions=(_check_xp1_prepared_reader(manifest['validation_identity'],consumer,producer,manifest,reference)
        if candidate is not None and candidate.family=='xp1-lan' and manifest['validation_identity']!=consumer else [])
    if candidate is not None and candidate.family=='xp2-lan' and manifest['validation_identity']!=consumer:
        transitions=_check_xp2_prepared_reader(manifest['validation_identity'],consumer,producer,manifest,reference)
    return dict(schema='civ6-host.prepared-capture-admission.v1',package=reference,
        authority='explicit_prepared_capture_and_versioned_producer_admission',runtime_bytes_revalidated=True,
        producer=producer,input_parser_transitions=transitions,
        actor_input=False,strategic_training_ready=False,**launch_binding)


def prepare_capture(reference,destination,*,input_profile):
    """Use the complete original admission once, then write its immutable inputs."""
    if configured_reference() is not None:
        raise ValueError('Preparation must start from the original capture, not another prepared package')
    from .import_boundary import enable
    from .provenance import verify_installation
    enable();verify_installation()
    from .native import native_official_bundle as original
    from .capture_package import export_capture
    identity=validation_identity()
    bundle=original.read_bundle(reference,input_profile=input_profile)
    if validation_identity()!=identity:raise ValueError('Preparation code changed during capture admission')
    raw=(original.ROOT/bundle.reference[0]).read_bytes()
    package=export_capture(bundle,destination,source_manifest_bytes=raw,validation_identity=identity)
    return dict(schema='civ6-host.capture-preparation.v1',status='prepared_from_full_original_validation',
        package=package,origin=dict(path=bundle.reference[0],sha256=bundle.reference[1]),input_profile=input_profile,
        original_dependency_pins=len(bundle.dependencies),initial_turn=bundle.initial_turn,
        gamecore_launched=False,training_started=False,standalone_host_resources_ready=False)


def main(argv=None):
    import argparse
    import time
    parser=argparse.ArgumentParser(description='Prepare compact native inputs from one fully validated official capture.')
    parser.add_argument('--resources',type=Path,required=True)
    parser.add_argument('--official-bundle',required=True)
    parser.add_argument('--sha256',required=True)
    from .capture_profiles import CAPTURE_MODES
    parser.add_argument('--input-profile',choices=tuple(CAPTURE_MODES),required=True)
    parser.add_argument('--destination',type=Path,required=True)
    args=parser.parse_args(argv)
    if not args.resources.is_absolute() or not args.resources.is_dir() or not args.destination.is_absolute():
        parser.error('Resources and new destination must be explicit absolute paths')
    if os.environ.get(ENV) is not None:parser.error('Unset '+ENV+' before full capture preparation')
    existing=os.environ.get('CIV6_HOST_RESOURCE_ROOT')
    if existing is not None and Path(existing).resolve()!=args.resources.resolve():
        parser.error('Resource environment differs from requested preparation root')
    os.environ['CIV6_HOST_RESOURCE_ROOT']=str(args.resources.resolve())
    started=time.perf_counter()
    report=prepare_capture(dict(path=args.official_bundle,sha256=args.sha256),args.destination,input_profile=args.input_profile)
    report['wall_seconds']=time.perf_counter()-started
    print(json.dumps(report),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
