"""Official Gathering Storm direct religious requests and their source admission."""

from collections.abc import Mapping
from dataclasses import dataclass

from . import xp2_religious_chain_source as chain
from .a0_family_source import family_profile, verify_pinned_files
from .configuration_profiles import XP2_CORE_SHA256, _source
from .execution_images import _PROFILE
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('work/x1trade/xp2-pantheon-runtime-stage/7892d6141b2ebfbecb08a96c7eaedcd7632c58fdf7e9e0144ece87bcbb28aada.json',
          '7892d6141b2ebfbecb08a96c7eaedcd7632c58fdf7e9e0144ece87bcbb28aada')
PANTHEON_BINDINGS = ('evidence/host-xp2-stock-pantheon-source.json',
                     'd6780d4a5e841f9143f2425f646327e69a1348da2eb7f5b5f2bbf775fe596cd1')
PANTHEON = 0x9671c7d1
FOUNDATION = 0xa4daffb5
BELIEF = 0xf8828e24
_INSERT_KEY = 0xac2fdc09
_EXCLUSIVE = 0x97fea5c6
_REQUESTS = {
    PANTHEON: ('FOUND_PANTHEON',0xa44b2907,'selected_hash'),
    FOUNDATION: ('FOUND_RELIGION',0x22a25b8b,'religion_hash'),
    BELIEF: ('ADD_BELIEF',0xa44b2907,'belief_hash'),
}
_SEAL = object()
_PANTHEON_NOTICES = {0x565abe26:195,0x51c84cba:103,0xb3495127:194}


def verify_source():
    from .native.native_event_565abe26 import verify_source as verify_pantheon_notice
    from .xp2_placement_event_source import RECORDS

    selected = _source(SOURCE)
    bindings = _source(PANTHEON_BINDINGS)
    if (selected['schema'] != 'civ6-host.xp2-pantheon-and-direct-religion-source.static.v1'
            or selected['image']['sha256'] != _PROFILE.image_sha256
            or selected['native_execution'] is not False
            or selected['u32s'] != {name:operation for operation,(name,_,_) in _REQUESTS.items()}
            or selected['references']['chain']['sha256'] != chain.SOURCE[1]
            or selected['references']['archive']['sha256'] != chain.ARCHIVE_SOURCE[1]
            or selected['references']['pantheon']['sha256'] != PANTHEON_BINDINGS[1]
            or {row['kind']:row['record'] for row in selected['known_callbacks']} != _PANTHEON_NOTICES
            or bindings['schema'] != 'civ6-host.xp2-stock-pantheon-source.v1'
            or bindings['core']['sha256'] != _PROFILE.image_sha256
            or bindings['contract']['source_only'] is not True
            or bindings['contract']['ui_calls_generic_can_start'] is not False
            or bindings['bindings']['CachePlayerReligion.GetPantheon']['callback']['rva'] != '0x6b36e0'
            or bindings['bindings']['CachePlayerReligion.CanCreatePantheon']['callback']['rva'] != '0x6b3510'):
        raise ValueError('Gathering Storm direct religious request source differs')
    records = family_profile().record_types_by_kind
    for kind,record in _PANTHEON_NOTICES.items():
        actual = (tuple(r for r,_ in RECORDS[kind]) if kind in RECORDS else records.get(kind,()))
        if record not in actual:
            raise ValueError('Gathering Storm pantheon notification profile differs')
    verify_pantheon_notice()
    return selected,bindings


def source_dependencies(image, *, reference):
    if image is not _PROFILE:
        raise ValueError('Direct religious requests require the exact Gathering Storm image')
    selected,bindings = verify_source()
    from .native.native_event_565abe26 import PIN as event_pin
    rows = [dict(path=path,sha256=digest) for path,digest in (SOURCE,PANTHEON_BINDINGS)]
    rows.extend(bindings['ui'].values())
    rows.append(dict(path=f'evidence/native-event-565abe26/{event_pin}.json',sha256=event_pin))
    pins = chain.source_dependencies(image,reference=reference,family=None)
    for row in rows:
        path = str(resolve_path(resource_root()/row['path']).resolve(strict=True))
        if pins.setdefault(path,row['sha256']) != row['sha256']:
            raise ValueError('Gathering Storm direct religion dependency conflict')
    verify_pinned_files(pins)
    return pins


def bind_prefix(prefix, *, family=None, action=False):
    """Reuse the known saved script/cache/notification/transport owners."""
    from .xp1_religious_unit_operations_source import _verify_spans
    from .xp1_saved_load_logger import XP2_SOURCE as logger_source

    chain.bind_prefix(prefix, family=family, action=action and family is not None)
    backend,core = prefix.backend,prefix.backend.core
    life = (core,core._handle,prefix,prefix.runtime)
    previous = getattr(prefix,'_xp2_direct_religion_lifetime',None)
    if previous is None:
        selected,bindings = verify_source()
        spans = [span for body in selected['bodies'].values() for span in body]
        spans.extend(selected['leafs'])
        spans.extend(dict(rva=row['rva'],length=row['bytes'],sha256=row['sha256'])
                     for section in ('bindings','enums')
                     for entry in bindings[section].values()
                     for row in entry.values() if isinstance(row,Mapping))
        spans.extend(dict(rva=row['rva'],length=row['bytes'],sha256=row['sha256'])
                     for row in bindings['paths'].values())
        _verify_spans(core._handle,backend.runtime.read,spans)
        prefix._xp2_direct_religion_lifetime = life
    elif previous != life:
        raise ValueError('Gathering Storm direct religion belongs to another saved lifetime')
    if action and family is None:
        consumer = prefix.event_arguments.consumer
        if (consumer._foundation_backend is not backend
                or getattr(backend,'_xp2_load_logger_activation',{}).get('source_sha256') != logger_source[1]
                or any(not consumer.handles_kind(kind) or not consumer.handles_record(record)
                       for kind,record in _PANTHEON_NOTICES.items())):
            raise ValueError('Gathering Storm pantheon action owner is missing')
        prefix.actions.require_transition()


@dataclass(frozen=True)
class _Permit:
    seal: object
    prefix: object
    core: object
    context: int
    player: int
    turn: int
    operation: int
    parameters: tuple
    borrowed_owner: object = None


def _require_actor(prefix, player, turn, borrowed_owner):
    owner = prefix.backend._xp1_continuation
    observation = owner.observation
    if observation['turn'] != turn:
        raise ValueError('Gathering Storm direct religious request crossed its turn')
    if borrowed_owner is None:
        if observation['player_id'] != player:
            raise ValueError('Gathering Storm direct religious request crossed its actor')
        return
    from .xp1_saved_load_owner import SavedLoadOwner
    from .xp1_session_view import _borrowed_xp2_reference

    if (type(borrowed_owner) is not SavedLoadOwner or borrowed_owner.backend is not prefix.backend
            or borrowed_owner.prefix is not prefix or borrowed_owner.continuation is not owner):
        raise ValueError('Gathering Storm religious request requires the exact borrowed saved owner')
    _borrowed_xp2_reference(borrowed_owner, player)
    source = f'''assert(Game.GetLocalPlayer()=={player} and Game.GetLocalObserver()=={player}
   and Game.GetCurrentGameTurn()=={turn},'borrowed religious perspective changed')
return "religion-actor"'''.encode('ascii')
    observed = prefix.runtime.evaluate_text(prefix.ui_child, source, b'@xp2_borrowed_religion_actor', capacity=32)
    if observed != b'religion-actor':
        raise ValueError('Gathering Storm religious request cannot verify its borrowed actor')


def _request_permit(prefix, player, turn, checked, *, borrowed_owner=None):
    """Seal the exact native Lua revalidation result, on this decision only."""
    if type(checked) is not dict or set(checked) != {'valid','choice','operation','parameters'} or checked['valid'] is not True:
        raise ValueError('Direct religion requires a fresh native revalidation')
    operation,choice,parameters = checked['operation'],checked['choice'],checked['parameters']
    if type(operation) is not int or operation not in _REQUESTS or type(choice) is not dict:
        raise ValueError('Unqualified direct religious operation')
    _,key,selected_hash = _REQUESTS[operation]
    if (type(player) is not int or not 0 <= player < 64 or type(turn) is not int or not 0 <= turn <= 0xffffffff
            or type(choice.get('player_id')) is not int or choice['player_id'] != player
            or type(choice.get('current_game_turn')) is not int or choice['current_game_turn'] != turn
            or type(choice.get(selected_hash)) is not int or not 0 <= choice[selected_hash] <= 0xffffffff
            or type(parameters) is not dict or any(type(k) is not int or type(v) is not int for k,v in parameters.items())
            or parameters != {key:choice[selected_hash],_INSERT_KEY:_EXCLUSIVE}
            or choice.get('parameters') != parameters):
        raise ValueError('Gathering Storm direct religious request values differ')
    family = {PANTHEON:None,FOUNDATION:'foundation',BELIEF:'beliefs'}[operation]
    bind_prefix(prefix,family=family,action=True)
    if prefix.ui_child is None or prefix.actions.pending or prefix.deferred_events.pending:
        raise ValueError('Gathering Storm direct religion requires a published view and drained queues')
    _require_actor(prefix, player, turn, borrowed_owner)
    return _Permit(_SEAL,prefix,prefix.core,prefix.context,player,turn,operation,tuple(parameters.items()),borrowed_owner)


def authorize_request(permit, core, context, player, operation, parameters, *,
                      core_sha256, submit, allow_empty):
    if (type(permit) is not _Permit or permit.seal is not _SEAL
            or permit.core is not core or type(context) is not int or context != permit.context
            or type(player) is not int or player != permit.player
            or type(operation) is not int or operation != permit.operation
            or getattr(core,'_civ6_host_execution_image',None) is not _PROFILE
            or core_sha256 != XP2_CORE_SHA256 or submit is not True or allow_empty is not False
            or type(parameters) is not dict or tuple(parameters.items()) != permit.parameters):
        raise ValueError('Missing exact Gathering Storm direct religious request permit')
    prefix = permit.prefix
    prefix.actions.require_transition()
    if (prefix.backend.prefix is not prefix or prefix.core is not core or prefix.context != context
            or prefix.actions.pending or prefix.deferred_events.pending):
        raise ValueError('Gathering Storm direct religious request no longer matches the live owner')
    _require_actor(prefix, player, permit.turn, permit.borrowed_owner)
    return _REQUESTS[operation][0]


def request(prefix, player, turn, checked, *, read, transport, borrowed_owner=None):
    permit = _request_permit(prefix,player,turn,checked,borrowed_owner=borrowed_owner)
    return transport(prefix.core,prefix.context,player,checked['operation'],checked['parameters'],
                     read=read,core_sha256=XP2_CORE_SHA256,religion_permit=permit)
