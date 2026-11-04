"""Private XP1 refresh phase in the shared publisher; no player admission."""
import ctypes as C
from .configuration_profiles import _source,_body,XP1_CORE_SHA256
from .saved_load_profiles import XP2_CORE_SHA256
from .loaded_cache_profiles import source as cache_source,verify_xp1_live
from .xp1_postload_candidate import FINISHED_STAGE

SOURCE=('work/host-extensions/xp1-publication-static/publication-update-source-v1.json',
        'fff6afbad1e02a9bfe4327353712f45c272019a5af4af51620573ff51a4a1ab5')
ACTIVE_STAGE='publication-candidate-active'
COMPLETED_STAGE='publication-candidate-observed-awaiting-controlled-stop'

def source(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_cache_source import source as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown cache publication engine')
    p=_source(SOURCE)
    if (p['schema']!='civ6_host.xp1_publication_update.static.v1' or p['image']['sha256']!=XP1_CORE_SHA256
            or p['entries']['outer190']!=0x4be760 or p['entries']['kind4_refresh']!=0x80e30
            or p['validation']['instruction_bytes_match'] is not True
            or p['validation']['native_execution'] is not False):
        raise ValueError('XP1 publication source/profile changed')
    for r in p['references'].values():_source((r['path'],r['sha256']))
    return p

def source_dependencies(*,core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_cache_source import source_dependencies as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown cache publication engine')
    from .paths import resource_root
    from .resource_resolution import resolve_path
    p=source();rows=[dict(path=SOURCE[0],sha256=SOURCE[1]),*p['references'].values()]
    return {str(resolve_path(resource_root()/r['path']).resolve()):r['sha256'] for r in rows}

def verify_live(owner):
    if owner.load_abi.core_sha256==XP2_CORE_SHA256:
        from .xp2_cache_source import verify_live as selected
        return selected(owner.core._handle,owner.runtime.read)
    if owner.load_abi.core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown cache publication engine')
    p=source();base=owner.core._handle;read=owner.runtime.read
    # Update is retained as source only. This phase invokes no Update wrapper.
    for name in ('outer190','service_factory','game_getter','kind4_refresh'):
        for f in _body(p['functions'][name])['fragments']:
            for i in f['instructions']:
                raw=bytes.fromhex(i['bytes'])
                if read(base+int(i['va'],16)-0x180000000,len(raw))!=raw:
                    raise ValueError('XP1 publication code changed: '+name)
    for r in p['slots'][:2]:
        if int.from_bytes(read(base+r['vtable_rva']+r['slot'],8),'little')!=base+r['target_rva']:
            raise ValueError('XP1 publication virtual target changed')
    verify_xp1_live(base,read,cache_source())

def publication_target(core_sha256):
    if core_sha256==XP2_CORE_SHA256:
        return int(source(core_sha256=XP2_CORE_SHA256)['functions']['outer190']['entry_rva'],16)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown cache publication engine')
    return 0x4be760


def validate_publisher(publisher,attempt):
    from .xp1_continuation import SavedContinuation
    if type(attempt) is SavedContinuation:return attempt.validate_publication(publisher)
    if type(attempt) is not SavedCachePublication or attempt.publisher is not publisher:
        raise ValueError('XP1 publication needs its exact private saved owner')
    attempt.check_active()
    if attempt.native_attempted:
        raise ValueError('XP1 publication cannot retry the native call')
    return publication_target(attempt.owner.load_abi.core_sha256)

def before_native(publisher,attempt):
    from .xp1_continuation import SavedContinuation
    if type(attempt) is SavedContinuation:return attempt.before_publication(publisher)
    validate_publisher(publisher,attempt)
    attempt.native_attempted=True

def after_native(publisher,attempt,result):
    from .xp1_continuation import SavedContinuation
    if type(attempt) is SavedContinuation:return attempt.after_publication(publisher,result)
    if type(attempt) is not SavedCachePublication or attempt.publisher is not publisher:
        raise ValueError('XP1 publication return has another owner')
    attempt.check_active()
    if not attempt.native_attempted or attempt.native_returned:
        raise ValueError('XP1 publication return out of order')
    if result!=(attempt.owner.loaded_readback['width'],attempt.owner.loaded_readback['height'],
                attempt.owner.loaded_readback['width']*attempt.owner.loaded_readback['height']):
        raise ValueError('Native publication map dimensions differ from loaded map')
    attempt.native_returned=True

class SavedCachePublication:
    def __init__(self,post):
        from .native.native_official_postload import OfficialPost160Backend
        from .loaded_cache_publication import LoadedCachePublication
        if type(post) is not OfficialPost160Backend or post.postload_mode!='candidate':
            raise ValueError('XP1 publication requires the completed shared postload owner')
        b=post.owner;lease=post._candidate_cache_lease
        if (type(lease) is not LoadedCachePublication or lease.owner is not b
                or lease.post160_attempt is not post or lease.post160_finished is not True
                or b.stage!=FINISHED_STAGE or b.busy or b.poisoned or b.destroyed
                or b._xp1_post160_attempt is not post or not post.attempted or not post.native_call_attempted
                or getattr(post,'candidate_diagnostics',{}).get('void_return_ignored') is not True
                or hasattr(b,'_xp1_publication_attempt')):
            raise ValueError('XP1 publication lacks its exact finished postload')
        self.post,self.owner,self.lease=post,b,lease
        self.facade=post.facade;self.publisher=self.facade.publisher
        self.facades=self.publisher._facades
        self.attempted=self.native_attempted=self.native_returned=self.completed=False
        self.result=None
        b._xp1_publication_attempt=self

    def check_active(self):
        b=self.owner;self.lease._check()
        if (b._xp1_publication_attempt is not self or b.stage!=ACTIVE_STAGE or b.busy is not True
                or self.lease.publication_attempt is not self or self.publisher is not b.prefix.view_publisher
                or self.publisher.native_cache_gate is not False or self.publisher.full_facade_initialization_reproduced is not False
                or self.publisher._facades is not self.facades):
            raise ValueError('XP1 publication ownership/gates changed')
        from .cache_facade_profiles import check_facades
        check_facades(self.publisher._facades,self.lease.identity,b.runtime.read)

    def run(self):
        from .xp1_load_capability import begin_cache_source_scope,finish_cache_source_scope
        from .saved_load_job_observer import require_quiescent
        from .native.native_official_postload import validate_owner
        if self.attempted:raise ValueError('XP1 publication sequence cannot retry')
        self.attempted=True;b=self.owner
        try:
            validate_owner(b,stage=FINISHED_STAGE);verify_live(b)
            b.prefix.event_arguments.consumer.enable_publication_events(self)
            self.lease.begin_publication(self)
            begin_cache_source_scope(self.facade)
            self.check_active();before=b.jobs_snapshot('before');require_quiescent(before)
            dims=self.publisher.publish(publication_owner=self)
            # Refresh may produce owned host records. Consume the same FIFO;
            # publication must not discard records or pretend the queue is empty.
            notifications_before=b.control(empty=False)
            notifications_consumed=b.prefix.deferred_events.drain()
            notifications_after=b.control(empty=True)
            after=b.jobs_snapshot('after');require_quiescent(after)
            if before!=after:raise ValueError('XP1 publication changed scheduler state')
            readback=self.post.readback()
            final=b.jobs_snapshot('after');require_quiescent(final)
            if final!=before or readback!=dict(current_game_turn=b.loaded_readback['turn'],
                width=dims[0],height=dims[1],major_player_ids=list(self.post.expected_major_ids),
                scope='privileged diagnostic; no learner observation',game_update_called=False):
                raise ValueError('XP1 publication changed native loaded readback or jobs')
            self.check_active();finish_cache_source_scope(self.facade)
            result=dict(post190_called=True,native_return_ignored=True,cache_dimensions=list(dims),readback=readback,
                jobs_before=before,jobs_after=after,jobs_final=final,public_runtime_admitted=False,
                notifications_before=notifications_before,notifications_consumed=notifications_consumed,
                notifications_after=notifications_after,
                public_player_observation=False,game_update_called=False,context_destroyed=False)
            self.result=result;self.completed=True
            self.lease.finish_publication(self)
            return result
        except BaseException:
            try:finish_cache_source_scope(self.facade)
            finally:self.lease.poison();b.stage='poisoned';b.busy=False
            raise
