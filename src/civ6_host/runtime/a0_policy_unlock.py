"""Source-qualified CivicsUnlocked producer in the existing owned A0/FIFO."""
import struct
from types import MappingProxyType

from .configuration_profiles import XP2_CORE_SHA256, _source

SOURCE = ('work/host-extensions/xp2-policy-controls/unlock-event-source.json',
          '81423df6f545f4f9f94b8d6926a5de46a6ff1f1c893c19d627f67a5aaefbac34')
KIND, RECORD_TYPE, RECORD_SIZE = 0x0a981150, 208, 96
EXE_SHA256 = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'


def source():
    proof = _source(SOURCE)
    event, receiver = proof['event'], proof['receiver']
    if (proof['schema'] != 'civ6-host.xp2-policy-unlock-event.static.v1'
            or proof['exe']['sha256'] != EXE_SHA256
            or proof['core']['sha256'] != XP2_CORE_SHA256
            or proof['all_instruction_bytes_match_installed_images'] is not True
            or proof['native_execution'] is not False
            or proof['gameplay_rules_reimplemented'] is not False
            or (event['kind'],event['callback_rva'],event['collector_rva'],event['writer_rva'],
                event['normalizer_rva'],event['record_type'],event['record_size'],event['host_return'])
                != (KIND,0x142ba0,0x14d160,0x13a2f0,0x1445f0,RECORD_TYPE,RECORD_SIZE,0)
            or tuple(tuple(r) for r in event['undefined_copied_stack_ranges']) != ((84,88),)
            or event['normalizer_discards_callback_return'] is not True
            or event['input_payload_used_by_exe_callback'] is not False
            or receiver['event_name'] != 'GameCoreEvent::CivicsUnlocked'
            or receiver['row_va'] != '0x1412c8fb0'
            or receiver['handler_va'] != '0x1400dae10'
            or receiver['handler_body_sha256'] != '41b7ee896df3ca9cefb2467aa064de80da7af7d938dc2b227b6bf835f4e142d4'
            or tuple(receiver['handler_calls']) != ('call 0x14098a780','call 0x1400dc0d0','call 0x14098a7b0')
            or receiver['headless_state'] != dict(observer_registered=False,state_pointer_nonnull=True,
                pre_hook=None,post_hook=None,subscriber_count=0,state_flags=0)
            or proof['source_scope'] != dict(per_thread_hook_present=False,
                writer_metadata_callback_present=False,dynamic_event_registration_present=False,
                normalizer_transform_present=False,entity_listener_count=0,counter_neutral=True)):
        raise ValueError('Policy unlock event source profile differs')
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    if EXE_EVENT_CALLBACKS.get(KIND) != event['callback_rva']:
        raise ValueError('Policy unlock event registry differs')
    return proof


def source_dependencies(*, execution_image=None):
    """Pin the active source contract, separating archived EXE provenance.

    The official EXE is not loaded by this host route. With an explicit current
    Core profile, keep its old EXE identity in the source proof for attribution,
    but include only the exact Core and static source/reference files as runtime
    dependencies. The legacy no-profile result remains unchanged.
    """
    if execution_image is not None:
        from .a0_policy_unlock_current import source_dependencies as current_dependencies
        return current_dependencies(execution_image)
    from .a0_family_source import verify_pinned_files
    from .execution_images import runtime_source_pins
    from .paths import resource_root
    from .resource_resolution import resolve_path
    proof = source()
    rows = (dict(path=SOURCE[0],sha256=SOURCE[1]),proof['core'],*proof['references'])
    if execution_image is None:
        rows = (rows[0],proof['exe'],*rows[1:])
    pins = {str(resolve_path(resource_root()/row['path']).resolve()):row['sha256'] for row in rows}
    pins = runtime_source_pins(pins, execution_image=execution_image)
    verify_pinned_files(pins)
    return pins


def receiver_row():
    row = source()['receiver']
    return {key:row[key] for key in ('event_name','handler_va','handler_body_sha256')} | {
        'record_sizes':{RECORD_SIZE}}


def enable(owner, backend):
    """Install once on the actual composed XP2 owner, before native Load."""
    image = getattr(getattr(backend, 'profile', None), 'execution_image', None)
    if image is not None:
        from .a0_policy_unlock_current import enable_current
        return enable_current(owner, backend, image)
    owner._check()
    backend.check_thread()
    if (owner.policy_unlock_event_profile is not None or owner.arguments.depth
            or owner.active_kind is not None or owner.pending or owner.deferred._draining_empty_receivers
            or owner.host_notification_counter or owner.host_metadata_counter
            or owner._foundation_backend is not backend or backend.stage != 'prepared'
            or backend.prefix is not None or backend.load_abi.core_sha256 != XP2_CORE_SHA256
            or getattr(backend,'_xp1_commands_requested',False) is not True
            or backend.host is not owner.arguments.host or backend.core is not owner.deferred.core
            or backend.context != owner.deferred.context or owner.handles_kind(KIND)
            or owner.handles_record(RECORD_TYPE)):
        raise ValueError('Policy unlock events require one idle composed XP2 command owner')
    proof = source()
    for body in proof['core_functions'].values():
        for fragment in body['fragments']:
            raw = bytes.fromhex(fragment['raw_hex'])
            rva = int(fragment['start_rva'],16)
            for offset in range(0,len(raw),4096):
                block = raw[offset:offset+4096]
                if owner.read(backend.core._handle+rva+offset,len(block)) != block:
                    raise ValueError('Live XP2 policy unlock producer differs from source')
    from .native.native_deferred_empty_profile import validate_empty_profile_record
    shape = bytearray(RECORD_SIZE)
    struct.pack_into('<II',shape,0,RECORD_SIZE,RECORD_TYPE)
    validate_empty_profile_record(shape,**owner.empty_receiver_state)
    from .a0_family_source import A0FamilyProfile
    profile = A0FamilyProfile(MappingProxyType({KIND:frozenset({RECORD_TYPE})}),
                             MappingProxyType({RECORD_TYPE:RECORD_SIZE}),SOURCE[1])
    owner.policy_unlock_event_profile = owner._policy_unlock_event_profile = profile
    return owner


def dispatch(owner, kind, fields):
    """Retain the real notification; execute no invented gameplay side effect."""
    owner._check()
    profile = owner.policy_unlock_event_profile
    expected_sha = SOURCE[1]
    image_id = getattr(owner, '_policy_unlock_current_image_id', None)
    if image_id is not None:
        from .a0_policy_unlock_current import CURRENT_PROFILE_ID, OBSOLETE_KIND, PROFILE_SHA256, dispatch_obsolescence
        image = getattr(owner.deferred.core, '_civ6_host_execution_image', None)
        if image_id != CURRENT_PROFILE_ID or getattr(image, 'id', None) != image_id:
            raise ValueError('Current policy unlock lost its execution image')
        if kind == OBSOLETE_KIND:
            return dispatch_obsolescence(owner, fields)
        expected_sha = PROFILE_SHA256
    if (kind != KIND or owner.active_kind != KIND or profile is None
            or profile is not owner._policy_unlock_event_profile
            or profile.source_sha256 != expected_sha
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False
            or owner.normalizer_transform_present is not False
            or owner.dynamic_event_registration_present is not False
            or type(owner.entity_listener_count) is not int or owner.entity_listener_count != 0):
        raise ValueError('Policy unlock event hooks, source or active owner differ')
    from .native.native_absent_scalar_a0 import _scalar_variant
    if type(fields) is not dict or set(fields) != {0xa1e5a149,0xd6fcf3e4}:
        raise ValueError('Policy unlock descriptor fields differ')
    _scalar_variant(fields[0xa1e5a149],3,'selector',value_must_be_zero=True)
    _scalar_variant(fields[0xd6fcf3e4],2,'player')
    if (len(owner.pending) >= owner.limit or type(owner._sequence) is not int
            or not 0 <= owner._sequence < 0x7fffffff):
        raise RuntimeError('Policy unlock event FIFO bound exceeded')
    before = (owner.host_notification_counter,owner.host_metadata_counter,owner._sequence,len(owner.pending))
    from .native.native_unary_event_family import _metadata_template
    record = bytearray(RECORD_SIZE)
    struct.pack_into('<IIII',record,0,RECORD_SIZE,RECORD_TYPE,owner._sequence+1,0)
    record[16:80] = _metadata_template()
    struct.pack_into('<I',record,80,owner._sequence+1)
    # The original writer copies four undefined stack bytes at +84. Canonical
    # zero is safe only in the explicitly empty receiver: no payload is read.
    record = bytes(record)
    owner._enqueue(record)
    n,m,sequence,count = before
    if (owner.host_notification_counter,owner.host_metadata_counter,owner._sequence,len(owner.pending)) != (n,m,sequence+1,count+1):
        raise RuntimeError('Policy unlock notification changed counter/FIFO semantics')
    owner.emit('xp2_policy_unlock_notification_enqueued',dispatch_kind=hex(kind),
        queue_type=hex(RECORD_TYPE),sequence=owner._sequence,record_hex=record.hex(),
        source_proof_sha256=expected_sha,counter_neutral=True,callback_return_discarded=True,
        undefined_stack_padding_canonicalized=[[84,88]],payload_exposed_to_learner=False,
        gameplay_effect_substituted=False,native_dispatch_return=0)
    return 0
