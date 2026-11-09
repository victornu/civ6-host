"""Source-bound Congress request permits; staged, not native qualification."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

from .paths import resource_root
from .resource_resolution import resolve_path
from .configuration_profiles import XP2_CORE_SHA256
from .a0_policy_unlock_current import _require_image

SOURCE = ('work/trade-common-client/congress-player-api-inventory.json',
          'c1eaf46d85b9f4163cf04dfe5fd83c2ba8719f77a54f759d4c1bbfb65b72df54')
OPERATION_SOURCE = ('work/trade-common-client/congress-api-staging-runtime/congress-operation-source.json',
                    'daf218294bd595822ac9eedbb8916aad5a6a07a8ffeec163cc18b73aa2f67fcb')
OPERATIONS = {
    'congress_resolution_vote': 'WORLD_CONGRESS_RESOLUTION_VOTE',
    'congress_discussion_vote': 'WORLD_CONGRESS_DISCUSSION_VOTE',
    'congress_discussion_selection': 'WORLD_CONGRESS_DISCUSSION_SELECTION',
    'congress_submit': 'WORLD_CONGRESS_SUBMIT_TURN',
    'congress_looked_at_available': 'WORLD_CONGRESS_LOOKED_AT_AVAILABLE',
}
PARAMETERS = ('PARAM_RESOLUTION_TYPE', 'PARAM_WORLD_CONGRESS_VOTES',
              'PARAM_RESOLUTION_OPTION', 'PARAM_RESOLUTION_SELECTION',
              'PARAM_PLAYER_ONE', 'PARAM_PLAYER_TWO', 'PARAM_OTHER_PLAYER', 'PARAM_DISCUSSION_TYPE')
EMPTY = frozenset(('WORLD_CONGRESS_SUBMIT_TURN', 'WORLD_CONGRESS_LOOKED_AT_AVAILABLE'))
PARAMETER_NAMES = {
    'congress_resolution_vote': ('PARAM_RESOLUTION_TYPE', 'PARAM_WORLD_CONGRESS_VOTES',
                                'PARAM_RESOLUTION_OPTION', 'PARAM_RESOLUTION_SELECTION'),
    'congress_discussion_vote': ('PARAM_PLAYER_ONE', 'PARAM_PLAYER_TWO', 'PARAM_WORLD_CONGRESS_VOTES'),
    'congress_discussion_selection': ('PARAM_OTHER_PLAYER', 'PARAM_DISCUSSION_TYPE'),
    'congress_submit': (), 'congress_looked_at_available': (),
}
_SEAL = object()


def operation_source():
    from .configuration_profiles import _source
    proof = _source(OPERATION_SOURCE)
    if (proof['schema'] != 'civ6-host.congress-operation-source.v1'
            or proof['core']['sha256'] != '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
            or proof['inactive_exception'] != dict(value_u32=0xdaa47655,
                name='START_OBSERVER_MODE', congress_operations_exempt=False)
            or set(proof['enums']) != set(OPERATIONS.values()) | set(PARAMETERS) | {'START_OBSERVER_MODE'}):
        raise ValueError('Congress enum/request authority proof differs')
    return proof


def enum_values():
    return {name: row['value_u32'] for name, row in operation_source()['enums'].items()
            if name != 'START_OBSERVER_MODE'}


def verify_live(saved):
    proof = operation_source()
    b = saved.backend
    for row in [*proof['enums'].values(), *proof['namespace'], proof['signed_enum_helper']]:
        raw = b.runtime.read(b.core._handle + int(row['rva'], 16), row['bytes'])
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Live Congress enum source changed at ' + row['rva'])


def source_dependencies(*, execution_image):
    _require_image(execution_image)
    path = resolve_path(resource_root() / SOURCE[0])
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SOURCE[1]:
        raise ValueError('Congress player-source inventory changed')
    proof = json.loads(raw)
    if proof['schema'] != 'civ6-host.world-congress-player-api-inventory.v1':
        raise ValueError('Unknown Congress player-source inventory')
    result = {str(path.resolve()): SOURCE[1]}
    operations = operation_source()
    result[str(resolve_path(resource_root() / OPERATION_SOURCE[0]).resolve())] = OPERATION_SOURCE[1]
    authority = operations['request_authority']
    authority_path = resolve_path(Path(authority['path']))
    if hashlib.sha256(authority_path.read_bytes()).hexdigest() != authority['sha256']:
        raise ValueError('Congress requested-player authority source changed')
    result[str(authority_path.resolve())] = authority['sha256']
    # Host rows are an inventory snapshot, not immutable runtime dependencies.
    for row in proof['source_files']:
        if row['id'].startswith('host:'):
            continue
        item = resolve_path(Path(row['path']))
        data = item.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('Installed Congress source changed: ' + row['id'])
        result[str(item.resolve())] = row['sha256']
    from .xp2_world_congress_popup import source_dependencies as popup_dependencies
    result.update(popup_dependencies())
    from .xp2_turn_segment import source_dependencies as segment_dependencies
    result.update(segment_dependencies(execution_image=execution_image))
    from .xp2_congress_configuration import source_dependencies as configuration_dependencies
    result.update(configuration_dependencies(execution_image=execution_image))
    return result


@dataclass(frozen=True)
class _Permit:
    seal: object
    core: object
    context: int
    player: int
    operation: int
    parameters: tuple
    name: str


def request_permit(saved, kind, operation, parameters, enums):
    """Only the already-revalidated player catalogue may call this helper."""
    from .xp1_world_input import _owner
    b, _, _, _ = _owner(saved, active=True)
    source_dependencies(execution_image=getattr(b.core, '_civ6_host_execution_image', None))
    name = OPERATIONS[kind]
    if (enums != enum_values() or type(operation) is not int or operation != enums[name]
            or not 0 <= operation <= 0xffffffff
            or type(parameters) is not dict
            or set(parameters) != {enums[k] for k in PARAMETER_NAMES[kind]}
            or any(type(v) is not int or not 0 <= v <= 0xffffffff for v in parameters.values())
            or bool(parameters) == (name in EMPTY)):
        raise ValueError('Congress request has a foreign operation or parameter shape')
    return _Permit(_SEAL, b.core, b.context, saved.continuation.observation['player_id'],
                   operation, tuple(parameters.items()), name)


def authorize_request(permit, core, context, player, operation, parameters, *,
                      core_sha256, submit, allow_empty):
    """Narrow admission used by the proposed shared transport patch.

    The official popup directly requests these five operations. This permit
    does not reinterpret CanStart, and does not assert an applied native effect.
    """
    if (type(permit) is not _Permit or permit.seal is not _SEAL
            or core is not permit.core or context != permit.context or player != permit.player
            or operation != permit.operation or type(parameters) is not dict
            or tuple(parameters.items()) != permit.parameters
            or core_sha256 != XP2_CORE_SHA256 or submit is not True
            or allow_empty is not (permit.name in EMPTY)):
        raise ValueError('Missing exact Congress request permit')
    _require_image(getattr(core, '_civ6_host_execution_image', None))
    return permit.name
