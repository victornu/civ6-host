"""Saved-owner checks around the shared native turn request/update algorithm.

No replacement scheduler or artificial diplomacy response is installed. The
existing strict event services still reject unqualified callbacks immediately.
"""
from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256


class SavedTurnBoundary:
    def __init__(self, core_sha256=XP1_CORE_SHA256):
        if core_sha256 not in (XP1_CORE_SHA256, XP2_CORE_SHA256):
            raise ValueError('Unknown saved turn engine')
        self.core_sha256 = core_sha256

    def _check(self, saved):
        saved._check_active()
        if saved.backend.load_abi.core_sha256 != self.core_sha256:
            raise ValueError('Saved turn boundary belongs to another engine')

    def state(self,saved):
        self._check(saved)
        from .xp1_session_view import _reference,_read_state
        pid=saved.network_reference['state']['player_id']
        ref,ids=_reference(saved,pid)
        session,activity=_read_state(saved,pid,ref,ids)
        saved.network_turn_rows={row['player_id']:row for row in activity['rows']}
        return session

    def controls(self,saved,session,player_id):
        self._check(saved)
        from .network_timer import read
        row=saved.network_turn_rows[player_id]
        return dict(schema='civ6-host.turn-controls.v1',player_id=player_id,
            turn=session['turn'],active=row['active'],active_complete=row['active_complete'],
            can_unready=row['can_unready'],timer_elapsed=read(saved.backend,core_sha256=self.core_sha256))

    def refusal(self,saved,action,before,player_id):
        self._check(saved)
        from .xp1_turn_ui_profile import read
        gates=read(saved,player_id,before['turn'],active=True)
        saved.emit('xp1_turn_request_ui_revalidated',action=action,**gates)
        value=gates['turn_availability'][action['kind']]
        if value is not True:
            return 'native_turn_ui_gate_unknown' if value is None else 'native_turn_ui_gate_unavailable'
        return None

    def retain(self,saved):
        saved._check_active()
        # No pending dialogue is consumed or answered here. An unexpected
        # ledger is explicitly refused; uninstalled callback families are also
        # rejected by their actual owners before returning from native code.
        if getattr(saved.prefix.deferred_events,'pending_diplomacy_statements',None):
            raise ValueError('XP1 pending dialogue requires its own qualified choice adapter')
        saved.backend.control(empty=True)
        return False

    def control(self,saved):
        saved._check_active()
        return saved.backend.control(empty=True)

    def verify_update(self,saved):
        self._check(saved)
        from .xp1_turn_profile import prepare_transport
        profile=prepare_transport(saved.continuation.transport)
        if profile.core_sha256!=self.core_sha256:
            raise ValueError('XP1 update transport profile changed')

    def turn_segment(self,saved,player_id,turn):
        # Historical Base/XP1/v36 paths perform no additional read.
        if (self.core_sha256 != XP2_CORE_SHA256
                or getattr(saved, 'world_congress_diagnostic', False) is not True):
            return None
        self._check(saved)
        from .xp2_turn_segment import read
        return read(saved, player_id, turn)

    def unchanged_request(self,saved,action,before,after):
        saved._check_active()
        from .network_turns import same_readiness
        # Shift+Enter can submit while this player is already waiting. Delivery
        # through the real Core queue is evidence of submission only. Equality
        # of these public controls proves neither a global no-op nor acceptance.
        if (action!={'kind':'force_end_turn'} or not same_readiness(before, after)
                or before['active'] is not False):
            raise RuntimeError('Native turn request was delivered but its effect is unresolved')
        return dict(status='submitted',reason='native_turn_controls_unchanged',
                    requested_action=action)


BOUNDARY=SavedTurnBoundary()
XP2_BOUNDARY=SavedTurnBoundary(XP2_CORE_SHA256)


def select(core_sha256):
    if core_sha256 == XP1_CORE_SHA256:return BOUNDARY
    if core_sha256 == XP2_CORE_SHA256:return XP2_BOUNDARY
    raise ValueError('Unknown saved turn boundary engine')
