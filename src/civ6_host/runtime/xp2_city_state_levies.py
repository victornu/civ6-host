"""Source and live guards for the installed Gathering Storm levy path."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from struct import pack

from civ6_host.contracts import city_state_levies as contract

from .configuration_profiles import XP2_CORE_SHA256, _source
from .execution_images import identity
from .paths import resource_root
from .resource_resolution import resolve_path
from .xp2_envoys_source import UI_SOURCE, bind_owner as bind_envoy_owner
from .xp2_strategic_resources import SOURCE as CAPABILITY_SOURCE, _proof as capability_proof
from .xp2_unit_upgrades import _verify_binding, _verify_bodies


QUERY_SOURCE = ('evidence/host-xp2-installed-levy-query-source.json',
                'c151463e6b4e9b3190a3bf7e4239161853267858ab1ad18cd729339bcb5d9a0d')
OPERATION_SOURCE = ('evidence/host-xp2-installed-levy-operation-source.json',
                    '31be405d6061818f81ead0769118a44ce5609e5ab7a3bbc3b1e3dc5b02d9a9b1')
INSTALLED_CORE_SHA256 = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
PLAYER_OPERATION_ARCHIVE = 3294486831
OPERATION = 0xe6e2dbb2
TARGET_PARAMETER = 0x0483191c
_REQUEST_SEAL = object()
_BINDINGS = {
    'GetCombat', 'GetOwner', 'GetOriginalOwner', 'GetProperty', 'FindID',
    'GetInfluence', 'IsUnitVisible', 'GetLevyTurnCounter', 'GetLevyTurnLimit',
    'GetSuzerain', 'CanLevyMilitary', 'GetLevyMilitaryCost',
}
_UNIT_FLAG_SHA256 = '26f056a54b9c0f8410af4d05721ab9584740f35906424974fed58e984cced0ea'
# CanLevyMilitary forwards to these two spans. Strategic command permission
# uses a separate native path and is not part of this button's predicate.
_ELIGIBILITY_SPANS = (
    {'rva': 0xbc800, 'bytes': 37,
     'sha256': '2dcc64d53d78403f085b5202452fc80b82fa37fbda85d25c28d9cde5ab2b411e'},
    {'rva': 0x2e90f0, 'bytes': 264,
     'sha256': '28b8c1e9ca5d1a8ec40718af8d0dd9c71965145743eb38f59b1c0c09a88aa5a9'},
)


def source(execution_image):
    selected = identity(execution_image)
    query, operation = _source(QUERY_SOURCE), _source(OPERATION_SOURCE)
    configuration = query['configuration_registration']
    if (selected['image_sha256'] != INSTALLED_CORE_SHA256
            or selected['reference_core_sha256'] != XP2_CORE_SHA256
            or query['schema'] != 'civ6-host.xp2-installed-levy-query-source.v1'
            or operation['schema'] != 'civ6-host.xp2-installed-levy-operation-source.v1'
            or query['core'] != operation['core']
            or query['core']['sha256'] != selected['image_sha256']
            or _path(query['core']['path']) != _path(selected['path'])
            or (operation['parent']['path'], operation['parent']['sha256']) != QUERY_SOURCE
            or query['official_ui']['sha256'] != _UNIT_FLAG_SHA256
            or query['bindings'].keys() != _BINDINGS
            or (configuration['first_index'], configuration['count']) != (0, 64)
            or query['expiry']['update_kind'] != '0xf2f69b23'
            or operation['constants'] != {'operation': OPERATION, 'target_key': TARGET_PARAMETER,
                                          'treasury_fixed_point_shift': 8}
            or query['contract'] != dict(getters_verified_by_named_lua_closure_builder_and_field_setter=True,
                                        gameplay_rule_in_gamecore=True, native_execution=False,
                                        api_integration=False, content_profile_qualified=False)
            or operation['contract'] != dict(public_candidates_require_native_eligibility=True,
                                            treasury_and_ownership_required_for_execution_evidence=True,
                                            native_execution=False, api_integration=False,
                                            content_profile_qualified=False)):
        raise ValueError('Gathering Storm military levy source differs')
    return query, operation


def _path(path):
    return Path(resolve_path(path)).resolve()


def source_dependencies(execution_image):
    query, operation = source(execution_image)
    official = _source(UI_SOURCE)
    files = official['files']
    if (official['schema'] != 'civ6-host.xp2-envoys-ui-source.v1'
            or files['base']['sha256'] != operation['official_panel']['sha256']
            or _path(files['base']['path']) != _path(operation['official_panel']['path'])
            or files['bbg_modinfo']['citystates_replacements']
            or files['bbg_modinfo']['citystates_ui_files']):
        raise ValueError('Gathering Storm city-state panel source differs')
    pins = {str(_path(resource_root() / path)): digest for path, digest in
            (QUERY_SOURCE, OPERATION_SOURCE, UI_SOURCE, CAPABILITY_SOURCE)}
    for row in (query['core'], query['official_ui'], files['base'], files['xp2_wrapper'],
                files['xp2_parent'], files['xp2_modinfo']):
        pins[str(_path(row['path']))] = row['sha256']
    from . import xp1_city_state_levies as shared
    from .native import native_envoy_actions, native_player_operation_request
    for path in (Path(__file__), Path(shared.__file__), Path(native_envoy_actions.__file__),
                 Path(native_player_operation_request.__file__)):
        pins[str(path.resolve())] = sha256(path.read_bytes()).hexdigest()
    return pins


def bind_owner(saved, *, active):
    backend = saved.backend
    core = backend.core
    if (getattr(saved, 'xp2_city_state_levies_enabled', False) is not True
            or backend.load_abi.core_sha256 != XP2_CORE_SHA256):
        raise ValueError('Military levy requires the admitted Gathering Storm owner')
    bind_envoy_owner(saved, active=active)
    query, operation = source(getattr(core, '_civ6_host_execution_image', None))
    lifetime = (core, saved.prefix)
    if getattr(saved, '_xp2_city_state_levy_lifetime', None) != lifetime:
        read = backend.runtime.read
        base = core._handle
        spans = [span for row in query['bindings'].values() for span in row.values()]
        spans.extend(_ELIGIBILITY_SPANS)
        spans.append(query['configuration_registration']['span'])
        spans.extend(query['expiry'][name] for name in ('counter_and_notification', 'return_control'))
        spans.extend(operation['spans'].values())
        for span in spans:
            raw = read(base + span['rva'], span['bytes'])
            if type(raw) is not bytes or len(raw) != span['bytes'] or sha256(raw).hexdigest() != span['sha256']:
                raise ValueError(f"Live Gathering Storm military levy source differs at {span['rva']:#x}")
        capability = capability_proof()['bindings']['HasCapability']
        _verify_binding(read, base, 'HasCapability', capability, 'bytes_hex')
        _verify_bodies(read, base, (capability['callback'],))
        saved._xp2_city_state_levy_lifetime = lifetime
    return operation


@dataclass(frozen=True)
class _Permit:
    seal: object
    core: object
    context: int
    player: int
    target: int


def request_permit(saved, observation, action, fresh, *, borrowed=False):
    """Seal the direct UI request for a revalidated native levy offer."""
    contract.validate_action(action)
    bind_owner(saved, active=True)
    continuation = saved.continuation
    if borrowed:
        from .xp1_city_state_levies import snapshot
        from .xp1_session_view import _borrowed_xp2_reference

        _borrowed_xp2_reference(saved, observation['player_id'])
        current = snapshot(saved, observation, active=True) == fresh
    else:
        current = continuation.explicit_city_state_levies is fresh and continuation.observation == observation
    if (not current or fresh['player_id'] != observation['player_id']
            or fresh['turn'] != observation['turn']
            or action not in contract.actions(fresh)):
        raise ValueError('Military levy request requires its exact live offer')
    backend = saved.backend
    return _Permit(_REQUEST_SEAL, backend.core, backend.context,
                   fresh['player_id'], action['target_player_id'])


def validate_target_archive(payload, player_id, operation, target):
    if (type(player_id) is not int or not 0 <= player_id < 64
            or type(target) is not int or not 0 <= target < 64 or player_id == target
            or operation not in (0x99ec0bce, OPERATION)):
        raise ValueError('Malformed borrowed city-state operation')
    scalar = bytes.fromhex('0000020000000000000000000000')
    expected = pack('<7I14sI', PLAYER_OPERATION_ARCHIVE, player_id, operation, 2,
                    0x80000001, 1, TARGET_PARAMETER, scalar, target)
    if type(payload) is not bytes or payload != expected:
        raise ValueError('Borrowed city-state archive differs from its actor, operation or target')


def authorize_request(permit, core, context, player, operation, parameters, *,
                      core_sha256, submit, allow_empty):
    if (type(permit) is not _Permit or permit.seal is not _REQUEST_SEAL
            or core is not permit.core or context != permit.context or player != permit.player
            or operation != OPERATION or type(parameters) is not dict
            or parameters != {TARGET_PARAMETER: permit.target}
            or core_sha256 != XP2_CORE_SHA256 or submit is not True or allow_empty is not False):
        raise ValueError('Missing exact Gathering Storm military levy request permit')
    source(getattr(core, '_civ6_host_execution_image', None))
    return 'LEVY_MILITARY'
