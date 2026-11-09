"""PRIVATE, UNAPPLIED: fixed TopPanel formatter inside the existing owner.

No formatter is selected by a request. The sole inputs are the already
validated raw session.v1 response and the retained localization owner. This
module does not collect a second observation or change Save/checkpoint data.
Live XP2/fr_FR qualification remains pending; offline fixtures are not receipts.
"""
from __future__ import annotations
import ast
import copy
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import struct
import threading

from civ6_host.contracts import yield_display982 as yields
from civ6_host.runtime import core_script_services
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.deferred_service import DeferredService
from civ6_host.runtime.native import native_locale_arguments as arguments
from civ6_host.runtime.native import native_locale_number982 as number
from civ6_host.runtime.native.native_official_load import OfficialLoadBackend
from civ6_host.runtime.native.native_script_runtime import NativeScriptRuntime
from civ6_host.runtime.native.native_script_threads import ThreadRegistry, ScriptContext
from civ6_host.runtime.network_protocol import NetworkProtocol, validate_network_response
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.xp1_continuation import SavedContinuation
from civ6_host.runtime.xp1_ui_binding import SavedPlayerView
from civ6_host.runtime.xp2_ui_binding_source import SOURCE as UI_SOURCE

SOURCE_SHA256='7749c927e085cc017839ab2a9f8f5e0fb7f8095a9f41b1b47537e45c47db89f3'
BBG_V8_SOURCE_SHA256='07e8e14a30bad31ad4978ff1d5b55ec014d3a4e0ab0fe05e49bd6b15123a31c1'
BBG_V9_SOURCE_SHA256='4e9d83fb149f2f50f2e6c2ab1db85ab04e7d2cc61d2a8f9b356b1bd79bc85300'
BBG_V10_SOURCE_SHA256='ed4cb39f16010e2c0d01835398a80faaa1c0345ce801e4fa21cd789d3989ba45'
BBG_V11_SOURCE_SHA256='d45a2acbc01ec438c284db3eb5a6edd75e360743d70704d7ceec2319ecfa1d22'
BBG_SOURCE_SHA256='345f350a9d741333e608f1502a7e71738a4c0b96effb12e53bb4bedb40106c57'
PROVIDER_ID='xp2-owned-toppanel-localization-bridge-v1'
PROVIDER_SHA256='28fb7cf1a285d426f25240206e09c312f9ac1dad6404b00f4a84ee633e123883'
BBG_V8_PROVIDER_SHA256='0928717b25e06a52c8cf494159af1f5d91496348024e9bded931d7dde6621a0d'
BBG_V9_PROVIDER_SHA256='93801bb259606be2e464cc918bcac50ad889f4c2c85187b21fece74246884ce0'
BBG_V10_PROVIDER_SHA256='a52afa2aa5d9fb9982223ba5f09bdd9feac0658d0fbe924269bada76f80621b7'
BBG_V11_PROVIDER_SHA256='1a9426d33e8f0b9bd409120e0394ca5981eeb41d747f1a4708091d5e93af74e7'
BBG_PROVIDER_SHA256='292e434ddf2c64f0cbcc0dbbc18cac2ac00c093601f57104f251aadc780dd92b'
STAGE='native_player_display_readback'
LOCALE='fr_FR'
FIELDS=('science','culture','gold','faith')
PROFILE_RELATIVE = 'work/host-extensions/xp2-player-display/owned-toppanel-formatter-source-v7.json'
BBG_V10_PROFILE_RELATIVE = 'work/host-extensions/xp2-player-display/owned-toppanel-formatter-source-v10.json'
BBG_V11_PROFILE_RELATIVE = 'work/host-extensions/xp2-player-display/owned-toppanel-formatter-source-v11.json'
BBG_PROFILE_RELATIVE = 'work/host-extensions/xp2-player-display/owned-toppanel-formatter-source-v12.json'
CURRENT_PROFILE_RELATIVE = 'work/host-extensions/xp2-player-display/owned-toppanel-formatter-current-source-v1.json'
CURRENT_SOURCE_SHA256 = '9f5f878c10800dd61cbe90b975c92bb9de69e2c50f80ff6aa335ba5969bce355'
CURRENT_PROVIDER_SHA256 = 'f4dea83b0ee555db935725cf8510851d33aa0cae24592303aaff731c2b1602c0'
CURRENT_PARENT_SOURCE_SHA256 = BBG_SOURCE_SHA256
CURRENT_EXECUTION_PROFILE_ID = 'xp2-gamecore-current-092abfbb'
CURRENT_LOCALIZATION_SHA256 = '8490e6694b966564f2f0baf6b685e6f23817c7348996511ce03891c0d14fe431'
CURRENT_HAVOK_SHA256 = '201979051f23378fed5ec50a49d36593591adbce5d1be6b7a42f482da46c73de'
BBG_V9_PROFILE_RELATIVE = 'work/host-extensions/xp2-player-display/owned-toppanel-formatter-source-v9.json'
BBG_V8_PROFILE_RELATIVE = 'work/host-extensions/xp2-player-display/owned-toppanel-formatter-source-v8.json'
_CURRENT='?GetCurrentLanguage@Localization@@YAAEBVLanguage@1@XZ'
_TYPE='?GetType@Language@Localization@@QEBAPEBDXZ'
_SIGNED=b'{1: number +#,###.#;-#,###.#}'
BASE_FIELDS={'stage','episode_id','game_generation','player_id','sequence','turn',
             'source_sha256','actor_channel'}
EXTRA_FIELDS={'locale','provider_id','provider_sha256','raw_observation_sha256',
              'response_binding_sha256','formatter_input_f64le','top_panel_text'}

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
                           ensure_ascii=True,allow_nan=False).encode()).hexdigest()

def _sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def selected_source(source_sha256=None):
    """Select only an owned, pinned launch capability, never a wire formatter."""
    if source_sha256 is None:
        return SOURCE_SHA256
    if type(source_sha256) is not str or source_sha256 not in (SOURCE_SHA256, BBG_V8_SOURCE_SHA256,
                                                            BBG_V9_SOURCE_SHA256, BBG_V10_SOURCE_SHA256, BBG_V11_SOURCE_SHA256, BBG_SOURCE_SHA256,
                                                            CURRENT_SOURCE_SHA256):
        raise ValueError('Unknown fixed TopPanel source profile')
    return source_sha256


def _profile(source_sha256):
    source_sha256=selected_source(source_sha256)
    if source_sha256==CURRENT_SOURCE_SHA256:
        return CURRENT_PROFILE_RELATIVE,CURRENT_PROVIDER_SHA256
    return {SOURCE_SHA256:(PROFILE_RELATIVE,PROVIDER_SHA256),
            BBG_V8_SOURCE_SHA256:(BBG_V8_PROFILE_RELATIVE,BBG_V8_PROVIDER_SHA256),
            BBG_V9_SOURCE_SHA256:(BBG_V9_PROFILE_RELATIVE,BBG_V9_PROVIDER_SHA256),
            BBG_V10_SOURCE_SHA256:(BBG_V10_PROFILE_RELATIVE,BBG_V10_PROVIDER_SHA256),
            BBG_V11_SOURCE_SHA256:(BBG_V11_PROFILE_RELATIVE,BBG_V11_PROVIDER_SHA256),
            BBG_SOURCE_SHA256:(BBG_PROFILE_RELATIVE,BBG_PROVIDER_SHA256)}[source_sha256]


def _runtime_class(source_sha256):
    if selected_source(source_sha256) in (BBG_V9_SOURCE_SHA256,BBG_V10_SOURCE_SHA256,BBG_V11_SOURCE_SHA256,BBG_SOURCE_SHA256,CURRENT_SOURCE_SHA256):
        from .xp2_bbg_nested_events import BBGNestedScriptRuntime
        return BBGNestedScriptRuntime
    return NativeScriptRuntime


def _verify_current_source(source, execution_image):
    """Verify the static current-library source lineage for explicit opt-in.

    This profile inherits only the v12 format contract. Runtime localization
    metadata is checked against the exact PreparedBundle fixture at the owner.
    """
    from civ6_host.runtime.execution_images import identity
    from civ6_host.runtime.xp2_bundle_inputs import verify_current_execution_image
    from civ6_host.runtime.native import native_locale_number982 as number
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    from civ6_host.runtime.native.native_shared_dependency_profiles import EVIDENCE_PATH, EVIDENCE_SHA256
    if execution_image is None:
        raise ValueError('Current TopPanel profile requires an explicit execution image')
    verify_current_execution_image(execution_image,
                                   core_path=execution_image.path)
    selected_identity=identity(execution_image)
    if (source.get('schema')!='civ6-host.xp2-owned-toppanel-formatter-current-source.v1'
            or source.get('static_only') is not True or source.get('native_execution') is not False
            or source.get('live_bridge_qualified') is not False
            or source.get('profile_id')!='current-d1a0-official-toppanel-v1'
            or execution_image.id!=CURRENT_EXECUTION_PROFILE_ID
            or source.get('execution_image')!={'profile_id':CURRENT_EXECUTION_PROFILE_ID,
                'exe_sha256':'d1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe',
                'gamecore_sha256':'092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'}
            or selected_identity['profile_id']!=CURRENT_EXECUTION_PROFILE_ID
            or source.get('expected_locale')!=LOCALE or tuple(source.get('fields',()))!=FIELDS
            or source.get('current_locale_exports')!={'?GetCurrentLanguage@Localization@@YAAEBVLanguage@1@XZ':'0x190a0',
                '?GetType@Language@Localization@@QEBAPEBDXZ':'0xb490'}):
        raise ValueError('Current TopPanel source profile or selected image differs')
    parent_path=_resource_path(BBG_PROFILE_RELATIVE)
    if _sha(parent_path)!=CURRENT_PARENT_SOURCE_SHA256:
        raise ValueError('Historical TopPanel format parent changed')
    parent=json.loads(parent_path.read_bytes())
    if (parent.get('patterns')!=source.get('patterns')
            or parent.get('expected_locale')!=source.get('expected_locale')
            or parent.get('fields')!=source.get('fields')
            or parent.get('current_locale_exports')!=source.get('current_locale_exports')
            or parent.get('official_formatter_source_sha256')!=source.get('official_formatter_source_sha256')
            or parent.get('official_lookup_source_sha256')!=source.get('official_lookup_source_sha256')
            or parent.get('projection_source')!=source.get('projection_source')
            or parent.get('official_display_sources')!=source.get('official_display_sources')):
        raise ValueError('Current TopPanel profile changed its exact historical display contract')
    current_exe=json.loads(_resource_path(source['current_exe_localization_bindings']['path']).read_bytes())
    if (current_exe.get('current_exe',{}).get('sha256')!='d1a0cfd439e7451be515f47595cfa0b6b983f56d1faf4ea434a4ce3b21491ebe'
            or not any(row.get('current_candidate_rva')=='0x4c9c30'
                       and row.get('name')=='Locale.Lookup implementation bound by current registration'
                       for row in current_exe.get('current_exe_bindings',()))):
        raise ValueError('Current Locale.Lookup registration source differs')
    shared=json.loads(_resource_path(source['current_localization_shared_bindings']['path']).read_bytes())
    if (shared.get('source_images',{}).get('Localization_FinalRelease.dll',{}).get('current_sha256')!=CURRENT_LOCALIZATION_SHA256
            or shared.get('source_images',{}).get('HavokScript_FinalRelease.dll',{}).get('current_sha256')!=CURRENT_HAVOK_SHA256
            or shared.get('source_images',{}).get('Localization_FinalRelease.dll',{}).get('current_path')!=source['library']['path']
            or shared.get('source_images',{}).get('HavokScript_FinalRelease.dll',{}).get('current_path')!=source['havok']['path']
            or not shared.get('body_span_correspondence',{}).get('localization',{}).get('spans')
            or any(row.get('exact_same_rva_bytes') is not True
                   for row in shared['body_span_correspondence']['localization']['spans'])):
        raise ValueError('Current Localization String source correspondence differs')
    interface=load_pinned_json(_resource_path(EVIDENCE_PATH),EVIDENCE_SHA256)
    if (source['current_shared_dependency_interface']!=
            {'root':'resource','path':EVIDENCE_PATH.as_posix(),'sha256':EVIDENCE_SHA256}
            or interface.get('schema')!='civ6-host.shared-dependency-interface-current.v1'
            or interface.get('engine_pair',{}).get('actual_image_sha256')!=
               '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
            or interface.get('engine_pair',{}).get('interface_reference_sha256')!=
               '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'):
        raise ValueError('Current shared-library interface evidence differs')
    body_ref=source.get('current_localization_string_body_evidence')
    if (type(body_ref) is not dict or body_ref.get('root')!='resource'
            or body_ref.get('path')!='work/official-capture/current-localization-number-string-bodies.json'
            or body_ref.get('sha256')!='b0b318cfeebcbbb7813e2c4b3257ce326b1f6e4f83597e20b9f09d3d3eebdfa5'):
        raise ValueError('Current Localization String body evidence pin differs')
    body_proof=json.loads(_dependency_path(body_ref).read_bytes())
    required_exports={'??0String@Localization@@QEAA@PEBD@Z',
        '??0String@Localization@@QEAA@PEBDI@Z','?PushArgument@String@Localization@@QEAA_NN@Z',
        '?toUTF8@String@Localization@@QEAAPEBDAEAIH@Z','??1String@Localization@@UEAA@XZ'}
    if (body_proof.get('schema')!='civ6rl.locale_number_current_string_abi.v1'
            or body_proof.get('current_image',{}).get('sha256')!=CURRENT_LOCALIZATION_SHA256
            or set(body_proof.get('exports',{}))!=required_exports
            or any(row.get('current_function',{}).get('complete_pdata_body') is not True
                   or row['current_function'].get('bytes')!=row['current_function'].get('capstone_decoded_bytes')
                   for row in body_proof['exports'].values())
            or sum(row.get('reference_body_evidence')=='exact_pinned_prior_body_sha256'
                   for row in body_proof['exports'].values())!=3):
        raise ValueError('Current Localization String export/body evidence is incomplete')
    _verify_number_legacy_api(number,parent,source)
    for row in _dependency_rows(source):
        if _sha(_dependency_path(row))!=row['sha256']:
            raise ValueError('Current TopPanel source dependency changed: '+row['path'])
    if source['parent_profile']!={'root':'resource','path':BBG_PROFILE_RELATIVE,'sha256':CURRENT_PARENT_SOURCE_SHA256}:
        raise ValueError('Current TopPanel parent source identity differs')
    if (source['library']['sha256']!=CURRENT_LOCALIZATION_SHA256
            or source['havok']['sha256']!=CURRENT_HAVOK_SHA256):
        raise ValueError('Current TopPanel shared-library identity differs')
    files=number.verified_files(execution_image=execution_image)
    library_path=Path(source['library']['path']).resolve(strict=True)
    if files.get(library_path)!=CURRENT_LOCALIZATION_SHA256:
        raise ValueError('Current TopPanel Localization library is not in the selected source closure')
    return source


def _verify_number_legacy_api(number,parent,source):
    """Prove the additive current-image branch preserves legacy formatter APIs."""
    legacy_rows={row['path']:row['sha256'] for row in parent['source_dependencies']}
    old_sha=legacy_rows.get('runtime/native/native_locale_number982.py')
    proof_sha=legacy_rows.get('work/phase1-learning982/locale-number-source.json')
    current_sha=next((row['sha256'] for row in source['source_dependencies']
                      if row['path']=='runtime/native/native_locale_number982.py'),None)
    if (old_sha!='5d2abf08793e5ec2c299301a0f6ce862e7825a2c9108778efdecfbcf95c48d7a'
            or proof_sha!='e9e329adfaa7e5e422994618bcf0f09ae851de771c2da2ec0a75fc352be62502'
            or number.SOURCE_PROOF_SHA256!=proof_sha
            or _sha(Path(number.__file__))!=current_sha):
        raise ValueError('Legacy/current Locale.ToNumber source lineage differs')
    old_ref=source.get('historical_number_module')
    if (type(old_ref) is not dict or old_ref.get('root')!='resource'
            or old_ref.get('path')!='work/source-review-v21-protocol/unpacked/src/civ6_host/runtime/native/native_locale_number982.py'
            or old_ref.get('sha256')!=old_sha):
        raise ValueError('Archived historical Locale.ToNumber source pin differs')
    old_path=_dependency_path(old_ref)
    if _sha(old_path)!=old_sha:
        raise ValueError('Pinned historical Locale.ToNumber source changed')
    def function(source,name):
        parsed=ast.parse(source)
        return next(node for node in parsed.body
                    if isinstance(node,ast.FunctionDef) and node.name==name)
    class ResolveResourcePath(ast.NodeTransformer):
        def visit_Call(self,node):
            self.generic_visit(node)
            if isinstance(node.func,ast.Name) and node.func.id=='_resolve_resource_path':
                return node.args[0]
            return node
    def normalized(node,name):
        node=ast.fix_missing_locations(node)
        node.args.kwonlyargs=[];node.args.kw_defaults=[]
        if name=='verified_files':
            index=next((i for i,statement in enumerate(node.body)
                       if isinstance(statement,ast.If) and isinstance(statement.test,ast.Compare)
                       and isinstance(statement.test.left,ast.Name)
                       and statement.test.left.id=='execution_image'),None)
            if index is not None:
                node.body=node.body[:index]+node.body[index+1:]
        elif name=='_check_library':
            index=next((i for i,statement in enumerate(node.body)
                       if isinstance(statement,ast.If) and isinstance(statement.test,ast.Compare)
                       and isinstance(statement.test.left,ast.Name)
                       and statement.test.left.id=='execution_image'),None)
            if index is not None:
                branch=node.body[index]
                node.body=node.body[:index]+branch.body+node.body[index+1:]
                node.body=[statement for statement in node.body if not
                    (isinstance(statement,ast.Assign) and any(isinstance(target,ast.Name)
                     and target.id=='expected_sha256' for target in statement.targets))]
                for child in ast.walk(node):
                    if isinstance(child,ast.Name) and child.id=='expected_sha256':
                        child.id='_LOCALIZATION_IMAGE_SHA256'
        elif name=='format_number':
            for child in ast.walk(node):
                if isinstance(child,ast.Call) and isinstance(child.func,ast.Name) and child.func.id in (
                        'verified_files','_check_library'):
                    child.keywords=[]
        node=ResolveResourcePath().visit(node)
        return ast.dump(ast.fix_missing_locations(node),include_attributes=False)
    old_text=old_path.read_text(encoding='utf-8')
    current_text=Path(number.__file__).read_text(encoding='utf-8')
    for name in ('verified_files','_check_library','format_number'):
        if normalized(function(old_text,name),name)!=normalized(function(current_text,name),name):
            raise ValueError('Current Locale.ToNumber additive branch changed legacy '+name)


def verify_source(source_sha256=SOURCE_SHA256, *, execution_image=None):
    relative,provider_sha256=_profile(source_sha256)
    path = _resource_path(relative)
    if _sha(path)!=source_sha256:raise ValueError('Formatter bridge source changed')
    source=json.loads(path.read_bytes())
    if source_sha256==CURRENT_SOURCE_SHA256:
        source=_verify_current_source(source,execution_image)
        material=dict(id=PROVIDER_ID,source_sha256=source_sha256,
            localization_image_sha256=source['library']['sha256'],fields=list(FIELDS),locale=LOCALE)
        if digest(material)!=provider_sha256:
            raise ValueError('Current formatter bridge provider changed')
        return source
    for row in _dependency_rows(source):
        if _sha(_dependency_path(row)) != row['sha256']:
            raise ValueError('Formatter bridge dependency changed: ' + row['path'])
    if _sha(source['library']['path'])!=source['library']['sha256']:
        raise ValueError('Formatter library image changed')
    material=dict(id=PROVIDER_ID,source_sha256=source_sha256,
        localization_image_sha256=source['library']['sha256'],fields=list(FIELDS),locale=LOCALE)
    if digest(material)!=provider_sha256:raise ValueError('Formatter bridge provider changed')
    return source

def _inputs(frame):
    raw=frame['observation'];economy=raw['economy'];result={}
    for field in FIELDS:
        value=economy[field]
        if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>number.MAX_ABS_VALUE:
            raise ValueError('TopPanel input is outside the shared formatter bounds')
        result[field]=math.floor(value) if field=='gold' else value
    return result

def _bits(inputs):return {key:struct.pack('<d',float(value)).hex() for key,value in inputs.items()}


def _current_bundle_image(saved):
    """Return the exact registered current image attached to this Load owner."""
    from civ6_host.runtime.native.native_official_bundle import PreparedBundle, _reuse_prepared_bundle
    from civ6_host.runtime.captured_session_profile import require_bbg_capture
    from civ6_host.runtime.xp2_bundle_inputs import verify_current_execution_image
    backend=saved.backend
    bundle=getattr(backend,'captured_bundle',None)
    if (type(bundle) is not PreparedBundle or bundle.inputs is not backend.inputs
            or bundle.reference!=backend.inputs.official_bundle
            or bundle.execution_image is None):
        raise ValueError('Current formatter requires its exact admitted PreparedBundle owner')
    image=bundle.execution_image
    verify_current_execution_image(image,core_path=str(bundle.engine_path))
    if getattr(backend.core,'_civ6_host_execution_image',None) is not image:
        raise ValueError('Current formatter Load core lost its attached execution image')
    reference=require_bbg_capture(bundle.reference,execution_image=image)
    if reference!=bundle.reference:
        raise ValueError('Current formatter bundle is not the exact registered capture')
    _reuse_prepared_bundle(bundle,reference,'xp2-lan',_input_only=True)
    return image,bundle


def _verify_current_havok(runtime,source,execution_image):
    from civ6_host.runtime.native.native_shared_dependency_profiles import NativeSharedDependencyProfile
    shared=getattr(runtime,'shared_dependency_profile',None)
    if (type(shared) is not NativeSharedDependencyProfile
            or (shared.actual_image_sha256,shared.interface_reference_sha256)!=
               ('092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f',
                '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c')):
        raise ValueError('Current formatter requires the exact shared-library interface profile')
    from civ6_host.runtime.execution_images import identity
    if (identity(execution_image)['profile_id']!=CURRENT_EXECUTION_PROFILE_ID
            or _sha(shared.verify_library_path('HavokScript_FinalRelease.dll',runtime.library._name))
               !=source['havok']['sha256']):
        raise ValueError('Current formatter HKS image differs from its current shared profile')

def _initialized_locale(host,source,bundle=None):
    """Readback guard over an already fully validated initialization owner.

    Reuse its immutable bootstrap metadata and private DB/ICU copies; do not
    rerun the historical official capture acquisition validator per response.
    """
    from civ6_host.runtime.paths import resource_root
    from civ6_host.runtime.resource_resolution import resolve_path
    manifest=host.manifest
    if source.get('schema')=='civ6-host.xp2-owned-toppanel-formatter-current-source.v1':
        from civ6_host.runtime.native.native_official_bundle import PreparedBundle
        if (type(bundle) is not PreparedBundle or bundle.fixture.get('input_profile')!='xp2-lan'
                or bundle.fixture.get('official_bundle')!=manifest.get('official_bundle')):
            raise ValueError('Current formatter requires its exact admitted bundle localization fixture')
        bootstrap=copy.deepcopy(bundle.fixture['localization_bootstrap'])
        settings=copy.deepcopy(manifest['localization_bootstrap'])
        if ('icu_data' not in bootstrap or 'icu_data' not in settings
                or type(bootstrap['icu_data']) is not dict or type(settings['icu_data']) is not dict):
            raise ValueError('Current formatter localization bootstrap is incomplete')
        bootstrap['icu_data'].pop('path',None)
        settings['icu_data'].pop('path',None)
        if (settings!=bootstrap or settings.get('locale')!=LOCALE
                or settings.get('icu_data',{}).get('sha256')!='02cfa347cf8e80e3d9ca925a8c3371db9a125c53234f3e1c03fc0eae4705153f'
                or type(settings.get('dictionary_flag')) is not bool
                or not host.localization_connection):
            raise ValueError('Current formatter localization metadata differs from its admitted bundle fixture')
        expected_row=bundle.fixture.get('databases',{}).get('localization')
        if (type(expected_row) is not dict or set(expected_row)!={'path','sha256','size_bytes'}
                or type(expected_row.get('path')) is not str
                or type(expected_row.get('size_bytes')) is not int):
            raise ValueError('Current formatter bundle has no exact Localization database row')
        expected_database={
            'sha256':expected_row['sha256'],
            'size_bytes':expected_row['size_bytes'],
            'source_path':str(resolve_path(Path(expected_row['path']))),
            'source_manifest_entry':copy.deepcopy(expected_row),
        }
        database=copy.deepcopy(manifest['databases']['localization'])
        if database.pop('path',None) is None or database!=expected_database:
            raise ValueError('Current formatter Localization database metadata differs from its admitted bundle fixture')
        root=(resource_root()/'work').resolve(strict=True)
        for row in (manifest['localization_bootstrap']['icu_data'],
                    manifest['databases']['localization']):
            raw=Path(row['path']);path=raw.resolve(strict=True)
            if (not raw.is_absolute() or raw.is_symlink() or not path.is_relative_to(root)
                    or _sha(path)!=row['sha256']):
                raise ValueError('Current formatter private Localization fixture bytes changed')
        return digest(manifest),host.localization_connection
    expected=source['initialized_localization']
    settings=manifest['localization_bootstrap'];metadata=copy.deepcopy(settings)
    metadata['icu_data'].pop('path')
    database=copy.deepcopy(manifest['databases']['localization']);database.pop('path')
    expected_database=copy.deepcopy(expected['database_metadata_except_private_path'])
    expected_database['source_path']=str(resolve_path(Path(expected_database['source_path'])))
    source_entry=expected_database['source_manifest_entry']
    source_entry['path']=str(resolve_path(Path(source_entry['path'])))
    if (manifest['official_bundle']!=expected['official_bundle']
            or ('input_profile' in expected and manifest.get('input_profile')!=expected['input_profile'])
            or metadata!=expected['bootstrap_metadata_except_private_icu_path']
            or database!=expected_database
            or type(settings.get('dictionary_flag')) is not bool
            or settings['locale']!=LOCALE or not host.localization_connection):
        raise ValueError('Formatter initialized localization metadata differs from XP2 source')
    root=(resource_root()/'work').resolve(strict=True)
    for row in (settings['icu_data'],manifest['databases']['localization']):
        raw=Path(row['path']);path=raw.resolve(strict=True)
        if not raw.is_absolute() or raw.is_symlink() or not path.is_relative_to(root) or _sha(path)!=row['sha256']:
            raise ValueError('Formatter initialized localization fixture bytes changed')
    return digest(manifest),host.localization_connection

def validate_readback(event,frame,*,source_sha256=SOURCE_SHA256):
    from civ6_host.runtime.information_store import _identity
    _,provider_sha256=_profile(source_sha256)
    if (type(event) is not dict or set(event)!=BASE_FIELDS|EXTRA_FIELDS
            or event.get('stage')!=STAGE or event.get('actor_channel') is not False
            or event.get('source_sha256')!=source_sha256
            or event.get('provider_id')!=PROVIDER_ID or event.get('provider_sha256')!=provider_sha256
            or event.get('locale')!=LOCALE or _identity(event) is None
            or _identity(event)!=_identity(frame,response=True)
            or frame.get('stage')!='official_session_response'
            or frame.get('outcome',{}).get('terminated') is not False
            or type(frame.get('outcome',{}).get('truncated')) is not bool):
        raise ValueError('Missing exact live formatter response/source/provider identity')
    if (event['response_binding_sha256']!=digest(frame)
            or event['raw_observation_sha256']!=digest(frame['observation'])):
        raise ValueError('Formatter readback belongs to another full raw response')
    inputs=_inputs(frame)
    if event['formatter_input_f64le']!=_bits(inputs):
        raise ValueError('Formatter inputs do not match the raw response inputs')
    text=event['top_panel_text']
    if type(text) is not dict or set(text)!=set(FIELDS):
        raise ValueError('Formatter did not return all four fixed TopPanel fields')
    for field in FIELDS:
        value=text[field]
        if (type(value) is not str or len(value.encode('utf-8'))>64
                or yields._FRENCH_DISPLAY_NUMBER.fullmatch(value) is None):
            raise ValueError('Formatter result differs from the governed French number syntax')
        shown=yields.public_number(value)
        if field=='gold':
            if shown!=inputs[field] or ',' in value or value.startswith('+'):
                raise ValueError('TopPanel gold text differs from the source floor balance')
        elif abs(shown-inputs[field])>yields._GLOBAL_TOLERANCE:
            raise ValueError('Formatter text exceeds the existing display consistency envelope')
        if field in ('science','culture') and inputs[field]!=0:
            if value[0]!=('+' if inputs[field]>0 else '-'):
                raise ValueError('TopPanel signed rate lost the official format pattern')
    return event

class OwnedNativeTopPanelFormatter:
    """Fixed owner capability. Construct once on the existing worker thread."""
    def __init__(self,saved,protocol,*,source_sha256=SOURCE_SHA256):
        if type(saved) is not SavedLoadOwner or type(protocol) is not NetworkProtocol:
            raise TypeError('Actual retained owner and network protocol required')
        self._saved=saved;self._protocol=protocol;self._thread=threading.get_ident()
        self._last={};self._busy=False
        self._source_sha256=selected_source(source_sha256)
        self._provider_sha256=_profile(self._source_sha256)[1]
        execution_image=(getattr(getattr(saved.backend,'captured_bundle',None),'execution_image',None)
                         if self._source_sha256==CURRENT_SOURCE_SHA256 else None)
        self._source=verify_source(self._source_sha256,execution_image=execution_image)

    def _locale(self,library):
        current=number._bind(library,_CURRENT,0x190a0,[],C.c_void_p)
        get_type=number._bind(library,_TYPE,0xb490,[C.c_void_p],C.c_char_p)
        language=current()
        if not language or get_type(language)!=LOCALE.encode('ascii'):
            raise ValueError('Owned initialized Localization selected another language')
        return language

    def _guard(self,frame,request):
        if threading.get_ident()!=self._thread:raise ValueError('Formatter crossed the owner thread')
        saved=self._saved;protocol=self._protocol
        saved._check('commands',requested='unit_commands_candidate',query=True)
        b=saved.backend;p=saved.prefix;rt=p.runtime;c=saved.continuation;view=saved.player_view
        current=self._source_sha256==CURRENT_SOURCE_SHA256
        execution_image,bundle=(_current_bundle_image(saved) if current else (None,None))
        if (type(b) is not OfficialLoadBackend or b.load_abi.core_sha256!=XP2_CORE_SHA256
                or type(p) is not SavedLoadServices or p.backend is not b or p.host is not b.host
                or p.core is not b.core or p.context!=b.context or p.core_sha256!=XP2_CORE_SHA256
                or type(rt) is not _runtime_class(self._source_sha256) or rt.closed or rt.service_owner is not b.host
                or type(rt.registry) is not ThreadRegistry or rt.root!=rt.registry.root
                or type(p.ui_child) is not ScriptContext or type(p.game_child) is not ScriptContext
                or p.ui_child is p.game_child or rt.registry.validate(p.ui_child)==rt.registry.validate(p.game_child)
                or type(c) is not SavedContinuation or c.owner is not b or c.prefix is not p
                or c.runtime is not rt or c.ui_child is not p.ui_child or c.game_child is not p.game_child
                or c.identity is not protocol.identity or c.poisoned or c.publishing
                or type(view) is not SavedPlayerView or not view.completed or view.owner is not b
                or view.prefix is not p or view.runtime is not rt or view.child is not p.ui_child
                or view.core_sha256!=XP2_CORE_SHA256 or view.source_sha256!=UI_SOURCE[1]
                or getattr(rt,'_xp2_ui_bind_entered',None) is not True
                or type(p.deferred_events) is not DeferredService
                or p.deferred_events.host is not b.host or p.deferred_events.core is not b.core
                or p.deferred_events.context!=b.context or p.deferred_events.cache_core_sha256!=XP2_CORE_SHA256
                or set(p.deferred_events.addresses)!={0xb0,0xe8,0xf0}):
            # Refusal-only Python identity diagnostics: do not call another
            # native method, relax the guard or recover from a foreign owner.
            nodes={'backend':(b,OfficialLoadBackend),'prefix':(p,SavedLoadServices),
                'runtime':(rt,_runtime_class(self._source_sha256)),'registry':(getattr(rt,'registry',None),ThreadRegistry),
                'continuation':(c,SavedContinuation),'view':(view,SavedPlayerView),
                'deferred':(getattr(p,'deferred_events',None),DeferredService),
                'ui_child':(getattr(p,'ui_child',None),ScriptContext),
                'game_child':(getattr(p,'game_child',None),ScriptContext)}
            types={name:type(value) is expected for name,(value,expected) in nodes.items()}
            links={
                'prefix_backend':getattr(p,'backend',None) is b,
                'prefix_host':getattr(p,'host',None) is b.host,
                'prefix_core':getattr(p,'core',None) is b.core,
                'prefix_context':getattr(p,'context',None)==b.context,
                'runtime_service_owner':getattr(rt,'service_owner',None) is b.host,
                'continuation_owner':getattr(c,'owner',None) is b,
                'continuation_prefix':getattr(c,'prefix',None) is p,
                'continuation_runtime':getattr(c,'runtime',None) is rt,
                'continuation_identity':getattr(c,'identity',None) is protocol.identity,
                'continuation_ui_child':getattr(c,'ui_child',None) is p.ui_child,
                'continuation_game_child':getattr(c,'game_child',None) is p.game_child,
                'view_owner':getattr(view,'owner',None) is b,
                'view_prefix':getattr(view,'prefix',None) is p,
                'view_runtime':getattr(view,'runtime',None) is rt,
                'view_child':getattr(view,'child',None) is p.ui_child,
                'deferred_host':getattr(p.deferred_events,'host',None) is b.host,
                'deferred_core':getattr(p.deferred_events,'core',None) is b.core,
                'deferred_context':getattr(p.deferred_events,'context',None)==b.context}
            flags={'runtime_closed':getattr(rt,'closed',None),
                'continuation_poisoned':getattr(c,'poisoned',None),
                'continuation_publishing':getattr(c,'publishing',None),
                'view_completed':getattr(view,'completed',None),
                'ui_bound':getattr(rt,'_xp2_ui_bind_entered',None),
                'prefix_core':getattr(p,'core_sha256',None),
                'view_core':getattr(view,'core_sha256',None),
                'view_source':getattr(view,'source_sha256',None),
                'deferred_core':getattr(p.deferred_events,'cache_core_sha256',None),
                'deferred_slots':sorted(getattr(p.deferred_events,'addresses',{}))}
            raise ValueError('Formatter lost the exact saved UI/localization owner graph: '+
                json.dumps(dict(types=types,links=links,flags=flags),sort_keys=True))
        p.check();p.deferred_events._check()
        lease=core_script_services.check_bound(rt,b.context,b.core)
        initialized=_initialized_locale(b.host,self._source,bundle=bundle)
        library=b.host.localization_library
        locale_files=number.verified_files(execution_image=execution_image) if current else number.verified_files()
        if current:
            number._check_library(library,locale_files,execution_image=execution_image)
            _verify_current_havok(rt,self._source,execution_image)
        else:
            number._check_library(library,locale_files)
            if (Path(rt.library._name).resolve()!=Path(self._source['library']['path']).with_name('HavokScript_FinalRelease.dll').resolve()
                    or _sha(rt.library._name)!=self._source['havok_image_sha256']):
                raise ValueError('Formatter owner uses another HKS image')
        pointers=(rt.root,p.ui_child.pointer,p.game_child.pointer)
        stacks=tuple(rt.lua['gettop'](pointer) for pointer in pointers)
        if stacks!=(0,0,0):raise ValueError('Formatter requires clean owned root/UI/game stacks')
        validate_network_response(frame,protocol,frame['operation'],request=request)
        if frame['outcome']['terminated'] or frame['observation'] is None:
            raise ValueError('Formatter requires an owned observation before teardown')
        language=self._locale(library)
        q=p.deferred_events
        return (b,p,rt,rt.registry,lease,library,library._handle,language,c,view,
                p.ui_child,p.game_child,c.sequence,c.publication_count,digest(c.observation),
                q,q._sequence,q.consumed_count,q.consumed_bytes,q.consumed_digest.hexdigest(),
                tuple(q.pending),q.host_notification_counter,q.host_metadata_counter,
                digest(frame),digest(request),protocol.sequence,protocol.rounds,stacks,initialized)

    def capture(self,frame,request=None):
        if self._busy:raise ValueError('Reentrant TopPanel formatter capture')
        # This method runs inside SavedLoadOwner._attempt opened by the fixed
        # worker hook, after raw response and checkpoint validation, before print.
        current_image=(getattr(getattr(self._saved.backend,'captured_bundle',None),'execution_image',None)
                       if self._source_sha256==CURRENT_SOURCE_SHA256 else None)
        verify_source(self._source_sha256,execution_image=current_image);self._busy=True
        try:
            before=self._guard(frame,request)
            pid=frame['observation']['player_id'];sequence=frame['sequence']
            if sequence<=self._last.get(pid,-1):raise ValueError('TopPanel response was already captured')
            library=before[5];inputs=_inputs(frame);text={}
            for field in FIELDS:
                value=inputs[field]
                if field in ('science','culture') and value!=0:
                    if self._source_sha256==CURRENT_SOURCE_SHA256:
                        text[field]=number.format_number(library,value,'+#,###.#;-#,###.#',
                                                         execution_image=current_image)
                    else:
                        text[field]=arguments.native_lookup(library,_SIGNED,(value,)).decode('utf-8','strict')
                else:
                    text[field]=number.format_number(library,value,None if field in ('science','culture') else '#,###.#',
                        **({'execution_image':current_image} if self._source_sha256==CURRENT_SOURCE_SHA256 else {}))
            if self._guard(frame,request)!=before:
                raise ValueError('Owner, locale, native FIFO or raw response changed during formatting')
            event=dict(stage=STAGE,episode_id=frame['episode_id'],game_generation=frame['game_generation'],
                player_id=pid,sequence=sequence,turn=frame['observation']['turn'],
                source_sha256=self._source_sha256,actor_channel=False,locale=LOCALE,
                provider_id=PROVIDER_ID,provider_sha256=self._provider_sha256,
                raw_observation_sha256=digest(frame['observation']),response_binding_sha256=digest(frame),
                formatter_input_f64le=_bits(inputs),top_panel_text=text)
            validate_readback(event,frame,source_sha256=self._source_sha256);self._last[pid]=sequence
            return event
        finally:self._busy=False

class NativeTopPanelReceiptConsumer:
    """Existing InformationStore -> existing private projection issuer.

    The adapter records both provider fingerprints. The old three-text
    projection contract remains unchanged; the fourth (gold) result must pass
    validation before the three-text internal capability can be issued.
    """
    def __init__(self,store,issuer):
        from .information_store import InformationStore
        from .player_display import NativeTopPanelIssuer
        if type(store) is not InformationStore or type(issuer) is not NativeTopPanelIssuer:
            raise TypeError('Exact existing store and fixed projection issuer required')
        self._source_sha256=selected_source(store._pins.get('display'))
        if store._pins.get('display')!=self._source_sha256:raise ValueError('Display store source differs')
        self._provider_sha256=_profile(self._source_sha256)[1]
        if getattr(issuer,'_native_consumer',None) is not None:
            raise ValueError('Projection issuer already owns its fixed native consumer')
        self._store=store;self._issuer=issuer;self._last={};self._thread=threading.get_ident()
        issuer._native_consumer=self

    def capture(self,frame):
        if threading.get_ident()!=self._thread:raise ValueError('Display consumer crossed its owner thread')
        event=self._store.read('display',frame)
        if event is None:raise ValueError('No same-response native TopPanel readback')
        validate_readback(event,frame,source_sha256=self._source_sha256)
        key=(frame['episode_id'],frame['game_generation'],event['player_id'])
        if event['sequence']<=self._last.get(key,-1):raise ValueError('TopPanel readback was already consumed')
        receipt=self._issuer._issue(frame,LOCALE,{k:event['top_panel_text'][k]
                   for k in ('science','culture','faith')},'bridge:'+self._source_sha256+':'+self._provider_sha256)
        self._last[key]=event['sequence']
        return receipt


def _resource_path(relative):
    from .paths import resource_root
    from .resource_resolution import resolve_path
    return resolve_path(resource_root() / relative).resolve(strict=True)


def _dependency_path(row):
    path = Path(row['path'])
    if row.get('root') == 'package':
        return (Path(__file__).resolve().parents[1] / path).resolve(strict=True)
    if row.get('root') == 'resource':
        return _resource_path(path)
    return path.resolve(strict=True)


def _dependency_rows(source):
    if source.get('schema')=='civ6-host.xp2-owned-toppanel-formatter-current-source.v1':
        return [*source['source_dependencies'],*source['official_display_sources'],
                source['projection_source']]
    return [*source['source_dependencies'], *source['official_display_sources'],
            source['projection_source'], source['initialized_localization']['reference'],
            *source.get('admission_dependencies',())]


def _closure_dependencies(source_sha256=SOURCE_SHA256,*,execution_image=None):
    source = verify_source(source_sha256,execution_image=execution_image)
    relative,_=_profile(source_sha256)
    dependencies = {_resource_path(relative): source_sha256}
    dependencies.update((_dependency_path(row), row['sha256']) for row in _dependency_rows(source))
    dependencies[Path(source['library']['path']).resolve(strict=True)] = source['library']['sha256']
    if source_sha256==CURRENT_SOURCE_SHA256:
        havok=Path(source['havok']['path']).resolve(strict=True)
        dependencies[havok]=source['havok']['sha256']
        from civ6_host.runtime.native import native_locale_number982 as number
        from .resource_resolution import resolve_path as _resolve_resource_path
        for path,expected in number.verified_files(execution_image=execution_image).items():
            resolved=_resolve_resource_path(Path(path)).resolve(strict=True)
            if resolved in dependencies and dependencies[resolved]!=expected:
                raise ValueError('Conflicting current formatter dependency pin')
            dependencies[resolved]=expected
        package_root=Path(__file__).resolve().parents[1]
        for relative_source in ('runtime/player_display_toppanel.py','runtime/player_display.py',
                'runtime/captured_session_profile.py','runtime/xp2_bundle_inputs.py',
                'runtime/native/native_official_bundle.py','runtime/native/native_shared_dependency_profiles.py'):
            path=(package_root/relative_source).resolve(strict=True)
            dependencies[path]=_sha(path)
    else:
        havok = Path(source['library']['path']).with_name('HavokScript_FinalRelease.dll')
        dependencies[havok.resolve(strict=True)] = source['havok_image_sha256']
        from .resource_resolution import resolve_path
        for path, expected in number.verified_files().items():
            resolved = resolve_path(Path(path)).resolve(strict=True)
            if resolved in dependencies and dependencies[resolved] != expected:
                raise ValueError('Conflicting formatter dependency pin')
            dependencies[resolved] = expected
    return dependencies


def pin_display_closure(closure,source_sha256=SOURCE_SHA256):
    from .xp1_session_inputs import saved_load_pin
    execution_image=_closure_execution_image(closure,source_sha256)
    if closure['input_profile'] != 'xp2-lan':
        raise ValueError('Formatter closure requires the selected XP2 owner')
    for path, expected in _closure_dependencies(source_sha256,execution_image=execution_image).items():
        saved_load_pin(closure['pins'], path, expected)
    _require_launch_scope(closure,source_sha256)
    closure['public_display_source'] = selected_source(source_sha256)


def require_display_closure(closure):
    source_sha256=selected_source(closure.get('public_display_source'))
    execution_image=_closure_execution_image(closure,source_sha256)
    if (closure.get('input_profile') != 'xp2-lan'
            or closure.get('public_display_source') != source_sha256
            or any(closure['pins'].get(str(path)) != expected
                   for path, expected in _closure_dependencies(source_sha256,execution_image=execution_image).items())):
        raise ValueError('Exact XP2 formatter closure pins are required')
    _require_launch_scope(closure,source_sha256)


def _closure_execution_image(closure,source_sha256):
    if source_sha256!=CURRENT_SOURCE_SHA256:
        return None
    from civ6_host.runtime.execution_images import from_identity
    try:
        image=from_identity(closure['execution_image'])
    except (KeyError,TypeError,ValueError) as exc:
        raise ValueError('Current formatter requires its explicit execution-image identity') from exc
    if image.id!=CURRENT_EXECUTION_PROFILE_ID:
        raise ValueError('Current formatter execution-image profile differs')
    return image


def _require_launch_scope(closure,source_sha256):
    if source_sha256==CURRENT_SOURCE_SHA256:
        from civ6_host.runtime.captured_session_profile import require_bbg_capture
        image=_closure_execution_image(closure,source_sha256)
        require_bbg_capture(closure.get('official_bundle'),execution_image=image)
        return
    if source_sha256 in (BBG_SOURCE_SHA256,BBG_V8_SOURCE_SHA256,BBG_V9_SOURCE_SHA256,BBG_V10_SOURCE_SHA256,BBG_V11_SOURCE_SHA256):
        source=verify_source(source_sha256)
        if closure.get('official_bundle')!=source['initialized_localization']['official_bundle']:
            raise ValueError('BBG formatter requires its exact captured bundle')


def emit_display_readback(formatter, owner, response, request, emit):
    # Worker calls this after raw checkpoint validation and before teardown.
    with owner._attempt():
        event = formatter.capture(response, request)
    stage = event.pop('stage')
    emit(stage, **event)
