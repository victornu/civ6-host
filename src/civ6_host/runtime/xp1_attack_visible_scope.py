"""One-query reuse of the complete observation's visible plot indices.

This scope is internal to the retained saved owner. It does not accept a client
list, infer visibility, or suppress native legality checks. Default collectors
and command/revalidation/readback routes do not use it.
"""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256
from .xp1_world_input import _owner


@dataclass(frozen=True,init=False)
class _VisibleScope:
    saved:object
    backend:object
    continuation:object
    prefix:object
    identity:object
    episode_id:str
    game_generation:str
    core:object
    core_base:int
    core_sha256:str
    sequence:int
    publication_count:int
    observation:dict
    plots:tuple
    deferred_sequence:int
    deferred_consumed:int

    def __init__(self,*args,**kwargs):
        raise TypeError('Visible scope is created only by capture(saved, observation)')


def _plots(observation):
    width,height=observation['width'],observation['height']
    if (type(width) is not int or type(height) is not int or min(width,height)<1
            or width*height>16384 or type(observation['plots']) is not list
            or len(observation['plots'])>width*height):
        raise ValueError('Invalid complete visible observation dimensions')
    result=[];seen=set()
    for row in observation['plots']:
        if type(row) is not dict or row.get('visible') is not True or row.get('revealed') is not True:
            raise ValueError('Visible scope requires currently visible native plot rows')
        index,x,y=(row.get(k) for k in ('index','x','y'))
        if (any(type(v) is not int for v in (index,x,y)) or not 0<=index<width*height
                or not 0<=x<width or not 0<=y<height or index!=y*width+x or index in seen):
            raise ValueError('Visible scope plot identity is invalid or duplicated')
        seen.add(index);result.append((index,x,y))
    return tuple(sorted(result))


def check(scope,prefix,turn,player_id,core_sha256):
    """Check the exact owner and published observation before/after one query."""
    if scope is None:return
    if type(scope) is not _VisibleScope or core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256):
        raise TypeError('Only an exact expansion owner-bound visible scope is admitted')
    b,t,p,identity=_owner(scope.saved,active=False)
    if (core_sha256!=scope.core_sha256 or b.load_abi.core_sha256!=scope.core_sha256
            or b.core is not scope.core or b.core._handle!=scope.core_base
            or b is not scope.backend or t is not scope.continuation or p is not prefix
            or p is not scope.prefix or identity is not scope.identity
            or identity.episode_id!=scope.episode_id or identity.game_generation!=scope.game_generation
            or t.sequence!=scope.sequence or t.publication_count!=scope.publication_count
            or getattr(t,'_xp1_attack_visible_scope',None) is not scope
            or t.observation!=scope.observation or _plots(t.observation)!=scope.plots
            or type(turn) is not int or type(player_id) is not int
            or turn!=scope.observation['turn'] or player_id!=scope.observation['player_id']
            or p.deferred_events._sequence!=scope.deferred_sequence
            or p.deferred_events.consumed_count!=scope.deferred_consumed):
        raise ValueError('Visible scope is partial, stale, foreign or crossed publication')
    t.transport.require_empty_native_queue();b.control(empty=True)


@contextmanager
def capture(saved,observation):
    """Bind all rows from the current native observation, with no row selection.

    The public read calls this immediately after its complete observe_player
    result has been joined to the continuation. A parsed arbitrary list is not
    a completeness certificate and is never accepted as a separate argument.
    """
    b,t,p,identity=_owner(saved,active=False)
    if type(observation) is not dict or observation!=t.observation:
        raise ValueError('Visible scope requires the complete current native observation')
    if getattr(t,'_xp1_attack_visible_scope',None) is not None:
        raise RuntimeError('Visible observation query cannot be nested')
    scope=object.__new__(_VisibleScope)
    values=dict(saved=saved,backend=b,continuation=t,prefix=p,identity=identity,
        episode_id=identity.episode_id,game_generation=identity.game_generation,
        core=b.core,core_base=b.core._handle,core_sha256=b.load_abi.core_sha256,
        sequence=t.sequence,publication_count=t.publication_count,
        observation=deepcopy(observation),plots=_plots(observation),
        deferred_sequence=p.deferred_events._sequence,
        deferred_consumed=p.deferred_events.consumed_count)
    for key,value in values.items():object.__setattr__(scope,key,value)
    t._xp1_attack_visible_scope=scope
    try:
        check(scope,p,observation['turn'],observation['player_id'],scope.core_sha256)
        yield scope
        check(scope,p,observation['turn'],observation['player_id'],scope.core_sha256)
    finally:
        if getattr(t,'_xp1_attack_visible_scope',None) is scope:
            t._xp1_attack_visible_scope=None


def checked_result(scope,prefix,turn,player_id,core_sha256,result):
    check(scope,prefix,turn,player_id,core_sha256)
    return result


def source_for_scope(source,scope,*,turn,player_id,core_sha256):
    """Select only the enumeration loop; keep the shared city/legality body."""
    if scope is None:return source
    check(scope,scope.prefix if type(scope) is _VisibleScope else None,
          turn,player_id,core_sha256)
    if type(source) is not bytes:raise TypeError('Expected shared city Lua bytes')
    begin=b'for index=0,count-1 do'
    gate=b' if visibility:IsVisible(x,y) and visibility:IsRevealed(index) then'
    finish=b'return out\n\n'
    if source.count(begin)!=1 or source.count(gate)!=1 or not source.endswith(finish):
        raise ValueError('Shared city visibility or serializer seam changed')
    rows=','.join('{'+','.join(map(str,row))+'}' for row in scope.plots)
    width,height=scope.observation['width'],scope.observation['height']
    loop=(f"assert(width=={width} and height=={height},'visible scope map changed')\n"
          f'for _,scopedPlot in ipairs({{{rows}}}) do\n local index=scopedPlot[1]').encode('ascii')
    visible=(b"  assert(x==scopedPlot[2] and y==scopedPlot[3],'visible scope coordinates changed')\n"
             b"  assert(visibility:IsVisible(x,y) and visibility:IsRevealed(index),'visible scope became hidden')\n"
             b'  do')
    boundary=(b"assert(Game.GetLocalPlayer()==pid and Game.GetLocalObserver()==pid and Game.GetCurrentGameTurn()==turn,'visible scope perspective changed after query')\n"
              b'local scopedWidth,scopedHeight=Map.GetGridSize()\n'
              b"assert(scopedWidth==width and scopedHeight==height and Map.GetPlotCount()==count,'visible scope map changed after query')\n")
    return source.replace(begin,loop,1).replace(gate,visible,1)[:-len(finish)]+boundary+finish
