"""EXE 13EBD0 metadata flags and secondary DWORD state, without host mutation."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
PROOF_SHA256 = '3c94b6ebd43d394b5bfa86b8df491814d9ea7b76700c61e7d2284cd78ce08611'
_PROOF = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_notification_metadata.py')))).resolve().parents[1] / 'evidence/native-notification-metadata-scope' / (PROOF_SHA256 + '.json')

def verify_source_evidence() -> None:
    from civ6_host.runtime.native.native_source_cache import load_pinned_json
    proof = load_pinned_json(_PROOF, PROOF_SHA256)
    if proof['schema'] != 'civ6rl.native_notification_metadata_scope.static.v1' or proof['kind'] != 2188544486 or proof['images']['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63' or (proof['captures']['metadata_builder']['reachable_bytes_sha256'] != 'b67ae6e02bb1eef84525103f3b32485ac22e85de478ca6dd4d7949bb975f906e') or (tuple(proof['contract']['supported_event_kinds']) != (2188544486,)) or (proof['contract']['state_domain'] != 'uint32-exact-int') or (proof['contract']['record_flag_offset'] != 72) or (proof['empty_receiver_source']['record_type'] != 181) or (proof['empty_receiver_source']['size'] != 128):
        raise RuntimeError('Notification metadata source contract changed')

def metadata_scope_transition(notification_counter: int, metadata_counter: int) -> tuple[int, int]:
    """Return (metadata+38 DWORD, next M) for source DWORDs N and M.

    N is EXE1422D7C6C; M is EXE1422D7C68. TEST N precedes the unsigned
    CMP M,N / JAE. Only N>0 and M<N increments M. Scope exit in host+F0
    separately updates both counters; no reset is invented at enqueue/drain.
    """
    verify_source_evidence()
    for name, value in (('notification_counter', notification_counter), ('metadata_counter', metadata_counter)):
        if type(value) is not int or not 0 <= value <= 4294967295:
            raise ValueError(f'Notification metadata {name} must be uint32')
    if notification_counter == 0:
        return (0, metadata_counter)
    if metadata_counter < notification_counter:
        return (32, metadata_counter + 1)
    return (64, metadata_counter)
