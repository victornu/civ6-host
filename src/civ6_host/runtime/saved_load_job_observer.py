"""Exact-profile candidate Load scheduler observer using the host-owned layout API.

This is a serial diagnostic profile. It does not certify scheduling cadence,
arbitrary job subclasses, a successful Load or a playable expansion session.
"""
import ctypes as C
import hashlib
from pathlib import Path
import struct

from .configuration_profiles import _source, BASE_CORE_SHA256, XP1_CORE_SHA256, XP2_CORE_SHA256
from .job_registry_snapshot import capture_registry, validate_empty_transition_data
from .native.native_checkpoint_job_observer import CurrentProcessApi
from .native.native_checkpoint_postload_jobs import _ledger_event
from .source_build_identity import verify_source_build, XP2_HOST_COMPONENT_SHA

SOURCE=('work/host-extensions/xp1-job-static/xp1-job-source-v1.json',
        '6074219bff39d74b4e8ab63f7d1230b2ab7a9502074604b6d9643ffdc601aee7')
XP2_SOURCE=('work/host-extensions/xp2-job-static/xp2-job-source-profile-v2.json',
            'a12d33466ee0c5a748e474ef4112f4d6c31271dcc47ce1942cd8e400b94e40e0')
BASE_SCHEDULER_SOURCE=('evidence/native-job-scheduler-cadence.json',
                       '54d4f3891c24d1bd74549702c45b3b804bb25032cb4423434f26f97ffc8d006e')
HOST_COMPONENT_SHA='37cc07fa13511a51166726fbd104538ee650ea5dcbcac273b4b3b3246cb6649f'
PROFILE='owned-serial-core-bound-job-registry-v1'
SCHEMA='civ6_host.saved_load_job_snapshot.v1'
ADDRESS_NAMES=('free_head','slots','active_head','lock','runtime_thread',
               'spawn_active','groups','submission_sequence')
LAYOUT_PREFIX=(1,8,64,32,56,32,4848501265015980593)
LAYOUT_TAIL=(0x1F00000000,0,8,16,24,40,48,16,24)

# C registry profile IDs are part of LAB_BindJobCore's explicit ABI.
# This selector never treats an unknown Core as one of the known profiles.
CORE_JOB_PROFILES={
    BASE_CORE_SHA256:dict(profile=1,source=BASE_SCHEDULER_SOURCE,
        schema='civ6rl.native_job_scheduler_cadence.static.v1',module='GameCore_Base_FinalRelease.dll',
        vtable_rva=0x799A30,destroy_rva=0x3D6220,execute_rva=0x3D75B0,completed_offset=0xF0,
        host_component_sha=HOST_COMPONENT_SHA,kind='base'),
    XP1_CORE_SHA256:dict(profile=2,source=SOURCE,
        schema='civ6_host.xp1_job_scheduler_source.v1',module='GameCore_XP1_FinalRelease.dll',
        vtable_rva=0x8A4870,destroy_rva=0x463E40,execute_rva=0x465110,completed_offset=0xF0,
        host_component_sha=HOST_COMPONENT_SHA,kind='xp1'),
    XP2_CORE_SHA256:dict(profile=3,source=XP2_SOURCE,
        schema='civ6_host.xp2_victory_job_static_source_profile.v2',module='GameCore_XP2_FinalRelease.dll',
        vtable_rva=0xA0B7D0,destroy_rva=0x535800,execute_rva=0x536B00,completed_offset=0xF0,
        host_component_sha=XP2_HOST_COMPONENT_SHA,kind='xp2'),
}
SOURCE_HASH_BY_PROFILE={1:BASE_SCHEDULER_SOURCE[1],2:SOURCE[1],3:XP2_SOURCE[1]}


def _live_body_matches(read,base,body):
    for fragment in body['fragments']:
        expected=b''.join(bytes.fromhex(row['bytes']) for row in fragment['instructions'])
        start_va=fragment.get('start_va')
        if start_va is None:
            start_va=hex(0x180000000+int(fragment['start_rva'],16))
        rva=int(start_va,16)-0x180000000
        if not expected or (fragment.get('length') is not None and len(expected)!=fragment['length']):
            raise ValueError('Job source fragment is not a complete instruction stream')
        if read(base+rva,len(expected))!=expected:
            raise ValueError('Live job code differs from exact source profile')


def _verify_core(backend):
    profile=backend.profile
    digest=getattr(profile,'source_core_sha256',profile.core_sha256)
    actual_digest=profile.core_sha256
    if getattr(profile,'execution_image',None) is not None:
        from .native.native_core_context_profiles import require_executable_profile
        require_executable_profile(profile)
    if backend.load_abi.core_sha256!=digest:
        raise ValueError('Job observer Core differs from saved-Load ABI')
    spec=CORE_JOB_PROFILES.get(digest)
    if spec is None:
        raise ValueError('No exact Base, XP1, or XP2 job profile; refusing fallback')
    path=Path(backend.core._name).resolve(strict=True)
    if path.name!=spec['module'] or hashlib.sha256(path.read_bytes()).hexdigest()!=actual_digest:
        raise ValueError('Selected GameCore file differs from exact job profile')
    proof=_source(spec['source'])
    if spec['kind']=='base':
        if proof.get('schema')!=spec['schema'] or proof['core_image']['sha256']!=digest:
            raise ValueError('Base scheduler source identity differs')
        descriptor=proof['core_job_descriptor']
        if (int(descriptor['vtable_va'],16)-0x180000000!=spec['vtable_rva']
                or int(descriptor['vtable_slots_0x00_and_0x08'][0],16)-0x180000000!=spec['destroy_rva']
                or int(descriptor['execute_va'],16)-0x180000000!=spec['execute_rva']):
            raise ValueError('Base source job slots differ from explicit profile')
        bodies=(descriptor['execute_body'],descriptor['destructor_body'])
        table_bytes=struct.pack('<QQ',0x180000000+spec['destroy_rva'],0x180000000+spec['execute_rva'])
    elif spec['kind']=='xp1':
        if proof.get('schema')!=spec['schema'] or proof['image']['sha256']!=digest:
            raise ValueError('XP1 job source identity differs')
        dependency=proof['shared_exe_contract']
        shared=_source((dependency['path'],dependency['sha256']))
        if shared['image']['sha256']!='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63':
            raise ValueError('Shared official EXE job adapter source differs')
        bodies=tuple(proof['functions'].values())
        table=proof['vtable']
        if (int(table['rva'],16)!=spec['vtable_rva']
                or int(table['destroy_rva'],16)!=spec['destroy_rva']
                or int(table['execute_rva'],16)!=spec['execute_rva']):
            raise ValueError('XP1 job slots differ from explicit profile')
        table_bytes=bytes.fromhex(table['bytes'])
    else:
        if proof.get('schema')!=spec['schema'] or proof['image']['sha256']!=digest:
            raise ValueError('XP2 job source identity differs')
        job=proof['xp2_class'];table=job['vtable']
        if (int(table['rva'],16)!=spec['vtable_rva']
                or job['slots']!={'0x00_destructor':'0x535800','0x08_execute':'0x536b00'}
                or int(job['execute_completion_byte_offset'],16)!=spec['completed_offset']):
            raise ValueError('XP2 job slots/completion offset differ from explicit profile')
        bodies=tuple(proof['bodies'].values())
        table_bytes=bytes.fromhex(table['raw_hex'])
    base=backend.core._handle
    read=backend.runtime.read
    for body in bodies:
        _live_body_matches(read,base,body)
    if len(table_bytes)<16:
        raise ValueError('Source job vtable lacks its two ABI slots')
    preferred_slots=(0x180000000+spec['destroy_rva'],0x180000000+spec['execute_rva'])
    source_slots=struct.unpack('<QQ',table_bytes[:16])
    if source_slots!=preferred_slots:
        raise ValueError('Source job vtable targets differ from selected ABI')
    rebased_table_bytes=struct.pack('<QQ',base+spec['destroy_rva'],base+spec['execute_rva'])+table_bytes[16:]
    if read(base+spec['vtable_rva'],len(rebased_table_bytes))!=rebased_table_bytes:
        raise ValueError('Live job vtable differs from exact source profile')
    return dict(sha256=digest,actual_image_sha256=actual_digest,
                reference_core_sha256=digest,base=base,path=str(path),profile=spec['profile'],
                vtable_rva=spec['vtable_rva'],destroy_rva=spec['destroy_rva'],
                execute_rva=spec['execute_rva'],completed_offset=spec['completed_offset'],
                source=spec['source'],source_sha256=spec['source'][1],
                host_component_sha=spec['host_component_sha'])


class SavedLoadJobObserver:
    def __init__(self,backend):
        if backend.stage!='copied' or backend.busy is not True or backend.runtime.thread()!=backend.thread:
            raise RuntimeError('Job observer requires exclusive copied-stage owner')
        self.backend=backend
        self.api=CurrentProcessApi()
        self.host=backend.prefix.runtime.host
        self.busy=False
        self._query_owner=None
        self.last_snapshots={}
        base=self.api.main_module()
        if int(self.host._handle)!=base or self.api.current_thread_id()!=backend.thread[1]:
            raise ValueError('Scheduler exports are not owned by the current native host')
        path=Path(self.api.module_filename(base)).resolve(strict=True)
        self.identity=dict(host_base=base,executable_path=str(path),os_thread_id=backend.thread[1])
        self.core=_verify_core(backend)
        from .source_build_identity import xp2_component_requirements
        required = {'gamecore_python_host.c':self.core['host_component_sha']}
        from .execution_images import _XP1_PROFILE, _verify_native_host_build
        if getattr(backend.profile, 'execution_image', None) is _XP1_PROFILE:
            from .paths import resource_root
            if path != (resource_root()/_XP1_PROFILE.native_host_build.executable_path).resolve():
                raise ValueError('Current XP1 scheduler requires its exact registered host build')
            self.build = _verify_native_host_build(_XP1_PROFILE)
        else:
            if self.core.get('reference_core_sha256', self.core['sha256']) == XP2_CORE_SHA256:
                required = xp2_component_requirements(path, required)
            self.build = verify_source_build(path, required_components=required)
        self.bind=self.host.LAB_BindJobCore
        self.bind.argtypes,self.bind.restype=[C.c_uint32,C.c_size_t],C.c_int
        self.layout=self.host.LAB_GetJobRegistryLayout
        self.layout.argtypes,self.layout.restype=[C.POINTER(C.c_uint64),C.c_size_t],C.c_int
        # This is the sole explicit configuration write, before any snapshot.
        # C refuses a different binding, pending groups or prior submissions.
        if self.bind(self.core['profile'],self.core['base'])!=0:
            raise RuntimeError('Native scheduler refused the exact bound Core profile')
        self.layout_words=self._layout()

    def _layout(self):
        values=(C.c_uint64*28)()
        if self.layout(values,28)!=0:
            raise RuntimeError('Native job introspection refused')
        words=tuple(values)
        if (words[:7]!=LAYOUT_PREFIX
                or words[15:20]!=(self.core['base'],self.core['profile'],self.core['execute_rva'],
                                  self.core['completed_offset'],LAYOUT_TAIL[0])
                or words[20:]!=LAYOUT_TAIL[1:]):
            raise ValueError('Native job registry layout differs from the shared walker')
        # All globals must belong to the actual host image, not the game heap.
        read=self.backend.runtime.read
        base=self.identity['host_base']
        pe_offset=struct.unpack('<I',read(base+0x3C,4))[0]
        if not 64<=pe_offset<=4096 or read(base+pe_offset,4)!=b'PE\0\0':
            raise ValueError('Actual host PE header differs')
        size=struct.unpack('<I',read(base+pe_offset+24+56,4))[0]
        addresses=dict(zip(ADDRESS_NAMES,words[7:15],strict=True))
        for name,address in addresses.items():
            width=2048 if name=='slots' else 4 if name in ('runtime_thread','spawn_active') else 8
            if not base<=address<=base+size-width or address%(4 if width==4 else 8):
                raise ValueError('Registry address is not a bounded host-owned field')
        return words

    def _exclusive(self):
        b=self.backend
        query=getattr(self,'_query_owner',None)
        if query is not None:
            from .xp1_saved_load_owner import SavedLoadOwner
            if (type(query) is not SavedLoadOwner or query.backend is not b
                    or b.jobs is not self or b.busy is not False
                    or b.snapshot_phase not in ('before','after')
                    or b.runtime.thread()!=b.thread or b.poisoned or b.destroyed):
                return False
            # The exact retained query graph, including the READY continuation,
            # owns this read. Do not impersonate an active game command by
            # changing stage/busy flags just to inspect the scheduler.
            query._check_query()
            return True
        if not (b.busy is True and b.snapshot_phase in ('before','after')
                and b.runtime.thread()==b.thread and not b.poisoned and not b.destroyed):
            return False
        if b.stage in ('loaded-lifetime-wrappers', 'loaded-lifetime-unloaded'):
            selected_profile=getattr(b,'profile',None)
            selected_source=getattr(selected_profile,'source_core_sha256',
                                    getattr(selected_profile,'core_sha256',None))
            if selected_source==XP2_CORE_SHA256:
                from .xp1_loaded_lifetime import LoadedLifetime
                from .xp2_loaded_lifetime_source import SOURCE as XP2_LIFETIME_SOURCE
                lifetime=getattr(b,'_loaded_lifetime',None)
                if (type(lifetime) is not LoadedLifetime or lifetime.owner is not b
                        or lifetime.source_reference!=XP2_LIFETIME_SOURCE
                        or self.core.get('profile')!=3 or self.core.get('sha256')!=XP2_CORE_SHA256
                        or b.load_abi.core_sha256!=XP2_CORE_SHA256):
                    return False
                if lifetime.raw_loaded is True:
                    if lifetime.lease is not None:
                        return False
                elif lifetime.raw_loaded is False:
                    from .loaded_cache_publication import LoadedCachePublication
                    from .xp1_loaded_lifetime import source_dependencies
                    if (not lifetime.xp2_loaded or type(lifetime.lease) is not LoadedCachePublication
                            or lifetime.lease.owner is not b or lifetime.lease.lifetime is not lifetime
                            or lifetime.lease.core_sha256!=XP2_CORE_SHA256
                            or not isinstance(lifetime.postload_source_dependencies,dict)
                            or not lifetime.postload_source_dependencies
                            or lifetime.postload_source_dependencies!=source_dependencies(XP2_CORE_SHA256,postload=True)):
                        return False
                else:
                    return False
            else:
                from .xp1_loaded_lifetime import LoadedLifetime
                lifetime = getattr(b, '_loaded_lifetime', None)
                if type(lifetime) is not LoadedLifetime or lifetime.owner is not b:
                    return False
            lifetime.check_job_snapshot()
            return True
        if b.stage=='player-view-candidate-active':
            from .xp1_ui_binding import SavedPlayerView
            view=getattr(b,'_xp1_player_view',None)
            if type(view) is not SavedPlayerView or view.owner is not b:return False
            view.check_active()
            return True
        if b.stage=='xp1-continuation-active':
            from .xp1_continuation import SavedContinuation
            token=getattr(b,'_xp1_continuation',None)
            if type(token) is not SavedContinuation or token.owner is not b:return False
            token.check(active=True)
            return True
        if b.stage=='copied':
            return True
        if b.stage not in ('raw-loaded', 'post160-candidate-active', 'publication-candidate-active'):
            return False
        # A raw-loaded label alone does not authorize another snapshot phase.
        # The facade owner lends its exact live candidate lease until finish.
        from .loaded_cache_publication import LoadedCachePublication
        lease=getattr(b,'_saved_load_job_cache_owner',None)
        if (type(lease) is not LoadedCachePublication or lease.owner is not b
                or lease.attempt.publication_owner is not lease
                or lease.attempt.owner is not b or lease.attempt.publication_mode!='candidate'):
            return False
        if b.stage == 'publication-candidate-active':
            from .xp1_cache_publication import SavedCachePublication
            attempt = getattr(lease, 'publication_attempt', None)
            if (type(attempt) is not SavedCachePublication or attempt.owner is not b
                    or attempt.lease is not lease
                    or getattr(b, '_xp1_publication_attempt', None) is not attempt):
                return False
        elif b.stage == 'post160-candidate-active':
            from .native.native_official_postload import OfficialPost160Backend
            attempt = getattr(lease, 'post160_attempt', None)
            if (type(attempt) is not OfficialPost160Backend or attempt.owner is not b
                    or attempt.postload_mode != 'candidate'
                    or getattr(b, '_xp1_post160_attempt', None) is not attempt):
                return False
        elif hasattr(lease, 'post160_attempt'):
            return False
        lease._check()
        return True

    def query_snapshot(self,saved,phase):
        """Inspect jobs during an existing saved-session read-only attempt."""
        from .xp1_saved_load_owner import SavedLoadOwner
        b=self.backend
        if (type(saved) is not SavedLoadOwner or saved.backend is not b
                or b.jobs is not self or phase not in ('before','after')
                or self.busy or getattr(self,'_query_owner',None) is not None):
            raise ValueError('Job query requires its exact idle saved-session observer')
        saved._check_query()
        previous=b.snapshot_phase
        self._query_owner=saved
        try:
            result=b.jobs_snapshot(phase)
            saved._check_query()
            return result
        finally:
            self._query_owner=None
            b.snapshot_phase=previous

    def __call__(self):
        if self.busy or not self._exclusive():
            raise RuntimeError('Job snapshot requires the exclusive saved Load boundary')
        self.busy=True
        try:
            if (self.api.main_module()!=self.identity['host_base']
                    or self.api.current_thread_id()!=self.identity['os_thread_id']
                    or str(Path(self.api.module_filename(self.identity['host_base'])).resolve(strict=True))!=self.identity['executable_path']):
                raise ValueError('Scheduler process identity changed')
            layout=self._layout()
            if layout!=self.layout_words:
                raise ValueError('Native job ownership/layout changed')
            observed=capture_registry(self.backend.runtime.read,dict(zip(ADDRESS_NAMES,layout[7:15],strict=True)),self.identity['os_thread_id'])
            if self._layout()!=layout or not self._exclusive():
                raise ValueError('Scheduler identity/admission changed while observing')
            result=dict(observed,schema=SCHEMA,profile=PROFILE,source_proof_sha256=self.core['source_sha256'],
                        host_sha256=self.build['host_sha256'],source_build=self.build,
                        current_executable=self.identity,core_identity=self.core,
                        native_methods_called=True,native_introspection_only=True)
            require_quiescent(result)
            # Phase belongs to the active owner call, not measured registry
            # state: identical cache snapshots must remain byte-for-byte equal.
            self.last_snapshots[self.backend.snapshot_phase]=result
            return result
        finally:
            self.busy=False


def require_quiescent(s):
    core=s.get('core_identity') if type(s) is dict else None
    profile=core.get('profile') if type(core) is dict else None
    if (type(s) is not dict or s.get('schema')!=SCHEMA or s.get('profile')!=PROFILE
            or type(profile) is not int or s.get('source_proof_sha256')!=SOURCE_HASH_BY_PROFILE.get(profile)
            or s.get('stable_read') is not True or s.get('memory_modified') is not False
            or s.get('concurrent_scheduler_supported') is not False
            or s.get('native_introspection_only') is not True or s.get('native_methods_called') is not True):
        raise ValueError('No source-bound scheduler snapshot')
    for key in ('spawn_active','registry_lock_raw','pending_items'):
        if type(s.get(key)) is not int or s[key]!=0:
            raise ValueError('Scheduler is not quiescent')
    slots=s.get('slots')
    if type(slots) is not list or len(slots)!=64:
        raise ValueError('Expected all64 scheduler slots')
    for index,slot in enumerate(slots,1):
        if (set(slot)!= {'handle','occupied','count','items'} or type(slot['handle']) is not int
                or slot['handle']!=index or type(slot['occupied']) is not bool
                or type(slot['count']) is not int or slot['count']!=0 or slot['items']!=[]):
            raise ValueError('Invalid or pending slot')
    groups=s.get('groups')
    if type(groups) is not list or len(groups)>4096:
        raise ValueError('Unbounded scheduler group list')
    seen=set();owners=set()
    for g in groups:
        if set(g)!= {'pointer','owner','pending'} or any(type(g[k]) is not int for k in g):
            raise ValueError('Invalid scheduler group')
        if (g['pending']!=0 or min(g['pointer'],g['owner'])<=0 or g['pointer']%8 or g['owner']%8
                or g['pointer'] in seen or g['owner'] in owners):
            raise ValueError('Pending or duplicate scheduler group')
        seen.add(g['pointer']);owners.add(g['owner'])
    if type(s.get('submission_sequence')) is not int or not 0<=s['submission_sequence']<1<<64:
        raise ValueError('Invalid native submission sequence')
    return s


def make_job_observer(backend):
    return SavedLoadJobObserver(backend)


def validate_transition(backend,before,after):
    if backend.runtime.thread()!=backend.thread or not backend.busy or not backend.load_attempted:
        raise RuntimeError('Job transition requires the actual synchronous Load return')
    observer=backend.jobs
    if not isinstance(observer,SavedLoadJobObserver) or observer.backend is not backend:
        raise ValueError('Scheduler observer is not owned by this Load')
    for phase,s in (('before',before),('after',after)):
        require_quiescent(s)
        if (observer.last_snapshots.get(phase) is not s or s['current_executable']!=observer.identity
                or s['source_build']!=observer.build or s['host_sha256']!=observer.build['host_sha256']
                or s['core_identity']!=observer.core or s['owner_thread_id']!=backend.thread[1]):
            raise ValueError('Job snapshot identity differs from the live observer')
    data=validate_empty_transition_data(before,after)
    return dict(data,schema='civ6_host.saved_load_empty_jobs_transition.v1',
                source_proof_sha256=observer.core['source_sha256'],source_build=observer.build,
                core_identity=observer.core,source_host_component_sha256=observer.core['host_component_sha'])


def reconcile_ledger(candidate,events):
    """Supervisor-only: events must be authenticated inside actual Load markers."""
    core=candidate.get('core_identity') if type(candidate) is dict else None
    core_profile=core.get('profile') if type(core) is dict else None
    if core is None:
        # Preserve the retained XP1 transcript format, which predates embedding
        # core_identity in the raw receipt. It remains bound to its sole exact
        # XP1 source pin; Base/XP2 require the explicit profile identity.
        source_matches=candidate.get('source_proof_sha256')==SOURCE[1]
    else:
        source_matches=(type(core_profile) is int
                        and candidate.get('source_proof_sha256')==SOURCE_HASH_BY_PROFILE.get(core_profile))
    if (candidate.get('schema')!='civ6_host.saved_load_empty_jobs_transition.v1'
            or not source_matches
            or candidate.get('ledger_reconciled') is not False
            or candidate.get('snapshot_structural_candidate') is not True
            or type(events) not in (list,tuple) or len(events)>4096):
        raise ValueError('Expected bounded unreconciled saved Load job evidence')
    operations=[_ledger_event(row) for row in events]
    creates=[handle for kind,handle in operations if kind=='create']
    if len(set(creates))!=len(creates) or sorted(creates)!=candidate['created_empty_handles_candidate']:
        raise ValueError('Scheduler ledger does not match actual empty-slot changes')
    return dict(candidate,ledger_reconciled=True,ledger_events_match_snapshot=True,
                native_load_success_claimed=False,ledger_provenance_checked_by_this_function=False)
