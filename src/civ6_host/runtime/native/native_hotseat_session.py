"""Interactive explicit choices for the retained official four-human save."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import copy
from civ6_host.runtime.native.native_action_session import ActionProtocol
from civ6_host.runtime.native.native_action_session import NativeActionSession
from civ6_host.runtime.native.native_action_session import validate_action_response
from civ6_host.runtime.native.native_diagnostic_roster import validate_player
from civ6_host.runtime.native.native_official_hotseat import PLAYERS
SCHEMA = 'civ6rl.hotseat_action_session923.v1'

class HotseatActionProtocol(ActionProtocol):
    schema = SCHEMA
    initial_turn = 3

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.player_id = 0
        self._validated_boundary = None
        self._response_advance = False
        self._turn_reactivation_sequence = 0

    def selected(self, request):
        validate_player(self.player_id, PLAYERS)
        if self.decisions is None or type(self.decisions.get('player_id')) is not int or self.decisions['player_id'] != self.player_id or (self.decisions.get('turn') != self.initial_turn + self.rounds) or (self.decisions.get('sequence') != self.sequence):
            raise ValueError('Catalogue is not bound to the current native hotseat actor')
        return super().selected(request)

    def mapped(self, request):
        base = super().mapped(request)
        if base['operation'] == 'diagnostic_development_turn' and (not self._response_advance):
            base['operation'] = 'observe'
        return base

    def native_boundary(self, request, native, turn_reactivation=None):
        if request is not None:
            self.validate(request)
        if type(native) is not dict or native.get('episode_id') != self.identity.episode_id or native.get('game_generation') != self.identity.game_generation or (type(native.get('episode_terminated')) is not bool):
            raise ValueError('Missing or foreign native handoff receipt')
        actor = native.get('player_id')
        turn = native.get('current_game_turn')
        validate_player(actor, PLAYERS)
        if type(turn) is not int:
            raise ValueError('Native turn must be an exact integer')
        current = self.initial_turn + self.rounds
        endturn = request is not None and request.get('operation') == 'act' and (self.selected(request)['kind'] in ('end_turn', 'force_end_turn'))
        same_turn_reactivation = not native['episode_terminated'] and endturn and ((actor, turn) == (self.player_id, current))
        reactivation_sequence = None
        if same_turn_reactivation:
            fields = {'schema', 'turn', 'player_id', 'callback_sequence', 'reason', 'source_sha256'}
            if type(turn_reactivation) is not dict or set(turn_reactivation) != fields or turn_reactivation.get('schema') != 'civ6rl.native_turn_reactivation.v1' or (turn_reactivation.get('player_id') != self.player_id) or (turn_reactivation.get('turn') != current) or (type(turn_reactivation.get('callback_sequence')) is not int) or (turn_reactivation['callback_sequence'] <= self._turn_reactivation_sequence):
                raise ValueError('Same-turn Hotseat actor requires a fresh callback for the requesting player')
            reactivation_sequence = turn_reactivation['callback_sequence']
        elif turn_reactivation is not None:
            raise ValueError('Turn reactivation receipt does not match the native same-turn boundary')
        if not endturn:
            if (actor, turn) != (self.player_id, current):
                raise ValueError('Non-turn action changed the native actor or turn')
        elif turn not in (current, current + 1):
            raise ValueError('Native handoff skipped or reversed a global turn')
        elif (actor, turn) == (self.player_id, current) and (not native['episode_terminated']) and (not same_turn_reactivation):
            raise ValueError('EndTurn returned the unchanged native actor and turn')
        rounds = turn - self.initial_turn
        if not 0 <= rounds <= self.limit:
            raise ValueError('Native turn exceeded the configured budget')
        return dict(player_id=actor, rounds=rounds, terminated=native['episode_terminated'], reactivation_sequence=reactivation_sequence)

    def commit(self, request, *, native_terminated=False, native=None, turn_reactivation=None):
        self.validate(request)
        if native is None:
            if self._validated_boundary is None or self._validated_boundary[0] != request:
                raise ValueError('Cannot commit without a validated native boundary')
            boundary = self._validated_boundary[1]
        else:
            boundary = self.native_boundary(request, native, turn_reactivation)
        if type(native_terminated) is not bool or native_terminated != boundary['terminated']:
            raise ValueError('Native terminal flag differs from accepted boundary')
        selected = self.selected(request) if request['operation'] == 'act' else None
        self.sequence = request['sequence']
        self.player_id = boundary['player_id']
        self.rounds = boundary['rounds']
        if boundary.get('reactivation_sequence') is not None:
            self._turn_reactivation_sequence = boundary['reactivation_sequence']
        if selected is not None and selected['kind'] == 'found_city':
            self.city = True
        self.closed = request['operation'] == 'close'
        self.ended = native_terminated or self.rounds == self.limit or self.closed
        self._validated_boundary = None

def validate_hotseat_response(response, protocol, operation, *, request=None):
    if type(protocol) is not HotseatActionProtocol:
        raise ValueError('Exact hotseat protocol required')
    protocol._validated_boundary = None
    if type(response) is not dict or type(response.get('outcome')) is not dict:
        raise ValueError('Missing native handoff outcome')
    boundary = protocol.native_boundary(request, response['outcome'].get('native_victory'), response.get('turn_reactivation'))
    proxy = copy.copy(protocol)
    proxy._response_advance = boundary['rounds'] > protocol.rounds
    result = validate_action_response(response, proxy, operation, request=request, expected_player=boundary['player_id'], initial_turn=protocol.initial_turn)
    if request is not None:
        protocol._validated_boundary = (copy.deepcopy(request), boundary)
    return result
from civ6_host.runtime.player_views import SessionViewsMixin

class NativeHotseatActionSession(SessionViewsMixin, NativeActionSession):
    input_profile = 'hotseat-four'
    worker_name = 'official_hotseat_worker923.py'
    closure_schema = 'civ6rl.hotseat_action_session923.closure.v1'
    protocol_class = HotseatActionProtocol
    response_validator = staticmethod(validate_hotseat_response)
    command_schema = SCHEMA

    def __init__(self, run_root=None, *, public_objective_players=None, **kwargs):
        from civ6_host.runtime.native.native_saved_session import ROOT
        from civ6_host.runtime.native.native_public_objective_witness import validate_players
        self.public_objective_players = validate_players(public_objective_players)
        self.public_continuity_sources = None
        self._public_witness_files = {}
        self._public_closure = None
        super().__init__(run_root or ROOT / 'work/interactive-hotseat923/runs', **kwargs)

    def _configure_closure(self, closure):
        from civ6_host.runtime.native.native_public_objective_witness import source_pins
        from civ6_host.runtime.native.native_public_objective_witness import sources_from_closure
        from civ6_host.runtime.native.native_saved_session import ROOT
        from civ6_host.runtime.native.native_host_turn_reactivation import verify_source
        from civ6_host.runtime.native.native_host_turn_reactivation import PROOF_PATH
        from civ6_host.runtime.native.native_host_turn_reactivation import PROOF_SHA256
        super()._configure_closure(closure)
        verify_source()
        closure['pins'][str(PROOF_PATH.relative_to(ROOT))] = PROOF_SHA256
        self._public_witness_files = {}
        self.public_continuity_sources = None
        self._public_closure = None
        if self.public_objective_players:
            closure['public_objective_players'] = list(self.public_objective_players)
            closure['pins'].update(source_pins())
            self.public_continuity_sources = sources_from_closure(closure)
            self._public_closure = copy.deepcopy(closure)

    def _read_stream(self, pipe, name, limit, events):
        if not events or not self.public_objective_players:
            return super()._read_stream(pipe, name, limit, events)
        session = self

        class PublicManifestPipe:

            def readline(self, maximum):
                import json
                line = pipe.readline(maximum)
                if len(line) <= maximum:
                    try:
                        value = json.loads(line)
                    except (ValueError, UnicodeError):
                        value = None
                    if type(value) is dict and value.get('stage') == 'public_objective_witnesses':
                        session._accept_public_manifest(value)
                return line
        return super()._read_stream(PublicManifestPipe(), name, limit, events)

    def _accept_public_manifest(self, value):
        from civ6_host.runtime.native.native_public_objective_witness import _integer
        from civ6_host.runtime.native.native_public_objective_witness import boundary_path
        from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
        expected = {'stage', 'nonce', 'episode_id', 'game_generation', 'sequence', 'file', 'sha256'}
        if type(value) is not dict or set(value) != expected or value['nonce'] != self.nonce:
            raise ValueError('Public witness manifest schema or nonce differs')
        DiagnosticEpisodeIdentity(value['episode_id'], value['game_generation'])
        sequence = _integer(value['sequence'], 0, self.protocol_class.max_commands, 'public manifest sequence')
        if value['file'] != str(boundary_path(self.run, sequence).relative_to(self.run)).replace('\\', '/'):
            raise ValueError('Public witness manifest path differs')
        digest = value['sha256']
        if type(digest) is not str or len(digest) != 64 or any((c not in '0123456789abcdef' for c in digest)):
            raise ValueError('Public witness manifest digest differs')
        if sequence in self._public_witness_files:
            raise ValueError('Duplicate public witness manifest')
        self._public_witness_files[sequence] = copy.deepcopy(value)

    def read_public_witnesses(self, response):
        """Read only the separate, pinned public reward channel for this boundary.

        It must never be merged into a model request, memory, replay or action
        mask. The returned PID keys include exactly the explicitly tracked list.
        """
        from civ6_host.runtime.native.native_saved_session import ROOT
        from civ6_host.runtime.native.native_public_objective_witness import _loads
        from civ6_host.runtime.native.native_public_objective_witness import boundary_path
        from civ6_host.runtime.native.native_public_objective_witness import MAX_BOUNDARY_BYTES
        from civ6_host.runtime.native.native_public_objective_witness import validate_boundary
        from civ6_host.runtime.native.native_public_objective_witness import source_pins
        import hashlib
        self._owner()
        if not self.public_objective_players:
            raise ValueError('Public objective tracking is disabled')
        if self.protocol is None or response != self.last or response['sequence'] != self.protocol.sequence:
            raise ValueError('Public witnesses require the latest accepted response')
        manifest = self._public_witness_files.get(response['sequence'])
        if manifest is None:
            raise ValueError('Public witness manifest missing')
        if any((manifest[key] != response[key] for key in ('nonce', 'episode_id', 'game_generation', 'sequence'))):
            raise ValueError('Public witness manifest belongs to another boundary')
        closure_path = self.run / 'closure.json'
        if _loads(_resolve_resource_path(closure_path).read_bytes()) != self._public_closure:
            raise ValueError('Public witness closure changed')
        if any((self._public_closure['pins'].get(name) != pin for name, pin in source_pins().items())):
            raise ValueError('Public witness source pin changed')
        path = boundary_path(self.run, response['sequence'])
        if path.is_symlink() or path.parent.is_symlink() or _resolve_resource_path(path).resolve().parent != _resolve_resource_path(path.parent).resolve():
            raise ValueError('Public witness file is redirected')
        with _resolve_resource_path(path).open('rb') as stream:
            raw = stream.read(MAX_BOUNDARY_BYTES + 1)
        if not raw or len(raw) > MAX_BOUNDARY_BYTES or hashlib.sha256(raw).hexdigest() != manifest['sha256']:
            raise ValueError('Public witness file size or hash differs')
        return validate_boundary(_loads(raw), response=response, players=self.public_objective_players, sources=self.public_continuity_sources, nonce=self.nonce)

    def _accepted_response(self, response):
        self.protocol.decisions = copy.deepcopy(response['decisions'])
        self.protocol.player_id = response['outcome']['native_victory']['player_id']
