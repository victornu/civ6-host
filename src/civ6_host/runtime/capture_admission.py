"""Explicit prepared capture inputs for the existing native Load implementation.

Preparation uses the original complete capture validator once. The immutable
package is then checked against its requested hash, installed validator code,
original capture identity and actual runtime files. Old capture evidence stays
separate; this does not qualify a different game profile or remove its guards.
"""
from __future__ import annotations

import copy
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import zipfile

ENV='CIV6_HOST_PREPARED_CAPTURE'
FIELD='prepared_capture'
XP2_LAUNCH_FIELD='xp2_prepared_launch'
_SETTING=object()
_UNSET=_SETTING
_STOCK_XP2_EXECUTION_ASSOCIATION=None
STOCK_XP2_READER_REVALIDATION=(
    'work/official-capture/bbg751-world-A-trade-ui-association/stock-prepared-reader-revalidation.json',
    '3902e018dcdfb8b622007071c2f049035a270441ee3ba9b2c9786308e1589650',
)
_STOCK_XP2_PRODUCER='fb8f64fccfaab86e947eb3f9263a149854bf0a2e7f50cc52fc5ecc6f218993bd'
_OFFICIAL_BUNDLE_READER='runtime/native/native_official_bundle.py'
_STOCK_RESPONSE_ARCHIVE_READER_TRANSITION=(
    '7eb90487b13b23e2bdc2def6a8862c985e083a3d5d27ea1afc150c01864294bd',
    'd4ec5e226a75957a23f37e23f3aa88e92fc79471f8f177ebdb4dd43fb72a822c',
)
_XP1_PACKAGE_READER_DELTA=(
    'c4d00df12acd6b420d55b661b85afff360afa6b41416144d11e2e1a35fb52145',
    '06a6933c0e032f3a15c1d252fca4c6b3f9b9bd04b67e07b7aa559d36e91d34be',
)
_XP1_CURRENT_READER_PINS=(
    'work/trade-common-client/xp1-installed-prepared-reader-with-response-pins.json',
    '390b500d1f1c0fe51b1f822ee021a722f8be6517e68f9723edeb08eb59905f9d',
)
_XP1_HANDOFF_CANDIDATE_DELTA=(
    '7a8cb86925f740aadb49e47e68ed4c0cb09811183024dd9265347da643e1ef75',
    'f7c0a56af6edfa32c8e5ed8327e249c55447eebba7ae78a43b1946a961d2cdf4',
)
_XP1_HANDOFF_ORCHESTRATION_DELTA={
    '_load':('d8bc3bed34d57d9570b7e9d02c9c893108c619dca57d3b9adb31e3878a1cb894',
             '53d421fdd37f4e468513bb3ae74c93208f9ae362518d8e9826cd1493c059558e'),
    'try_bundle':('849910fa484c7dce9018104168d583576a973c01ef1919bf3c69da212b1d77e8',
                  '6abcdf4160ed61063c07a50f0a0a2c60f0209d440a20cc7602b064537907c934'),
    'consume_prepared_closure':('767220c66ff80207e86e41502dee4df95f18b47fe0a89cf10f5ffb69a71c3571',
                                '7f60c413a1e90369a39d0dbb1e913cc10e9408edbf27ca16fef193773b5f344e'),
}

# Explicit artifact-reader compatibility, not a rewrite of producer identity.
# Each entry binds one exact producer identity to its scoped evidence and
# origin. Original validator sources must still match; unknown versions refuse.
_COMPATIBLE_PRODUCERS={
    # Exact producer of the retained current-image World A input package.
    # Its native run is separately reviewed; package reuse still rechecks all
    # current consumer sources and the unchanged input-reader set below.
    '99cf8602fcd4725ae5fec5bd2731f82985c21d70d890294fa77c5cf3747fb31f':{
        'qualification_evidence_path':'evidence/host-current-bbg751-world-a-headless.json',
        'qualification_evidence_sha256':'95f2a08e7053124528424dfc5cf6b2d58247952bf94d49030739fe6836145913',
        'origin_sha256':'0438263e3e78b78233153afe0bc4e1ace6ac8e315aed21e4507f738bae8b285d',
        'origin_path':'work/official-capture/bbg751-world-A-ui/manifest.json',
        'package_sha256':'b4404de5ec63ac9a958ff1c9a84a6c3312eab160f9d1e7cb70454d01bea4d35c',
        'package_path':'work/host-prepared-captures/bbg751-world-A-current-icu/manifest.json',
        'private_input_profile':'xp2-lan',
        'qualification_scope':'world-A single saved-load, offered-action, reset interval',
        'native_session_qualified':True,
        'input_reader_archive_path':('work/official-capture/bbg751-world-A-headless-admission/'
                                     'installed-sources-icu.zip'),
        'input_reader_archive_sha256':'5971579ea40819015ac7825b46c19cefb3e405e49ed5d51340b22d40caa467c6',
        'input_reader_pins_path':('work/official-capture/bbg751-world-A-headless-admission/'
                                  'installed-source-pins-icu.json'),
        'input_reader_pins_sha256':'a41ad53c0971a714dd2fe4b01548207cefca574e2c3c9701f34f79a0570313bb',
    },
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

_XP2_PREPARED_INPUT_MODULES=(
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
    'runtime/xp2_bundle_inputs.py', 'runtime/xp2_bbg_inputs.py',
    'runtime/xp2_capture_selection.py',
)
_CURRENT_BBG_UNCHANGED_READER_FUNCTIONS=(
    '_reference', '_bootstrap', '_same_origin', '_pin_original', '_files',
    '_check_localization', '_verify_content_profile',
)
_CURRENT_BBG_REVIEWED_ORCHESTRATION_AST_SHA256={
    name:pair[1] for name,pair in _XP1_HANDOFF_ORCHESTRATION_DELTA.items()
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


def _stock_xp2_execution(execution_image,reference=None,origin=None):
    if execution_image is None:return False
    from . import xp2_bundle_inputs as xp2
    from .execution_images import identity
    selected=identity(execution_image)
    from .paths import resource_root
    expected_package=(str((resource_root()/'work/host-prepared-captures/'
        'xp2-gs-lan-rows-20261102/manifest.json').resolve()),
        '6468bf13145fa712438bd276896273630789ca4afb6003d904b66a8aa29e2020')
    configured=configured_reference()
    if (selected['profile_id']!='xp2-gamecore-current-092abfbb'
            or selected['image_sha256']!='092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
            or selected['reference_core_sha256']!='324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'
            or selected['path']!=r"C:\Program Files (x86)\Steam\steamapps\common\Sid Meier's Civilization VI\DLC\Expansion2\Binaries\Win64\GameCore_XP2_FinalRelease.dll"
            or configured is None or configured!={'path':expected_package[0],'sha256':expected_package[1]}
            or (reference is not None and reference!=configured)
            or (origin is not None and origin!=xp2.REFERENCE)):
        raise ValueError('Current execution image requires the exact retained stock XP2 package and origin')
    return True


def _register_stock_xp2_execution(reference,origin,execution_image,producer):
    global _STOCK_XP2_EXECUTION_ASSOCIATION
    from .execution_images import identity
    association=(copy.deepcopy(reference),tuple(origin),identity(execution_image),
        execution_image,copy.deepcopy(producer))
    if (_STOCK_XP2_EXECUTION_ASSOCIATION is not None
            and (_STOCK_XP2_EXECUTION_ASSOCIATION[:3]!=association[:3]
                 or _STOCK_XP2_EXECUTION_ASSOCIATION[4]!=association[4])):
        raise RuntimeError('Stock XP2 execution association is frozen for this process')
    _STOCK_XP2_EXECUTION_ASSOCIATION=association


def _prepared_xp2_execution(execution_image, reference=None, origin=None):
    """Keep captured current BBG inputs distinct from the retained stock pair."""
    if execution_image is None:
        return False
    from . import xp2_bbg_inputs as bbg
    registered = bbg.registered_reference()
    if registered is None or origin != registered:
        return _stock_xp2_execution(execution_image, reference=reference, origin=origin)
    from .execution_images import identity
    selected = identity(execution_image)
    configured = configured_reference()
    if (selected['profile_id'] != 'xp2-gamecore-current-092abfbb'
            or selected['reference_core_sha256'] != bbg.xp2.XP2_CORE_SHA256
            or configured is None or reference is not None and reference != configured):
        raise ValueError('Current BBG execution requires its exact registered origin and prepared package')
    return True


def _prepared_current_execution(execution_image, reference, origin):
    from .execution_images import _XP1_PROFILE
    if execution_image is not _XP1_PROFILE:
        return _prepared_xp2_execution(execution_image, reference=reference, origin=origin)
    from .paths import resource_root
    from .xp1_prepared_reader_transition import PACKAGE_RELATIVE, PACKAGE_SHA256
    from .xp1_saved_load import REFERENCE
    expected=dict(path=str((resource_root()/PACKAGE_RELATIVE).resolve()),sha256=PACKAGE_SHA256)
    if reference!=expected or configured_reference()!=expected or origin!=REFERENCE:
        raise ValueError('Current XP1 execution requires its exact prepared package and origin')
    return True


def _review_xp1_current_reader(producer,consumer,manifest,execution_image):
    """Check the reader identity before the full current input revalidation."""
    from .execution_images import identity
    from .native.native_source_cache import load_pinned_json
    from .paths import resource_root
    from .xp1_prepared_reader_transition import PACKAGE_SHA256, PRODUCER_IDENTITY_SHA256
    path=(resource_root()/_XP1_CURRENT_READER_PINS[0]).resolve(strict=True)
    proof=load_pinned_json(path,_XP1_CURRENT_READER_PINS[1])
    digest=_sha(json.dumps(producer,sort_keys=True,separators=(',',':')).encode())
    if (proof['schema']!='civ6-host.xp1-installed-prepared-reader-pins.v1'
            or proof['producer_identity_sha256']!=digest or digest!=PRODUCER_IDENTITY_SHA256
            or manifest['input_profile']!='xp1-lan' or manifest['origin']!=proof['origin']
            or proof['package']['sha256']!=PACKAGE_SHA256
            or proof['execution_image']!=identity(execution_image)
            or producer['schema']!=consumer['schema']):
        raise ValueError('Current XP1 prepared reader has a different capture or producer')
    tools=proof['original_tool_pairs']
    if (producer['original_validator_sources']!={name:pair[0] for name,pair in tools.items()}
            or consumer['original_validator_sources']!={name:pair[1] for name,pair in tools.items()}):
        raise ValueError('Current XP1 original input tool differs from its reviewed identity')
    for name,pair in proof['input_reader_pairs'].items():
        if (producer['runtime_sources'].get(name),consumer['runtime_sources'].get(name))!=tuple(pair):
            raise ValueError('Current XP1 input reader differs from its reviewed identity: '+name)
    return dict(mode='exact_xp1_current_input_revalidation',producer_identity_sha256=digest,
                reader_pins_sha256=_XP1_CURRENT_READER_PINS[1],producer_identity_substituted=False)


def _stock_xp2_association(capture,reference=None):
    association=_STOCK_XP2_EXECUTION_ASSOCIATION
    if association is None:return None
    package_ref,origin,image_identity,execution_image,producer=association
    configured=configured_reference()
    if (configured!=package_ref or (reference is not None and reference!=tuple(origin))
            or type(capture) is not dict):
        raise ValueError('Stock XP2 execution association belongs to another capture')
    return execution_image,copy.deepcopy(producer),image_identity


def require_explicit_stock_execution(reference,execution_image):
    if execution_image is not None:return
    association=_STOCK_XP2_EXECUTION_ASSOCIATION
    if association is not None:
        raise ValueError('Stock XP2 current-image handoff must explicitly repeat its selected image')


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
    if digest not in _COMPATIBLE_PRODUCERS or producer.get('schema')!=consumer.get('schema'):
        raise ValueError('Prepared capture producer is not compatible with this reader')
    extra={}
    if producer.get('original_validator_sources')!=consumer.get('original_validator_sources'):
        if digest!=_STOCK_XP2_PRODUCER:
            raise ValueError('Prepared capture producer is not compatible with this reader')
        _check_stock_xp2_prepared_reader(producer,consumer)
        extra['stock_reader_revalidation_sha256']=STOCK_XP2_READER_REVALIDATION[1]
    mode=('retained_preparation_producer' if
          _COMPATIBLE_PRODUCERS[digest].get('native_session_qualified') is False
          else 'retained_qualified_producer')
    return dict(mode=mode,producer_identity_sha256=digest,
        **_COMPATIBLE_PRODUCERS[digest],**extra)


def _check_stock_xp2_prepared_reader(producer,consumer):
    """Allow the exact stock producer only after scoped current-reader review."""
    from .paths import resource_root
    from .native.native_source_cache import load_pinned_json
    root=resource_root()
    path,digest=STOCK_XP2_READER_REVALIDATION
    proof=load_pinned_json(root/path,digest)
    scope=_COMPATIBLE_PRODUCERS[_STOCK_XP2_PRODUCER]
    package=proof['package']
    if (proof['schema']!='civ6-host.stock-xp2-retained-reader-revalidation.v1'
            or proof['producer_identity_sha256']!=_STOCK_XP2_PRODUCER
            or package['sha256']!=scope['package_sha256']
            or proof['origin']['path']!=scope['origin_path']
            or proof['origin']['sha256']!=scope['origin_sha256']
            or configured_reference()!=dict(path=str((root/package['path']).resolve()),sha256=package['sha256'])):
        raise ValueError('Stock XP2 reader requires its exact retained package and origin')
    before=producer['original_validator_sources']
    expected=dict(before)
    for key,(previous,current) in proof['changed_original_capture_tools'].items():
        if before.get(key)!=previous:
            raise ValueError('Stock XP2 capture producer input identity changed')
        expected[key]=current
    readers=dict(proof['current_reader_sha256'])
    previous,current=_STOCK_RESPONSE_ARCHIVE_READER_TRANSITION
    if readers[_OFFICIAL_BUNDLE_READER]!=previous:
        raise ValueError('Stock XP2 response archive reader has no reviewed predecessor')
    readers[_OFFICIAL_BUNDLE_READER]=current
    # The retained AST comparisons remove only the guarded XP1 branches.
    for module,(previous,current) in (
            ('runtime/capture_package.py',_XP1_PACKAGE_READER_DELTA),
            ('runtime/capture_candidates.py',_XP1_HANDOFF_CANDIDATE_DELTA)):
        if readers[module]!=previous:
            raise ValueError('Stock XP2 package reader has no exact XP1-only transition')
        readers[module]=current
    if expected!=consumer['original_validator_sources'] or any(
            consumer['runtime_sources'].get(key)!=expected_hash
            for key,expected_hash in readers.items()):
        raise ValueError('Stock XP2 current input reader changed')
    functions=_current_bbg_functions(Path(__file__).read_bytes())
    orchestration=dict(proof['current_reader_ast_sha256'])
    for name,(previous,current) in _XP1_HANDOFF_ORCHESTRATION_DELTA.items():
        if orchestration[name]!=previous:
            raise ValueError('Stock XP2 orchestration has no exact XP1-only transition')
        orchestration[name]=current
    if any(_sha(ast.dump(functions[name],include_attributes=False).encode('utf-8'))!=expected_hash
            for name,expected_hash in orchestration.items()):
        raise ValueError('Stock XP2 input reader orchestration changed')


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


def _check_xp2_prepared_reader(producer,consumer,admission,manifest,reference,*,
                               native_session_qualified=False):
    """Reuse the exact input package with unchanged original input decoders.

    Native callback additions are independently source-pinned by their caller;
    they cannot authorize a different input parser, capture or engine. The
    recorded producer stays intact and this admits no native game session.
    """
    if (admission.get('private_input_profile')!='xp2-lan'
            or admission.get('native_session_qualified') is not native_session_qualified
            or manifest['input_profile']!='xp2-lan'
            or manifest['origin']['path']!=admission.get('origin_path')
            or manifest['origin']['sha256']!=admission.get('origin_sha256')
            or reference.get('sha256')!=admission.get('package_sha256')):
        raise ValueError('Prepared XP2 producer lacks its exact qualified input-only scope')
    from .xp2_bundle_inputs import reader_validator_digests
    package=Path(__file__).resolve().parents[1]
    validators={Path(p).relative_to(package).as_posix():digest
                for p,digest in reader_validator_digests().items()}
    for key in _XP2_PREPARED_INPUT_MODULES:
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
        if (native_session_qualified
                and key==_OFFICIAL_BUNDLE_READER
                and (previous,digest)==_STOCK_RESPONSE_ARCHIVE_READER_TRANSITION):
            reader_transitions.append(dict(module=key, producer_sha256=previous, consumer_sha256=digest,
                transition='exact_stock_xp2_response_source_archive',
                changed_functions=['_stock_response_source_archive','_response_transport'],
                bbg_reader_branch_unchanged=True, producer_identity_substituted=False))
            continue
        if (native_session_qualified and (key, previous, digest) == (
                'runtime/capture_script_paths.py',
                'b7b4f2f753ce59787507341bc4591a34844b6cab5f763d5282a174c7fabeabac',
                'c8edf2b81fe45855242ce155a7abe14dd3bec78cc52d752eda2a155c695a1220')):
            if (producer['runtime_sources'].get('runtime/script_wire_paths.py')
                    != '444211fbf3e716bd450d5ba3556db003741f62645bf47eaa8b4cfa16d3694898'
                    or consumer['runtime_sources'].get('runtime/script_wire_paths.py')
                    != '341089859dc5249b7823ef01ca390b6d76205d2da1298a81ce25eead4c7f07c2'
                    or consumer['runtime_sources'].get('runtime/script_observer_sources.py')
                    != '84c2524fbb8adad27f8d768166637d022d71e10c6d0336f6c13038aa963be933'):
                raise ValueError('Retained observer source reader changed')
            reader_transitions.append(dict(module=key, producer_sha256=previous, consumer_sha256=digest,
                transition='exact_retained_script_observer_bytes', witness_reference_unchanged=True,
                source_review_sha256='07a2a393a785d326d72eb51c5a984fb906b3d69edf310d1da9302f5af65a9e80',
                producer_identity_substituted=False))
            continue
        if (key,previous,digest)==(
                'runtime/capture_script_paths.py',
                'd1ed79521048d0d451714b4642267faa29f91656e9259d2cb5eefcb8fd982c87',
                '44763044232af82190a01dbd3f7b249184566285eeacd12cedec3f298d1ffc9c'):
            reader_transitions.append(dict(module=key,producer_sha256=previous,consumer_sha256=digest,
                transition='xp2_script_proof_physical_path_relocation_v1',
                logical_reference_preserved=True,proof_bytes_rechecked=True,
                producer_identity_substituted=False))
            continue
        if (key, previous, digest) == (
                'runtime/capture_script_paths.py',
                'd1ed79521048d0d451714b4642267faa29f91656e9259d2cb5eefcb8fd982c87',
                'f9ad44fb643e4abeb6a78b83b8e5ec9b147e1e191484732b134be828107c2a91'):
            reader_transitions.append(dict(module=key, producer_sha256=previous, consumer_sha256=digest,
                transition='xp2_script_proof_pinned_workshop_path_support',
                stock_relative_path_resolution_unchanged=True, proof_bytes_rechecked=True,
                producer_identity_substituted=False))
            continue
        if (key, previous, digest) == (
                'runtime/capture_candidates.py',
                'eec84eb7164e1febf6be4cd5472e8309ffacbdc018ecf3c19014e15d544eac93',
                'fb4c7c279910ee49bf4eb098314166c79f5eaf8ff208f583786752c18af36e72'):
            reader_transitions.append(dict(module=key, producer_sha256=previous, consumer_sha256=digest,
                transition='explicit_bbg751_handoff_selection',
                original_stock_validator_unchanged=True, producer_identity_substituted=False))
            continue
        if (key, previous, digest) == (
                'runtime/native/native_localization.py',
                '9c6c4f9fe1e8498cc15997d4d5a85ce91840f68ff9265e70ff3512538092523e',
                'b7b4e3218e4e22c9c773155fea86f08c78950d7568923c383aa6ef0b149cb3d7'):
            reader_transitions.append(dict(module=key, producer_sha256=previous, consumer_sha256=digest,
                transition='exact_bbg751_private_localization_branch',
                original_stock_validator_unchanged=True, producer_identity_substituted=False))
            continue
        if (key, previous, digest) == (
                'runtime/native/native_official_bundle.py',
                '713204d0a967b415a5bdd5d809c3045b945ef33ae5963469fd2fa5b62bffd83f',
                'e31887271a31d1c62bfdea18a309d2c05d89d9ea2b11e54389b54f8aba1b1946'):
            reader_transitions.append(dict(module=key, producer_sha256=previous, consumer_sha256=digest,
                transition='optional_authenticated_file_prefix', original_stock_validator_unchanged=True,
                producer_identity_substituted=False))
            continue
        if (key, previous, digest) == (
                'runtime/native/native_source_cache.py',
                '33a5680d79204bf54944b8dd7f3a386a782ed26fcbd4baa6319b216f17a27457',
                '62e3c722719e25a49c5840e4ca79ac56d6b471d3255f0ae1df48f9a77b425dfa'):
            reader_transitions.append(dict(module=key, producer_sha256=previous, consumer_sha256=digest,
                transition='parent_scoped_static_proof_reuse', original_stock_validator_unchanged=True,
                producer_identity_substituted=False))
            continue
        if native_session_qualified and (key,previous,digest) in (
                ('runtime/capture_package.py',*_XP1_PACKAGE_READER_DELTA),
                ('runtime/capture_candidates.py',*_XP1_HANDOFF_CANDIDATE_DELTA)):
            reader_transitions.append(dict(module=key, producer_sha256=previous, consumer_sha256=digest,
                transition='exact_xp1_engine_gate_in_shared_package_reader',
                original_input_parsers_unchanged=True, producer_identity_substituted=False))
            continue
        if (native_session_qualified and (key, previous, digest) == (
                'runtime/xp2_bbg_inputs.py',
                'fd2cc4a9779fb17c136c0da6209ffef4f936652ae39c5da487f69129bd33238a',
                'bb7b2171e24a8a7dd8228e6cfa72dfcfabeb1d8e3de681e0cb9de3739fff0617')):
            reader_transitions.append(dict(module=key, producer_sha256=previous, consumer_sha256=digest,
                transition='world_a_current_strings_host_selection',
                source_review_sha256='64dea572a7e4162989ab0182c152c8a47921d588e8601fc4bdeb45c0b81757f8',
                original_input_parsers_unchanged=True, producer_identity_substituted=False))
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


def _current_bbg_functions(source):
    try:
        tree=ast.parse(source.decode('utf-8'))
    except (UnicodeDecodeError,SyntaxError) as exc:
        raise ValueError('Current BBG reader source is not valid Python') from exc
    return {node.name:node for node in tree.body
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))}


def _check_current_bbg_reader_source(producer,consumer,*,current_source=None):
    """Reconcile exact archived input readers and reviewed local orchestration."""
    digest=_sha(json.dumps(producer,sort_keys=True,separators=(',',':')).encode())
    proof=_COMPATIBLE_PRODUCERS.get(digest)
    if proof is None or proof.get('package_sha256')!='b4404de5ec63ac9a958ff1c9a84a6c3312eab160f9d1e7cb70454d01bea4d35c':
        raise ValueError('Current BBG reader has no pinned producer archive')
    from .paths import resource_root
    root=resource_root()
    archive_path=(root/proof['input_reader_archive_path']).resolve(strict=True)
    pins_path=(root/proof['input_reader_pins_path']).resolve(strict=True)
    if (not archive_path.is_relative_to(root/'work') or not pins_path.is_relative_to(root/'work')
            or archive_path.stat().st_size>8*1024*1024
            or pins_path.stat().st_size>1024*1024):
        raise ValueError('Current BBG reader proof files exceed their retained bounds')
    archive_raw=archive_path.read_bytes()
    pins_raw=pins_path.read_bytes()
    if (_sha(archive_raw)!=proof['input_reader_archive_sha256']
            or _sha(pins_raw)!=proof['input_reader_pins_sha256']):
        raise ValueError('Current BBG reader archive or source pins changed')
    pins=json.loads(pins_raw)
    if type(pins) is not dict or len(pins)!=753:
        raise ValueError('Current BBG reader source pin set differs from its retained scope')
    package=Path(__file__).resolve().parents[1]
    current_source=Path(__file__).read_bytes() if current_source is None else current_source
    current_sha=_sha(current_source)
    current_map=consumer.get('runtime_sources') if type(consumer) is dict else None
    producer_map=producer.get('runtime_sources') if type(producer) is dict else None
    if (type(current_map) is not dict or current_map.get('runtime/capture_admission.py')!=current_sha
            or type(producer_map) is not dict):
        raise ValueError('Current BBG capture-admission source identity differs')
    try:
        with zipfile.ZipFile(archive_path) as source_archive:
            members=set(source_archive.namelist())
            reader_rows={}
            for name in (*_XP2_PREPARED_INPUT_MODULES,'runtime/capture_admission.py'):
                member='src/civ6_host/'+name
                if member not in members:
                    raise ValueError('Current BBG reader archive lacks a required input source')
                raw=source_archive.read(member)
                if len(raw)>4*1024*1024:
                    raise ValueError('Current BBG reader archive source exceeds its bound')
                source_sha=_sha(raw)
                installed_path=str((package/name).resolve())
                if (pins.get(installed_path)!=source_sha
                        or producer_map.get(name)!=source_sha):
                    raise ValueError('Current BBG producer reader differs from its pinned archive: '+name)
                reader_rows[name]=source_sha
            archived_admission=source_archive.read('src/civ6_host/runtime/capture_admission.py')
    except (OSError,zipfile.BadZipFile,KeyError) as exc:
        raise ValueError('Current BBG reader source archive is malformed') from exc
    current_functions=_current_bbg_functions(current_source)
    producer_functions=_current_bbg_functions(archived_admission)
    for name in _CURRENT_BBG_UNCHANGED_READER_FUNCTIONS:
        if name not in current_functions or name not in producer_functions:
            raise ValueError('Current BBG input reader function is absent: '+name)
        if (ast.dump(current_functions[name],include_attributes=False)
                !=ast.dump(producer_functions[name],include_attributes=False)):
            raise ValueError('Current BBG archived input reader function changed: '+name)
    orchestration={}
    for name,expected_sha in _CURRENT_BBG_REVIEWED_ORCHESTRATION_AST_SHA256.items():
        node=current_functions.get(name)
        if node is None:
            raise ValueError('Current BBG admission orchestration function is absent: '+name)
        actual_sha=_sha(ast.dump(node,include_attributes=False).encode('utf-8'))
        if actual_sha!=expected_sha:
            raise ValueError('Current BBG admission orchestration changed: '+name)
        orchestration[name]=actual_sha
    return dict(schema='civ6-host.current-bbg-input-reader-source-proof.v1',
        producer_identity_sha256=digest,archive_path=proof['input_reader_archive_path'],
        archive_sha256=proof['input_reader_archive_sha256'],pins_path=proof['input_reader_pins_path'],
        pins_sha256=proof['input_reader_pins_sha256'],archived_input_module_count=len(_XP2_PREPARED_INPUT_MODULES),
        archived_input_module_sha256=reader_rows,
        unchanged_reader_functions=list(_CURRENT_BBG_UNCHANGED_READER_FUNCTIONS),
        reviewed_orchestration_ast_sha256=orchestration,
        producer_identity_substituted=False,native_session_admitted=False)


def _check_current_bbg_prepared_reader(producer,consumer,manifest,reference):
    """Admit only the retained World A package with its archived input readers."""
    digest=_sha(json.dumps(producer,sort_keys=True,separators=(',',':')).encode())
    expected=_COMPATIBLE_PRODUCERS.get(digest)
    if (expected is None or expected.get('package_sha256')!='b4404de5ec63ac9a958ff1c9a84a6c3312eab160f9d1e7cb70454d01bea4d35c'
            or expected.get('origin_sha256')!='0438263e3e78b78233153afe0bc4e1ace6ac8e315aed21e4507f738bae8b285d'):
        raise ValueError('Current BBG prepared reader has no exact producer proof')
    from .paths import resource_root
    expected_package=(resource_root()/expected['package_path']).resolve(strict=True)
    expected_origin={'path':expected['origin_path'],'sha256':expected['origin_sha256']}
    if (type(reference) is not dict or reference.get('sha256')!=expected['package_sha256']
            or Path(reference.get('path','')).resolve()!=expected_package
            or manifest.get('origin')!=expected_origin):
        raise ValueError('Current BBG prepared reader package or origin differs from its exact proof')
    evidence_path=(resource_root()/expected['qualification_evidence_path']).resolve(strict=True)
    if (not evidence_path.is_relative_to(resource_root()/'evidence')
            or evidence_path.stat().st_size>256*1024):
        raise ValueError('Current BBG qualification evidence exceeds its retained bound')
    evidence_raw=evidence_path.read_bytes()
    if _sha(evidence_raw)!=expected['qualification_evidence_sha256']:
        raise ValueError('Current BBG scoped qualification evidence changed')
    evidence=json.loads(evidence_raw)
    prepared=evidence.get('prepared_package',{})
    qualified=evidence.get('qualification',{})
    if (evidence.get('schema')!='civ6-host.current-bbg-world-input-admission.v1'
            or evidence.get('status')!='passed_scoped_native_input_action_reset'
            or evidence.get('source_capture')!=expected_origin
            or prepared.get('sha256')!=expected['package_sha256']
            or Path(prepared.get('path','')).resolve()!=expected_package
            or qualified.get('new_world_native_load') is not True
            or qualified.get('initial_official_readback_equal') is not True
            or qualified.get('reset_restores_entire_initial_client_observation') is not True
            or qualified.get('strategic_training_ready') is not False
            or qualified.get('whole_game_fidelity_100_percent_claimed') is not False):
        raise ValueError('Current BBG qualification evidence differs from its bounded scope')
    if producer.get('original_validator_sources')!=consumer.get('original_validator_sources'):
        raise ValueError('Current BBG original capture validators changed')
    source_proof=_check_current_bbg_reader_source(producer,consumer)
    transition=_check_xp2_prepared_reader(producer,consumer,expected,manifest,reference,
                                          native_session_qualified=True)
    transition[0]['reader_source_proof']=source_proof
    return transition


def _load(*, _xp1_candidate=False, _candidate_profile=None,execution_image=None):
    from .capture_candidates import select_private_candidate
    from .execution_images import _XP1_PROFILE
    candidate=select_private_candidate(xp1_candidate=_xp1_candidate,
                                       candidate_profile=_candidate_profile)
    reference=configured_reference()
    if reference is None:return None
    current_stock=_prepared_current_execution(execution_image,reference=reference,
        origin=(candidate.reference if candidate is not None else None))
    from .capture_package import read_package
    manifest,folder,files=read_package(reference, _xp1_candidate=_xp1_candidate,
                                      _candidate_profile=_candidate_profile,
                                      **({'execution_image':execution_image} if current_stock else {}))
    producer,consumer=manifest['validation_identity'],validation_identity()
    if execution_image is _XP1_PROFILE:
        _review_xp1_current_reader(producer,consumer,manifest,execution_image)
    else:
        admission=admit_producer(producer,consumer)
        if candidate is not None and candidate.family=='xp1-lan' and producer != consumer:
            _check_xp1_prepared_reader(producer,consumer,admission,manifest,reference)
    if candidate is not None and candidate.family=='xp2-lan':
        from . import xp2_bbg_inputs as bbg
        if (current_stock and producer!=consumer
                and candidate.reference==bbg.registered_reference()):
            _check_current_bbg_prepared_reader(producer,consumer,manifest,reference)
        elif producer!=consumer and not current_stock:
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


def try_bundle(reference,*,input_profile,_xp1_candidate=False,_candidate_profile=None,
               execution_image=None):
    from .execution_images import _XP1_PROFILE
    from .capture_candidates import select_private_candidate
    from . import xp2_bbg_inputs as bbg
    candidate=select_private_candidate(xp1_candidate=_xp1_candidate,
                                       candidate_profile=_candidate_profile,
                                       official_bundle=reference)
    loaded=_load(_xp1_candidate=_xp1_candidate,_candidate_profile=_candidate_profile,
                 execution_image=execution_image)
    if loaded is None:return None
    package_ref,manifest,folder,_,capture=loaded
    origin=_same_origin(reference,manifest)
    if manifest['input_profile']!=input_profile:raise ValueError('Prepared capture turn profile differs')
    input_parser_transitions=[]
    if (execution_image is not None
            and manifest['validation_identity']!=validation_identity()
            and candidate is not None and candidate.family=='xp2-lan'
            and origin==bbg.registered_reference()):
        input_parser_transitions=_check_current_bbg_prepared_reader(
            manifest['validation_identity'],validation_identity(),manifest,package_ref)
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
    complete_bbg = candidate is not None and origin != bbg.REFERENCE and bbg.is_reference(origin)
    if not complete_bbg:
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
    if complete_bbg and execution_image is not None:
        CORE_SHA256 = execution_image.image_sha256
    if (content['engine']['gamecore_sha256']!=engine['sha256'] or engine['sha256']!=CORE_SHA256
            or capture['preflight']['process']['gamecore_module']['sha256']!=engine['sha256']):
        raise ValueError('Prepared engine/content identity differs')
    dependencies={str((folder/r['path']).resolve()):r['sha256'] for r in manifest['files'].values()}
    dependencies.update({package_ref['path']:package_ref['sha256'],str((original.ROOT/origin[0]).resolve()):origin[1],str(Path(engine['path']).resolve()):engine['sha256']})
    if execution_image is not None:
        if not (candidate is not None
                and (candidate.family=='xp2-lan' or (candidate.family=='xp1-lan' and execution_image is _XP1_PROFILE))
                and _prepared_current_execution(execution_image,reference=package_ref,origin=origin)):
            raise ValueError('Selected execution image is not admitted for this prepared capture')
        from .execution_images import runtime_source_pins
        if complete_bbg:
            # This origin was captured from the actual current image. Its
            # provenance must never be rewritten to the reference ABI image.
            if dependencies.get(execution_image.path) != execution_image.image_sha256:
                raise ValueError('Current BBG package does not pin its actual captured Core')
        else:
            selected_dependencies=runtime_source_pins(dependencies,execution_image=execution_image)
            if (selected_dependencies.get(execution_image.path)!=execution_image.image_sha256
                    or dependencies.get(execution_image.path)!=execution_image.reference_core_sha256):
                raise ValueError('Stock package does not pin the exact reference Core dependency')
            dependencies=selected_dependencies
        if execution_image is _XP1_PROFILE:
            from .paths import resource_root
            pin_path,pin_hash=_XP1_CURRENT_READER_PINS
            dependencies[str((resource_root()/pin_path).resolve(strict=True))]=pin_hash
    if complete_bbg:
        bbg.verify_original_streams(inputs, capture, dependencies)
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
    if complete_bbg:
        from .xp2_capture_selection import _selected_scripts
        from .resource_resolution import resolve_path
        capture_folder = resolve_path(original.ROOT / origin[0]).resolve(strict=True).parent
        scripts, _, _ = _selected_scripts(capture, capture['preflight']['process'], capture_folder,
                                          dependencies, bbg751=True)
    elif candidate is not None and candidate.family=='xp2-lan':
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
        copy.deepcopy(manifest['expected_readback']),content,execution_image=execution_image)
    if candidate is not None:
        candidate.validate_inputs(inputs,bundle)
    admitted=original._remember_prepared_bundle(bundle,input_profile,original._prepared_bundle_validator_digests(),_token=original._PARENT_ADMISSION_TOKEN,_input_only=candidate is not None)
    if execution_image is not None:
        producer,consumer=manifest['validation_identity'],validation_identity()
        producer_admission=(_review_xp1_current_reader(producer,consumer,manifest,execution_image)
                            if execution_image is _XP1_PROFILE else admit_producer(producer,consumer))
        if input_parser_transitions:
            producer_admission['input_parser_transitions']=copy.deepcopy(input_parser_transitions)
        _register_stock_xp2_execution(package_ref,origin,execution_image,producer_admission)
    return admitted


def _verify_content_profile(content, process, databases, bootstrap, runtimes, scripts):
    from .native import native_official_bundle as original
    from .workers.capture_phase1_bundle994 import (
        _content_semantics, _join_native_report, _selection_semantics,
    )

    for runtime in runtimes:
        report = runtime['content929']
        from .workers.capture_phase1_bundle994 import CURRENT_EXE_SHA
        _join_native_report(report, process,
            'civ6rl.official_resolved_content929.capture.v2' if process.get('exe_sha256') == CURRENT_EXE_SHA
            else 'civ6rl.official_resolved_content929.capture.v1')
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
    association=_stock_xp2_association(capture,reference)
    execution_image=None if association is None else association[0]
    if execution_image is not None and core == execution_image.image_sha256:
        candidate_profile = 'xp2-lan'
    loaded=_load(_candidate_profile=candidate_profile,execution_image=execution_image)
    if loaded is None:return None
    _,manifest,folder,_,expected=loaded
    if capture!=expected:raise ValueError('Prepared Localization origin manifest differs')
    if reference is not None:_same_origin(reference,manifest)
    files=_files(manifest,folder)
    for role in ('database_localization','icu_data'):
        row=files[role];dependencies[row['path']]=row['sha256']
    result=files['database_localization'],_check_localization(manifest,folder,capture,dependencies)
    if association is not None:
        from .execution_images import identity
        if association[2]!=identity(execution_image):
            raise ValueError('Stock XP2 Localization image differs from its frozen package association')
    return result


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
    execution = getattr(captured, 'execution_image', None)
    if execution is not None:
        from .execution_images import identity
        selected = identity(execution)
        if closure.get('execution_image', selected) != selected:
            raise ValueError('Worker execution image differs from its admitted input owner')
        closure['execution_image'] = selected
    elif 'execution_image' in closure:
        raise ValueError('Worker cannot add an execution image to a historical input owner')
    if closure.get('input_profile') == 'xp2-lan':
        from .captured_saved_load import validate_candidate_inputs
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
    from . import xp2_bbg_inputs as bbg
    candidate=select_private_candidate(xp1_candidate=_xp1_candidate,
                                       candidate_profile=_candidate_profile,
                                       official_bundle=closure.get('official_bundle'))
    if candidate is not None and candidate.reference == bbg.REFERENCE:
        if reference != bbg.prepared_reference() or closure['input_profile'] != candidate.family:
            raise ValueError('BBG worker requires its exact recovered handoff')
        execution_options = {}
        if 'execution_image' in closure:
            from .execution_images import from_identity
            execution_options['execution_image'] = from_identity(closure['execution_image'])
        bundle = bbg.read_bundle(**execution_options)
        binding = _xp2_launch_binding(bundle.inputs.configuration, _sha(bundle.inputs.game),
                                      bundle.initial_turn, bundle.expected_readback)
        if json.dumps(closure.get(XP2_LAUNCH_FIELD), sort_keys=True) != json.dumps(binding, sort_keys=True):
            raise ValueError('BBG launch binding differs from the verified recovered inputs')
        return dict(schema='civ6-host.prepared-capture-admission.v1', package=reference,
            authority='exact_bbg751_recovered_capture_revalidation', runtime_bytes_revalidated=True,
            actor_input=False, strategic_training_ready=False, **{XP2_LAUNCH_FIELD: binding})
    if 'execution_image' in closure:
        from .execution_images import _XP1_PROFILE, from_identity
        selected=closure['execution_image']
        if type(selected) is dict and selected.get('profile_id')==_XP1_PROFILE.id:
            execution_image=from_identity(selected)
            if (candidate is None or candidate.family!='xp1-lan'
                    or closure.get('input_profile')!='xp1-lan'
                    or closure.get('official_bundle')!=dict(path=candidate.reference[0],sha256=candidate.reference[1])
                    or XP2_LAUNCH_FIELD in closure):
                raise ValueError('Selected XP1 image requires the retained Rise and Fall worker closure')
            bundle=try_bundle(candidate.reference,input_profile=candidate.family,
                _xp1_candidate=_xp1_candidate,_candidate_profile=_candidate_profile,
                execution_image=execution_image)
            association=_STOCK_XP2_EXECUTION_ASSOCIATION
            if (bundle is None or association is None or association[2]!=closure['execution_image']
                    or any(closure['pins'].get(path)!=digest for path,digest in bundle.dependencies.items())):
                raise ValueError('XP1 worker pins differ from the fully revalidated capture')
            return dict(schema='civ6-host.prepared-capture-admission.v1',package=reference,
                authority='exact_current_xp1_full_input_revalidation',runtime_bytes_revalidated=True,
                producer=copy.deepcopy(association[4]),actor_input=False,strategic_training_ready=False)
        if (candidate is None or candidate.family!='xp2-lan'
                or closure.get('input_profile')!='xp2-lan'):
            raise ValueError('Selected current image requires the exact stock XP2 candidate')
        execution_image=from_identity(closure['execution_image'])
        _prepared_xp2_execution(execution_image,reference=reference,origin=candidate.reference)
        bundle=try_bundle(candidate.reference,input_profile=candidate.family,
            _xp1_candidate=_xp1_candidate,_candidate_profile=_candidate_profile,
            execution_image=execution_image)
        if bundle is None:
            raise ValueError('Selected current image requires its exact prepared XP2 package')
        binding=_xp2_launch_binding(bundle.inputs.configuration,_sha(bundle.inputs.game),
                                    bundle.initial_turn,bundle.expected_readback)
        if json.dumps(closure.get(XP2_LAUNCH_FIELD),sort_keys=True)!=json.dumps(binding,sort_keys=True):
            raise ValueError('XP2 launch binding differs from the fully revalidated stock inputs')
        association=_STOCK_XP2_EXECUTION_ASSOCIATION
        if association is None or association[2]!=closure['execution_image']:
            raise ValueError('Stock XP2 execution association was not established by full input validation')
        authority = ('exact_registered_bbg751_current_image_full_revalidation'
                     if bbg.is_reference(candidate.reference) else 'exact_stock_xp2_current_image_full_revalidation')
        return dict(schema='civ6-host.prepared-capture-admission.v1',package=reference,
            authority=authority,runtime_bytes_revalidated=True,
            producer=copy.deepcopy(association[4]),
            input_parser_transitions=copy.deepcopy(association[4].get('input_parser_transitions',[])),
            actor_input=False,strategic_training_ready=False,**{XP2_LAUNCH_FIELD:binding})
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
