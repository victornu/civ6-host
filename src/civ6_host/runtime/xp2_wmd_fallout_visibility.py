"""Exact XP2 WMDFalloutVisibilityChanged wire, shared metadata and FIFO."""
import hashlib
import struct
from pathlib import Path

from .a0_family_source import _path, verify_pinned_files
from .configuration_profiles import XP2_CORE_SHA256, _source

SOURCE=('work/host-extensions/xp2-wmd-fallout-visibility-static/source-profile-v1.json',
        '7791d4ea7a6d1dfcab4f293c5ea49b53748347bfc552009f72c42249b01f82da')
KIND, RECORD_TYPE, RECORD_SIZE = 0x8cbda9f3, 0xc9, 96
SELECTOR, VALUE, POSITION, PLAYER = 0xa1e5a149, 0xd6fcf3e4, 0x8c468e3c, 0xf06a2af2
_FIELDS = frozenset((SELECTOR, VALUE, POSITION))
_EXE = 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'


def source():
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    proof=_source(SOURCE)
    contract=proof['contract']
    if (proof['schema']!='civ6-host.xp2-wmd-fallout-visibility.static.v1'
            or proof['images']!={'core':XP2_CORE_SHA256,'exe':_EXE}
            or proof['native_execution'] is not False
            or (contract['kind'],contract['record_type'],contract['record_size'])!=(KIND,RECORD_TYPE,RECORD_SIZE)
            or contract['callback_rva']!=EXE_EVENT_CALLBACKS.get(KIND)
            or contract['field_tags']!={hex(SELECTOR):3,hex(VALUE):2,hex(POSITION):13,hex(PLAYER):2}
            or contract['core_literal_rvas']!=(0x1ed801,0x1ee791,0x1ef581,0x35c1b9)
            or contract['values']!=(0,2) or contract['selector']!=0
            or contract['record_scope_flag_offset']!=72 or contract['native_queries']!=0
            or contract['reserved_record_bytes']!=(76,80)
            or contract['reserved_policy']!='zero-writer-allocation'
            or contract['perspective_player_optional'] is not True
            or contract['position_blob']!={'length':8,'flags':0x21000001}):
        raise ValueError('XP2 WMD visibility source contract changed')
    return proof


def receiver_row():
    proof=source()
    row=proof['receiver']
    if (row['name']!='GameCoreEvent::WMDFalloutVisibilityChanged'
            or row['row_va']!='0x1412c8e60' or row['setup_va']!='0x1400d1aa0'
            or row['handler_va']!='0x1400dab10'
            or row['calls']!=('call 0x14098a780','call 0x1400dc0d0','call 0x14098a7b0')):
        raise ValueError('XP2 WMD visibility receiver changed')
    body=proof['bodies']['exe']['0xdab10']
    return dict(event_name=row['name'],handler_va=row['handler_va'],
                handler_body_sha256=body['sha256'],record_sizes={RECORD_SIZE})


def source_dependencies():
    proof=source()
    pins={str(_path(SOURCE[0])):SOURCE[1]}
    for ref in (*proof['references'],proof['extractor']):
        path=str(_path(ref['path']))
        if path in pins and pins[path]!=ref['sha256']:
            raise ValueError('Conflicting XP2 WMD visibility pin')
        pins[path]=ref['sha256']
    module=Path(__file__).resolve()
    pins[str(module)]=hashlib.sha256(module.read_bytes()).hexdigest()
    verify_pinned_files(pins)
    return pins


def verify_live(base,read):
    if type(base) is not int or not 0<base<(1<<47)-0x1000000 or not callable(read):
        raise ValueError('WMD visibility requires the bound XP2 module')
    for body in source()['bodies']['core'].values():
        for fragment in body.get('fragments') or (body,):
            raw=bytes.fromhex(fragment['raw_hex'])
            start=int(fragment['start_rva'],16)
            if len(raw)!=fragment['length'] or hashlib.sha256(raw).hexdigest()!=fragment['sha256']:
                raise ValueError('XP2 WMD visibility proof body changed at '+hex(start))
            for offset in range(0,len(raw),4096):
                expected=raw[offset:offset+4096]
                actual=read(base+start+offset,len(expected))
                if type(actual) is not bytes or actual!=expected:
                    raise ValueError('XP2 WMD visibility producer body changed at '+hex(start+offset))


def dispatch(owner, fields):
    """Run after existing XP2 foundation borrow and internal cache checks."""
    from .a0_foundation_events import require_borrow
    from .native.native_application_mirror import decode_scalar
    from .native.native_event_827289e6 import _copy_blob
    from .native.native_notification_metadata import metadata_scope_transition
    from .native.native_player_event_domains import validate_sequence
    from .native.native_unary_event_family import _METADATA

    require_borrow(owner)
    owner._require_no_f391_reentry()
    if (owner.foundation_core_sha256!=XP2_CORE_SHA256 or owner.active_kind!=KIND
            or owner.normalizer_transform_present is not False
            or owner.per_thread_hook_present is not False
            or owner.writer_metadata_callback_present is not False):
        raise ValueError('XP2 WMD visibility requires its exact callback owner')
    if type(fields) is not dict or set(fields) not in (_FIELDS,_FIELDS|{PLAYER}):
        raise ValueError('XP2 WMD visibility fields are outside the proved producers')
    selector=decode_scalar(fields[SELECTOR],3)
    value=decode_scalar(fields[VALUE],2)
    if selector!=0 or value not in (0,2):
        raise ValueError('XP2 WMD visibility selector or value changed')
    if PLAYER in fields:
        decode_scalar(fields[PLAYER],2)
    position=_copy_blob(fields[POSITION],owner.read,13,'WMD visibility position')
    notification=owner.host_notification_counter
    metadata=owner.host_metadata_counter
    flag,next_metadata=metadata_scope_transition(notification,metadata)
    sequence=owner._sequence+1
    validate_sequence(sequence)
    record=bytearray(RECORD_SIZE)
    struct.pack_into('<IIII',record,0,RECORD_SIZE,RECORD_TYPE,sequence,0)
    record[16:80]=_METADATA
    struct.pack_into('<I',record,72,flag)
    struct.pack_into('<I8sI',record,80,sequence,position,value)
    owner._enqueue(bytes(record))
    owner.host_metadata_counter=next_metadata
    owner.emit('native_deferred_host_event_enqueued',dispatch_kind=hex(KIND),
               queue_type=hex(RECORD_TYPE),record_hex=record.hex(),pending_count=len(owner.pending),
               source_proof_sha256=SOURCE[1],host_notification_counter=notification,
               metadata_counter_before=metadata,metadata_counter_after=next_metadata,
               scope_flag=flag,native_queries_executed=False,consumer_validated=False,
               eligible_for_training=False,native_dispatch_return=0)
    return 0
