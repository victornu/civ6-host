"""PRIVATE, UNAPPLIED: fixed TopPanel formatter inside the existing owner.

No formatter is selected by a request. The sole inputs are the already
validated raw session.v1 response and the retained localization owner. This
module does not collect a second observation or change Save/checkpoint data.
Live XP2/fr_FR qualification remains pending; offline fixtures are not receipts.
"""
from __future__ import annotations
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
PROVIDER_ID='xp2-owned-toppanel-localization-bridge-v1'
PROVIDER_SHA256='28fb7cf1a285d426f25240206e09c312f9ac1dad6404b00f4a84ee633e123883'
STAGE='native_player_display_readback'
LOCALE='fr_FR'
FIELDS=('science','culture','gold','faith')
PROFILE_RELATIVE = 'work/host-extensions/xp2-player-display/owned-toppanel-formatter-source-v7.json'
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

def verify_source():
    path = _resource_path(PROFILE_RELATIVE)
    if _sha(path)!=SOURCE_SHA256:raise ValueError('Formatter bridge source changed')
    source=json.loads(path.read_bytes())
    for row in _dependency_rows(source):
        if _sha(_dependency_path(row)) != row['sha256']:
            raise ValueError('Formatter bridge dependency changed: ' + row['path'])
    if _sha(source['library']['path'])!=source['library']['sha256']:
        raise ValueError('Formatter library image changed')
    material=dict(id=PROVIDER_ID,source_sha256=SOURCE_SHA256,
        localization_image_sha256=source['library']['sha256'],fields=list(FIELDS),locale=LOCALE)
    if digest(material)!=PROVIDER_SHA256:raise ValueError('Formatter bridge provider changed')
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

def _initialized_locale(host,source):
    """Readback guard over an already fully validated initialization owner.

    Reuse its immutable bootstrap metadata and private DB/ICU copies; do not
    rerun the historical official capture acquisition validator per response.
    """
    from civ6_host.runtime.paths import resource_root
    from civ6_host.runtime.resource_resolution import resolve_path
    manifest=host.manifest;expected=source['initialized_localization']
    settings=manifest['localization_bootstrap'];metadata=copy.deepcopy(settings)
    metadata['icu_data'].pop('path')
    database=copy.deepcopy(manifest['databases']['localization']);database.pop('path')
    expected_database=copy.deepcopy(expected['database_metadata_except_private_path'])
    expected_database['source_path']=str(resolve_path(Path(expected_database['source_path'])))
    source_entry=expected_database['source_manifest_entry']
    source_entry['path']=str(resolve_path(Path(source_entry['path'])))
    if (manifest['official_bundle']!=expected['official_bundle']
            or metadata!=expected['bootstrap_metadata_except_private_icu_path']
            or database!=expected_database
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
    if (type(event) is not dict or set(event)!=BASE_FIELDS|EXTRA_FIELDS
            or event.get('stage')!=STAGE or event.get('actor_channel') is not False
            or source_sha256!=SOURCE_SHA256 or event.get('source_sha256')!=SOURCE_SHA256
            or event.get('provider_id')!=PROVIDER_ID or event.get('provider_sha256')!=PROVIDER_SHA256
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
    def __init__(self,saved,protocol):
        if type(saved) is not SavedLoadOwner or type(protocol) is not NetworkProtocol:
            raise TypeError('Actual retained owner and network protocol required')
        self._saved=saved;self._protocol=protocol;self._thread=threading.get_ident()
        self._last={};self._busy=False
        self._source=verify_source()

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
        if (type(b) is not OfficialLoadBackend or b.load_abi.core_sha256!=XP2_CORE_SHA256
                or type(p) is not SavedLoadServices or p.backend is not b or p.host is not b.host
                or p.core is not b.core or p.context!=b.context or p.core_sha256!=XP2_CORE_SHA256
                or type(rt) is not NativeScriptRuntime or rt.closed or rt.service_owner is not b.host
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
            raise ValueError('Formatter lost the exact saved UI/localization owner graph')
        p.check();p.deferred_events._check()
        lease=core_script_services.check_bound(rt,b.context,b.core)
        initialized=_initialized_locale(b.host,self._source)
        library=b.host.localization_library
        number._check_library(library,number.verified_files())
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
        verify_source();self._busy=True
        try:
            before=self._guard(frame,request)
            pid=frame['observation']['player_id'];sequence=frame['sequence']
            if sequence<=self._last.get(pid,-1):raise ValueError('TopPanel response was already captured')
            library=before[5];inputs=_inputs(frame);text={}
            for field in FIELDS:
                value=inputs[field]
                if field in ('science','culture') and value!=0:
                    text[field]=arguments.native_lookup(library,_SIGNED,(value,)).decode('utf-8','strict')
                else:
                    text[field]=number.format_number(library,value,None if field in ('science','culture') else '#,###.#')
            if self._guard(frame,request)!=before:
                raise ValueError('Owner, locale, native FIFO or raw response changed during formatting')
            event=dict(stage=STAGE,episode_id=frame['episode_id'],game_generation=frame['game_generation'],
                player_id=pid,sequence=sequence,turn=frame['observation']['turn'],
                source_sha256=SOURCE_SHA256,actor_channel=False,locale=LOCALE,
                provider_id=PROVIDER_ID,provider_sha256=PROVIDER_SHA256,
                raw_observation_sha256=digest(frame['observation']),response_binding_sha256=digest(frame),
                formatter_input_f64le=_bits(inputs),top_panel_text=text)
            validate_readback(event,frame);self._last[pid]=sequence
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
        if store._pins.get('display')!=SOURCE_SHA256:raise ValueError('Display store source differs')
        if getattr(issuer,'_native_consumer',None) is not None:
            raise ValueError('Projection issuer already owns its fixed native consumer')
        self._store=store;self._issuer=issuer;self._last={};self._thread=threading.get_ident()
        issuer._native_consumer=self

    def capture(self,frame):
        if threading.get_ident()!=self._thread:raise ValueError('Display consumer crossed its owner thread')
        event=self._store.read('display',frame)
        if event is None:raise ValueError('No same-response native TopPanel readback')
        validate_readback(event,frame)
        key=(frame['episode_id'],frame['game_generation'],event['player_id'])
        if event['sequence']<=self._last.get(key,-1):raise ValueError('TopPanel readback was already consumed')
        receipt=self._issuer._issue(frame,LOCALE,{k:event['top_panel_text'][k]
                   for k in ('science','culture','faith')},'bridge:'+SOURCE_SHA256+':'+PROVIDER_SHA256)
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
    return [*source['source_dependencies'], *source['official_display_sources'],
            source['projection_source'], source['initialized_localization']['reference']]


def _closure_dependencies():
    source = verify_source()
    dependencies = {_resource_path(PROFILE_RELATIVE): SOURCE_SHA256}
    dependencies.update((_dependency_path(row), row['sha256']) for row in _dependency_rows(source))
    dependencies[Path(source['library']['path']).resolve(strict=True)] = source['library']['sha256']
    havok = Path(source['library']['path']).with_name('HavokScript_FinalRelease.dll')
    dependencies[havok.resolve(strict=True)] = source['havok_image_sha256']
    from .resource_resolution import resolve_path
    for path, expected in number.verified_files().items():
        resolved = resolve_path(Path(path)).resolve(strict=True)
        if resolved in dependencies and dependencies[resolved] != expected:
            raise ValueError('Conflicting formatter dependency pin')
        dependencies[resolved] = expected
    return dependencies


def pin_display_closure(closure):
    from .xp1_session_inputs import saved_load_pin
    if closure['input_profile'] != 'xp2-lan':
        raise ValueError('Formatter closure requires the selected XP2 owner')
    for path, expected in _closure_dependencies().items():
        saved_load_pin(closure['pins'], path, expected)
    closure['public_display_source'] = SOURCE_SHA256


def require_display_closure(closure):
    if (closure.get('input_profile') != 'xp2-lan'
            or closure.get('public_display_source') != SOURCE_SHA256
            or any(closure['pins'].get(str(path)) != expected
                   for path, expected in _closure_dependencies().items())):
        raise ValueError('Exact XP2 formatter closure pins are required')


def emit_display_readback(formatter, owner, response, request, emit):
    # Worker calls this after raw checkpoint validation and before teardown.
    with owner._attempt():
        event = formatter.capture(response, request)
    stage = event.pop('stage')
    emit(stage, **event)
