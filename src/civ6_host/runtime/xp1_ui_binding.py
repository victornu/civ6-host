"""Separate source-selected UI child, using the existing player observation reader.

No gameplay globals are copied into this child. This private saved-capture
qualification does not open the shared public session or event-cache gates.
"""
import ctypes as C
from .configuration_profiles import _source,_body,XP1_CORE_SHA256,XP2_CORE_SHA256

SOURCE=('work/host-extensions/xp1-ui-binding-static/ui-binding-source-v1.json',
        'e4e74533e8d85320a9f4509638fb6220108235e7f00a68c302b89138d505d061')
ACTIVE_STAGE='player-view-candidate-active'

def source():
    p=_source(SOURCE)
    if (p['schema']!='civ6_host.xp1_ui_binding.static.v1'
            or p['images']['xp1']['sha256']!=XP1_CORE_SHA256
            or p['entries']['xp1']['ui_thunk']!=0x4cbe50
            or p['entries']['xp1']['ui_registration']!=0x4df4e0
            or p['validation']['all_captured_instruction_bytes_match_images'] is not True
            or p['native_execution'] is not False):
        raise ValueError('XP1 UI registration source identity changed')
    for row in p['references'].values():_source((row['path'],row['sha256']))
    return p

def source_dependencies(core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_ui_binding_source import source_dependencies as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown UI binding engine')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p=source();rows=[dict(path=SOURCE[0],sha256=SOURCE[1]),*p['references'].values()]
    return {str(resolve_path(resource_root()/r['path']).resolve()):r['sha256'] for r in rows}

def verify_live(base,read):
    p=source()
    for name,body in p['functions']['xp1'].items():
        for fragment in _body(body)['fragments']:
            for i in fragment['instructions']:
                raw=bytes.fromhex(i['bytes'])
                if read(base+int(i['va'],16)-0x180000000,len(raw))!=raw:
                    raise ValueError('XP1 UI registration bytes changed: '+name)
    for row in p['slots']['xp1']:
        if int.from_bytes(read(base+row['table_rva']+row['slot'],8),'little')!=base+row['target_rva']:
            raise ValueError('XP1 UI registration slot changed')

def bind_xp1_ui_api(runtime,game_child,ui_child,core_context,core):
    from .native.native_xp1_script_bindings import (
        source_profile,verify_getter,verify_interface,verify_registration_owner)
    from .native.native_core_context_profiles import profile_for_core,validate_loaded_modules
    from .native.native_probe import Windows
    from .native.native_setup import local_reader
    from .paths import resource_root
    game=runtime.registry.validate(game_child);ui=runtime.registry.validate(ui_child)
    if (game==ui or getattr(runtime,'_xp1_ui_bind_entered',False)
            or not getattr(runtime,'_xp1_script_bind_entered',False)
            or not(runtime.database_bound and runtime.configuration_bound and runtime.locale_bound)
            or runtime.lua['gettop'](game) or runtime.lua['gettop'](ui)
            or not hasattr(runtime.host,'LAB_XP1ScriptCoreUIBindingsInstall')):
        raise ValueError('XP1 UI binding requires fresh distinct owned children and its native export')
    profile=profile_for_core(core._name,mode='context')
    if profile.ruleset!='xp1' or profile.core_sha256!=XP1_CORE_SHA256:
        raise ValueError('XP1 UI binder refuses other engines')
    validate_loaded_modules(profile,Windows().modules())
    read=local_reader();verify_live(core._handle,read)
    proof=source_profile(resource_root())
    getter=verify_getter(read,core._handle,core_context,proof)
    verify_registration_owner(read,core._handle,proof)
    interface=C.WINFUNCTYPE(C.c_void_p,C.c_void_p)(getter)(core_context)
    verify_interface(read,core._handle,interface)
    install=runtime.host.LAB_XP1ScriptCoreUIBindingsInstall
    install.argtypes,install.restype=[C.c_void_p]*4,C.c_int
    runtime._xp1_ui_bind_entered=True
    runtime.emit('before_xp1_ui_api_bind',method_rva='0x4cbe50',source_sha256=SOURCE[1])
    status=install(game,ui,interface,core._handle)
    runtime._status(ui,status,'XP1 native UI GameCore API registration')
    if runtime.lua['gettop'](game) or runtime.lua['gettop'](ui):
        raise RuntimeError('XP1 UI registration left a nonempty Lua stack')
    receipt=dict(native_ui_registration_returned=True,outer_protected_status=status,
        complete_registration_verified=False,method_rva='0x4cbe50',
        distinct_managed_children=True,gameplay_api_copied=False,source_sha256=SOURCE[1])
    runtime.emit('xp1_ui_api_bind_returned',**receipt)
    return receipt

class SavedPlayerView:
    """Read one original player view without substituting gameplay getters."""
    def __init__(self,publication):
        from .xp1_cache_publication import SavedCachePublication,COMPLETED_STAGE
        if type(publication) is not SavedCachePublication or not publication.completed:
            raise ValueError('XP1 player view requires completed native publication')
        b=publication.owner
        publication.lease._check_state(COMPLETED_STAGE,False)
        if (b._xp1_publication_attempt is not publication
                or getattr(b,'_xp1_player_view',None) is not None
                or getattr(b.prefix,'ui_child',None) is not None
                or b.load_abi.core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)):
            raise ValueError('Player view owner is replaced or already used')
        self.core_sha256=b.load_abi.core_sha256
        if self.core_sha256==XP2_CORE_SHA256:
            from .xp2_ui_binding_source import SOURCE as selected_source
        else:selected_source=SOURCE
        self.source_sha256=selected_source[1]
        self.publication,self.owner,self.prefix=publication,b,b.prefix
        self.runtime=self.prefix.runtime;self.child=None;self.attempted=self.completed=False
        self.result=None;b._xp1_player_view=self

    def check_active(self):
        b=self.owner;p=self.prefix;pub=self.publication
        if (b._xp1_player_view is not self or b.prefix is not p
                or b.load_abi.core_sha256!=self.core_sha256
                or p.runtime is not self.runtime or b._xp1_publication_attempt is not pub
                or b.stage!=ACTIVE_STAGE or b.busy is not True
                or not pub.completed or not pub.lease.publication_finished
                or p.view_publisher.native_cache_gate is not False
                or p.view_publisher.full_facade_initialization_reproduced is not False
                # SavedLoadServices owns DeferredService, which does not install
                # the legacy Base UI event gate. Refuse it if later enabled.
                or getattr(p.deferred_events,'ui_cache_callbacks_enabled',False) is not False
                or (self.child is not None and p.ui_child is not self.child)):
            raise ValueError('XP1 player view ownership or candidate gates changed')
        pub.lease._check_state(ACTIVE_STAGE,True)
        if self.child is not None:self.runtime.registry.validate(self.child)

    def run(self):
        from .xp1_cache_publication import COMPLETED_STAGE
        from .saved_load_job_observer import require_quiescent
        from .native.native_player_observation import observe_player
        if self.attempted:raise ValueError('XP1 player view cannot retry registration')
        self.publication.lease._check_state(COMPLETED_STAGE,False)
        self.attempted=True;b=self.owner;p=self.prefix;rt=self.runtime
        try:
            b.stage=ACTIVE_STAGE;b.busy=True;self.check_active()
            before=b.jobs_snapshot('before');require_quiescent(before)
            self.child=rt.acquire();p.ui_child=self.child
            rt.attach_standard_libraries(self.child);rt.attach_ui_enums(self.child)
            rt.namespaces.register(self.child,'GameInfo')
            if self.core_sha256 == XP2_CORE_SHA256:
                rt.namespaces.register(self.child,'Locale')
            binding=rt.bind_native_ui_api(p.game_child,self.child,b.context,b.core,core_sha256=self.core_sha256)
            # Native getters decide the perspective. The original configuration
            # remains unchanged; never force a player ID or local observer.
            player=b.loaded_readback['player_id']
            observation=observe_player(rt,self.child,player)
            if tuple(observation[k] for k in ('turn','width','height'))!=tuple(b.loaded_readback[k] for k in ('turn','width','height')):
                raise ValueError('XP1 player observation differs from the loaded state')
            rt.execute(p.game_child,
                b"assert(type(PlayersVisibility[0].IsUnitVisible)~='function','UI binding polluted gameplay visibility')",
                b'@xp1_ui_gameplay_binding_isolation')
            self.check_active();control=b.control(empty=True)
            after=b.jobs_snapshot('after');require_quiescent(after)
            if before!=after:raise ValueError('XP1 UI observation changed native scheduler state')
            result=dict(binding=binding,observation=observation,jobs_before=before,jobs_after=after,
                core_sha256=self.core_sha256,source_sha256=self.source_sha256,
                control_after=control,player_id=player,public_runtime_admitted=False,
                source='separate official native UI child; shared player collector',
                complete_player_observation=False,explored_memory_included=False,
                visibility_parity_qualified=False,game_update_called=False,
                gameplay_api_copied=False,gameplay_visibility_unchanged=True)
            self.result=result;self.completed=True;b.stage=COMPLETED_STAGE;b.busy=False
            return result
        except BaseException:
            self.publication.lease.poison();b.stage='poisoned';b.busy=False
            raise
