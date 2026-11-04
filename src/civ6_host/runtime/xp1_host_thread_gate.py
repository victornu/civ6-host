"""Select the retained synchronous host thread/controller service for XP1.

No thread result is constant: the shared callback compares real Win32 thread
IDs. The other slot observes our explicit idle host controller profile. It is
not a replay of an EXE activity counter, nor admission of external GUI scopes.
"""
from dataclasses import dataclass
import ctypes as C
import hashlib

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source, _body

SOURCE = ('work/host-extensions/xp1-thread-gate-static/thread-gate-source-v1.json',
          '3413c89ca59bf16eb6d118ee08c815b7d6be4cf04201228cfaf30f0d1b3f3a62')


def verify_source(*, core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_source import source
        return source()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown host thread gate source engine')
    from .native.native_host_thread_gate import PROFILE, PROOF_SHA
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6_host.xp1_host_thread_gate.static.v1'
            or proof['image']['sha256'] != XP1_CORE_SHA256
            or proof['native_execution'] is not False
            or proof['shared_exe_source']['sha256'] != PROOF_SHA
            or proof['explicit_host_profile'] != PROFILE
            or proof['host_global_rva'] != 0x9f2640
            or set(proof['slots']) != {'0x60', '0x58'}
            or any(row['signature'] != 'bool __fastcall(void *host)'
                   for row in proof['slots'].values())
            or proof['flow']['base_pair_normalized_equal'] is not True
            or proof['flow']['slot58_only_after_owner_thread'] is not True
            or proof['flow']['active_controller_returns_false_before_core_work'] is not True):
        raise ValueError('XP1 thread/controller gate source changed')
    rows = {int(row['va'],16)-0x180000000: row
            for fragment in _body(proof['functions']['0x50b10'])['fragments']
            for row in fragment['instructions']}
    if (rows[0x50b40]['bytes'] != 'ff5060'
            or rows[0x50b4d]['bytes'] != 'ff5058'
            or tuple(rows[0x50b33]['rip_targets']) != ('0x1809f2640',)
            or rows[0x50b43]['bytes'] != '84c0' or rows[0x50b50]['bytes'] != '84c0'):
        raise ValueError('XP1 two-slot Boolean ABI changed')
    return proof


def source_dependencies(*, core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_source import source_dependencies as selected
        return selected()
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown host thread gate source engine')
    from .paths import resource_root
    from .provenance import installed_host_source_reference
    from .resource_resolution import resolve_path
    proof = verify_source()
    shared_adapter = installed_host_source_reference(proof['shared_adapter']['path'])
    if shared_adapter is None or shared_adapter.name != 'native_host_thread_gate.py':
        raise ValueError('XP1 thread gate shared adapter reference changed')
    result = {}
    for ref, installed in ((dict(path=SOURCE[0],sha256=SOURCE[1]), None),
                           (proof['shared_exe_source'], None),
                           (proof['shared_adapter'], shared_adapter),
                           (proof['refused_native_witness'], None)):
        path = (installed or resolve_path(resource_root()/ref['path'])).resolve()
        raw = path.read_bytes()
        if (hashlib.sha256(raw).hexdigest() != ref['sha256']
                or 'bytes' in ref and len(raw) != ref['bytes']):
            raise ValueError('XP1 thread gate source dependency changed: '+str(path))
        result[str(path)] = ref['sha256']
    return result


def verify_live(base, reader, host_pointer, *, core_sha256=XP1_CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_source import verify_live as selected
        return selected(base,reader,family='thread',host_pointer=host_pointer)
    if core_sha256!=XP1_CORE_SHA256:raise ValueError('Unknown host thread gate source engine')
    from .xp1_status_profiles import _instruction_spans
    if (type(base) is not int or base <= 0 or not callable(reader)
            or type(host_pointer) is not int or host_pointer <= 0):
        raise ValueError('XP1 thread gate requires its live module and host')
    proof = verify_source()
    flat = {'functions': {name: {'instructions': [row for fragment in _body(body)['fragments']
        for row in fragment['instructions']]} for name,body in proof['functions'].items()}}
    spans = _instruction_spans(flat)
    for rva, raw in spans:
        if reader(base+rva, len(raw)) != raw:
            raise ValueError('XP1 thread gate instruction mismatch at '+hex(rva))
    if reader(base+proof['host_global_rva'],8) != host_pointer.to_bytes(8,'little'):
        raise ValueError('XP1 thread gate points to another native host')
    return len(spans)


@dataclass(frozen=True)
class InstalledThreadGate:
    owner: object
    host: object
    gate: object
    core: object
    slots: tuple
    source_sha256: str
    instruction_read_spans: int


def install(backend):
    """Install before cache/lifetime owners freeze the host callback identity.

The callback roots belong to DiagnosticHost for its entire native lifetime;
there is no separate allocation, thread or native controller to destroy here.
"""
    from .native.native_host_thread_gate import install_synchronous_host_thread_gate, PROFILE
    backend.check_thread()
    host = backend.host
    core_sha256 = backend.load_abi.core_sha256
    if (getattr(backend,'_saved_load_candidate',False) is not True
            or core_sha256 not in (XP1_CORE_SHA256,XP2_CORE_SHA256)
            or backend.stage != 'prepared' or backend.prefix is not None
            or backend.destroyed or backend.poisoned or backend.busy is not True
            or hasattr(host,'thread_gate') or hasattr(backend,'_xp1_thread_gate')):
        raise ValueError('XP1 thread gate requires the fresh prepared saved owner')
    reference=SOURCE
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_turn_source import SOURCE as reference, require_prepared_owner
        require_prepared_owner(backend)
    source_dependencies(core_sha256=core_sha256)
    spans = verify_live(backend.core._handle, backend.runtime.read, host.pointer,core_sha256=core_sha256)
    for slot in (0x58, 0x60):
        binding = host._slot_bindings.get((C.addressof(host.vtable),slot))
        if (binding is None or binding[0] != host.vtable[slot//8]
                or getattr(binding[1], '_native_unavailable', None) != ('host',slot)):
            raise ValueError('XP1 thread gate would replace another admitted service')
    # Shared semantics and ABI, including actual GetCurrentThreadId and host
    # identity checks, remain implemented in the already-retained service.
    install_synchronous_host_thread_gate(host, profile=PROFILE)
    slots = tuple((slot,host.vtable[slot//8],
                   host._slot_bindings[C.addressof(host.vtable),slot][1])
                  for slot in (0x58,0x60))
    result = InstalledThreadGate(backend,host,host.thread_gate,backend.core,slots,reference[1],spans)
    backend._xp1_thread_gate = result
    backend.emit('xp1_host_thread_gate_installed', source_sha256=reference[1],
        core_sha256=core_sha256, slots=['0x58','0x60'],
        owner_thread_id=host.thread_gate.owner_thread_id,
        actual_win32_thread_comparison=True, external_controller_activity_producers_admitted=False,
        original_exe_application_lifecycle_verified=False)
    return result
