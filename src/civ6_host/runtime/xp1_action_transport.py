"""Owned use of the shared command transport on a captured expansion owner."""
import ctypes as C
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from struct import unpack_from
from .configuration_profiles import XP1_CORE_SHA256,XP2_CORE_SHA256
from .native.native_action_transport import NativeActionTransport


_UNIT_ORDER_MESSAGES = {'command': 0x493830AF, 'operation': 0x8C0F3F36}


@dataclass
class _UnitOrder:
    player_id: int
    unit_id: int
    route: str
    opcode: int | None = None
    delivered: bool = False


@dataclass
class _ArchiveCheck:
    validators: tuple
    delivered: int = 0


class SavedActionTransport(NativeActionTransport):
    def __init__(self,services):
        b=services.backend;b.check_thread()
        core_sha256=b.load_abi.core_sha256
        if (b.stage!='prepared' or b.prefix is not None or services.host is not b.host
                or hasattr(services,'actions') or core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)):
            raise ValueError('XP1 command transport must be composed once before saved Load')
        if core_sha256==XP2_CORE_SHA256:
            from .saved_load_services import SavedLoadServices
            from .action_transport_profiles import transport_profile
            from .xp2_action_transport_source import verify_owners,verify_host_build
            if (type(services) is not SavedLoadServices or services.core is not b.core
                    or services.context!=b.context or services.core_sha256!=core_sha256
                    or b.configuration_abi.core_sha256!=core_sha256
                    or getattr(b.host,'_saved_load_services',None) is not services):
                raise ValueError('XP2 commands require their exact saved service owner')
            # Complete source and owner checks precede installing either callback.
            transport_profile(core_sha256,b.core,b.context,b.runtime.read)
            verify_owners(b.core._handle,b.context,b.runtime.read,
                host_pointer=b.host.pointer,auxiliary_pointer=C.addressof(b.host.aux_object))
            verify_host_build()
        self.services,self.backend=services,b;self.closed=False
        key=(C.addressof(b.host.vtable),0x70)
        self.previous=(b.host.vtable[0x70//8],b.host._slot_bindings.get(key))
        if self.previous[1] is None or getattr(self.previous[1][1],'_native_unavailable',None)!=('host',0x70):
            raise ValueError('XP1 action transport requires the original strict host callback')
        from .xp1_log_event_profile import verify_live
        from .native.native_events import NativeEventRecorder
        if getattr(b.host,'event_recorder',None) is not None or NativeEventRecorder._installed is not None:
            raise ValueError('XP1 command owner cannot replace an existing event recorder')
        self.event_source=verify_live(b.core._handle,b.runtime.read,core_sha256=core_sha256)
        self.recorder=NativeEventRecorder(Path(b.fixture).resolve().parent/'native-events',b.host)
        self.recorder.install();b.host.event_recorder=self.recorder
        try:
            if core_sha256==XP2_CORE_SHA256:
                from .xp2_action_transport_source import verify_log_binding
                self.log_binding=verify_log_binding(b.core,b.runtime.read,self.recorder)
            super().__init__(b.host,b.core,b.context,services.emit,core_sha256=core_sha256)
        except BaseException:
            # Preserve live callback owners for controlled worker quarantine;
            # never invent native cleanup after a partially installed binding.
            b.poisoned=True
            raise
        self.address=b.host.vtable[0x70//8];services.actions=self

    def check(self):
        b=self.backend;b.check_thread()
        if (self.closed or getattr(self.services,'actions',None) is not self
                or b.prefix is not self.services or b.host is not self.host or b.core is not self.core
                or b.context!=self.context or b.destroyed or b.poisoned
                or b.load_abi.core_sha256!=self.transport_abi.core_sha256
                or self.host.vtable[0x70//8]!=self.address):
            raise ValueError('XP1 action transport lost its live saved owner')
        if self.transport_abi.core_sha256==XP2_CORE_SHA256:
            from .native.native_events import NativeEventRecorder
            if (self.services.core_sha256!=XP2_CORE_SHA256
                    or getattr(self.host,'_saved_load_services',None) is not self.services
                    or self.host.event_recorder is not self.recorder
                    or NativeEventRecorder._installed is not self.recorder):
                raise ValueError('XP2 action transport lost its selected service/recorder owner')

    def capture(self,receiver,archive):
        self.check()
        return super().capture(receiver,archive)

    def require_transition(self):
        self.check()
        from .xp1_continuation import SavedContinuation
        token=getattr(self.backend,'_xp1_continuation',None)
        if type(token) is not SavedContinuation or token.transport is not self:
            raise ValueError('Native command execution needs its exact continuation owner')
        token.check(active=True)

    def deliver_one(self,context_value=0xFFFFFFFF):
        self.require_transition()
        order = getattr(self, '_expected_unit_order', None)
        checked = getattr(self, '_expected_archives', None)
        if checked is not None:
            remaining = checked.validators[checked.delivered:]
            if not remaining or len(self.pending) != len(remaining):
                raise RuntimeError('Unexpected guarded XP2 archive count')
            # Validate the whole pending gesture before applying its first command.
            for validate, payload in zip(remaining, self.pending):
                validate(payload)
        if order is not None:
            if order.delivered or len(self.pending) != 1:
                raise RuntimeError('Expected one borrowed XP2 unit-order archive')
            archive = self.pending[0]
            # Both XP2 serializers write the cached Unit owner WORD, kind
            # WORD (1) and native ID DWORD. The two message IDs are distinct.
            if (type(archive) is not bytes or len(archive) < 20
                    or unpack_from('<IHHI', archive) != (
                        _UNIT_ORDER_MESSAGES[order.route], order.player_id, 1, order.unit_id)):
                raise ValueError('XP2 unit-order archive differs from its route, acting seat or unit')
            if order.route == 'operation' and (
                    len(archive) != 28 or unpack_from('<III', archive, 16) != (0xffffffff, 0, 0)):
                raise ValueError('XP2 parameterless unit operation contains target or parameter data')
            if order.opcode is not None and unpack_from('<I', archive, 12)[0] != order.opcode:
                raise ValueError('XP2 unit operation opcode differs from its selected action')
        result = super().deliver_one(context_value)
        if order is not None:
            order.delivered = True
        if checked is not None:
            checked.delivered += 1
        return result

    def require_xp2_single_archive(self, validate, *, allow_no_archive=False):
        """Check the one archive produced by an admitted borrowed action."""
        return self.require_xp2_archives((validate,), allow_no_archive=allow_no_archive)

    @contextmanager
    def require_xp2_archives(self, validators, *, allow_no_archive=False):
        """Guard the complete ordered archive sequence of one borrowed gesture."""
        self.require_transition()
        self.require_empty_native_queue()
        if (self.transport_abi.core_sha256 != XP2_CORE_SHA256
                or type(validators) is not tuple or not 1 <= len(validators) <= 2
                or type(allow_no_archive) is not bool or allow_no_archive and len(validators) != 1
                or not all(callable(validate) for validate in validators)
                or getattr(self, '_expected_unit_order', None) is not None
                or getattr(self, '_expected_archives', None) is not None):
            raise ValueError('Invalid guarded XP2 archive scope')
        checked = _ArchiveCheck(validators)
        self._expected_archives = checked
        try:
            yield
            if checked.delivered != len(validators) and not (
                    allow_no_archive and checked.delivered == 0 and not self.pending):
                raise RuntimeError('Guarded XP2 archive sequence was not delivered')
        finally:
            del self._expected_archives

    @contextmanager
    def require_xp2_unit_order(self, player_id, unit_id, route, *, opcode=None):
        """Limit this native submission to one exact action route and owner/unit."""
        self.require_transition()
        self.require_empty_native_queue()
        if (self.transport_abi.core_sha256 != XP2_CORE_SHA256
                or type(player_id) is not int or not 0 <= player_id < 64
                or type(unit_id) is not int or not 0 <= unit_id <= 0xffffffff
                or type(route) is not str or route not in _UNIT_ORDER_MESSAGES
                or (opcode is not None and (route != 'operation' or type(opcode) is not int
                                            or not 0 <= opcode <= 0xffffffff))
                or getattr(self, '_expected_archives', None) is not None
                or getattr(self, '_expected_unit_order', None) is not None):
            raise ValueError('Invalid borrowed XP2 unit-order scope')
        order = _UnitOrder(player_id, unit_id, route, opcode)
        self._expected_unit_order = order
        try:
            yield
            if not order.delivered:
                raise RuntimeError('Borrowed XP2 unit order was not delivered')
        finally:
            del self._expected_unit_order

    def update_game_once(self):
        self.require_transition()
        return super().update_game_once()

    def require_empty_native_queue(self):
        self.check()
        sentinel=self.core._handle+self.transport_abi.receive_queue_rva
        if self.pending or self.read(sentinel,16)!=sentinel.to_bytes(8,'little')*2:
            raise ValueError('XP1 command transport still has pending host/native work')

    def close(self):
        b=self.backend
        # NativeLoadBackend.check_thread deliberately rejects destroyed owners;
        # this callback is released only AFTER the actual native Destroy.
        if b.runtime.thread()!=b.thread or b.poisoned:
            raise ValueError('XP1 action callback shutdown has a foreign/poisoned owner')
        if self.closed:return
        from .xp1_loaded_lifetime import require_lifetime
        token=require_lifetime(getattr(b,'_loaded_lifetime',None),b)
        if (not b.destroyed or token.phase!='services' or not token.destroy_returned
                or self.pending or self.host.vtable[0x70//8]!=self.address
                or getattr(self.services,'actions',None) is not self):
            raise ValueError('XP1 action callback cannot close before actual native Destroy')
        self.host.vtable[0x70//8]=self.previous[0]
        self.host._slot_bindings[(C.addressof(self.host.vtable),0x70)]=self.previous[1]
        self.closed=True

def configure_requested(backend,closure):
    requested=closure.get('unit_commands_candidate',False)
    if type(requested) is not bool:
        raise ValueError('XP1 command scope must be explicit')
    if requested and not(closure.get('observe_player_candidate') is True
                         and closure.get('close_loaded_candidate') is True):
        raise ValueError('XP1 commands require actual player observation and loaded close')
    backend._xp1_commands_requested=requested

