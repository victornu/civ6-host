"""Opt-in public perspectives on the existing native session transport.

Files hold only the latest accepted boundary, never a growing replay or a
privileged critic channel. Reading a view does not submit a game command.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

from civ6_host.player_view import SCHEMA, WAR_STATUS_SCHEMA, validate_player_view

STAGE = 'host_public_player_views'
MAX_VIEW_BYTES = 8 * 1024 * 1024
DIRECTORY = 'public-player-views'
CHECKPOINT_SCHEMA = 'civ6-host.checkpoint-public-views.v1'
CHECKPOINT_DECISIONS_SCHEMA = 'civ6-host.checkpoint-public-views.v2'
CHECKPOINT_DEVELOPMENT_SCHEMA = 'civ6-host.checkpoint-public-views.v3'
CHECKPOINT_COMBAT_SCHEMA = 'civ6-host.checkpoint-public-views.v4'
CHECKPOINT_OCCUPATION_SCHEMA = 'civ6-host.checkpoint-public-views.v5'
CHECKPOINT_RANGED_SHOTS_SCHEMA = 'civ6-host.checkpoint-public-views.v6'
CHECKPOINT_PURCHASE_SCHEMA = 'civ6-host.checkpoint-public-views.v7'
CHECKPOINT_GOVERNMENT_SCHEMA = 'civ6-host.checkpoint-public-views.v8'
CHECKPOINT_CITY_STATES_SCHEMA = 'civ6-host.checkpoint-public-views.v9'
CHECKPOINT_UNIT_WORK_SCHEMA = 'civ6-host.checkpoint-public-views.v10'
CHECKPOINT_ADJACENT_WORK_SCHEMA = 'civ6-host.checkpoint-public-views.v11'


def validate_players(value):
    if value is None:
        return ()
    if type(value) not in (list, tuple) or not 1 <= len(value) <= 64:
        raise ValueError('Public view players require an explicit nonempty list')
    if any(type(p) is not int or not 0 <= p < 64 for p in value) or len(set(value)) != len(value):
        raise ValueError('Public view players must be distinct native player IDs')
    return tuple(sorted(value))


def _relative(pid):
    return f'{DIRECTORY}/player-{pid}.json'


def _path(run, pid):
    run = Path(run).resolve(strict=True)
    path = run / _relative(pid)
    if path.is_symlink() or path.parent.is_symlink() or path.resolve() != path:
        raise ValueError('Public player view path is redirected')
    return path


def _read_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate public view key')
            result[key] = value
        return result
    def invalid(value):
        raise ValueError('Nonfinite public view value: ' + value)
    return json.loads(raw, object_pairs_hook=unique, parse_constant=invalid)


def _lan_source_pins():
    from civ6_host import player_view
    from . import xp1_saved_load_owner, xp2_diplomatic_relationships, xp2_human_perspective, xp2_local_player_changed
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .source_verification import file_sha256

    return {
        **{str(resolve_path(resource_root() / path).resolve()): digest for path, digest in
           (xp2_human_perspective.SOURCE, xp2_local_player_changed.SOURCE)},
        **{str(path): file_sha256(path) for path in
           (Path(name).resolve() for name in (__file__, player_view.__file__,
             xp1_saved_load_owner.__file__, xp2_human_perspective.__file__,
             xp2_local_player_changed.__file__, xp2_diplomatic_relationships.__file__))},
    }


def validate_lan_views(closure):
    """Check the selected XP2 view source closure before opening the GameCore."""
    players = validate_players(closure.get('public_view_players'))
    if not players:
        if 'public_view_sources' in closure:
            raise ValueError('LAN perspective sources require explicit human seat IDs')
        return ()
    from .execution_images import _PROFILE, from_identity
    if (closure.get('input_profile') != 'xp2-lan'
            or from_identity(closure.get('execution_image')) is not _PROFILE):
        raise ValueError('LAN public views require the installed Gathering Storm image')
    pins = _lan_source_pins()
    if closure.get('public_view_sources') != pins or any(closure['pins'].get(k) != v for k, v in pins.items()):
        raise ValueError('XP2 public perspective source closure differs')
    return players


def _validated_view(view, identity, sequence, player_id, turn):
    fields = dict(episode_id=identity.episode_id, game_generation=identity.game_generation,
                  sequence=sequence, player_id=player_id, turn=turn)
    schema = WAR_STATUS_SCHEMA if 'diplomatic_wars' in view else SCHEMA
    return validate_player_view(dict(schema=schema, **fields, **view), **fields)


def checkpoint_view_players(closure, boundary):
    """Select the public views explicitly opted into on a multi-human run."""
    if 'secondary_controls' not in boundary:
        return ()
    players = validate_players(closure.get('public_view_players'))
    session = boundary['session']
    if not set(players).issubset(session['human_player_ids']):
        raise ValueError('Checkpoint public views include an unauthenticated human seat')
    return players


def checkpoint_decision_players(closure, boundary, players):
    if closure.get('secondary_unit_commands') is not True:
        return ()
    return tuple(pid for pid in players if pid != boundary['session']['local_player_id'])


def checkpoint_view_digests(owner, boundary, players, *, decision_players=(), restored_envoy_views=None,
                            city_panel_groups=None, great_people_mode=None,
                            great_person_activation_enabled=None, pantheon_enabled=None,
                            governors_enabled=None, espionage_enabled=None, spy_completion_enabled=None,
                            religion_groups=None, trade_enabled=None, formation_enabled=None,
                            dedication_enabled=None, congress_mode=None, congress_actions=None,
                            restored_congress_ballots=None, city_building_version=None, unit_panel_families=None,
                            city_state_peace_enabled=None, world_score_enabled=None, archaeology_mode=None):
    """Hash the exact player-scoped fields, independent of new episode identity."""
    from civ6_host.contracts import city_buildings, network_turn

    digest = network_turn.digest

    token = owner.continuation
    identity, sequence = token.identity, token.sequence
    turn = boundary['session']['turn']
    controls = {row['player_id']: row for row in (boundary['controls'], *boundary['secondary_controls'])}
    groups = ()
    people_mode = 'off'
    activation_scope = False
    pantheon_scope = False
    governor_scope = False
    espionage_scope = False
    completion_scope = False
    religion_scope = ()
    trade_scope = False
    formation_scope = False
    dedication_scope = False
    congress_scope = 'off'
    compare_congress_actions = False
    effective_building_version = None
    unit_panel = ()
    peace_scope = False
    score_scope = False
    artifact_mode = 'off'
    if decision_players:
        from .xp2_human_perspective import city_panel_scope, unit_panel_scope
        from .xp2_lan_great_people import mode
        from .xp1_great_person_activation import borrowed_enabled as borrowed_activation_enabled
        from .xp1_pantheon import borrowed_enabled
        from .xp2_governors import borrowed_enabled as borrowed_governors_enabled
        from .xp2_espionage import borrowed_enabled as borrowed_espionage_enabled
        from .xp2_spy_completion import borrowed_enabled as borrowed_completion_enabled
        from .xp2_lan_religion import scope as religion_scope_for
        from .xp2_trade import borrowed_enabled as borrowed_trade_enabled
        from .xp2_unit_formations import borrowed_enabled as borrowed_formation_enabled
        from .xp2_dedications import borrowed_enabled as borrowed_dedication_enabled
        from .xp2_lan_congress import mode as borrowed_congress_mode
        from .xp2_lan_city_states import peace_scope as borrowed_peace_scope
        from .world_score import borrowed_enabled as borrowed_score_enabled
        from .xp2_archaeology import borrowed_mode as borrowed_archaeology_mode

        groups = city_panel_scope(owner, city_panel_groups)
        unit_panel = unit_panel_scope(owner, unit_panel_families)
        peace_scope = borrowed_peace_scope(owner, city_state_peace_enabled)
        score_scope = borrowed_score_enabled(owner, world_score_enabled)
        artifact_mode = borrowed_archaeology_mode(owner, archaeology_mode)
        people_mode = mode(owner, great_people_mode)
        activation_scope = borrowed_activation_enabled(owner, great_person_activation_enabled)
        pantheon_scope = borrowed_enabled(owner, pantheon_enabled)
        governor_scope = borrowed_governors_enabled(owner, governors_enabled)
        espionage_scope = borrowed_espionage_enabled(owner, espionage_enabled)
        completion_scope = borrowed_completion_enabled(owner, spy_completion_enabled)
        religion_scope = religion_scope_for(owner, religion_groups)
        trade_scope = borrowed_trade_enabled(owner, trade_enabled)
        formation_scope = borrowed_formation_enabled(owner, formation_enabled)
        dedication_scope = borrowed_dedication_enabled(owner, dedication_enabled)
        congress_scope = borrowed_congress_mode(owner, congress_mode)
        if (congress_actions is not None and type(congress_actions) is not bool
                or congress_actions is True and congress_scope != 'review'):
            raise ValueError('Checkpoint Congress actions require the admitted review scope')
        compare_congress_actions = congress_scope == 'review' and congress_actions is not False
    if city_building_version is not None and 'city_buildings' not in groups:
        raise ValueError('A checkpoint building version requires the city building panel')
    rows = []
    for pid in players:
        control = controls[pid]
        decisions = None
        congress_read = None
        if pid in decision_players:
            from .xp2_human_perspective import read_network_boundary
            from .xp2_lan_unit_commands import public_decisions

            options = {} if restored_envoy_views is None else {'restore_envoys': restored_envoy_views.get(pid)}
            if groups or city_panel_groups is not None:
                options['city_panel_groups'] = groups
            if unit_panel or unit_panel_families is not None:
                options['unit_panel_families'] = unit_panel
            if peace_scope or city_state_peace_enabled is not None:
                options['city_state_peace_enabled'] = peace_scope
            if score_scope or world_score_enabled is not None:
                options['world_score_enabled'] = score_scope
            if artifact_mode != 'off' or archaeology_mode is not None:
                options['archaeology_mode'] = artifact_mode
            if people_mode != 'off' or great_people_mode is not None:
                options['great_people_mode'] = people_mode
            if activation_scope or great_person_activation_enabled is not None:
                options['great_person_activation_enabled'] = activation_scope
            if pantheon_scope or pantheon_enabled is not None:
                options['pantheon_enabled'] = pantheon_scope
            if governor_scope or governors_enabled is not None:
                options['governors_enabled'] = governor_scope
            if espionage_scope or espionage_enabled is not None:
                options['espionage_enabled'] = espionage_scope
            if completion_scope or spy_completion_enabled is not None:
                options['spy_completion_enabled'] = completion_scope
            if religion_scope or religion_groups is not None:
                options['religion_groups'] = religion_scope
            if trade_scope or trade_enabled is not None:
                options['trade_enabled'] = trade_scope
            if formation_scope or formation_enabled is not None:
                options['formation_enabled'] = formation_scope
            if dedication_scope or dedication_enabled is not None:
                options['dedication_enabled'] = dedication_scope
            if congress_scope != 'off' or congress_mode is not None:
                options['congress_mode'] = congress_scope
            if compare_congress_actions:
                from .xp2_lan_congress import CheckpointRead

                congress_read = CheckpointRead((restored_congress_ballots or {}).get(pid))
                options['congress_checkpoint'] = congress_read
            native = read_network_boundary(owner, pid, None, **options)
            decisions = public_decisions(owner, native, identity, sequence, pid)
            if decisions is None or decisions['turn_controls'] != control:
                raise ValueError('Checkpoint public decisions crossed their native readiness')
            if tuple(key for key in network_turn.SECONDARY_CITY_PANEL_FIELDS if key in decisions) != groups:
                raise ValueError('Checkpoint public city panel scope differs from its live readers')
            if tuple(kind for kind in network_turn.SECONDARY_UNIT_PANEL_KINDS
                     if kind in decisions.get('families', {})) != unit_panel:
                raise ValueError('Checkpoint secondary UnitPanel scope differs from its live choices')
            if ('city_state_peace' in decisions) is not peace_scope:
                raise ValueError('Checkpoint city-state peace differs from its live choices')
            if ('world_score' in decisions) is not score_scope:
                raise ValueError('Checkpoint world score scope differs from its live choices')
            from civ6_host.contracts import archaeology

            if (('archaeology' in decisions) != (artifact_mode != 'off')
                    or (archaeology.EXCAVATE in decisions['families']) != (artifact_mode == 'commands')):
                raise ValueError('Checkpoint archaeology scope differs from its live choices')
            command_scope = decisions.get('great_people_actions')
            expected = None if people_mode == 'off' else people_mode == 'actions'
            if command_scope is not expected:
                raise ValueError('Checkpoint Great People scope differs from the live catalogue')
            if ('great_person_activation' in decisions) is not activation_scope:
                raise ValueError('Checkpoint Great Person activation scope differs from the live catalogue')
            if ('pantheon' in decisions) is not pantheon_scope:
                raise ValueError('Checkpoint pantheon scope differs from the live catalogue')
            if ('governors' in decisions) is not governor_scope:
                raise ValueError('Checkpoint governor scope differs from the live catalogue')
            if ('espionage' in decisions) is not espionage_scope:
                raise ValueError('Checkpoint espionage scope differs from the live catalogue')
            if ('spy_completion' in decisions) is not completion_scope:
                raise ValueError('Checkpoint spy completion scope differs from the live catalogue')
            if tuple(field for field in network_turn.SECONDARY_RELIGION_CONTRACTS if field in decisions) != religion_scope:
                raise ValueError('Checkpoint religion scope differs from the live catalogue')
            if ('trade_routes' in decisions) is not trade_scope:
                raise ValueError('Checkpoint trade scope differs from the live catalogue')
            if ('unit_formations' in decisions) is not formation_scope:
                raise ValueError('Checkpoint formation scope differs from the live catalogue')
            if ('dedications' in decisions) is not dedication_scope:
                raise ValueError('Checkpoint dedication scope differs from the live catalogue')
            actual_congress = ('review' if 'world_congress_review' in decisions
                               else 'catalogue' if 'world_congress' in decisions else 'off')
            if actual_congress != congress_scope:
                raise ValueError('Checkpoint Congress scope differs from the live catalogue')
            raw_view = native.view
        else:
            raw_view = owner.read_xp2_human_view(pid)
        view = _validated_view(raw_view, identity, sequence, pid, turn)
        if (view['player_turn']['active'] != control['active']
                or view['player_turn']['turn_active_complete'] != control['active_complete']
                or owner.continuation is not token or token.identity is not identity or token.sequence != sequence):
            raise ValueError('Checkpoint public view crossed its native readiness or revision')
        row = dict(player_id=pid, observation_sha256=digest(view['observation']),
                   player_map_sha256=digest(view['player_map']))
        if decisions is not None:
            from .native.native_session_resume import semantic_decisions

            comparable_decisions = decisions
            if compare_congress_actions:
                from .network_checkpoint import rebind_congress_candidates

                comparable_decisions = copy.deepcopy(decisions)
                rebind_congress_candidates(comparable_decisions)
            if 'city_buildings' in decisions:
                version = (decisions['city_buildings']['schema']
                           if city_building_version is None else city_building_version)
                if effective_building_version not in (None, version):
                    raise ValueError('Checkpoint city building versions differ across seats')
                effective_building_version = version
                comparable_decisions, _, _ = network_turn.project_city_building_version(comparable_decisions, version)
            comparable = semantic_decisions(comparable_decisions)
            for field in ('world_congress', 'world_congress_review', 'world_congress_active_effects'):
                if comparable.get(field) is not None:
                    comparable[field].pop('sequence')
            row['decisions_sha256'] = digest(comparable)
            if congress_read is not None and congress_read.ballot is not None:
                row['congress_ballot'] = congress_read.ballot
            envoys = decisions.get('envoys')
            schema = network_turn.xp2_great_person_base_schema(decisions['schema'])
            if (schema in (network_turn.CAPABILITY_SECONDARY_CITY_STATES_SCHEMA,
                           network_turn.CAPABILITY_SECONDARY_UNIT_WORK_SCHEMA,
                           network_turn.CAPABILITY_SECONDARY_ADJACENT_WORK_SCHEMA)
                    and envoys is not None and envoys['considered'] is False):
                row['envoys'] = copy.deepcopy(envoys)
        rows.append(row)
    receipt = dict(schema=CHECKPOINT_SCHEMA, players=rows)
    if decision_players:
        schema = (CHECKPOINT_DEVELOPMENT_SCHEMA if getattr(owner, '_xp2_lan_unit_development_enabled', False)
                  else CHECKPOINT_DECISIONS_SCHEMA)
        if getattr(owner, '_xp2_lan_unit_attacks_enabled', False):
            schema = CHECKPOINT_COMBAT_SCHEMA
        if getattr(owner, '_xp2_lan_occupation_enabled', False):
            schema = CHECKPOINT_OCCUPATION_SCHEMA
        if getattr(owner, '_xp2_lan_ranged_shots_enabled', False):
            schema = (CHECKPOINT_PURCHASE_SCHEMA if getattr(owner, '_xp2_lan_purchases_enabled', False)
                      else CHECKPOINT_RANGED_SHOTS_SCHEMA)
            if getattr(owner, '_xp2_lan_government_enabled', False):
                schema = CHECKPOINT_GOVERNMENT_SCHEMA
            if getattr(owner, '_xp2_lan_city_states_enabled', False):
                schema = CHECKPOINT_CITY_STATES_SCHEMA
            if getattr(owner, '_xp2_lan_unit_work_enabled', False):
                schema = CHECKPOINT_UNIT_WORK_SCHEMA
                if getattr(owner, '_xp2_lan_adjacent_work_enabled', False):
                    schema = CHECKPOINT_ADJACENT_WORK_SCHEMA
            receipt['occupation_enabled'] = getattr(owner, '_xp2_lan_occupation_enabled', False) is True
        receipt['schema'] = schema
        if groups:
            receipt['city_panel_groups'] = list(groups)
        if unit_panel:
            receipt['unit_panel_families'] = list(unit_panel)
        if peace_scope:
            receipt['city_state_peace_enabled'] = True
        if score_scope:
            receipt['world_score_enabled'] = True
        if artifact_mode != 'off':
            receipt['archaeology_mode'] = artifact_mode
        if effective_building_version in city_buildings.GREAT_WORK_SCHEMAS:
            receipt['city_building_version'] = effective_building_version
        if people_mode != 'off':
            receipt['great_people_mode'] = people_mode
        if activation_scope:
            receipt['great_person_activation_enabled'] = True
        if pantheon_scope:
            receipt['pantheon_enabled'] = True
        if governor_scope:
            receipt['governors_enabled'] = True
        if espionage_scope:
            receipt['espionage_enabled'] = True
        if completion_scope:
            receipt['spy_completion_enabled'] = True
        if religion_scope:
            receipt['religion_groups'] = list(religion_scope)
        if trade_scope:
            receipt['trade_enabled'] = True
        if formation_scope:
            receipt['formation_enabled'] = True
        if dedication_scope:
            receipt['dedication_enabled'] = True
        if congress_scope != 'off':
            receipt['congress_mode'] = congress_scope
        if compare_congress_actions:
            receipt['congress_actions'] = True
    return receipt


def publish_player_views(emit, owner, protocol, observation, closure, closure_path, *, lan_players=()):
    """Worker hook: preserve legacy reply/action semantics and original actor."""
    players = validate_players(closure.get('public_view_players'))
    if not players or protocol.ended or protocol.closed or observation is None:
        return
    from .native.native_player_observation import observe_player
    if lan_players:
        from .xp2_human_perspective import InactiveHumanView

        if (players != lan_players
                or not set(players).issubset(owner.network_reference['human_player_ids'])):
            raise ValueError('LAN public view selection includes an unauthenticated human seat')

        def read(pid):
            try:
                if closure.get('diplomacy_overview_diagnostic', False) is True:
                    return owner.read_xp2_human_view(pid, include_wars=True)
                return owner.read_xp2_human_view(pid)
            except InactiveHumanView:
                return None
    else:
        from .human_perspective import collect_player_view, source_pins
        from .native.native_official_hotseat import PLAYERS
        pins = source_pins()
        if closure.get('public_view_sources') != pins or any(closure['pins'].get(k) != v for k, v in pins.items()):
            raise ValueError('Public perspective source closure differs')

        def read(pid):
            return collect_player_view(owner, pid, player_ids=PLAYERS)

    current = observation['player_id']
    # Read the initial actor last so the existing reply can be compared at the
    # same retained boundary after all requested human perspective changes.
    ordered = [p for p in players if p != current] + ([current] if current in players else [])
    payloads = {}
    for pid in ordered:
        view = read(pid)
        if view is None:
            if pid == current:
                raise RuntimeError('The current LAN actor lost its live view during public collection')
            continue
        payloads[pid] = _validated_view(view, protocol.identity, protocol.sequence,
                                       pid, observation['turn'])
    retained = (payloads[current]['observation'] if current in payloads else
                observe_player(owner.prefix.runtime, owner.prefix.ui_child, current))
    if retained != observation:
        raise ValueError('Public perspective collection changed the retained actor observation')
    run = Path(closure_path).resolve(strict=True).parent
    rows = []
    for pid in players:
        path = _path(run, pid)
        if pid not in payloads:
            path.unlink(missing_ok=True)
            rows.append(dict(player_id=pid, file=None, bytes=0, sha256=None))
            continue
        path.parent.mkdir(exist_ok=True)
        raw = json.dumps(payloads[pid], sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')
        if len(raw) > MAX_VIEW_BYTES:
            raise ValueError('Public player view exceeds file bound')
        temporary = path.with_suffix('.pending')
        with temporary.open('xb') as stream:
            stream.write(raw)
        os.replace(temporary, path)
        rows.append(dict(player_id=pid, file=_relative(pid), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    emit(STAGE, nonce=protocol.nonce, episode_id=protocol.identity.episode_id,
        game_generation=protocol.identity.game_generation, sequence=protocol.sequence,
        turn=observation['turn'], files=rows)


class SessionViewsMixin:
    """Add views without creating a second native worker/session pipeline."""
    def __init__(self, *args, public_view_players=None, **kwargs):
        self.public_view_players = validate_players(public_view_players)
        self._view_manifest = None
        super().__init__(*args, **kwargs)

    def _configure_closure(self, closure):
        super()._configure_closure(closure)
        self._configure_public_views(closure)

    def _configure_public_views(self, closure):
        self._view_manifest = None
        if not getattr(self, 'public_view_players', ()):
            return
        if closure.get('input_profile') == 'xp2-lan':
            from .xp1_session_inputs import saved_load_pin
            pins = _lan_source_pins()
            for path, digest in pins.items():
                saved_load_pin(closure['pins'], path, digest)
        else:
            from .human_perspective import source_pins, verify_source
            verify_source()
            pins = source_pins()
            closure['pins'].update(pins)
        closure['public_view_players'] = list(self.public_view_players)
        closure['public_view_sources'] = pins

    def _read_stream(self, pipe, name, limit, events):
        if not events or not getattr(self, 'public_view_players', ()):
            return super()._read_stream(pipe, name, limit, events)
        session = self
        class ManifestPipe:
            def readline(self, maximum):
                line = pipe.readline(maximum)
                if len(line) <= maximum:
                    try:
                        value = json.loads(line)
                    except (ValueError, UnicodeError):
                        value = None
                    if type(value) is dict and value.get('stage') == STAGE:
                        session._accept_view_manifest(value)
                return line
        return super()._read_stream(ManifestPipe(), name, limit, events)

    def _accept_view_manifest(self, value):
        from .native.native_episode_identity import DiagnosticEpisodeIdentity
        fields = {'stage', 'nonce', 'episode_id', 'game_generation', 'sequence', 'turn', 'files'}
        if type(value) is not dict or set(value) != fields or value['stage'] != STAGE or value['nonce'] != self.nonce:
            raise ValueError('Public view manifest identity differs')
        DiagnosticEpisodeIdentity(value['episode_id'], value['game_generation'])
        if type(value['sequence']) is not int or not 0 <= value['sequence'] <= self.protocol_class.max_commands:
            raise ValueError('Public view manifest sequence differs')
        if type(value['turn']) is not int or value['turn'] < 0:
            raise ValueError('Public view manifest turn differs')
        if self._view_manifest is not None and value['sequence'] <= self._view_manifest['sequence']:
            raise ValueError('Duplicate or reversed public view manifest')
        files = value['files']
        if type(files) is not list or len(files) != len(self.public_view_players):
            raise ValueError('Public view manifest roster differs')
        for row, pid in zip(files, self.public_view_players):
            if type(row) is not dict or set(row) != {'player_id', 'file', 'bytes', 'sha256'}:
                raise ValueError('Public view file manifest fields differ')
            if type(row['player_id']) is not int or row['player_id'] != pid:
                raise ValueError('Public view file player or path differs')
            if (getattr(self, 'input_profile', None) == 'xp2-lan' and row['file'] is None
                    and type(row['bytes']) is int and row['bytes'] == 0 and row['sha256'] is None):
                continue
            if row['file'] != _relative(pid):
                raise ValueError('Public view file player or path differs')
            pin = row['sha256']
            if type(pin) is not str or len(pin) != 64 or any(c not in '0123456789abcdef' for c in pin):
                raise ValueError('Public view manifest hash differs')
            if type(row['bytes']) is not int or not 0 < row['bytes'] <= MAX_VIEW_BYTES:
                raise ValueError('Public view manifest size differs')
        self._view_manifest = copy.deepcopy(value)

    def read_player_view(self, response, player_id):
        self._owner()
        if type(player_id) is not int or player_id not in self.public_view_players:
            raise ValueError('Player not authorized by public_view_players')
        if self.finished or self.protocol is None or response != self.last or response['sequence'] != self.protocol.sequence:
            raise ValueError('Public view requires the latest live accepted response')
        if any(response['outcome'][k] for k in ('terminated', 'truncated')):
            raise ValueError('Public view requires a live episode')
        manifest = self._view_manifest
        if manifest is None or any(manifest[k] != response[k] for k in ('nonce','episode_id','game_generation','sequence')):
            raise ValueError('Public view manifest belongs to another boundary')
        turn = response['observation']['turn']
        if manifest['turn'] != turn:
            raise ValueError('Public view manifest turn differs from accepted response')
        row = next(r for r in manifest['files'] if r['player_id'] == player_id)
        if row['file'] is None:
            from civ6_host.client import InformationUnavailable
            raise InformationUnavailable('The captured human player has no living public view')
        with _path(self.run, player_id).open('rb') as stream:
            raw = stream.read(MAX_VIEW_BYTES + 1)
        if len(raw) != row['bytes'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Public view file size or hash differs')
        return validate_player_view(_read_json(raw), episode_id=response['episode_id'],
            game_generation=response['game_generation'], sequence=response['sequence'],
            player_id=player_id, turn=turn)
