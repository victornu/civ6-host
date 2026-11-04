"""One diagnostic identity shared by native outcome and remote decisions.

This is collector bookkeeping, not a native game ID, reset implementation,
reward policy or declaration of training readiness.
"""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from dataclasses import dataclass
from uuid import UUID
from uuid import uuid4

@dataclass(frozen=True)
class DiagnosticEpisodeIdentity:
    episode_id: str
    game_generation: str

    def __post_init__(self):
        if type(self.episode_id) is not str or str(UUID(self.episode_id)) != self.episode_id or self.game_generation != 'native-' + self.episode_id:
            raise ValueError('Expected a canonical diagnostic episode and its generation')

def initialize_episode(host):
    """Call once on a new native diagnostic owner, before setup/actions."""
    if hasattr(host, '_diagnostic_episode_identity'):
        raise RuntimeError('Diagnostic owner already has an episode; create a fresh owner')
    episode = str(uuid4())
    identity = DiagnosticEpisodeIdentity(episode, 'native-' + episode)
    host._diagnostic_episode_identity = identity
    return identity

def require_episode(host):
    identity = getattr(host, '_diagnostic_episode_identity', None)
    if type(identity) is not DiagnosticEpisodeIdentity:
        raise RuntimeError('Native diagnostic episode must be initialized before use')
    return identity
