"""Read-only authentication of grouped shared expansion client receipts."""
import argparse
import hashlib
import json
from pathlib import Path
import qualify_xp1_configuration as q


_XP2_FEATURE_REVEAL_REVIEW_SOURCE=(
    'work/host-extensions/xp2-combat-notification-static/feature-reveal-arguments-source-v2.json',
    'e4658a1bb64a32fc94e735b0f8ef47d94d75cf3ad8377f34973c9daa5e2e2c20')
_XP2_COMBAT_DIAGNOSTIC_SOURCE=(
    'work/host-extensions/xp2-combat-events-static/source-profile-v2.json',
    '951ff441db51dc18ce568dcd4ed354dbb26185c1c91235b414760b70000cd9e5')
_XP2_COMBAT_DIAGNOSTIC_PRODUCER_SHA256='512e11c1463a8f5152c7b87541d83b408d9f57fc7d92f791231648a3f576057f'


def pin(path):
    path=Path(path).resolve();raw=path.read_bytes()
    return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def _xp2_weather_omission_payload(event):
    """Validate copied values only; this does not authenticate a completed interval."""
    from civ6_host.runtime import xp2_weather_lifecycle as lifecycle
    from civ6_host.runtime import xp2_turn_event_profile as weather
    def require(ok, message):
        if not ok:raise ValueError('XP2 weather omission '+message)
    def uint(value, maximum=0xffffffff):
        return type(value) is int and 0<=value<=maximum
    expected={'stage','dispatch_kind','source_proof_sha256','dispatch_scope_sha256','policy',
        'administrative_arguments','information_scope','public_visibility_qualified',
        'native_queries_executed','native_gameplay_written','presentation_arrays_allocated',
        'records_enqueued','fifo_sequence_before','fifo_sequence_after',
        'preceding_pending_records_preserved','native_dispatch_return','eligible_for_training'}
    require(type(event) is dict and set(event)==expected,'receipt fields differ')
    try:kind=int(event['dispatch_kind'],16)
    except (TypeError,ValueError):raise ValueError('XP2 weather omission kind differs') from None
    require(kind in lifecycle.KINDS and event['dispatch_kind']==hex(kind),'kind is unqualified')
    p=lifecycle.source();weather.scope_source();route=p['routes'][hex(kind)]
    require(event['stage']=='native_xp2_weather_presentation_omitted'
        and event['source_proof_sha256']==lifecycle.SOURCE[1]
        and event['dispatch_scope_sha256']==weather.SCOPE_SOURCE[1]
        and event['policy']==lifecycle.POLICY
        and event['information_scope']=='administrative-unfiltered'
        and event['public_visibility_qualified'] is False
        and event['native_queries_executed'] is False
        and event['native_gameplay_written'] is False
        and event['presentation_arrays_allocated'] is False
        and type(event['records_enqueued']) is int and event['records_enqueued']==0
        and event['preceding_pending_records_preserved'] is True
        and type(event['native_dispatch_return']) is int and event['native_dispatch_return']==0
        and event['eligible_for_training'] is False,'source, scope or zero-record policy differs')
    before,after=event['fifo_sequence_before'],event['fifo_sequence_after']
    require(uint(before,0x7ffffffe) and type(after) is int and after==before,
            'FIFO sequence changed or is invalid')
    values=event['administrative_arguments']
    require(type(values) is dict and set(values)=={'selector','identifier','status','status_key',
        'input_position','input_plot_indices','field_tags','pointer_payloads_copied',
        'borrowed_pointer_addresses_retained'},'administrative argument shape differs')
    require(uint(values['selector']) and uint(values['identifier'])
        and values['pointer_payloads_copied'] is True
        and values['borrowed_pointer_addresses_retained'] is False
        and type(values['field_tags']) is dict and values['field_tags']==dict(route['fields'])
        and all(type(v) is int for v in values['field_tags'].values()),'typed copied inputs differ')
    position=values['input_position'];indices=values['input_plot_indices']
    require(type(position) is list and len(position)==2
        and all(type(v) is int and -0x80000000<=v<=0x7fffffff for v in position),
        'copied position width differs')
    if kind==lifecycle.STORM_REMOVED:
        require(values['status'] is None and values['status_key'] is None,'removed Storm status is invented')
    else:
        require(uint(values['status']) and values['status_key']==hex(
            lifecycle.STATUS if kind==lifecycle.STORM_CHANGED else lifecycle.DROUGHT_STATUS),
            'copied status differs')
    require((type(indices) is list and len(indices)<=lifecycle.MAX_INPUT_INDICES
             and all(uint(v) for v in indices)) if kind==lifecycle.STORM_CHANGED else indices is None,
            'copied input DWORD vector differs')
    return dict(dispatch_kind=hex(kind),source_proof_sha256=lifecycle.SOURCE[1],
        dispatch_scope_sha256=weather.SCOPE_SOURCE[1],policy=lifecycle.POLICY,
        administrative_arguments=json.loads(json.dumps(values)),fifo_sequence=before,
        records_enqueued=0,native_queries_executed=False,native_gameplay_written=False)


def _xp2_empty_presentation_installation(event):
    """Authenticate only the fixed feature-reveal family installed by composition."""
    from civ6_host.runtime import xp2_feature_reveal_source as source
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
    expected={'stage','core_sha256','source_module','source_proof_sha256','dispatch_kinds',
              'policy','synthetic_records','unknown_service_fallback'}
    if (type(event) is not dict or set(event)!=expected
            or event['stage']!='native_empty_presentation_family_installed'
            or event['core_sha256']!=XP2_CORE_SHA256
            or event['source_module']!='civ6_host.runtime.xp2_feature_reveal_source'
            or source.SOURCE!=_XP2_FEATURE_REVEAL_REVIEW_SOURCE
            or event['source_proof_sha256']!=source.SOURCE[1]
            or type(event['dispatch_kinds']) is not list
            or event['dispatch_kinds']!=[hex(k) for k in sorted(source.KINDS)]
            or event['policy']!=source.POLICY
            or event['synthetic_records'] is not False
            or event['unknown_service_fallback'] is not False):
        raise ValueError('XP2 empty presentation installation differs')
    source.source()
    return json.loads(json.dumps(event))


def _xp2_empty_presentation_omission_payload(event):
    """Validate copied administrative values without reading a native pointer."""
    from civ6_host.runtime import xp2_feature_reveal_source as source
    def require(ok,message):
        if not ok:raise ValueError('XP2 empty presentation omission '+message)
    def uint(value):return type(value) is int and 0<=value<=0xffffffff
    expected={'stage','dispatch_kind','source_module','source_proof_sha256','policy',
        'administrative_arguments','information_scope','public_visibility_qualified',
        'native_queries_executed','native_gameplay_written','presentation_arrays_allocated',
        'records_enqueued','fifo_sequence_before','fifo_sequence_after',
        'preceding_pending_records_preserved','native_dispatch_return','eligible_for_training'}
    require(type(event) is dict and set(event)==expected,'receipt fields differ')
    try:kind=int(event['dispatch_kind'],16)
    except (TypeError,ValueError):raise ValueError('XP2 empty presentation omission kind differs') from None
    require(kind in source.KINDS and event['dispatch_kind']==hex(kind),'kind is unqualified')
    source.source()
    require(event['stage']=='native_empty_presentation_callback_omitted'
        and event['source_module']=='civ6_host.runtime.xp2_feature_reveal_source'
        and source.SOURCE==_XP2_FEATURE_REVEAL_REVIEW_SOURCE
        and event['source_proof_sha256']==source.SOURCE[1] and event['policy']==source.POLICY
        and event['information_scope']=='administrative-unfiltered'
        and event['public_visibility_qualified'] is False
        and event['native_queries_executed'] is False
        and event['native_gameplay_written'] is False
        and event['presentation_arrays_allocated'] is False
        and type(event['records_enqueued']) is int and event['records_enqueued']==0
        and event['preceding_pending_records_preserved'] is True
        and type(event['native_dispatch_return']) is int and event['native_dispatch_return']==0
        and event['eligible_for_training'] is False,'source, scope or zero-record policy differs')
    before,after=event['fifo_sequence_before'],event['fifo_sequence_after']
    require(type(before) is int and 0<=before<=0x7ffffffe and type(after) is int and after==before,
            'FIFO sequence changed or is invalid')
    values=event['administrative_arguments']
    require(type(values) is dict and set(values)=={'kind','event_name','selector','coordinate',
        'value_key','value','field_tags','borrowed_position_payload_copied','borrowed_pointer_retained'},
        'administrative argument shape differs')
    require(values['kind']==hex(kind) and values['event_name']==source.EVENT_NAMES[kind]
        and type(values['selector']) is int and values['selector']==0
        and values['value_key']==hex(source.VALUE_KEY) and uint(values['value'])
        and values['borrowed_position_payload_copied'] is True
        and values['borrowed_pointer_retained'] is False
        and type(values['field_tags']) is dict
        and values['field_tags']=={hex(source.SELECTOR_KEY):3,hex(source.POSITION_KEY):0,hex(source.VALUE_KEY):2}
        and all(type(v) is int for v in values['field_tags'].values()),'typed copied inputs differ')
    coordinate=values['coordinate']
    require(type(coordinate) is list and len(coordinate)==2
        and all(type(v) is int and -0x80000000<=v<=0x7fffffff for v in coordinate),
        'copied coordinate width differs')
    return dict(dispatch_kind=hex(kind),source_module=event['source_module'],
        source_proof_sha256=source.SOURCE[1],policy=source.POLICY,
        administrative_arguments=json.loads(json.dumps(values)),fifo_sequence=before,
        records_enqueued=0,native_queries_executed=False,native_gameplay_written=False)


def _xp2_combat_diagnostic_pair(generic, detailed, *, pending_count, live_tokens, next_token):
    """Bind the two adjacent receipts emitted around one shared F8 enqueue."""
    import struct
    from civ6_host.runtime import xp2_combat_event_source as source
    from civ6_host.runtime.native.native_combat_receiver import PADDING_POLICY
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
    def require(ok,message):
        if not ok:raise ValueError('XP2 combat diagnostic pair '+message)
    generic_fields={'stage','dispatch_kind','queue_type','record_hex','pending_count',
        'consumer_validated','eligible_for_training','native_dispatch_return'}
    policy=source.administrative_snapshot_policy(XP2_CORE_SHA256)
    detailed_fields={'stage','dispatch_kind','queue_type','token','record_hex','source_proof_sha256',
        'owned_root_field_count','native_deep_copy_executed','owned_map_retained_until_post_hook',
        'padding_policy','query_inputs','query_results','registry_live_maps','pending_count',
        'callback_completed','eligible_for_training','native_dispatch_return',*policy}
    require(type(generic) is dict and set(generic)==generic_fields
        and type(detailed) is dict and set(detailed)==detailed_fields,'receipt fields differ')
    require(source.SOURCE==_XP2_COMBAT_DIAGNOSTIC_SOURCE,'source is unreviewed')
    require(generic['stage']=='native_deferred_host_event_enqueued'
        and detailed['stage']=='native_combat_record_enqueued'
        and generic['consumer_validated'] is False,'source emission path differs')
    for event in (generic,detailed):
        require(event['dispatch_kind']=='0x8256dbe1' and event['queue_type']=='0xf8'
            and type(event['pending_count']) is int and event['pending_count']==pending_count
            and event['eligible_for_training'] is False
            and type(event['native_dispatch_return']) is int and event['native_dispatch_return']==0,
            'shared metadata differs')
    value=generic['record_hex']
    require(type(value) is str and len(value)==256 and detailed['record_hex']==value,'record copies differ')
    try:raw=bytes.fromhex(value)
    except ValueError:raise ValueError('XP2 combat diagnostic pair record is not hexadecimal') from None
    require(raw.hex()==value,'record is not canonical hexadecimal')
    size,kind,sequence,metadata=struct.unpack_from('<IIII',raw)
    token=struct.unpack_from('<I',raw,120)[0]
    require((size,kind,metadata)==(128,248,0) and 0<sequence<=0x7ffffffe
        and struct.unpack_from('<I',raw,80)[0]==sequence
        and raw[16:24]==b'\xff'*8 and raw[64:72]==bytes(8) and raw[76:80]==bytes(4)
        and raw[84:88]==bytes(4) and raw[124:128]==bytes(4),'record layout differs')
    require(type(detailed['token']) is int and detailed['token']==token==next_token
        and token not in live_tokens and 0<token<=0xffffffff,'registry token differs')
    descriptors=[raw[88+i*8:96+i*8] for i in range(4)]
    normalized=bytearray(struct.pack('<HHI',0xffff,0,0xffffffff)*5)
    for index,descriptor in enumerate(descriptors):
        descriptor_type=struct.unpack_from('<H',descriptor,2)[0]
        if descriptor_type==1:normalized[index*8:index*8+8]=descriptor
        elif descriptor_type==2:normalized[32:40]=descriptor
    require(raw[24:64]==normalized,'copied descriptor metadata differs')
    inputs=[]
    for descriptor in descriptors[:2]:
        owner,_,identifier=struct.unpack('<HHI',descriptor)
        inputs.append(None if owner==0xffff or identifier==0xffffffff else struct.unpack_from('<h',descriptor)[0])
    require(type(detailed['query_inputs']) is list and len(detailed['query_inputs'])==2
        and all(type(actual) is type(expected) and actual==expected
                for actual,expected in zip(detailed['query_inputs'],inputs)),'query input metadata differs')
    results=detailed['query_results']
    require(type(results) is list and len(results)==2
        and all(result is None if owner is None else type(result) is bool
                for owner,result in zip(inputs,results)),'query disposition metadata differs')
    flag=struct.unpack_from('<I',raw,72)[0]
    require(flag==18 if any(result is True for result in results) else flag in (1,2),
            'query/record flag metadata differs')
    require(detailed['source_proof_sha256']==source.SOURCE[1]
        and type(detailed['owned_root_field_count']) is int
        and detailed['owned_root_field_count']==len(source.source()['root_fields'])
        and detailed['native_deep_copy_executed'] is True
        and detailed['owned_map_retained_until_post_hook'] is True
        and detailed['padding_policy']==PADDING_POLICY and detailed['callback_completed'] is True
        and type(detailed['registry_live_maps']) is int
        and detailed['registry_live_maps']==len(live_tokens)+1
        and all(type(detailed[key]) is type(expected) and detailed[key]==expected
                for key,expected in policy.items()),'owned map or administrative metadata differs')
    return dict(sequence=sequence,record_type=248,record_size=128,token=token,
        record_sha256=hashlib.sha256(raw).hexdigest(),source_proof_sha256=source.SOURCE[1],
        administrative_snapshot_complete=False,native_modifier_lists_preserved=True,
        modifier_values_decoded=False)


def _xp2_combat_post_hook(event, row, *, live_map_count):
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
    from civ6_host.runtime.native.native_combat_receiver import PROOF_SHA256,verify_source_evidence
    expected={'stage','sequence','owned_map_core_sha256','record_type','record_size','token',
        'post_hook_reproduced','native_map_destructor_returned','registry_live_maps',
        'source_proof_sha256','subscribers_invoked','full_exe_frame_schedule_reproduced','eligible_for_training'}
    if (type(event) is not dict or set(event)!=expected
            or event['stage']!='native_combat_post_hook_consumed'
            or any(type(event[key]) is not int or event[key]!=row[key]
                   for key in ('sequence','record_type','record_size','token'))
            or event['owned_map_core_sha256']!=XP2_CORE_SHA256
            or event['post_hook_reproduced'] is not True
            or event['native_map_destructor_returned'] is not True
            or type(event['registry_live_maps']) is not int or event['registry_live_maps']!=live_map_count
            or event['source_proof_sha256']!=PROOF_SHA256
            or type(event['subscribers_invoked']) is not int or event['subscribers_invoked']!=0
            or event['full_exe_frame_schedule_reproduced'] is not False
            or event['eligible_for_training'] is not False):
        raise ValueError('XP2 combat diagnostic post-hook metadata differs')
    verify_source_evidence()
    return dict(post_hook_reproduced=True,native_map_destructor_returned=True,
                receiver_source_proof_sha256=PROOF_SHA256)


def _xp2_weather_favor_records(records, intervals, *, lifecycle_omissions=False,
                               empty_presentation_omissions=False, combat_diagnostic_receipts=False):
    """Join copied notifications to source-selected empty FIFO receipts.

    Records are the existing stdout parser's (physical line, bytes, event)
    triples. Pointer values are opaque: replay never reads old process memory.
    The caller authenticates the producing/consuming implementation and profiles.
    """
    import struct
    from civ6_host.runtime import xp2_turn_event_profile as weather
    from civ6_host.runtime import xp2_turn_event_records as codec
    from civ6_host.runtime import xp2_favor_event_profile as favor
    receivers={**codec.receiver_rows(),**favor.receiver_rows()}
    enqueue={'native_xp2_climate_event_enqueued','native_xp2_turn_event_enqueued'}
    pending={};seen=set();leases={};reviewed=[];last_sequence=0;last_consumed=0
    omissions=[];empty_omissions=[];installation=None
    fifo_pending={};fifo_consumed={};last_enqueued=0;last_line=0
    track_fifo=lifecycle_omissions or empty_presentation_omissions or combat_diagnostic_receipts
    next_combat_receipt=None;combat_pending={};combat_reviewed=[];combat_tokens=set();next_combat_token=1
    def require(ok, message):
        if not ok:raise ValueError('XP2 weather/Favor '+message)
    def uint(value, maximum=0xffffffff):
        return type(value) is int and 0<=value<=maximum
    def copied_hex(value, size):
        require(type(value) is str and len(value)==size*2,'copy size differs')
        try:raw=bytes.fromhex(value)
        except ValueError:raise ValueError('XP2 weather/Favor copy is not hexadecimal') from None
        require(len(raw)==size and raw.hex()==value,'copy is not canonical hexadecimal')
        return raw
    def scope(line):
        found=[r for r in intervals if r['first_line']<line<r['last_line']]
        require(len(found)==1,'record lies outside one completed native transition')
        return found[0]
    def completed_scope(line):
        interval=scope(line);phase=interval.get('phase');returned=interval.get('event',{})
        require(phase in ('unit_commands','turn_update')
            and returned.get('stage')=='xp1_saved_'+phase+'_returned'
            and type(interval.get('protocol_sequence')) is int and interval['protocol_sequence']>0
            and type(returned.get('protocol_sequence')) is int
            and returned['protocol_sequence']==interval['protocol_sequence'],
            'omission lacks a completed native transition return')
        return interval
    for line,_,event in records:
        stage=event['stage']
        preceding_combat=next_combat_receipt;next_combat_receipt=None
        if preceding_combat is not None:
            require(stage=='native_combat_record_enqueued' and type(line) is int
                    and line==preceding_combat[0]+1,'F8 detailed receipt is not physically adjacent')
        if track_fifo:
            require(type(line) is int and line>last_line,'physical event order differs')
            last_line=line
        if stage=='native_combat_record_enqueued':
            require(combat_diagnostic_receipts and preceding_combat is not None,
                    'F8 detailed receipt lacks its executed adjacent producer')
            row=_xp2_combat_diagnostic_pair(preceding_combat[1],event,
                pending_count=len(fifo_pending),live_tokens=combat_tokens,next_token=next_combat_token)
            interval=completed_scope(line)
            require(interval['first_line']<preceding_combat[0]
                and row['sequence']==last_enqueued and row['sequence'] in fifo_pending,
                'F8 diagnostic receipt differs from its completed FIFO producer')
            row.update(enqueued_line=preceding_combat[0],diagnostic_line=line,
                protocol_sequence=interval['protocol_sequence'],transition_last_line=interval['last_line'])
            combat_pending[row['sequence']]=row;combat_tokens.add(row['token']);next_combat_token+=1
            continue
        if track_fifo:
            # These are actual serialized records from the existing producers.
            # The private ring uses sequence0 and does not belong to this FIFO.
            hexes=event.get('record_hex')
            hexes=[hexes] if type(hexes) is str else hexes
            if (type(hexes) is list and stage.endswith(('_enqueued','_retained'))
                    and stage!='native_private_ring_record_retained'):
                for value in hexes:
                    require(type(value) is str,'FIFO record copy differs')
                    try:raw=bytes.fromhex(value)
                    except ValueError:raise ValueError('XP2 weather/Favor FIFO record is not hexadecimal') from None
                    require(len(raw)>=12 and int.from_bytes(raw[:4],'little')==len(raw),
                            'FIFO record header differs')
                    seq=int.from_bytes(raw[8:12],'little')
                    require(seq==last_enqueued+1 and seq not in fifo_pending,
                            'FIFO enqueue sequence is missing, repeated or out of order')
                    fifo_pending[seq]=line;last_enqueued=seq
                    if int.from_bytes(raw[4:8],'little')==0xf8:
                        require(combat_diagnostic_receipts and stage=='native_deferred_host_event_enqueued'
                            and next_combat_receipt is None,'F8 producer lacks its executed diagnostic source')
                        next_combat_receipt=(line,event)
        if stage=='native_empty_presentation_family_installed':
            require(empty_presentation_omissions,'installation lacks its executed empty presentation source contract')
            require(installation is None,'empty presentation family installation is repeated')
            installation=dict(_xp2_empty_presentation_installation(event),line=line)
            continue
        if stage in ('native_xp2_weather_presentation_omitted','native_empty_presentation_callback_omitted'):
            feature=stage=='native_empty_presentation_callback_omitted'
            if feature:
                require(empty_presentation_omissions,'omission lacks its executed empty presentation source contract')
                require(installation is not None,'omission lacks its preceding fixed family installation')
                row=_xp2_empty_presentation_omission_payload(event)
                selected_omissions=empty_omissions
            else:
                require(lifecycle_omissions,'omission lacks its executed lifecycle source contract')
                row=_xp2_weather_omission_payload(event)
                selected_omissions=omissions
            interval=completed_scope(line)
            require(row['fifo_sequence']==last_enqueued and last_consumed<=last_enqueued,
                    'omission does not match the preceding FIFO state')
            selected_omissions.append(dict(row,omission_ordinal=len(selected_omissions)+1,line=line,
                protocol_sequence=interval['protocol_sequence'],transition_last_line=interval['last_line'],
                preceding_pending_sequences=list(fifo_pending)))
            continue
        if stage in enqueue:
            try:kind=int(event.get('dispatch_kind',''),16)
            except (ValueError,TypeError):raise ValueError('XP2 weather/Favor dispatch kind differs') from None
            require(kind in weather.RECORDS,'dispatch kind is unqualified')
            is_favor=kind==weather.FAVOR_KIND
            require(stage==('native_xp2_turn_event_enqueued' if is_favor else 'native_xp2_climate_event_enqueued')
                and event.get('source_proof_sha256')==(favor.SOURCE[1] if is_favor else weather.SOURCE[1])
                and event.get('information_scope')=='administrative-unfiltered'
                and event.get('public_visibility_qualified') is False
                and type(event.get('native_dispatch_return')) is int and event['native_dispatch_return']==0
                and event.get('eligible_for_training') is False,'source or visibility receipt differs')
            types=sorted(weather.RECORDS[kind]);sequences=event.get('record_sequences');hexes=event.get('record_hex')
            require(type(sequences) is list and type(hexes) is list
                and len(sequences)==len(hexes)==len(types)
                and all(uint(s,0x7ffffffe) and s>0 for s in sequences)
                and sequences==list(range(sequences[0],sequences[0]+len(types)))
                and sequences[0]>last_sequence,'record sequence/count/order differs')
            interval=scope(line);first_payload=None
            for sequence,record_type,hex_record in zip(sequences,types,hexes):
                require(sequence not in seen,'record sequence was already enqueued')
                raw=copied_hex(hex_record,weather.SIZES[record_type]);word=lambda at:struct.unpack_from('<I',raw,at)[0]
                random=record_type in (0x135,0x136,0x137);array=record_type in (0x138,0x13b)
                flag=6 if random else 4 if array else 0
                require(struct.unpack_from('<IIII',raw)==(len(raw),record_type,sequence,0)
                    and raw[20:64]==b'\xff'*4+struct.pack('<HHI',0xffff,0,0xffffffff)*5
                    and raw[64:80]==struct.pack('<QII',0,flag,0)
                    and word(80)==sequence,'record header/type/size/sequence differs')
                details={};pointer=None
                if array:
                    indices=event.get('copied_plot_indices');pairs=event.get('copied_plot_positions')
                    require(event.get('native_queries_executed') is True
                        and event.get('undefined_record_ranges')==[[84,88]] and raw[84:88]==bytes(4)
                        and word(16)==0xffffffff
                        and struct.unpack_from('<HH',raw,88)==(0xffff,0x52 if record_type==0x138 else 0x53)
                        and event.get('storage_release_policy')=='host-owned-after-empty-consumption'
                        and type(indices) is list and type(pairs) is list
                        and 0<len(indices)==len(pairs)<=65536
                        and all(uint(v,0x7fffffff) for v in indices),'array/query/storage receipt differs')
                    snapshot=b''.join(copied_hex(pair,8) for pair in pairs)
                    count_at,pointer_at=(108,112) if record_type==0x138 else (100,104)
                    pointer=struct.unpack_from('<Q',raw,pointer_at)[0]
                    require(word(count_at)==len(indices) and pointer>0 and pointer not in leases,
                            'array count/pointer/live lease differs')
                    words=event.get('copied_service_words')
                    if record_type==0x138:
                        require(type(words) is list and len(words)==2 and all(uint(v) for v in words)
                            and struct.unpack_from('<II',raw,100)==(words[1],words[0])
                            and raw[120:128]==bytes(8),'Storm service words differ')
                    else:require(words is None,'descriptor53 must not query Storm service words')
                    details=dict(array_count=len(indices),array_copy_sha256=hashlib.sha256(snapshot).hexdigest(),
                        copied_plot_indices=indices,copied_plot_positions=pairs,copied_service_words=words,
                        descriptor_identifier=word(92),value=word(96),opaque_array_pointer=pointer)
                    leases[pointer]=sequence
                elif random:
                    coordinates=struct.unpack_from('<ii',raw,100);query=all(v>-9999 for v in coordinates)
                    index=event.get('native_position_index')
                    require(event.get('native_queries_executed') is query
                        and (uint(index) and word(16)==index if query else index is None and word(16)==0xffffffff)
                        and event.get('undefined_record_ranges')==[[92,96]]
                        and raw[92:100]==bytes(8) and raw[108:112]==bytes(4),
                        'random-event query/index/padding differs')
                    require(first_payload is None or first_payload==raw[84:],
                            'Occurred and Narrative payloads differ')
                    first_payload=raw[84:]
                    details=dict(identifier=word(84),selector=word(88),position=list(coordinates),native_position_index=index)
                else:
                    require(event.get('native_queries_executed') is False
                        and event.get('undefined_record_ranges')==[] and word(16)==0xffffffff,
                        'scalar query/undefined-range receipt differs')
                    if is_favor:details=dict(values=list(struct.unpack_from('<III',raw,84)))
                    else:
                        require(event.get('native_position_index') is None and raw[88:96]==bytes(8),
                                'climate scalar padding differs')
                        details=dict(selector=word(84))
                pending[sequence]=dict(sequence=sequence,record_type=record_type,record_size=len(raw),
                    dispatch_kind=hex(kind),enqueued_line=line,protocol_sequence=interval['protocol_sequence'],
                    transition_last_line=interval['last_line'],record_sha256=hashlib.sha256(raw).hexdigest(),
                    **details)
                seen.add(sequence);last_sequence=sequence
        elif stage in ('native_deferred_empty_record_consumed','native_cache_update_dispatched',
                       'native_combat_post_hook_consumed'):
            sequence=event.get('sequence')
            require(uint(sequence),'FIFO consumer sequence is invalid')
            if stage=='native_combat_post_hook_consumed':
                require(combat_diagnostic_receipts and sequence in combat_pending,
                        'F8 post-hook lacks its authenticated diagnostic producer')
                row=combat_pending[sequence]
                require(line<row['transition_last_line'],'F8 post-hook escapes its completed transition')
                row.update(_xp2_combat_post_hook(event,row,live_map_count=len(combat_tokens)-1),consumed_line=line)
                combat_tokens.remove(row['token']);combat_reviewed.append(row);del combat_pending[sequence]
            elif sequence in combat_pending:
                raise ValueError('XP2 weather/Favor F8 record bypasses its native post-hook')
            # All consumer events commit the one shared FIFO. This also catches a
            # selected record moved past an unrelated cache/empty consumer.
            require(uint(sequence) and sequence>last_consumed,'FIFO consumption is repeated or out of order')
            last_consumed=sequence
            if track_fifo:
                require(bool(fifo_pending) and sequence==next(iter(fifo_pending)),
                        'FIFO consumer has no ordered serialized producer')
                del fifo_pending[sequence];fifo_consumed[sequence]=line
            target=stage=='native_deferred_empty_record_consumed' and event.get('record_type') in weather.SIZES
            if target or sequence in seen:
                require(target and sequence in pending and sequence==next(iter(pending)),
                        'FIFO consumption has no ordered producer or is repeated')
                row=pending[sequence];receiver=receivers[row['record_type']]
                require(line<row['transition_last_line']
                    and type(event.get('record_type')) is int and event['record_type']==row['record_type']
                    and type(event.get('record_size')) is int and event['record_size']==row['record_size']
                    and event.get('handler_va')==receiver['handler_va']
                    and event.get('gameplay_event_name')==receiver['event_name']
                    and event.get('native_handler_has_no_gameplay_callback_in_this_profile') is True
                    and event.get('native_profiling_reproduced') is False
                    and event.get('eligible_for_training') is False,'receiver or storage lifetime differs')
                row.update(consumed_line=line,gameplay_event_name=receiver['event_name'])
                if 'opaque_array_pointer' in row:del leases[row['opaque_array_pointer']]
                reviewed.append(row);del pending[sequence]
    require(next_combat_receipt is None,'F8 producer lacks its adjacent detailed receipt')
    require(not combat_pending and not combat_tokens,'F8 producer lacks its native post-hook consumption')
    require(not pending and not leases,'producer lacks its FIFO consumption')
    require(not track_fifo or not fifo_pending,'FIFO producer lacks its consumption')
    require(not empty_presentation_omissions or installation is not None,
            'empty presentation source lacks its fixed family installation')
    for row in [*omissions,*empty_omissions]:
        require(all(sequence in fifo_consumed and row['line']<fifo_consumed[sequence]<row['transition_last_line']
                    for sequence in row['preceding_pending_sequences']),
                'omission preceding FIFO record escapes its completed transition')
    return dict(records=reviewed,record_count=len(reviewed),array_record_count=sum('array_count' in r for r in reviewed),
        presentation_omissions=omissions,presentation_omission_count=len(omissions),
        empty_presentation_omissions=empty_omissions,empty_presentation_omission_count=len(empty_omissions),
        empty_presentation_family_installation=installation,
        combat_diagnostic_records=combat_reviewed,combat_diagnostic_record_count=len(combat_reviewed),
        combat_post_hook_count=len(combat_reviewed),
        information_scope='administrative-unfiltered',public_visibility_qualified=False,
        native_pointer_dereferenced_during_review=False,array_bytes_reobserved_during_review=False,
        array_lifetime_evidence='source-bound consumer checks its owned snapshot before FIFO commit')


def review_xp2_weather_favor(run, closure, report, archive, intervals):
    """Read-only interval evidence, independent of session acceptance status."""
    import zipfile
    from civ6_host.runtime import xp2_turn_event_profile as weather
    from civ6_host.runtime import xp2_weather_lifecycle as lifecycle
    from civ6_host.runtime import xp2_feature_reveal_source as feature
    from civ6_host.runtime.a0_family_source import _path
    from civ6_host.runtime.stdout_transport_profiles import session_records
    if closure.get('input_profile')!='xp2-lan':
        raise ValueError('XP2 weather/Favor review requires the explicit XP2 closure')
    # Explicit historical implementations reviewed with retained native08/09.
    # Their bytes must still be present in the supplied execution archive; these
    # hashes never admit the new omission policy or stand in for its producer.
    legacy={'a0_xp2_turn_events':'ef3fecbcd9d70dbf60c91d15f7473fe8a46579bfe2153d15850c353781aa9567',
            'xp2_turn_event_profile':'38b544ee526bf5d242325aaea0dd0370bc829339cf03189a2ced8f9b871672f2'}
    scope_path=str(_path(weather.SCOPE_SOURCE[0]).resolve())
    lifecycle_path=str(_path(lifecycle.SOURCE[0]).resolve())
    with_lifecycle=scope_path in closure['pins'] or lifecycle_path in closure['pins']
    if with_lifecycle:
        dependencies=weather.source_dependencies()
    else:
        weather.source()
        from civ6_host.runtime import xp2_turn_event_records as records, xp2_favor_event_profile as favor
        from civ6_host.runtime import xp2_weather_position as position, xp2_storm_query as storm
        from civ6_host.runtime import xp2_descriptor53_query as drought
        dependencies={str(_path(weather.SOURCE[0]).resolve()):weather.SOURCE[1]}
        for module in (records,favor,position,storm,drought):
            for path,sha in module.source_dependencies().items():
                if path in dependencies and dependencies[path]!=sha:
                    raise ValueError('XP2 legacy weather/Favor source pin conflict')
                dependencies[path]=sha
    native_records=list(session_records(run,report=report))
    with_combat=any(event['stage'] in ('native_combat_record_enqueued','native_combat_post_hook_consumed')
        or (event['stage']=='native_deferred_host_event_enqueued'
            and type(event.get('record_hex')) is str and event['record_hex'][8:16]=='f8000000')
        for _,_,event in native_records)
    combat_modules=('native/native_host_events','xp1_combat_profile','xp2_combat_event_source',
        'combat_map_profiles','combat_event_profile','a0_combat_events','deferred_service',
        'native/native_event_8256dbe1','native/native_combat_argument_snapshot',
        'native/native_combat_map_owner','native/native_combat_receiver')
    if with_combat:
        from civ6_host.runtime import xp2_combat_event_source as combat
        from civ6_host.runtime.combat_map_profiles import RECEIVER_SOURCE
        if combat.SOURCE!=_XP2_COMBAT_DIAGNOSTIC_SOURCE:
            raise ValueError('XP2 combat diagnostic source is unreviewed')
        combat_pins=combat.source_dependencies()
        combat_pins[str(_path(RECEIVER_SOURCE[0]).resolve())]=RECEIVER_SOURCE[1]
        for path,sha in combat_pins.items():
            if path in dependencies and dependencies[path]!=sha:
                raise ValueError('XP2 combat diagnostic source pin conflict')
            dependencies[path]=sha
    feature_modules=('empty_presentation_events','xp2_feature_reveal_source',
        'a0_family_service','a0_family_source','a0_foundation_events','xp1_continuation',
        'event_argument_service','event_argument_source','deferred_service',
        'xp1_saved_load_composition','xp1_session_inputs','configuration_profiles',
        'native/native_host_event_registry','native/native_absent_unit_scalar_family',
        'native/native_event_argument_tree','native/native_host_events','native/native_deferred_empty_profile')
    feature_paths=[str(_path(feature.SOURCE[0]).resolve()),
        *(str((q.REPO/('src/civ6_host/runtime/'+m+'.py')).resolve())
          for m in ('empty_presentation_events','xp2_feature_reveal_source'))]
    with_feature=any(path in closure['pins'] for path in feature_paths)
    if with_feature:
        if not with_lifecycle:raise ValueError('XP2 empty presentation requires its executed lifecycle composition')
        for path,sha in feature.source_dependencies().items():
            if path in dependencies and dependencies[path]!=sha:
                raise ValueError('XP2 empty presentation source pin conflict')
            dependencies[path]=sha
    if any(closure['pins'].get(path)!=sha or pin(path)['sha256']!=sha for path,sha in dependencies.items()):
        raise ValueError('XP2 weather/Favor source profile differs from executed closure')
    modules=('a0_xp2_turn_events','xp2_turn_event_profile','xp2_turn_event_records','xp2_favor_event_profile',
        'xp2_weather_position','xp2_storm_query','xp2_descriptor53_query',
        'native/native_host_events','native/native_deferred_empty_profile')
    # This exact first lifecycle implementation is retained in native15. Later
    # current implementations additionally require their own archived bytes.
    lifecycle_versions={
        'a0_xp2_turn_events':'d64bcb00053da2daa324698df38019f0d928054f3433de7a06000e4949f92024',
        'xp2_turn_event_profile':'c7e5c03ff2206c4b73d246febf063a7f23080ecf8b99b5ed944b1927e459174a',
        'xp2_weather_lifecycle':'e35f7a43e5e518d89fd6d7b313a6527334dbd4921341eecbc08fdbc522ffc2aa',
        'a0_family_service':'9cd30dbce17c86634ef41f22c28c21c279b375a51f9531ff8b60e1cda0a91dd1',
        'a0_foundation_events':'3a40f6f690e12e12afd929f5b974eb63822701dad10d7a0792158862774969d4',
        'event_argument_service':'bb7dc1dc4eb2ab87acc42f83dbcd5b3d0621ec06f70ba75d94c0e92f2e67c01d',
        'deferred_service':'b1550cd58594586bc66d14ab5760427498fec0c33c9ce1544fd7e8c01ba80e12',
        'xp1_continuation':'421be51fbf443fbc9e498b130bccb19fbe304a6c95fbd2d901eab17365883685'}
    if with_lifecycle:
        modules=(*modules,'xp2_weather_lifecycle','a0_family_service','a0_foundation_events',
                 'event_argument_service','deferred_service','xp1_continuation')
    if with_feature:modules=tuple(dict.fromkeys((*modules,*feature_modules)))
    if with_combat:modules=tuple(dict.fromkeys((*modules,*combat_modules)))
    # Exact legacy08 body reviewed against current AST: only
    # NativeDeferredHostEvents._enqueue_combat adds the combat-specific
    # administrative_snapshot_policy keyword expansion; every other method and
    # all weather paths are identical. This pin also occurs in native15.
    reviewed_shared={'native/native_host_events':
        'fad6ceb4725d288778b7d9b663774b77bbf87576c812c539e0f3ea1e08e5e34d'}
    executed={}
    with zipfile.ZipFile(archive) as saved:
        names=saved.namelist()
        if len(names)!=len(set(names)):raise ValueError('XP2 weather/Favor archive has duplicate members')
        for module in modules:
            name='src/civ6_host/runtime/'+module+'.py';path=(q.REPO/name).resolve()
            sha=closure['pins'].get(str(path))
            allowed=({legacy[module]} if not with_lifecycle and module in legacy
                     else {pin(path)['sha256']})
            if with_lifecycle and module in lifecycle_versions:allowed.add(lifecycle_versions[module])
            if module in reviewed_shared:allowed.add(reviewed_shared[module])
            # Generic omissions require the current fixed source, registry,
            # synchronous borrower and installation path, never legacy adapters.
            if with_feature and module in feature_modules:allowed={pin(path)['sha256']}
            if with_combat and module in combat_modules:allowed={pin(path)['sha256']}
            # Reviewed _enqueue_combat emits one enqueue and then its adjacent
            # detailed receipt for the same record variable and native token.
            if with_combat and module=='native/native_host_events':
                allowed={_XP2_COMBAT_DIAGNOSTIC_PRODUCER_SHA256}
            if (name not in names or saved.getinfo(name).file_size>4*1024*1024
                    or sha not in allowed or hashlib.sha256(saved.read(name)).hexdigest()!=sha):
                raise ValueError('XP2 weather/Favor implementation differs from executed source: '+name)
            executed[name]=sha
    result=_xp2_weather_favor_records(native_records,intervals,
                                    lifecycle_omissions=with_lifecycle,
                                    empty_presentation_omissions=with_feature,
                                    combat_diagnostic_receipts=with_combat)
    result['executed_weather_contract']='lifecycle-empty-presentation' if with_lifecycle else 'legacy-records'
    result['executed_empty_presentation_contract']=feature.SOURCE[1] if with_feature else None
    result['executed_combat_diagnostic_contract']=_XP2_COMBAT_DIAGNOSTIC_SOURCE[1] if with_combat else None
    result.update(source_profiles=dependencies,executed_sources=executed,transcript=pin(Path(run)/'events.jsonl'))
    return result


def review_session_identity(closure, *, production_queue=False, placement=False, combat=False):
    """Bind the explicit saved family to its immutable input and source pins."""
    from civ6_host.runtime.captured_session_profile import for_family
    from civ6_host.runtime.paths import resource_root
    from civ6_host.runtime.resource_resolution import resolve_path
    if (type(production_queue) is not bool or type(placement) is not bool
            or type(closure) is not dict or closure.get('schema')!='civ6-host.session.closure.v1'
            or closure.get('input_profile') not in ('xp1-lan','xp2-lan')
            or type(closure.get('pins')) is not dict or closure.get('close_loaded_candidate') is not True):
        raise ValueError('Review requires an explicit source-bound expansion session closure')
    candidate=for_family(closure['input_profile']).candidate
    selected=q.saved_load_review_profile(candidate.core_sha256)
    if closure.get('official_bundle')!=dict(path=candidate.reference[0],sha256=candidate.reference[1]):
        raise ValueError('Session capture does not match its selected Core engine')
    references=(candidate.reference,selected['job']['source'],selected['unit_source'],selected['turn_ui_source'])
    if selected['xp2'] and production_queue:
        from civ6_host.runtime.xp2_production_queue_source import SOURCE as QUEUE_SOURCE
        references=(*references,QUEUE_SOURCE)
    if selected['xp2'] and placement:
        from civ6_host.runtime.xp2_production_placement_source import SOURCE as PLACEMENT_SOURCE
        references=(*references,PLACEMENT_SOURCE)
    if type(combat) is not bool:raise ValueError('Combat source selection must be Boolean')
    if combat:
        from civ6_host.runtime.xp1_unit_attack_profile import source_reference,precision_reference,READINESS_SOURCE
        references=(*references,source_reference(selected['core_sha256']),precision_reference(selected['core_sha256']))
        if not selected['xp2']:references=(*references,READINESS_SOURCE)
    selected['legacy_unpinned_job_source']=None
    for name,sha in references:
        path=resolve_path(resource_root()/name).resolve()
        recorded=closure['pins'].get(str(path))
        # Retained XP1 session closures predate the transitive JSON job pin.
        # Its exact digest is still checked here and in the original receipts;
        # report the gap, never relabel it as a newly executed source pin.
        legacy=(not selected['xp2'] and name==selected['job']['source'][0] and recorded is None)
        if (not legacy and recorded!=sha) or pin(path)['sha256']!=sha:
            raise ValueError('Session engine source/input differs from its closure pin: '+name)
        if legacy:selected['legacy_unpinned_job_source']=dict(path=name,sha256=sha)
    if selected['xp2']:
        from civ6_host.runtime.stdout_transport_profiles import validate_profile
        transport=closure.get('stdout_transport')
        validate_profile(transport)
        if transport['core_sha256']!=candidate.core_sha256:
            raise ValueError('Session stdout selects a different Core engine')
    return selected


def review_session_job_identity(closure, snapshot, selected, *, transition=False):
    """Keep Core/source/build identities joined to the actually executed pins."""
    q.saved_load_validate_engine(snapshot,selected['core_sha256'],allow_legacy_transition=transition)
    core=snapshot.get('core_identity')
    if core is None:return  # Exact retained XP1 transition shape; later snapshots carry the owner.
    build=snapshot.get('source_build')
    if (type(build) is not dict or type(build.get('sources')) is not dict
            or build['sources'].get('gamecore_python_host.c')!=selected['job']['host_component_sha']
            or closure['pins'].get(str(Path(core.get('path','')).resolve()))!=selected['core_sha256']
            or closure['pins'].get(str(Path(build.get('executable_path','')).resolve()))!=build.get('host_sha256')):
        raise ValueError('Session scheduler Core/build is outside the exact executed closure')
    transport=closure.get('stdout_transport')
    if transport is not None and transport['host_sha256']!=build['host_sha256']:
        raise ValueError('Session stdout and job ledger identify different host builds')


def project_preparer_receipt(value, archive):
    """Project only the retained preparer's completed pending-review shape.

    This authenticates metadata and archived source identity. The ordinary
    reviewer still has to prove every native interval, Save and normal close.
    """
    import copy
    import zipfile
    fields={'status','training','public_selector','commands','runs','input_checkpoint',
            'turns_advanced','poll_calls','selector_sha256','combat_information',
            'offered_attacks','prepared_public','checkpoint','seconds'}
    partial=value.get('status')=='partial_public_exploration_checkpoint_retained' if type(value) is dict else False
    if partial:
        fields-= {'offered_attacks','prepared_public'}
        if 'stop_reason' in value:fields.add('stop_reason')
    if (type(value) is not dict or set(value)!=fields
            or value['status'] not in ('native_unit_attack_checkpoint_prepared_pending_review','partial_public_exploration_checkpoint_retained')
            or value['training'] is not False or value['public_selector'] is not True
            or type(value['runs']) is not list or len(value['runs'])!=1
            or type(value['commands']) is not list
            or type(value['turns_advanced']) is not int or not 0<=value['turns_advanced']<=48
            or type(value['poll_calls']) is not int or value['poll_calls']<0
            or len(value['commands'])+value['poll_calls']>48
            or not partial and (type(value['prepared_public']) is not str
                or type(value['offered_attacks']) is not list or not value['offered_attacks'])):
        raise ValueError('Preparation is not the completed public-selector receipt shape')
    item=value['runs'][0]
    if (type(item) is not dict or set(item)!={'run','report','checkpoint',
            'reset_timings_seconds','initial_native_remaining_seconds'}
            or type(item['run']) is not str or not Path(item['run']).is_absolute()
            or item['checkpoint']!=value['checkpoint'] or item['checkpoint'] is None):
        raise ValueError('Preparation lacks its single actual supervised Save')
    run=Path(item['run']).resolve();closure=json.loads((run/'closure.json').read_bytes())
    if partial:
        if closure['input_profile']!='xp2-lan' or value.get('stop_reason') not in (None,'no_action_or_turn_progress_in_this_lifetime'):
            raise ValueError('Partial exploration review requires its explicit XP2 selector receipt')
    else:
        prepared=Path(value['prepared_public']).resolve()
        if prepared.parent!=run or prepared.name not in {p.name for p in run.glob('public-*.json')}:
            raise ValueError('Prepared public revision is outside its producing run')
    from civ6_host.runtime import network_checkpoint
    loaded=closure.get('network_checkpoint')
    if not value['commands'] and closure['input_profile']!='xp2-lan':
        raise ValueError('Historical preparation requires its native commands')
    if ((value['input_checkpoint'] is None)!=(loaded is None)
            or loaded is not None and network_checkpoint.normalize(value['input_checkpoint'])!=network_checkpoint.normalize(loaded)):
        raise ValueError('Preparation input differs from the actual loaded checkpoint')
    sources={Path(p).relative_to(q.REPO).as_posix():sha for p,sha in closure['pins'].items()
             if Path(p).is_relative_to(q.REPO) and Path(p).suffix=='.py'}
    selector='tools/unit_attack_preparation.py'
    with zipfile.ZipFile(archive) as saved:
        names=saved.namelist()
        if (not sources or len(names)!=len(set(names)) or selector not in names
                or saved.getinfo(selector).file_size>4*1024*1024
                or hashlib.sha256(saved.read(selector)).hexdigest()!=value['selector_sha256']
                or any(name not in names or saved.getinfo(name).file_size>4*1024*1024
                       or hashlib.sha256(saved.read(name)).hexdigest()!=sha for name,sha in sources.items())):
            raise ValueError('Preparation selector/archive differs from its executed source pins')
    projected=copy.deepcopy(value)
    projected.update(status='native_unit_attack_preparation_checkpoint_saved',
                     supervised_runs=projected.pop('runs'))
    return projected,dict(original_status=value['status'],projection_only=True,
        original_files_modified=False,executed_sources_archive=pin(archive),
        source_selector=dict(archive_member=selector,sha256=value['selector_sha256']),
        executed_host_python_source_count=len(sources))


def review_prepared_attack_boundary(acceptance, rows):
    """Join declared offers to the fully authenticated final public/Save boundary."""
    if len(rows)!=1:raise ValueError('Prepared attack requires its single reviewed native lifetime')
    row=rows[0];live=[p for p in row['public'] if p['decisions'].get('unit_attacks') is not None]
    final=live[-1] if live else None
    if (final is None or final['reference']['path']!=str(Path(acceptance['prepared_public']).resolve())
            or acceptance['offered_attacks']!=final['decisions']['unit_attacks']['offers']
            or not acceptance['offered_attacks']
            or any(sum(candidate['action']==action for candidate in final['candidates'])!=1
                   for action in acceptance['offered_attacks'])
            or acceptance['checkpoint']!=row['ledger']['checkpoint']['phase_receipt']['manifest_reference']
            or acceptance['runs'][0]['checkpoint']!=acceptance['checkpoint']):
        raise ValueError('Declared prepared offers/public revision/Save differ from actual native receipts')
    return dict(prepared_public=final['reference'],sequence=final['sequence'],turn=final['turn'],
        offered_attacks=acceptance['offered_attacks'],checkpoint=acceptance['checkpoint'],
        native_ledger_save_and_close_authenticated=True,attack_execution_claimed=False)


_POST_CLOSE_COMBAT_ACCEPTANCE_SHA256='902eb83dd5a4afe77a45a20efd3ab55d7480feb53213de366f04a7665cf76d4a'
_POST_CLOSE_COMBAT_ARCHIVE_SHA256='18af9017fbdc5f845ada67683fb3647ab51bb19300725cbd8cfef7aaa4738ad4'
_POST_CLOSE_COMBAT_SCRIPT_SHA256='57dfa9e47ea6fd11e16f85412aee859143e24e12ba2919c40d97abb565a7c724'


def project_post_close_combat_query_refusal(acceptance_path, archive):
    """Admit only the known parent query-after-close error to offline review.

    The original refusal is immutable. No native response or supervisor is
    projected; the ordinary complete native review must still pass afterward.
    """
    import copy
    import zipfile
    acceptance_path=Path(acceptance_path).resolve();archive=Path(archive).resolve()
    if (pin(acceptance_path)['sha256']!=_POST_CLOSE_COMBAT_ACCEPTANCE_SHA256
            or pin(archive)['sha256']!=_POST_CLOSE_COMBAT_ARCHIVE_SHA256):
        raise ValueError('Post-close combat review requires its exact retained acceptance and executed archive')
    value=json.loads(acceptance_path.read_bytes())
    expected_runs=('run-b6b1a76d5d3f49a1b97631cfb0f063e5','run-fd62ca2f98e2486bb00f1feb13346901')
    if (value.get('status')!='refused'
            or value.get('error')!="InformationUnavailable('Reset and observe an active session first')"
            or value.get('script_sha256')!=_POST_CLOSE_COMBAT_SCRIPT_SHA256
            or value.get('training') is not False or len(value.get('supervised_runs',[]))!=2
            or tuple(Path(row['run']).name for row in value['supervised_runs'])!=expected_runs
            or type(value.get('combat_information')) is not list or len(value['combat_information'])!=2
            or 'line 1592, in main' not in value.get('traceback','')
            or "record['combat_information'].append(combat_information_snapshot(client,fresh))" not in value['traceback']
            or acceptance_path.parent!=Path(value['supervised_runs'][1]['run']).resolve()
            or len(value.get('commands',[]))!=1 or value['commands'][0].get('status')!='completed'
            or value['commands'][0].get('requested_action')!=value.get('unit_attack_group',{}).get('action')
            or value['unit_attack_group'].get('poll_calls')!=0):
        raise ValueError('Retained refusal is not the exact completed attack/reset post-close query error')
    closures=[]
    for row in value['supervised_runs']:
        run=Path(row['run']);report=json.loads((run/'supervisor.json').read_bytes())
        closure=json.loads((run/'closure.json').read_bytes())
        if (report!=row['report'] or report.get('reaped') is not True or report.get('exit_code')!=90
                or report.get('normal_destroy_called') is not True or report.get('error') is not None
                or report.get('timed_out') is not False or not report.get('source_unchanged')
                or not all(v is True for v in report['source_unchanged'].values())
                or closure.get('input_profile')!='xp2-lan'):
            raise ValueError('Post-close query projection cannot repair a native lifetime or source failure')
        closures.append(closure)
    changed=[];archived={}
    allowed={'tools/accept_session.py','tools/review_xp1_session.py','tools/review_unit_attacks.py'}
    with zipfile.ZipFile(archive) as saved:
        names=saved.namelist()
        if len(names)!=len(set(names)) or sum(i.file_size for i in saved.infolist())>64*1024*1024:
            raise ValueError('Post-close combat archive has duplicate/oversized members')
        for name in names:
            relative=Path(name)
            if relative.is_absolute() or relative.drive or '..' in relative.parts or saved.getinfo(name).file_size>8*1024*1024:
                raise ValueError('Post-close combat archive member escaped its exact host source root')
            data=saved.read(name);sha=hashlib.sha256(data).hexdigest();archived[name]=sha
            current=pin(q.REPO/relative)
            if current['sha256']!=sha:
                if name not in allowed:raise ValueError('Executed runtime/source changed outside the explicit reader fix: '+name)
                changed.append(dict(path=name,executed_sha256=sha,current_sha256=current['sha256'],
                    classification='qualification_reader_change_only',native_execution_repeated=False))
        script=saved.read('tools/accept_session.py')
        if (hashlib.sha256(script).hexdigest()!=value['script_sha256']
                or script.splitlines()[1591].strip()!=b"record['combat_information'].append(combat_information_snapshot(client,fresh))"):
            raise ValueError('Archived acceptance does not contain the executed query-after-close site')
        # The forward fix is exactly this move, not substitution of a different
        # accepted scenario or executed client implementation.
        old=b"            record['replacement_episode'] = fresh['episode_id']\n            save_view(client.close(pid))"
        new=b"            record['replacement_episode'] = fresh['episode_id']\n            if args.unit_attack_group and config.get('administrative_information') is True:\n                record['combat_information'].append(combat_information_snapshot(client,fresh))\n            save_view(client.close(pid))"
        late=b"            if args.unit_attack_group:\n                if config.get('administrative_information') is True:\n                    record['combat_information'].append(combat_information_snapshot(client,fresh))\n"
        if script.count(old)!=1 or script.count(late)!=1:
            raise ValueError('Archived post-close query move has a different exact preimage')
        expected=script.replace(old,new).replace(late,b'            if args.unit_attack_group:\n')
        if (q.REPO/'tools/accept_session.py').read_bytes()!=expected:
            raise ValueError('Current acceptance differs from the exact reviewed query-before-close fix')
        for closure in closures:
            sources={Path(path).resolve().relative_to(q.REPO.resolve()).as_posix():sha
                     for path,sha in closure['pins'].items()
                     if Path(path).is_absolute() and Path(path).resolve().is_relative_to(q.REPO.resolve())
                     and path.endswith('.py')}
            if not sources or any(archived.get(name)!=sha for name,sha in sources.items()):
                raise ValueError('Post-close combat archive differs from the complete executed host Python closure')
    projected=copy.deepcopy(value);projected['status']='native_capability_unit_attack_group_reset_verified'
    return projected,dict(classification='single_known_post_close_combat_query_refusal',
        original_acceptance=pin(acceptance_path),original_status=value['status'],original_error=value['error'],
        original_traceback_sha256=hashlib.sha256(value['traceback'].encode()).hexdigest(),
        executed_sources_archive=pin(archive),executed_acceptance_script_sha256=value['script_sha256'],
        archived_file_count=len(archived),executed_host_python_source_count=len(sources),
        source_transitions=changed,projection_only=True,original_files_modified=False,
        native_responses_modified=False,supervisors_modified=False,
        recorded_live_combat_query_count=2,reset_combat_query_live_executed=False,
        replay_after_full_native_authentication_required=True)


def review(acceptance_path, archive, *, stdout_parser_replay=None,replay_post_close_combat_information=False):
    acceptance=json.loads(Path(acceptance_path).read_bytes())
    preparation_correction=None
    preparer_receipt=None
    combat_query_correction=None
    if type(replay_post_close_combat_information) is not bool:
        raise ValueError('Post-close combat replay must be an explicit Boolean')
    if replay_post_close_combat_information:
        if stdout_parser_replay is not None:raise ValueError('Post-close combat replay cannot repair a supervisor refusal')
        acceptance,combat_query_correction=project_post_close_combat_query_refusal(acceptance_path,archive)
    if acceptance.get('status') in ('native_unit_attack_checkpoint_prepared_pending_review','partial_public_exploration_checkpoint_retained'):
        if stdout_parser_replay is not None:
            raise ValueError('Normally closed preparation cannot use parser-refusal replay')
        preparer_receipt=acceptance
        acceptance,preparation_correction=project_preparer_receipt(acceptance,archive)
        preparation_correction['original_preparation']=pin(acceptance_path)
    if stdout_parser_replay is not None:
        if (type(stdout_parser_replay) is not dict
                or set(stdout_parser_replay)!={'run','supervisor_sha256','archive_sha256'}):
            raise ValueError('Parser-only replay requires exact retained run and source identities')
        if acceptance.get('status')=='refused':
            import copy
            if (acceptance.get('error')!="RuntimeError('Native session did not close with unchanged inputs and controlled exit')"
                    or acceptance.get('training') is not False
                    or acceptance.get('public_selector') is not True
                    or len(acceptance.get('runs',[]))!=1
                    or acceptance['runs'][0]['run']!=stdout_parser_replay['run']):
                raise ValueError('Retained preparation is not the exact close-parser refusal')
            original=acceptance;acceptance=copy.deepcopy(original)
            run=Path(stdout_parser_replay['run'])
            initial=json.loads((run/'public-0000.json').read_bytes())
            final=json.loads(sorted(run.glob('public-*.json'))[-1].read_bytes())
            acceptance.update(status='native_unit_attack_preparation_checkpoint_saved',
                supervised_runs=acceptance.pop('runs'),
                turns_advanced=final['observation']['turn']-initial['observation']['turn'])
            preparation_correction=dict(original_preparation=pin(acceptance_path),
                original_status=original['status'],original_error=original['error'],
                original_turns_advanced=original['turns_advanced'],
                reviewed_turns_advanced=acceptance['turns_advanced'],
                projection_only=True,original_files_modified=False)
    if acceptance['status'] not in ('native_capability_foundation_reset_verified',
                                    'native_capability_choice_group_reset_verified',
                                    'native_capability_turn_group_reset_verified',
                                    'native_capability_world_input_group_reset_verified',
                                    'native_capability_unit_order_group_reset_verified',
                                    'native_capability_unit_order_group_incomplete',
                                    'native_capability_production_queue_group_reset_verified',
                                    'native_capability_placement_group_reset_verified',
                                    'native_placement_inventory_checkpoint_reset_verified',
                                    'native_capability_unit_attack_group_reset_verified',
                                    'native_unit_attack_preparation_turn_saved',
                                    'native_unit_attack_preparation_checkpoint_saved',
                                    'native_xp1_checkpoint_cycle_verified',
                                    'native_xp2_checkpoint_cycle_verified',
                                    'native_expansion_city_controls_observed',
                                    'native_xp2_city_placement_checkpoint_observed'):
        raise ValueError('Acceptance group did not complete')
    city_group=acceptance['status']=='native_expansion_city_controls_observed'
    city_checkpoint_group=acceptance['status']=='native_xp2_city_placement_checkpoint_observed'
    city_v12=city_group or city_checkpoint_group
    turn_group=acceptance['status']=='native_capability_turn_group_reset_verified'
    world_group=acceptance['status']=='native_capability_world_input_group_reset_verified'
    order_group=acceptance['status'] in ('native_capability_unit_order_group_reset_verified',
                                       'native_capability_unit_order_group_incomplete')
    xp2_checkpoint_group=acceptance['status']=='native_xp2_checkpoint_cycle_verified'
    checkpoint_group=acceptance['status'] in ('native_xp1_checkpoint_cycle_verified','native_xp2_checkpoint_cycle_verified')
    queue_group=acceptance['status']=='native_capability_production_queue_group_reset_verified'
    placement_group=acceptance['status']=='native_capability_placement_group_reset_verified'
    placement_commands=placement_group or city_checkpoint_group
    placement_preparation=acceptance.get('placement_preparation')
    if city_checkpoint_group and (type(placement_preparation) is not dict
            or len(acceptance['supervised_runs'])!=1):
        raise ValueError('City placement checkpoint requires one prepared native lifetime')
    if placement_preparation is not None and not placement_commands:
        raise ValueError('Placement preparation requires its exact placement group')
    inventory_group=acceptance['status']=='native_placement_inventory_checkpoint_reset_verified'
    attack_group=acceptance['status']=='native_capability_unit_attack_group_reset_verified'
    preparation_group=acceptance['status'] in ('native_unit_attack_preparation_turn_saved',
                                             'native_unit_attack_preparation_checkpoint_saved')
    persistence_group=checkpoint_group or inventory_group or preparation_group or city_checkpoint_group
    input_group=world_group or order_group or persistence_group or queue_group or placement_group or attack_group or city_group
    transition_group=turn_group or input_group
    rows=[];selected_engine=None
    if stdout_parser_replay is not None and (len(acceptance['supervised_runs'])!=1
            or acceptance['supervised_runs'][0]['run']!=stdout_parser_replay['run']):
        raise ValueError('Parser-only replay must select exactly its original single run')
    for item in acceptance['supervised_runs']:
        run=Path(item['run']);report=json.loads((run/'supervisor.json').read_bytes())
        if report!=item['report']:
            raise ValueError('Client report differs from its retained supervisor')
        parser_correction=None
        if stdout_parser_replay is not None:
            report,parser_correction=q.replay_saved_close_parser_refusal(run,stdout_parser_replay['supervisor_sha256'],
                archive=archive,archive_sha256=stdout_parser_replay['archive_sha256'])
        if (report['exit_code']!=90 or not report['reaped']
                or report['error'] is not None or report['normal_destroy_called'] is not True):
            raise ValueError('Client cycle lacks clean authenticated native teardown')
        closure=json.loads((run/'closure.json').read_bytes());pins=dict(closure['pins'])
        selected=review_session_identity(closure,production_queue=queue_group,placement=placement_commands or inventory_group,combat=attack_group or preparation_group)
        if selected_engine is not None and selected_engine['core_sha256']!=selected['core_sha256']:
            raise ValueError('Reset cannot substitute another captured engine')
        selected_engine=selected
        city_sources=review_city_sources(acceptance,closure,archive,selected,
            city_checkpoint=city_checkpoint_group) if city_v12 else None
        if checkpoint_group and xp2_checkpoint_group is not selected['xp2']:
            raise ValueError('Checkpoint acceptance status selects another captured engine')
        if selected['xp2'] and input_group and not (world_group or order_group or queue_group or placement_commands or xp2_checkpoint_group or attack_group or preparation_group or city_v12):
            raise ValueError('XP2 session review is limited to explicitly source-selected captured families')
        engine_options=dict(core_sha256=selected['core_sha256'],session_supervision=True)
        lifetime_seconds=review_lifetime_seconds(closure,report,placement_preparation=placement_preparation,
            city_checkpoint=city_checkpoint_group)
        if placement_preparation is not None:
            from accept_session import placement_preparation_identity
            expected_identity=placement_preparation_identity(dict(prepared_capture=closure['prepared_capture']))
            if placement_preparation['source_identity']!=expected_identity:
                raise ValueError('Placement preparation differs from the captured prerequisite database')
            if pins.get(expected_identity['database']['path'])!=expected_identity['database']['sha256']:
                raise ValueError('Placement prerequisite database is outside the executed closure')
            engine_options['placement_preparation']=True
        resumed_placement=(placement_group or inventory_group) and closure.get('network_checkpoint') is not None
        pins[str((run/'closure.json').resolve())]=pin(run/'closure.json')['sha256']
        event_path=run/'events.jsonl'
        def events(**kwargs):
            transport=closure.get('stdout_transport')
            return q.saved_load_events(event_path,allow_multiple_commands=True,
                                       allow_turn_updates=transition_group,allow_world_input=input_group,
                                       allow_unit_orders=order_group or checkpoint_group,
                                       allow_checkpoint=persistence_group or resumed_placement or attack_group,allow_production_queue=queue_group,allow_placements=placement_commands or inventory_group,allow_unit_attacks=attack_group,
                                       allow_city_controls=city_group,
                                       stdout_transport=transport,stdout_native_records=report.get('stdout_native_records',[]) if transport else None,
                                       stdout_limit_bytes=closure['stdout_limit_bytes'],**kwargs)[1]
        e=events(require_load_interval=True)
        if placement_group and ('before_xp1_saved_checkpoint' in e or closure.get('checkpoint_on_close') is not False):
            raise ValueError('Placement acceptance cannot create an unreviewed checkpoint')
        raw=q.saved_load_result_file(run,e['xp1_saved_raw_load_observed'],'raw-load-result.json')
        review_session_job_identity(closure,raw['raw_load_receipt']['jobs_structural_candidate'],selected,transition=True)
        ledgers={}
        ledgers['load']=q.saved_load_reconcile_jobs(report,pins,raw,e['load_job_interval'],lifetime_seconds=lifetime_seconds,**engine_options)
        e=events(require_post160_interval=True)
        post=q.saved_load_result_file(run,e['xp1_saved_post160_sequence_returned'],'post160-result.json')
        prior=ledgers['post160']=q.saved_load_reconcile_post160(report,pins,raw,post,e,ledgers['load'],lifetime_seconds=lifetime_seconds,**engine_options)
        review_session_job_identity(closure,prior['final_jobs'],selected)
        for phase,stage,filename in (
                ('publication','xp1_saved_cache_publication_returned','publication-result.json'),
                ('player_view','xp1_saved_player_view_returned','player-view-result.json')):
            e=events(require_interval=phase)
            result=q.saved_load_result_file(run,e[stage],filename)
            prior=ledgers[phase]=q.saved_load_reconcile_later(report,pins,raw,result,e,prior,
                                                           phase=phase,lifetime_seconds=lifetime_seconds,**engine_options)
        public_views={}
        for path in sorted(run.glob('public-*.json')):
            view=json.loads(path.read_bytes());seq=view['sequence']
            if (type(seq) is not int or seq<0 or seq in public_views
                    or path.name!='public-%04d.json'%seq):
                raise ValueError('Public receipt lacks a unique protocol sequence')
            if input_group:
                from civ6_host.contracts.network_turn import validate_capability_catalogue, CAPABILITY_WORLD_SCHEMA, CAPABILITY_UNIT_ORDERS_SCHEMA, CAPABILITY_PRODUCTION_QUEUE_SCHEMA, CAPABILITY_PLACEMENT_SCHEMA, CAPABILITY_PLACEMENT_INVENTORY_SCHEMA, CAPABILITY_UNIT_ATTACKS_SCHEMA, CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA,CAPABILITY_CITY_CONTROLS_SCHEMA
                from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
                if city_v12 and view['decisions']['schema']!=CAPABILITY_CITY_CONTROLS_SCHEMA:
                    raise ValueError('City acceptance requires an exact v12 public reply')
                if not city_v12 and (view['decisions']['schema'] not in (CAPABILITY_WORLD_SCHEMA,CAPABILITY_UNIT_ORDERS_SCHEMA,CAPABILITY_PRODUCTION_QUEUE_SCHEMA,CAPABILITY_PLACEMENT_SCHEMA,CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA)
                        or (order_group or checkpoint_group) and view['decisions']['schema'] not in (CAPABILITY_UNIT_ORDERS_SCHEMA,CAPABILITY_PRODUCTION_QUEUE_SCHEMA,CAPABILITY_PLACEMENT_SCHEMA,CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA)
                        or queue_group and view['decisions']['schema'] not in (CAPABILITY_PRODUCTION_QUEUE_SCHEMA,CAPABILITY_PLACEMENT_SCHEMA,CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA)
                        or placement_group and view['decisions']['schema'] not in (CAPABILITY_PLACEMENT_SCHEMA,CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA)
                        or inventory_group and view['decisions']['schema'] not in (CAPABILITY_PLACEMENT_INVENTORY_SCHEMA,CAPABILITY_UNIT_ATTACKS_SCHEMA,CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA)):
                    raise ValueError('World-input reply lacks its explicit versioned public boundary')
                validate_capability_catalogue(view['decisions'],
                    DiagnosticEpisodeIdentity(view['episode_id'],view['game_generation']),seq,
                    view['observation']['turn'],player_id=view['observation']['player_id'],
                    actions_closed=bool(view['outcome']['terminated'] or view['outcome']['truncated']),
                    observation=view['observation'])
            public_views[seq]=(path,view)
        if not public_views or min(public_views)!=0:
            raise ValueError('Client cycle lacks its initial public observation')
        initial=public_views[0][1]
        combat_events={}
        from civ6_host.contracts.network_turn import CAPABILITY_COMBAT_PUBLIC_SCHEMA, CAPABILITY_COMBAT_READINESS_SCHEMA
        if city_v12 or initial['decisions']['schema'] in (CAPABILITY_COMBAT_PUBLIC_SCHEMA,CAPABILITY_COMBAT_READINESS_SCHEMA):
            from review_unit_attacks import combat_readbacks
            combat_events=combat_readbacks(run,public_views,core_sha256=selected['core_sha256'])
        placement_input=(review_placement_input(closure,e,initial,allow_native_save=inventory_group or city_checkpoint_group or preparer_receipt is not None,
                                              combat_evidence=combat_events.get(0),core_sha256=selected['core_sha256'])
                         if placement_commands or inventory_group or attack_group or preparer_receipt is not None else None)
        inventory_receipts=None
        inventory_required=(inventory_group or selected['xp2']
                            and any('placement_inventory' in v['decisions'] for _,v in public_views.values()))
        previous_transition=None
        if transition_group:
            if initial['observation']!=result['observation']:
                raise ValueError('Initial public observation differs from native player-view receipt')
            previous_transition=dict(episode_id=initial['episode_id'],game_generation=initial['game_generation'],
                sequence=0,publication_count=0,observation=result['observation'])
        command_rows=[];update_rows=[];transition_rows=[]
        for interval in (e['_transition_intervals'] if transition_group else e['_command_intervals']):
            seq=interval['protocol_sequence']
            phase=interval['phase'] if transition_group else 'unit_commands'
            update=phase=='turn_update'
            stage='xp1_saved_turn_update_returned' if update else 'xp1_saved_unit_commands_returned'
            filename=('update-result-' if update else 'command-result-')+str(seq)+'.json'
            command_events=events(require_interval=phase,command_sequence=seq)
            result=q.saved_load_result_file(run,command_events[stage],filename)
            prior=q.saved_load_reconcile_later(report,pins,raw,result,command_events,prior,
                phase=phase,lifetime_seconds=lifetime_seconds,previous_transition=previous_transition,
                city_controls=city_group,**engine_options)
            if transition_group:
                if seq not in public_views:
                    raise ValueError('Native transition has no matching public protocol reply')
                public_view=public_views[seq][1]
                turn_request=(not update and result['action']['kind'] in ('end_turn','force_end_turn','unready_turn'))
                command_result=(review_command_result(result,prior['phase_receipt'])
                                if not update and (turn_request or input_group) else None)
                applied=(None if update or (command_result is not None and command_result['status']!='completed')
                         else result['action'])
                if (any(public_view[k]!=result[k] for k in ('episode_id','game_generation'))
                        or public_view['observation']!=result['observation_after']
                        or public_view['applied_action']!=applied):
                    raise ValueError('Public reply differs from its native transition receipt')
                if input_group and not update:
                    previous_view=public_views[max(s for s in public_views if s<seq)][1]
                    preparing_placement=(placement_preparation is not None
                        and seq<=placement_preparation['prepared_boundary']['sequence'])
                    if city_group:
                        validate_city_public_transition(result,previous_view,public_view,prior['phase_receipt'])
                    elif preparing_placement and result['action']['kind'] in ('found_city','research','civic','end_turn','force_end_turn'):
                        if not any(r['action']==result['action'] for r in previous_view['decisions']['candidates']):
                            raise ValueError('Placement preparation command was not publicly offered')
                    elif xp2_checkpoint_group and result['action']['kind'] in ('found_city','research','civic','production','end_turn','force_end_turn','unready_turn'):
                        if not any(r['action']==result['action'] for r in previous_view['decisions']['candidates']):
                            raise ValueError('Checkpoint preparation or resumed foundation command was not publicly offered')
                    elif preparation_group and result['action']['kind'] in ('end_turn','force_end_turn','unready_turn'):
                        pass  # The shared turn validator already authenticated this request/effect.
                    elif attack_group and result['action']['kind']=='unit_attack':
                        from review_unit_attacks import validate_public_attack
                        validate_public_attack(result,previous_view,public_view,prior['phase_receipt'])
                    elif (placement_commands or inventory_group) and result['action']['kind'] in ('production_placement','production_resume','production'):
                        validate_placement_public_transition(result,previous_view,public_view,prior['phase_receipt'])
                    elif result['action']['kind']=='unit_order':
                        validate_order_public_transition(result,previous_view,public_view)
                    elif result['action']['kind'] in ('queue_append','queue_remove','queue_swap'):
                        validate_queue_public_transition(result,previous_view,public_view)
                    elif result['action']['kind']=='found_city' and queue_group:
                        if not any(r['action']==result['action'] for r in previous_view['decisions']['candidates']):
                            raise ValueError('Queue preparation foundation was not publicly offered')
                    else:
                        validate_world_public_transition(result,previous_view,public_view)
                previous_transition=prior['continuation']
            row=dict(protocol_sequence=seq,action=result['action'],ledger=prior,receipt=pin(run/filename))
            if transition_group:
                row.update(phase=phase,continuation_sequence=result['sequence'],
                           turn_before=result['observation_before']['turn'],turn_after=result['observation_after']['turn'])
                transition_rows.append(row)
                if input_group:
                    row['command_result']=command_result
            (update_rows if update else command_rows).append(row)
        ledgers['commands']=command_rows
        if transition_group:
            ledgers.update(updates=update_rows,transitions=transition_rows)
        checkpoint_sequence=None
        manifest=None
        if persistence_group and 'before_xp1_saved_checkpoint' in e:
            producer_options=({} if parser_correction is None else dict(
                reviewed_producers={str((run/'supervisor.json').resolve()):parser_correction}))
            e=events(require_interval='checkpoint')
            seq=e['xp1_saved_checkpoint_returned']['protocol_sequence']
            checkpoint_sequence=seq
            filename='checkpoint-result-'+str(seq)+'.json'
            result=q.saved_load_result_file(run,e['xp1_saved_checkpoint_returned'],filename)
            prior=ledgers['checkpoint']=q.saved_load_reconcile_later(report,pins,raw,result,e,prior,
                phase='checkpoint',lifetime_seconds=lifetime_seconds,previous_transition=previous_transition,**producer_options,**engine_options)
            ledgers['checkpoint_receipt']=pin(run/filename)
            saved_view=public_views[max(s for s in public_views if s<seq)][1]
            from civ6_host.runtime import network_checkpoint
            from civ6_host.runtime.native.native_session_resume import semantic_decisions
            manifest=network_checkpoint.manifest(prior['phase_receipt']['manifest_reference'],**producer_options)
            if (manifest['observation']!=saved_view['observation']
                    or semantic_decisions(manifest['decisions'])!=semantic_decisions(saved_view['decisions'])):
                raise ValueError('Saved checkpoint differs from the last actual public command boundary')
        e=events(require_interval='lifetime')
        result=q.saved_load_result_file(run,e['xp1_saved_loaded_close_returned'],'loaded-lifetime-result.json')
        ledgers['lifetime']=q.saved_load_reconcile_later(report,pins,raw,result,e,prior,
                                                       phase='lifetime',lifetime_seconds=lifetime_seconds,**engine_options)
        if inventory_required:
            from review_placement_inventory import validate_inventory_readback
            inventory_receipts=validate_inventory_readback(run,public_views,core_sha256=selected['core_sha256'],
                allow_authenticated_closing=xp2_checkpoint_group)
        if selected['xp2']:
            ledgers['weather_favor']=review_xp2_weather_favor(run,closure,report,archive,
                e.get('_transition_intervals',e['_command_intervals']))
        public=[]
        for path,view in (public_views[seq] for seq in sorted(public_views)):
            ob=view['observation'];dec=view['decisions']
            public.append(dict(reference=pin(path),episode_id=view['episode_id'],generation=view['game_generation'],
                sequence=view['sequence'],turn=ob['turn'],own_units=len(ob['units']),own_cities=len(ob['cities']),
                candidates=dec['candidates'],families=dec['families'],turn_controls=dec['turn_controls'],
                choice_state=dec.get('choice_state'),turn_availability=dec.get('turn_availability')))
            if input_group:
                public[-1].update(observation=ob,world_input=dec['world_input'],queued_orders=dec['queued_orders'])
                if 'unit_orders' in dec:public[-1]['unit_orders']=dec['unit_orders']
                if 'production_queues' in dec:public[-1]['production_queues']=dec['production_queues']
                for k in ('placements','placement_offers','placement_observation_scope','placement_inventory'):
                    if k in dec:public[-1][k]=dec[k]
            if persistence_group or attack_group:public[-1]['decisions']=dec
        rows.append(dict(run=str(run),closure=pin(run/'closure.json'),supervisor=pin(run/'supervisor.json'),
            transcript=pin(run/'events.jsonl'),ledger=ledgers,public=public,source_count=len(pins),
            all_source_pins_unchanged=all(report['source_unchanged'].values()),elapsed_seconds=report['elapsed_seconds'],
            memory=report['sampled_memory_peaks'],normal_native_destroy_authenticated=True,
            legacy_unpinned_job_source=selected['legacy_unpinned_job_source']))
        if parser_correction is not None:
            rows[-1]['retained_supervision_correction']=parser_correction
        if persistence_group:
            rows[-1]['checkpoint_reloaded']=e.get('official_lan_checkpoint_reloaded')
            rows[-1]['checkpoint_input']=closure.get('network_checkpoint')
            rows[-1]['checkpoint_on_close']=closure.get('checkpoint_on_close')
        if placement_commands:
            rows[-1]['placement_input']=placement_input
        if inventory_group:
            rows[-1].update(placement_input=placement_input,inventory_receipts=inventory_receipts)
        elif inventory_receipts is not None:
            rows[-1]['inventory_receipts']=inventory_receipts
        if attack_group:rows[-1]['combat_readbacks']=combat_events
        if preparer_receipt is not None:rows[-1]['preparation_input']=placement_input
        if city_group:
            rows[-1]['city_summary']=validate_city_group(acceptance,run,closure,public_views,command_rows,
                                                       update_rows,city_sources,selected)
        if city_checkpoint_group:
            rows[-1]['city_placement_checkpoint']=validate_city_placement_checkpoint(
                acceptance,run,closure,public_views,rows[-1],city_sources,selected,
                checkpoint_sequence,manifest)
    checkpoint_summary=None
    inventory_summary=None
    if city_v12:
        if len(rows)!=1:
            raise ValueError('City acceptance requires its one closed native lifetime')
    elif checkpoint_group:
        checkpoint_summary=(validate_xp2_checkpoint_group(acceptance,rows) if xp2_checkpoint_group
                            else validate_checkpoint_group(acceptance,rows))
    elif inventory_group:
        from review_placement_inventory import validate_inventory_group
        inventory_summary=validate_inventory_group(acceptance,rows)
    elif preparation_group:
        strict_turn=acceptance['status']=='native_unit_attack_preparation_turn_saved'
        if (len(rows)!=1 or not rows[0]['ledger']['commands'] and not (selected_engine['xp2'] and preparer_receipt is not None)
                or strict_turn and (len(rows[0]['ledger']['commands'])!=1
                    or rows[0]['ledger']['commands'][0]['action']!={'kind':'force_end_turn'}
                    or not rows[0]['ledger']['updates'])
                or 'checkpoint' not in rows[0]['ledger']
                or rows[0]['checkpoint_on_close'] is not True
                or acceptance['commands']!=[r['command_result'] for r in rows[0]['ledger']['commands']]
                or acceptance['poll_calls']!=len(rows[0]['ledger']['updates'])):
            raise ValueError('Preparation lacks its native commands and Save')
        public=rows[0]['public'];live=[p for p in public if p['decisions']['unit_attacks'] is not None]
        initial,final=live[0],live[-1]
        if (not strict_turn and type(acceptance.get('turns_advanced')) is not int
                or final['turn']-initial['turn']!=(1 if strict_turn else acceptance['turns_advanced'])
                or not 0<=final['turn']-initial['turn']<=48 or not final['turn_controls']['active']
                or not final['turn_controls']['active_complete']):
            raise ValueError('Preparation did not return the human active and completely ready')
        checkpoint_summary=dict(checkpoint=rows[0]['ledger']['checkpoint']['phase_receipt']['manifest_reference'],
                turn_before=initial['turn'],turn_after=final['turn'],human_ready=True,
            native_commands=len(rows[0]['ledger']['commands']),
            poll_calls=len(rows[0]['ledger']['updates']),reset_qualified=False)
    else:
        if len(rows)!=2 or not rows[0]['ledger']['commands'] or rows[1]['ledger']['commands']:
            raise ValueError('Expected one explicit group and one independent fresh reset')
        first,fresh=rows[0]['public'][0],rows[1]['public'][0]
        if (first['episode_id']==fresh['episode_id'] or first['generation']==fresh['generation']
                or any(first[k]!=fresh[k] for k in ('turn','candidates','families','choice_state'))):
            raise ValueError('Independent reset did not restore the captured choices')
    turn_summary=None
    if turn_group:
        turn_summary=validate_turn_group(acceptance,rows)
    world_summary=validate_world_group(acceptance,rows) if world_group else None
    order_summary=validate_order_group(acceptance,rows) if order_group else None
    queue_summary=validate_production_queue_group(acceptance,rows) if queue_group else None
    placement_summary=validate_placement_group(acceptance,rows) if placement_group else None
    if placement_group:
        if rows[0]['placement_input']!=rows[1]['placement_input']:
            raise ValueError('Placement reset used a different captured/checkpoint input')
        placement_summary['input']=rows[0]['placement_input']
    attack_summary=None
    if attack_group:
        from review_unit_attacks import validate_attack_group,replay_reset_combat_information
        replay=None
        if combat_query_correction is not None:
            replay=replay_reset_combat_information(Path(rows[1]['run']),rows[1]['combat_readbacks'][0])
            acceptance['combat_information'].append(replay['query'])
            combat_query_correction['reconstructed_reset_query']=replay
        attack_summary=validate_attack_group(acceptance,rows,core_sha256=selected_engine['core_sha256'],
                                           information_query_replay=replay)
    prepared_attack=(review_prepared_attack_boundary(preparer_receipt,rows)
                     if preparer_receipt is not None and preparer_receipt.get('offered_attacks') else None)
    return dict(schema=('civ6-host.xp2-city-placement-checkpoint-preparation.v1' if city_checkpoint_group else
                        'civ6-host.xp2-shared-session-city-controls.v1' if city_group else
                        'civ6-host.xp1-combat-input-preparation.v1' if preparation_group else
                        'civ6-host.xp1-shared-session-unit-attack-cycle.v1' if attack_group else
                        'civ6-host.xp1-shared-session-placement-inventory-cycle.v1' if inventory_group else
                        'civ6-host.xp1-shared-session-placement-cycle.v1' if placement_group else
                        'civ6-host.xp1-shared-session-production-queue-cycle.v1' if queue_group else
                        'civ6-host.xp1-shared-session-checkpoint-cycle.v1' if checkpoint_group else
                        'civ6-host.xp1-shared-session-unit-order-cycle.v1' if order_group else
                        'civ6-host.xp1-shared-session-world-input-cycle.v1' if world_group else
                        'civ6-host.xp1-shared-session-turn-cycle.v1' if turn_group else
                        'civ6-host.xp1-shared-session-choice-cycle.v1').replace('xp1-',selected_engine['engine']+'-',1),
        status=('native_public_xp2_city_placement_save_and_close_authenticated' if city_checkpoint_group else
                'native_public_expansion_city_controls_close_authenticated' if city_group else
                'native_combat_inputs_turn_save_and_close_authenticated' if preparation_group else
                'native_public_unit_attack_group_close_reset_authenticated' if attack_group else
                'native_public_placement_inventory_checkpoint_reset_authenticated' if inventory_group else
                'native_public_placement_group_close_reset_authenticated' if placement_group else
                'native_public_production_queue_group_close_reset_authenticated' if queue_group else
                'native_public_checkpoint_cycle_close_reset_authenticated' if checkpoint_group else
                ('native_public_unit_order_group_close_reset_authenticated' if order_summary['complete'] else
                 'native_public_unit_order_group_incomplete') if order_group else
                'native_public_world_input_group_close_reset_authenticated' if world_group else
                'native_public_turn_group_close_reset_authenticated' if turn_group else
                'native_public_choice_group_close_reset_authenticated'),
        verifier=pin(q.__file__),reviewer=pin(__file__),acceptance=pin(acceptance_path),
        core_sha256=selected_engine['core_sha256'],input_profile=selected_engine['engine']+'-lan',
        executed_sources_archive=pin(archive),runs=rows,
        retained_preparation_correction=preparation_correction,
        retained_post_close_combat_query_correction=combat_query_correction,
        prepared_attack_boundary=prepared_attack,
        retained_producer_review_only=stdout_parser_replay is not None,
        normal_checkpoint_load_admission_unchanged=True,
        native_calls_during_review=False,official_same_save_command_transition_compared=False,
        engine_turns_qualified=turn_group,qualified_turn_interval=turn_summary,
        qualified_world_input_group=world_summary,
        qualified_unit_order_group=order_summary,
        qualified_checkpoint_cycle=checkpoint_summary,
        qualified_production_queue_group=queue_summary,
        qualified_placement_group=placement_summary,
        qualified_placement_inventory=inventory_summary,
        qualified_unit_attack=attack_summary,
        **({'qualified_city_controls': rows[0]['city_summary']} if city_group else {}),
        **({'qualified_city_placement_checkpoint': rows[0]['city_placement_checkpoint']} if city_checkpoint_group else {}),
        terminal_transition_qualified=False,complete_gameplay_qualified=False,
        full_fidelity_claim=False,strategic_training_ready=False,
        limits=['One exact '+selected_engine['engine'].upper()+' captured state, not a complete expansion game.',
            ('Combat input/readback, the authenticated public turn interval, Save and close only. An offered target is authenticated when explicitly recorded; no executed attack or reset is claimed.' if preparation_group else
             'One prepared Holy Site placement, Save and close. Specialist clicks, district completion and fresh reload remain outside this witness.' if city_checkpoint_group else
             'Three production focus clicks and one ordinary worked-tile lock/unlock on the founded city. Specialist clicks, queue edits and independent reset remain outside this witness.' if city_group else
             'Only the witnessed unit attack operation/target and actual readbacks are qualified; other combat branches remain unqualified.' if attack_group else
             'Native inventory is limited to visible own-city placement rows. Tracking remains preserved; unseen categories and completion remain unqualified.' if inventory_group else
             'Only the witnessed placement category is qualified; completion and untracked plots remain unqualified.' if placement_group else
             'Placement-required queue items and nonstandard formations remain explicitly unqualified.' if queue_group else
             'Production placements, wonders, queue editing, purchases and formations remain explicitly unqualified.'),
            'No two-human simultaneous, complete observations, broader expansion/mod compatibility or production throughput claim.'])


def review_city_sources(acceptance, closure, archive, selected, *, city_checkpoint=False):
    """Authenticate the explicit city producer set against the retained archive."""
    import zipfile
    from civ6_host.runtime.expansion_city_controls_profile import source_dependencies

    exercise = ('Native city preparation and placed Holy Site checkpoint' if city_checkpoint
                else 'Expansion native focus and citizen controls')
    if (not selected['xp2'] or acceptance.get('training') is not False
            or acceptance.get('native_exercise')!=exercise
            or closure.get('city_focus_diagnostic') is not True
            or closure.get('city_management_diagnostic') is not True
            or closure.get('checkpoint_on_close') is not city_checkpoint
            or closure.get('network_checkpoint') is not None
            or closure.get('resume_checkpoint') is not None):
        raise ValueError('City review requires its source-selected XP2 original Load')
    dependencies = source_dependencies(selected['core_sha256'])
    for path, digest in dependencies.items():
        if closure['pins'].get(path)!=digest or pin(path)['sha256']!=digest:
            raise ValueError('City source differs from its executed closure: '+path)
    names = ('contracts/network_turn.py','contracts/capability_city_controls.py',
             'contracts/city_controls_base.py','runtime/native/network_session.py',
             'runtime/workers/network_worker.py','runtime/xp1_continuation.py',
             'runtime/xp1_session_view.py','runtime/expansion_city_controls.py',
             'runtime/expansion_city_controls_profile.py',
             'runtime/native/native_saved_city_focus1000.py','runtime/native/native_saved_citizens.py')
    executed = {}
    with zipfile.ZipFile(archive) as saved:
        members = saved.namelist()
        if len(members)!=len(set(members)):
            raise ValueError('City execution archive repeats a member')
        for name in ('tools/accept_session.py', *('src/civ6_host/'+n for n in names)):
            path = (q.REPO/name).resolve()
            expected = (acceptance['script_sha256'] if name=='tools/accept_session.py'
                        else closure['pins'].get(str(path)))
            if (expected!=pin(path)['sha256'] or name not in members
                    or saved.getinfo(name).file_size>4*1024*1024
                    or hashlib.sha256(saved.read(name)).hexdigest()!=expected):
                raise ValueError('City execution archive differs from its selected producer: '+name)
            executed[name] = expected
    return dict(source_dependencies=dependencies,executed_sources=executed)


def validate_city_public_transition(result, previous, current, receipt):
    action = result['action']
    if (previous['observation']!=result['observation_before']
            or sum(r['action']==action for r in previous['decisions']['candidates'])!=1):
        raise ValueError('City group action differs from its public before-view or offer')
    if action['kind']=='found_city':
        return
    key = {'city_focus':'city_focus_catalogs','city_citizen':'citizen_catalogs'}.get(action['kind'])
    if key is None or receipt.get('city_control_applied') is not True:
        raise ValueError('City group contains another command')
    for view, side in ((previous,'before'),(current,'after')):
        rows = [r for r in view['decisions'][key] if r['city_id']==action['city_id']]
        if rows!=[receipt['catalogue_'+side]]:
            raise ValueError('City native catalogue differs from its public view')


def validate_city_protocol(run, closure, public, transitions, selected):
    """Join the native replies and client projections to every authenticated interval."""
    from civ6_host.runtime.native.native_episode_identity import DiagnosticEpisodeIdentity
    from civ6_host.runtime.network_protocol import NetworkProtocol, validate_network_response
    from civ6_host.runtime.stdout_transport_profiles import session_records
    from civ6_host.session_client import SessionClient

    transitions = {r['protocol_sequence']:r for r in transitions}
    close_sequence = len(transitions)+1
    command_lines = (run/'commands.jsonl').read_bytes().splitlines()
    if (sorted(public)!=list(range(close_sequence+1))
            or set(transitions)!=set(range(1,close_sequence))
            or len(command_lines)!=close_sequence+1 or command_lines[0]!=b'go'):
        raise ValueError('City group lacks its exact client request transcript')
    requests = [json.loads(line) for line in command_lines[1:]]
    replies = [(number,event) for number,_,event in session_records(run)
               if event['stage']=='official_session_response']
    if len(replies)!=close_sequence+1:
        raise ValueError('City group lacks its exact native response transcript')
    initial = public[0][1]
    identity = DiagnosticEpisodeIdentity(initial['episode_id'],initial['game_generation'])
    protocol = NetworkProtocol(identity,replies[0][1]['nonce'],round_limit=closure['rounds'],
                               initial_turn=initial['observation']['turn'],core_sha256=selected['core_sha256'])
    for seq,(line,reply) in enumerate(replies):
        row = transitions.get(seq)
        op = ('reset' if seq==0 else 'close' if seq==close_sequence else
              'poll' if row['phase']=='turn_update' else 'act')
        request = None if seq==0 else requests[seq-1]
        if request is not None:
            if protocol.validate(request)!=op:
                raise ValueError('City group request selects another operation')
            if op=='act' and protocol.selected(request)!=row['action']:
                raise ValueError('City group request selects another publicly offered action')
        validate_network_response(reply,protocol,op,request=request)
        if SessionClient._actor_view(reply)!=public[seq][1]:
            raise ValueError('City public file differs from the actual native response')
        if row is not None and ((op=='act' and reply['command_result']!=row['command_result'])
                or not replies[seq-1][0] < row['ledger']['first_line'] < row['ledger']['last_line'] < line):
            raise ValueError('City public status differs from the native transition interval')
        if request is not None:
            protocol.commit_reply(request,reply)
        protocol.accept_response(reply)
    return replies[-2][0],replies[-1][0]


def validate_city_group(acceptance, run, closure, public, commands, updates, sources, selected):
    """Check the recorded client selections and exact one-lifetime city script."""
    expected_kinds = ['found_city','city_focus','city_focus','city_focus','city_citizen','city_citizen']
    if (sorted(public)!=list(range(8)) or updates
            or [r['protocol_sequence'] for r in commands]!=list(range(1,7))
            or [r['action']['kind'] for r in commands]!=expected_kinds
            or acceptance['commands']!=[r['command_result'] for r in commands]
            or acceptance['replays']!=[str(public[n][0]) for n in range(8)]):
        raise ValueError('City group differs from the captured reset/foundation/focus/citizen/close script')
    initial = public[0][1]
    closed = public[7][1]
    turn = initial['observation']['turn']
    if (initial['observation']['cities'] or acceptance['final_turn']!=turn
            or any(v['observation']['turn']!=turn for _,v in public.values())
            or closed['outcome']!=dict(terminated=False,truncated=True,reason='requested_close')
            or closed['observation']!=public[6][1]['observation']):
        raise ValueError('City group crossed its same-turn close or original city boundary')
    validate_city_protocol(run,closure,public,commands,selected)

    foundation = commands[0]['action']
    city = public[1][1]['observation']['cities']
    if len(city)!=1 or (city[0]['x'],city[0]['y'])!=(foundation['x'],foundation['y']):
        raise ValueError('City group lacks the one founded own city')
    city_id = city[0]['id']
    focuses = [r['action'] for r in commands[1:4]]
    if (any(a['city_id']!=city_id or a['yield_type']!='YIELD_PRODUCTION' for a in focuses)
            or [(a['favored'],a['disfavored']) for a in focuses]!=[(False,False),(True,False),(False,True)]
            or public[1][1]['decisions']['city_focus_catalogs']!=public[4][1]['decisions']['city_focus_catalogs']):
        raise ValueError('City group did not restore the exact three-state focus catalogue')
    clicks = [r['action'] for r in commands[4:]]
    tile = clicks[0]['plot_id']
    if (clicks[1]!=dict(clicks[0],locked=True) or clicks[0]['locked'] is not False
            or clicks[0]['occupied'] is not True or clicks[0]['city_id']!=city_id
            or clicks[0]['workers'] is not None or clicks[0]['capacity'] is not None
            or (clicks[0]['x'],clicks[0]['y'])==(city[0]['x'],city[0]['y'])):
        raise ValueError('City group must lock and unlock its same ordinary worked tile')
    def tile_state(sequence):
        catalog = public[sequence][1]['decisions']['citizen_catalogs'][0]
        return next((row for row in catalog['plots'] if row['plot_id']==tile),None)
    action_fields = {k:v for k,v in clicks[0].items() if k not in ('kind','city_id')}
    if [tile_state(seq) for seq in (4,5,6)]!=[action_fields,dict(action_fields,locked=True),action_fields]:
        raise ValueError('City ordinary tile lock state did not round-trip')
    archives = [r['ledger']['phase_receipt']['archives'] for r in commands[1:]]
    if [len(row) for row in archives]!=[1,2,1,1,1] or archives[3]!=archives[4]:
        raise ValueError('City group archive counts or repeated MANAGE archive differ')
    summary = dict(city_id=city_id,citizen_plot_id=tile,focus_restored=True,citizen_unlocked=True)
    if acceptance['city_controls']!=summary:
        raise ValueError('City client summary differs from native evidence')
    return dict(**summary,turn=turn,focus_archive_counts=[1,2,1],ordinary_citizen_clicks=2,
                specialist_qualified=False,queue_edits_qualified=False,independent_reset_qualified=False,
                archive_parameter_bytes_independently_decoded=False,
                native_close_public_sequence=7,commands=pin(command_path),sources=sources)


def valid_placement_preparation_budget(preparation, *, city_checkpoint):
    if (type(preparation) is not dict or type(preparation.get('max_turns')) is not int
            or type(preparation.get('total_group_seconds')) is not int):
        return False
    turns=preparation['max_turns'];total=preparation['total_group_seconds']
    reserve=preparation.get('reset_reserve_seconds',180 if total==840 else None)
    if city_checkpoint:
        return type(reserve) is int and (turns,total,reserve)==(12,900,0)
    return 1<=turns<=12 and total in (840,1200) and reserve==180


def review_lifetime_seconds(closure, report, *, placement_preparation=None, city_checkpoint=False):
    """Use the actual pinned run budget; never relabel a 120s run as 300s."""
    seconds=closure.get('lifetime_seconds')
    if placement_preparation is not None:
        if (not valid_placement_preparation_budget(placement_preparation,city_checkpoint=city_checkpoint)
                or closure.get('input_profile')!='xp2-lan'
                or (seconds!=900 if city_checkpoint else seconds==900 and placement_preparation['total_group_seconds']!=1200)
                or closure.get('checkpoint_on_close') is not city_checkpoint
                or closure.get('network_checkpoint') is not None):
            raise ValueError('Placement preparation lifetime lacks its exact captured session selection')
    if (type(seconds) is not int or seconds not in ((45,60,120,300,420,600,900) if placement_preparation is not None or closure.get('input_profile')=='xp2-lan' else (45,60,120,300,420))
            or type(report.get('timeout_seconds')) is not int or report['timeout_seconds']!=seconds):
        raise ValueError('Session review lifetime differs from its actual pinned supervision')
    return seconds


def review_placement_input(closure, events, initial, *, allow_native_save=False, combat_evidence=None, core_sha256=None):
    """Authenticate the input checkpoint, without claiming a new Save cycle."""
    ref=closure.get('network_checkpoint');marker=events.get('official_lan_checkpoint_reloaded')
    turn=initial['observation']['turn']
    if (type(allow_native_save) is not bool or type(closure.get('checkpoint_on_close')) is not bool
            or not allow_native_save and closure['checkpoint_on_close'] is not False
            or type(closure.get('initial_turn')) is not int or closure['initial_turn']!=turn
            or initial['sequence']!=0):
        raise ValueError('Placement input turn differs from the loaded public boundary')
    if ref is None:
        if marker is not None:
            raise ValueError('Placement input has an unexpected checkpoint marker')
        return dict(official_bundle=closure['official_bundle'],checkpoint=None,turn=turn)
    from civ6_host.runtime import network_checkpoint
    from civ6_host.contracts.network_turn import checkpoint_catalogue
    from civ6_host.runtime.native.native_session_resume import semantic_decisions
    pair=network_checkpoint.normalize(ref)
    manifest=network_checkpoint.manifest(ref,official_bundle=closure['official_bundle'])
    from civ6_host.runtime.xp1_unit_attack_profile import precision_reference,source_reference, READINESS_SOURCE, verify_source, verify_readiness_source
    from civ6_host.runtime.captured_session_profile import for_family
    selected_core=for_family(closure['input_profile']).candidate.core_sha256
    if core_sha256 is not None and core_sha256!=selected_core:raise ValueError('Checkpoint comparison selects another engine')
    if manifest['core_sha256']!=selected_core:raise ValueError('Checkpoint comparison has another saved engine')
    from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
    precision=precision_reference(selected_core)[1]
    from civ6_host.contracts.network_turn import CAPABILITY_COMBAT_READINESS_SCHEMA
    readiness_source=None
    if (initial['decisions']['schema']==CAPABILITY_COMBAT_READINESS_SCHEMA
            and manifest['decisions']['schema']!=CAPABILITY_COMBAT_READINESS_SCHEMA):
        verify_source(selected_core);verify_readiness_source(selected_core)
        readiness_source=(READINESS_SOURCE[1] if selected_core==XP1_CORE_SHA256 else source_reference(selected_core)[1])
    comparable,transition=checkpoint_catalogue(initial['decisions'],manifest['decisions'],initial['observation'],
        combat_evidence=combat_evidence,combat_source_sha256=precision,
        combat_readiness_source_sha256=readiness_source,core_sha256=selected_core)
    lines=events['_event_lines'];marker_line=lines.get('official_lan_checkpoint_reloaded',0)
    next_lines=[row['first_line'] for row in events['_transition_intervals']]
    if 'before_xp1_saved_loaded_close' in lines:next_lines.append(lines['before_xp1_saved_loaded_close'])
    if (ref!={'path':pair[0],'sha256':pair[1]}
            or manifest['observed_game_turn']!=turn or initial['observation']!=manifest['observation']
            or semantic_decisions(comparable)!=semantic_decisions(manifest['decisions'])
            or type(marker) is not dict or marker.get('checkpoint')!=list(pair)
            or marker.get('turn')!=turn or marker.get('public_observation_equal') is not True
            or marker.get('public_decisions_equal') is not (transition is None)
            or marker.get('saved_decision_fields_equal') is not True
            or marker.get('catalogue_transition')!=transition or marker.get('identity_rebound') is not True
            or marker.get('complete_state_compared') is not False or marker.get('strategic_training_ready') is not False
            or not next_lines or not lines['xp1_saved_player_view_returned']<marker_line<min(next_lines)):
        raise ValueError('Placement checkpoint input differs from its native reload/public receipt')
    return dict(official_bundle=closure['official_bundle'],checkpoint=dict(path=pair[0],sha256=pair[1]),
                turn=turn,catalogue_transition=transition,native_save_in_this_group=closure['checkpoint_on_close'])


def validate_xp2_checkpoint_group(acceptance, rows):
    """Authenticate the existing two-Save/three-lifetime XP2 checkpoint cycle."""
    from civ6_host.runtime import network_checkpoint
    from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
    from civ6_host.runtime.xp2_bundle_inputs import XP2_LAN_PROFILE, REFERENCE
    from civ6_host.runtime.native.native_session_resume import semantic_decisions
    group=acceptance['checkpoint_cycle']
    if (len(rows)!=3 or len({r['run'] for r in rows})!=3
            or [len(r['ledger']['commands']) for r in rows]!=[3,1,1]
            or ['checkpoint' in r['ledger'] for r in rows]!=[True,True,False]
            or [r['checkpoint_on_close'] for r in rows]!=[True,True,False]
            or any(r['ledger']['updates'] for r in rows[1:])
            or any(r['normal_native_destroy_authenticated'] is not True
                   or r['all_source_pins_unchanged'] is not True for r in rows)
            or type(group['save_count']) is not int or group['save_count']!=2
            or type(group['poll_calls']) is not int or not 0<=group['poll_calls']<=64
            or group['poll_calls']!=len(rows[0]['ledger']['updates'])
            or acceptance['poll_calls']!=group['poll_calls']
            or group['complete_hidden_state_compared'] is not False
            or type(group['unit_id']) is not int
            or type(group['saved_sequences']) is not list or len(group['saved_sequences'])!=2
            or any(type(s) is not int or s<1 for s in group['saved_sequences'])
            or type(group['resumed_episodes']) is not list or len(group['resumed_episodes'])!=2):
        raise ValueError('XP2 checkpoint cycle requires two Saves and three clean independent lifetimes')
    a,b,c=rows;first,resumed,fresh=(r['public'][0] for r in rows)
    if (a['checkpoint_input'] is not None or a['checkpoint_reloaded'] is not None
            or type(group['initial_turn']) is not int or group['initial_turn']!=first['turn']
            or type(group['saved_turn']) is not int or group['saved_turn']!=first['turn']+1
            or acceptance['final_turn']!=group['saved_turn']
            or acceptance['commands']!=[r['command_result'] for row in rows for r in row['ledger']['commands']]
            or [r['action']['kind'] for r in a['ledger']['commands']]!=['found_city','force_end_turn','world_select_unit']
            or b['ledger']['commands'][0]['action']!={'kind':'world_deselect_unit'}
            or c['ledger']['commands'][0]['action']['kind']!='civic'
            or group['post_resume_actions']!=[r['ledger']['commands'][0]['action'] for r in (b,c)]
            or any(cmd['command_result']['status']!='completed' for row in rows for cmd in row['ledger']['commands'])
            or group['final_command_sequence']!=c['ledger']['commands'][0]['protocol_sequence']):
        raise ValueError('XP2 checkpoint preparation, turn advance or post-resume commands differ')
    saved=[];references=[]
    for index,row in enumerate((a,b)):
        public={v['sequence']:v for v in row['public']};sequence=group['saved_sequences'][index]
        if (sequence!=max(public) or sequence not in public
                or sequence!=row['ledger']['commands'][-1]['protocol_sequence']):
            raise ValueError('XP2 Save is not joined to its last actual public command boundary')
        saved.append(public[sequence]);references.append(row['ledger']['checkpoint']['phase_receipt']['manifest_reference'])
    if (acceptance['checkpoints']!=references
            or references[0]['path']==references[1]['path']
            or a['ledger']['commands'][-1]['action']!={'kind':'world_select_unit','unit_id':group['unit_id']}
            or saved[0]['world_input']['selected_unit_id']!=group['unit_id']
            or saved[1]['world_input']['selected_unit_id'] is not None
            or len({v['episode_id'] for v in (first,resumed,fresh)})!=3
            or len({v['generation'] for v in (first,resumed,fresh)})!=3):
        raise ValueError('XP2 checkpoint pair, explicit selection or independent episode identity differs')
    for row in rows:
        turns=[v['turn'] for v in row['public']]
        if (turns!=sorted(turns) or any(t not in (first['turn'],group['saved_turn']) for t in turns)
                or row is not a and any(t!=group['saved_turn'] for t in turns)
                or any(cmd['turn_before']!=group['saved_turn'] or cmd['turn_after']!=group['saved_turn']
                       for cmd in row['ledger']['commands'] if row is not a or cmd['action']['kind']=='world_select_unit')):
            raise ValueError('XP2 checkpoint cycle did not retain its exact advanced turn')
    for index,(row,initial) in enumerate(((b,resumed),(c,fresh))):
        reference=references[index];marker=row['checkpoint_reloaded'];boundary=saved[index]
        expected_ref={k:reference[k] for k in ('path','sha256')}
        if (initial['sequence']!=0 or initial['episode_id']!=group['resumed_episodes'][index]
                or row['checkpoint_input']!=expected_ref
                or initial['observation']!=boundary['observation']
                or semantic_decisions(initial['decisions'])!=semantic_decisions(boundary['decisions'])
                or boundary['turn']!=group['saved_turn'] or boundary['turn_controls']['active'] is not True
                or boundary['turn_controls']['active_complete'] is not True
                or type(marker) is not dict or marker.get('checkpoint')!=[reference['path'],reference['sha256']]
                or marker.get('turn')!=group['saved_turn'] or marker.get('public_observation_equal') is not True
                or marker.get('public_decisions_equal') is not True or marker.get('saved_decision_fields_equal') is not True
                or marker.get('catalogue_transition') is not None or marker.get('identity_rebound') is not True
                or marker.get('complete_state_compared') is not False or marker.get('strategic_training_ready') is not False):
            raise ValueError('XP2 fresh Load differs from its exact saved public state/catalogue')
    origin=dict(path=REFERENCE[0],sha256=REFERENCE[1])
    manifests=[network_checkpoint.manifest(ref,official_bundle=origin) for ref in references]
    root,child=manifests;parent={k:references[0][k] for k in ('path','sha256')}
    if (root['lineage_depth']!=0 or root['parent_checkpoint'] is not None
            or child['lineage_depth']!=1 or child['parent_checkpoint']!=parent
            or child['input_components_sha256']!={k:root['components'][k]['sha256'] for k in ('gamecore','application_configuration')}
            or any(root['components'][k]['path']==child['components'][k]['path'] for k in ('gamecore','application_configuration'))
            or root['session_closure']['path']==child['session_closure']['path']
            or any(m['core_sha256']!=XP2_CORE_SHA256 or m['input_profile']!=XP2_LAN_PROFILE.name
                   or m['source_official_bundle']!=origin or m['observed_game_turn']!=group['saved_turn']
                   or m['observation']!=boundary['observation']
                   or semantic_decisions(m['decisions'])!=semantic_decisions(boundary['decisions'])
                   for m,boundary in zip(manifests,saved))
            or root['host_world_selection']!=group['unit_id'] or child['host_world_selection'] is not None):
        raise ValueError('XP2 child checkpoint lost its exact native pair ancestry or original capture')
    return dict(checkpoints=references,save_count=2,independent_loads=2,native_lifetimes=3,
        initial_turn=first['turn'],saved_turn=group['saved_turn'],lineage_depths=[0,1],
        child_components_descend_from_parent=True,original_capture_preserved=True,
        qualified_public_observation_equal=True,qualified_semantic_decisions_equal=True,
        native_commands_after_each_resume=True,explicit_selection_restored=True,
        child_deselection_restored=True,poll_calls=group['poll_calls'],
        complete_hidden_state_compared=False,complete_gameplay_qualified=False)


def validate_checkpoint_group(acceptance, rows):
    """One native Save, two independent Loads, and qualified public state only."""
    from civ6_host.runtime.native.native_session_resume import semantic_decisions
    group=acceptance['checkpoint_cycle']
    if (len(rows)!=3 or len({r['run'] for r in rows})!=3
            or [len(r['ledger']['commands']) for r in rows]!=[2,2,0]
            or any(r['ledger']['updates'] for r in rows)
            or ['checkpoint' in r['ledger'] for r in rows]!=[True,False,False]
            or [r['checkpoint_on_close'] for r in rows]!=[True,False,False]
            or type(group['save_count']) is not int or group['save_count']!=1
            or type(group['poll_calls']) is not int or group['poll_calls']!=0
            or group['complete_hidden_state_compared'] is not False
            or type(group['unit_id']) is not int):
        raise ValueError('Checkpoint cycle lacks three independent lifetimes, one Save and zero polls')
    uid=group['unit_id'];a,b,c=rows
    first=a['public'][0];resumed=b['public'][0];fresh=c['public'][0]
    originals={r['sequence']:r for r in a['public']};returns={r['sequence']:r for r in b['public']}
    rest,select=a['ledger']['commands'];release,deselect=b['ledger']['commands']
    saved=originals[group['selection_sequence']]
    reference=a['ledger']['checkpoint']['phase_receipt']['manifest_reference']
    if (group['checkpoint']!=reference or acceptance['checkpoints']!=[reference]
            or a['checkpoint_input'] is not None
            or acceptance['commands']!=[r['command_result'] for run in rows for r in run['ledger']['commands']]
            or group['turn']!=first['turn']
            or any(v['turn']!=first['turn'] for r in rows for v in r['public'])
            or any(cmd['turn_before']!=first['turn'] or cmd['turn_after']!=first['turn']
                   for r in rows for cmd in r['ledger']['commands'])):
        raise ValueError('Checkpoint source, commands or public turn differs from its actual receipt')
    expected_ref={k:reference[k] for k in ('path','sha256')}
    for row,initial,episode in ((b,resumed,group['resumed_episode']),(c,fresh,group['reset_episode'])):
        marker=row['checkpoint_reloaded']
        if (initial['sequence']!=0 or initial['episode_id']!=episode or row['checkpoint_input']!=expected_ref
                or initial['observation']!=saved['observation']
                or semantic_decisions(initial['decisions'])!=semantic_decisions(saved['decisions'])
                or type(marker) is not dict or marker.get('checkpoint')!=[reference['path'],reference['sha256']]
                or marker.get('turn')!=first['turn'] or marker.get('public_observation_equal') is not True
                or marker.get('public_decisions_equal') is not True or marker.get('saved_decision_fields_equal') is not True
                or marker.get('catalogue_transition') is not None or marker.get('identity_rebound') is not True
                or marker.get('complete_state_compared') is not False or marker.get('strategic_training_ready') is not False):
            raise ValueError('Checkpoint Load differs from its exact saved public state and decision catalogue')
    if (len({v['episode_id'] for v in (first,resumed,fresh)})!=3
            or len({v['generation'] for v in (first,resumed,fresh)})!=3):
        raise ValueError('Checkpoint Loads reused an episode or generation')
    re=rest['ledger']['phase_receipt'];rr=release['ledger']['phase_receipt']
    if (rest['action']!=group['rest_action'] or rest['action']['kind']!='unit_order'
            or rest['action']['unit_id']!=uid
            or rest['action']['item_type'] not in ('UNITOPERATION_SLEEP','UNITOPERATION_FORTIFY')
            or rest['protocol_sequence']!=group['rest_sequence'] or re['state_changed'] is not True
            or select['protocol_sequence']!=group['selection_sequence']
            or select['action']!=dict(kind='world_select_unit',unit_id=uid)
            or saved['world_input']['selected_unit_id']!=uid
            or release['action']!=group['release_action'] or release['action']['kind']!='unit_order'
            or release['action']['unit_id']!=uid
            or release['action']['item_type'] not in ('UNITCOMMAND_WAKE','UNITCOMMAND_CANCEL')
            or release['protocol_sequence']!=group['release_sequence'] or rr['state_changed'] is not True
            or rr['unit_before']!=re['unit_after']
            or rr['unit_after']['activity_type']!=re['unit_before']['activity_type']
            or deselect['protocol_sequence']!=group['deselection_sequence']
            or deselect['action']!=dict(kind='world_deselect_unit')
            or returns[group['deselection_sequence']]['world_input']['selected_unit_id'] is not None):
        raise ValueError('Checkpoint preparation or resumed explicit release/deselection differs')
    return dict(checkpoint=reference,save_count=1,independent_loads=2,native_lifetimes=3,
        unit_id=uid,rest_action=rest['action'],release_action=release['action'],
        qualified_public_observation_equal=True,qualified_semantic_decisions_equal=True,
        native_command_after_resume=True,explicit_selection_restored=True,
        poll_calls=0,complete_hidden_state_compared=False,complete_gameplay_qualified=False)


def review_command_result(result, phase_receipt):
    """Join existing family receipts without imposing an adapter on foundation."""
    action=result['action']
    if action['kind']=='found_city':
        # The established foundation result is its concrete city/unit effect,
        # not the status/refusal envelope used by newer explicit adapters.
        if phase_receipt.get('explicit_unit_command_applied') is not True:
            raise ValueError('Foundation command lacks its authenticated native effect')
        return dict(status='completed',reason=None,requested_action=action)
    if action['kind'] in ('research','civic','production'):
        if (phase_receipt.get('explicit_choice_applied') is not True
                or phase_receipt.get('kind')!=action['kind']):
            raise ValueError('Explicit choice lacks its authenticated native effect')
        return dict(status='completed',reason=None,requested_action=action)
    if action['kind'] in ('city_focus','city_citizen'):
        if phase_receipt.get('city_control_applied') is not True or phase_receipt['kind']!=action['kind']:
            raise ValueError('City command lacks its authenticated native effect')
        return dict(status='completed',reason=None,requested_action=action)
    if action['kind'] not in ('end_turn','force_end_turn','unready_turn','world_select_unit',
            'world_plot_click','world_deselect_unit','unit_order','queue_append','queue_remove','queue_swap','production_placement','production_resume','unit_attack'):
        raise ValueError('Command result family is not explicitly reviewed')
    effect=result['effect'];status=effect['status']
    if status not in ('completed','refused'):
        raise ValueError('Explicit adapter returned no reviewed command status')
    return dict(status=status,reason=effect.get('refusal_code'),requested_action=action)


def validate_world_public_transition(result, previous, current):
    """No private target information is needed to join selection and own queue."""
    action=result['action'];before=result['observation_before'];after=result['observation_after']
    if previous['observation']!=before or current['observation']!=after:
        raise ValueError('World-input public observations differ from native transition boundaries')
    if not any(r['action']==action for r in previous['decisions']['candidates']):
        raise ValueError('World input was not offered at the actual preceding public revision')
    prior=previous['decisions']['world_input'];state=current['decisions']['world_input']
    queues=current['decisions']['queued_orders'];receipt=result['effect']['receipt']
    if prior is None or state is None or queues is None:
        raise ValueError('World-input transition lost its available player-scoped state')
    kind=action['kind']
    expected=(action['unit_id'] if kind=='world_select_unit' else None if kind=='world_deselect_unit'
              else action['unit_id'] if any(u['id']==action['unit_id'] for u in after['units']) else None)
    if state['selected_unit_id']!=expected:
        raise ValueError('Public unit selection differs from its explicit world input')
    if kind!='world_plot_click' or result['effect']['status']=='refused':
        if queues!=previous['decisions']['queued_orders']:
            raise ValueError('UI-only/refused input changed the public queued orders')
    if kind=='world_plot_click':
        if prior['selected_unit_id']!=action['unit_id']:
            raise ValueError('World click did not target the explicitly selected own unit')
        row=next((r for r in queues['units'] if r['unit_id']==action['unit_id']),None)
        actual=receipt['queued_destination_after']
        if ((row is None and actual is not None) or row is not None
                and actual!=dict(unit_present=True,plot_id=row['plot_id'])):
            raise ValueError('Public queued order differs from the native own-unit readback')
        if result['effect']['status']=='refused' and state!=prior:
            raise ValueError('Refused world input changed the public selection state')


def validate_order_public_transition(result, previous, current):
    """Join native order state to the actually offered public input and readback."""
    action=result['action'];receipt=result['effect']['receipt'];uid=action['unit_id']
    if (previous['observation']!=result['observation_before']
            or current['observation']!=result['observation_after']
            or not any(r['action']==action for r in previous['decisions']['candidates'])
            or not any(r['action']==action and r['legal'] is True
                       for r in previous['decisions']['unit_orders']['offers'])):
        raise ValueError('Unit order differs from its actual public native offer/observation')
    for view,key in ((previous,'unit_before'),(current,'unit_after')):
        unit=next((u for u in view['decisions']['unit_orders']['units'] if u['unit_id']==uid),None)
        if unit!=receipt[key]:
            raise ValueError('Public unit activity differs from the native order result')
    if current['decisions']['world_input']!=previous['decisions']['world_input']:
        raise ValueError('Unit order changed host selection without explicit world input')


def validate_queue_public_transition(result, previous, current):
    """Bind one edit to its offered queue revision and exact native readback."""
    action=result['action'];receipt=result['effect']['receipt'];city_id=action['city_id']
    if (previous['observation']!=result['observation_before']
            or current['observation']!=result['observation_after']
            or not any(r['action']==action for r in previous['decisions']['candidates'])):
        raise ValueError('Queue edit differs from its actual public offer/observation')
    for view,key in ((previous,'queue_before'),(current,'queue_after')):
        state=view['decisions']['production_queues']
        if state is None or next((q for q in state if q['city_id']==city_id),None)!=receipt[key]:
            raise ValueError('Public production queue differs from the exact native readback')
    a=[q for q in previous['decisions']['production_queues'] if q['city_id']!=city_id]
    b=[q for q in current['decisions']['production_queues'] if q['city_id']!=city_id]
    # Other cities' offers may legitimately change with shared limits. Their
    # actual queues must not be edited by a command targeting this city.
    if [(q['city_id'],q['entries']) for q in a]!=[(q['city_id'],q['entries']) for q in b]:
        raise ValueError('Queue edit changed another city queue')
    if current['decisions']['world_input']!=previous['decisions']['world_input']:
        raise ValueError('Queue edit changed the explicit unit selection')


def validate_production_queue_group(acceptance, rows):
    """Authenticate append to eight, observable swap/tail replacement/removal."""
    from civ6_host.contracts.production_queue import check_effect
    group=acceptance['production_queue_group'];first=rows[0]['public'][0];fresh=rows[1]['public'][0]
    ledger=rows[0]['ledger'];commands=ledger['commands'];city_id=group['city_id']
    public={r['sequence']:r for r in rows[0]['public']};byseq={r['protocol_sequence']:r for r in commands}
    if (ledger['updates'] or rows[1]['ledger']['transitions'] or group['poll_calls']!=0
            or group['private_target_queries_used'] is not False
            or group['complete_append_catalogue_claimed'] is not False
            or group['placement_or_formation_qualified'] is not False
            or any(first[k]!=fresh[k] for k in ('observation','production_queues','unit_orders','world_input','queued_orders','turn_availability'))
            or group['initial_turn']!=first['turn'] or group['final_turn']!=first['turn']
            or any(c['turn_before']!=first['turn'] or c['turn_after']!=first['turn'] for c in commands)):
        raise ValueError('Queue group lacks same-turn scope, exact reset or explicit qualification limits')
    steps=group['steps'];foundation=group['foundation']
    expected=[]
    if foundation is not None:
        seq=foundation['sequence'];row=byseq[seq];expected.append(seq)
        prior=public[max(s for s in public if s<seq)];after=public[seq]
        if (foundation['action']!=row['action'] or row['action']['kind']!='found_city'
                or foundation['command_result']!=row['command_result']
                or len(after['observation']['cities'])!=len(prior['observation']['cities'])+1
                or len(after['observation']['units'])!=len(prior['observation']['units'])-1):
            raise ValueError('Queue preparation does not match the native foundation')
    if len(steps)!=11:raise ValueError('Queue group must include eight appends and three exact permutations')
    for step in steps:
        seq=step['sequence'];row=byseq[seq];expected.append(seq)
        prior=public[max(s for s in public if s<seq)];after=public[seq];phase=row['ledger']['phase_receipt']
        if (step['action']!=row['action'] or step['action']['city_id']!=city_id
                or step['command_result']!=row['command_result'] or row['command_result']['status']!='completed'
                or row['command_result']['reason'] is not None
                or not any(r['action']==row['action'] for r in prior['candidates'])
                or phase.get('production_queue_status')!='completed' or phase.get('native_request_delivered') is not True):
            raise ValueError('Queue group edit lacks its actual native command and public offer')
        for key,view in (('queue_before',prior),('queue_after',after)):
            q=next((q for q in view['production_queues'] if q['city_id']==city_id),None)
            if q!=step[key] or q!=phase[key]:raise ValueError('Queue group lost its exact ordered native states')
        check_effect(step['action'],step['queue_before'],step['queue_after'])
    if expected!=[c['protocol_sequence'] for c in commands] or len(set(expected))!=len(expected):
        raise ValueError('Queue group omits, reorders or duplicates native commands')
    for i,step in enumerate(steps[:8]):
        if (step['action']['kind']!='queue_append' or step['action']['mode']!='append'
                or len(step['queue_before']['entries'])!=i or len(step['queue_after']['entries'])!=i+1):
            raise ValueError('Queue group did not witness native growth from empty to eight')
    swap,tail,remove=steps[8:]
    if (group['full_queue_sequence']!=steps[7]['sequence'] or group['swap_sequence']!=swap['sequence']
            or group['replace_tail_sequence']!=tail['sequence'] or group['remove_sequence']!=remove['sequence']
            or swap['action']['kind']!='queue_swap'
            or swap['queue_before']['entries']==swap['queue_after']['entries']
            or tail['action']['kind']!='queue_append' or tail['action']['mode']!='replace_tail'
            or len(tail['queue_before']['entries'])!=8 or len(tail['queue_after']['entries'])!=8
            or tail['queue_before']['entries'][-1]==tail['queue_after']['entries'][-1]
            or remove['action']['kind']!='queue_remove' or len(remove['queue_after']['entries'])!=7):
        raise ValueError('Queue swap, eighth-slot replacement or removal was not actually witnessed')
    return dict(city_id=city_id,command_count=len(commands),queue_edit_count=len(steps),
        foundation_performed=foundation is not None,empty_to_eight=True,observable_swap=True,
        eighth_slot_replaced=True,removal_witnessed=True,poll_calls=0,turn=first['turn'],
        public_queues_reset_equal=True,complete_append_catalogue=False,
        placements_and_nonstandard_formations_qualified=False)


def validate_placement_public_transition(result, previous, current, phase_receipt):
    """Join placement/current-production inputs and tracked public readback."""
    action=result['action'];cid=action['city_id'];kind=action['kind']
    if (previous['observation']!=result['observation_before'] or current['observation']!=result['observation_after']
            or not any(r['action']==action for r in previous['decisions']['candidates'])
            or current['decisions']['world_input']!=previous['decisions']['world_input']):
        raise ValueError('Placement group lost its actual public input or observation boundary')
    old,new=previous['decisions'],current['decisions']
    for d in (old,new):
        if d['placement_observation_scope']!='host_tracked':raise ValueError('Placement tracking scope was broadened')
    head=next(r for r in new['choice_state']['production'] if r['city_id']==cid)
    if (head['hash']!=action['hash'] or head['item_index']!=action['index']
            or head['kind']!={'unit':'U','building':'B','district':'D','project':'P'}[action['category']]):
        raise ValueError('Public current production differs from the selected native item')
    if kind=='production':
        if old['placements']!=new['placements'] or phase_receipt.get('explicit_choice_applied') is not True:
            raise ValueError('Ordinary replacement changed tracked placement identities')
        return
    if action not in old['placement_offers'] or phase_receipt.get('placement_status')!='completed':
        raise ValueError('Placement command lacks its actual native offer and result')
    receipt=result['effect']['receipt'];native=receipt['effect']
    for view,key in ((previous,'production_before'),(current,'production_after')):
        state=next(r for r in view['decisions']['choice_state']['production'] if r['city_id']==cid)
        actual=phase_receipt[key]
        expected=dict(city_id=actual['city_id'],queue_size=actual['queue_size'],kind=actual['kind'],
            item_index=actual['item_index'],hash=actual['current_production_hash'] & 0xffffffff,formation=actual['formation'])
        if state!=expected:raise ValueError('Public production snapshot differs from the native placement event')
    if kind=='production_resume':
        if old['placements']!=receipt['placements_before'] or new['placements']!=receipt['placements_after']:
            raise ValueError('Public resumption lost its exact native tracked snapshots')
        return
    old_map={(r['city_id'],r['plot_id']):r for r in old['placements']}
    new_map={(r['city_id'],r['plot_id']):r for r in new['placements']};key=(cid,action['plot_id'])
    expected=dict(city_id=cid,category=action['category'],index=action['index'],item_type=action['item_type'],
        plot_id=action['plot_id'],x=action['x'],y=action['y'],placement_turn=previous['observation']['turn'],
        observed_turn=current['observation']['turn'],exists=True,complete=False)
    if (key in old_map or set(new_map)!=set(old_map)|{key} or new_map[key]!=expected
            or any(new_map[k]!=v for k,v in old_map.items()) or native['new_placement_verified'] is not True):
        raise ValueError('Public placement did not add only the actual unfinished selected plot')


def validate_placement_preparation(acceptance, row, *, city_checkpoint=False):
    """Join the optional caller-selected prefix to already authenticated transitions."""
    prep=acceptance['placement_preparation'];public={v['sequence']:v for v in row['public']}
    first=row['public'][0];boundary=prep.get('prepared_boundary')
    if (type(boundary) is not dict or set(boundary)!={'sequence','turn'}
            or type(boundary['sequence']) is not int or boundary['sequence'] not in public
            or prep.get('initial_sequence')!=first['sequence'] or prep.get('initial_turn')!=first['turn']
            or not valid_placement_preparation_budget(prep,city_checkpoint=city_checkpoint)
            or prep.get('max_polls_per_turn')!=32
            or prep.get('public_selector') is not True or prep.get('checkpoint_used') is not False
            or type(acceptance.get('seconds')) not in (int,float) or not 0<acceptance['seconds']<=prep['total_group_seconds']):
        raise ValueError('Placement preparation lacks its explicit bounded public selection')
    prepared=public[boundary['sequence']];controls=prepared['turn_controls']
    if (boundary['turn']!=prepared['turn'] or prep.get('turns_advanced')!=prepared['turn']-first['turn']
            or not 0<=prep['turns_advanced']<=prep['max_turns']
            or controls['active'] is not True or controls['active_complete'] is not True
            or controls['can_unready'] is not False or controls['timer_elapsed'] is not False):
        raise ValueError('Placement preparation did not reach the recorded active boundary')
    transitions=[r for r in row['ledger']['transitions'] if r['protocol_sequence']<=boundary['sequence']]
    expected=[dict(sequence=r['protocol_sequence'],action=r['action'],command_result=r['command_result'],
        turn_before=r['turn_before'],turn_after=r['turn_after']) for r in transitions]
    updates=[r for r in transitions if r['phase']=='turn_update']
    if (prep.get('transitions')!=expected or prep.get('poll_calls')!=len(updates)
            or (transitions[-1]['protocol_sequence'] if transitions else first['sequence'])!=boundary['sequence']
            or any(sum(r['turn_before']==turn for r in updates)>32 for turn in {r['turn_before'] for r in updates})):
        raise ValueError('Placement preparation omitted or changed an actual bounded transition')
    for r in transitions:
        if r['phase']=='turn_update':continue
        action=r['action'];prior=public[max(s for s in public if s<r['protocol_sequence'])]
        if (action['kind'] not in ('found_city','research','civic','production','end_turn','force_end_turn')
                or not any(v['action']==action for v in prior['candidates'])
                or r['command_result']!=dict(status='completed',reason=None,requested_action=action)):
            raise ValueError('Placement preparation used an unoffered or uncompleted command')
    if transitions:
        identity=prep['source_identity'];index=prep.get('astrology_native_index')
        astrology=[a['action'] for a in transitions if a['action'] is not None
                   and a['action']['kind']=='research' and a['action']['hash']==identity['action_hash']]
        initially_selected=first['choice_state']['research']['research']
        if (prep['turns_advanced'] and (type(index) is not int or
                not astrology and initially_selected!=index or any(a['index']!=index for a in astrology))):
            raise ValueError('Placement preparation has no actual Astrology selection')
    return prepared,dict(initial_turn=first['turn'],prepared_turn=prepared['turn'],
        prepared_sequence=boundary['sequence'],turns_advanced=prep['turns_advanced'],
        command_count=len(transitions)-len(updates),poll_calls=len(updates),public_selector=True,
        checkpoint_used=False,reset_to_original_capture=True)


def validate_city_placement_checkpoint(acceptance, run, closure, public, row, sources, selected,
                                       checkpoint_sequence, manifest):
    """Join one placement and its root Save to the authenticated v12 preparation."""
    prepared,preparation=validate_placement_preparation(acceptance,row,city_checkpoint=True)
    ledger=row['ledger'];after_prepare=[r for r in ledger['transitions']
                                         if r['protocol_sequence']>prepared['sequence']]
    action=acceptance.get('placement_action')
    if (len(after_prepare)!=1 or type(action) is not dict
            or action.get('kind')!='production_placement' or action.get('category')!='district'
            or action.get('item_type')!=acceptance['placement_preparation']['source_identity']['target_type']
            or action!=after_prepare[0]['action']
            or after_prepare[0]['command_result']!=dict(status='completed',reason=None,requested_action=action)
            or acceptance['commands']!=[r['command_result'] for r in ledger['commands']]):
        raise ValueError('City preparation lacks its one completed Holy Site placement')
    placed=after_prepare[0]['protocol_sequence']
    if (checkpoint_sequence!=placed+1 or checkpoint_sequence not in public or manifest is None
            or acceptance.get('checkpoint')!=ledger['checkpoint']['phase_receipt']['manifest_reference']
            or manifest['lineage_depth']!=0 or manifest['parent_checkpoint'] is not None
            or row['checkpoint_reloaded'] is not None or row['checkpoint_input'] is not None):
        raise ValueError('City placement lacks its original-load root Save')
    before=public[prepared['sequence']][1];after=public[placed][1];closed=public[checkpoint_sequence][1]
    matching=[offer for offer in before['decisions']['placement_offers']
              if offer['kind']=='production_placement' and offer['item_type']==action['item_type']]
    def inventory(view):
        return {(r['city_id'],r['category'],r['plot_id']):r for r in view['decisions']['placement_inventory']['rows']}
    old,new=inventory(before),inventory(after)
    key=action['city_id'],action['category'],action['plot_id']
    native=new.get(key)
    if (not matching or action!=min(matching,key=lambda offer:(offer['city_id'],offer['plot_id']))
            or key in old or set(new)!=set(old)|{key} or any(new[k]!=v for k,v in old.items())
            or native['complete'] is not False or any(native[k]!=action[k] for k in
                ('city_id','category','index','hash','item_type','plot_id','x','y'))
            or row.get('inventory_receipts') is None or inventory(closed)!=new
            or after['observation']!=closed['observation']
            or acceptance['final_turn']!=after['observation']['turn'] or prepared['turn']!=acceptance['final_turn']
            or closed['outcome']!=dict(terminated=False,truncated=True,reason='requested_close')
            or acceptance['replays']!=[str(public[n][0]) for n in sorted(public)]):
        raise ValueError('City preparation changed its selected unfinished placement or closing boundary')
    prior_line,close_line=validate_city_protocol(run,closure,public,ledger['transitions'],selected)
    checkpoint=ledger['checkpoint'];lifetime=ledger['lifetime']
    if not (prior_line < checkpoint['first_line'] < checkpoint['last_line']
            < lifetime['first_line'] < lifetime['last_line'] < close_line):
        raise ValueError('City checkpoint is outside its placement-to-close interval')
    return dict(preparation=preparation,input=row['placement_input'],placement=action,
                native_inventory_row=native,placement_sequence=placed,close_sequence=checkpoint_sequence,
                checkpoint=acceptance['checkpoint'],root_lineage=True,source_identity=sources,
                fresh_reload_qualified=False,specialist_qualified=False,district_completion_qualified=False)


def validate_placement_group(acceptance, rows):
    group=acceptance['placement_group'];first,fresh=rows[0]['public'][0],rows[1]['public'][0]
    ledger=rows[0]['ledger'];commands=ledger['commands'];steps=group['steps'];category=group['category']
    public={r['sequence']:r for r in rows[0]['public']}
    preparation=None;prepared=first
    if acceptance.get('placement_preparation') is not None:
        prepared,preparation=validate_placement_preparation(acceptance,rows[0])
        commands=[r for r in commands if r['protocol_sequence']>prepared['sequence']]
        if any(r['protocol_sequence']>prepared['sequence'] for r in ledger['updates']):
            raise ValueError('Placement updates continued past the prepared boundary')
        if acceptance['commands']!=[r['command_result'] for r in ledger['commands']]:
            raise ValueError('Placement group omitted a preparation command')
    fields=('observation','placements','placement_offers','placement_observation_scope','production_queues',
            'unit_orders','world_input','queued_orders','turn_availability')
    if (category not in ('district','building') or len(commands)!=3 or len(steps)!=3
            or (ledger['updates'] and preparation is None) or rows[1]['ledger']['transitions'] or group['poll_calls']!=0
            or group['observation_scope']!='host_tracked' or group['completion_witnessed'] is not False
            or group['other_category_qualified'] is not False or group['unobserved_placement_inventory_complete'] is not False
            or any(first[k]!=fresh[k] for k in fields) or group['initial_turn']!=prepared['turn'] or group['final_turn']!=prepared['turn']):
        raise ValueError('Placement group lacks exact same-boundary scope/reset or claims unsupported coverage')
    def state(summary):
        return dict(production=next(r for r in summary['choice_state']['production'] if r['city_id']==group['city_id']),
                    placements=summary['placements'],production_queues=summary['production_queues'])
    for expected_kind,step,row in zip(('production_placement','production','production_resume'),steps,commands):
        seq=row['protocol_sequence'];prior=public[max(s for s in public if s<seq)];after=public[seq]
        if (step['sequence']!=seq or step['action']!=row['action'] or row['action']['kind']!=expected_kind
                or step['command_result']!=row['command_result'] or row['command_result']['status']!='completed'
                or row['command_result']['reason'] is not None or step['before']!=state(prior) or step['after']!=state(after)
                or row['turn_before']!=prepared['turn'] or row['turn_after']!=prepared['turn']
                or row['action']['city_id']!=group['city_id']
                or not any(r['action']==row['action'] for r in prior['candidates'])):
            raise ValueError('Placement group omitted or changed its actual native/public transition')
    placed,replaced,resumed=steps
    if (placed['action']['category']!=category or placed['action']['item_type']!=group['item_type']
            or placed['action']['plot_id']!=group['plot_id']
            or any(resumed['action'][k]!=placed['action'][k] for k in ('city_id','category','index','hash','item_type'))
            or replaced['action']['hash']==placed['action']['hash']
            or any(s['after']['placements']!=placed['after']['placements'] for s in (replaced,resumed))):
        raise ValueError('Placement group did not replace and resume the same native placed item')
    a,b=commands[0]['ledger']['phase_receipt'],commands[-1]['ledger']['phase_receipt']
    if (a.get('placement_status')!='completed' or b.get('placement_status')!='completed'
            or a['effect']['new_placement_verified'] is not True or b['kind']!='production_resume'
            or b['progress_before']!=b['progress_after']):
        raise ValueError('Placement group lacks native placement or retained progress resumption')
    result=dict(category=category,city_id=group['city_id'],plot_id=group['plot_id'],item_type=group['item_type'],
        command_count=3,placement_witnessed=True,ordinary_replacement_witnessed=True,resumption_witnessed=True,
        retained_progress=b['progress_after'],positive_retained_progress_witnessed=b['progress_after']>0,
        public_tracking_reset_equal=True,observation_scope='host_tracked',poll_calls=0,turn=prepared['turn'],
        completion_qualified=False,other_category_qualified=False,preexisting_placement_inventory_complete=False)
    if preparation is not None:result['preparation']=preparation
    if rows[0].get('inventory_receipts') is not None:
        key=(group['city_id'],category,group['plot_id'])
        def inventory(view):return {(r['city_id'],r['category'],r['plot_id']):r for r in view['placement_inventory']['rows']}
        old=inventory(public[max(s for s in public if s<steps[0]['sequence'])]);new=inventory(public[steps[0]['sequence']])
        native=new.get(key);action=steps[0]['action']
        if (native is None or key in old or set(new)!=set(old)|{key}
                or any(new[k]!=v for k,v in old.items()) or native['complete'] is not False
                or any(native[k]!=action[k] for k in ('city_id','category','index','hash','item_type','plot_id','x','y'))
                or any(inventory(public[s['sequence']])!=new for s in steps[1:])
                or inventory(first)!=inventory(fresh) or rows[1].get('inventory_receipts') is None):
            raise ValueError('Placement inventory did not witness the exact new item and original reset')
        result['native_inventory']=dict(positive_in_session=True,original_capture_reset_equal=True,
            original_and_reset_empty=not inventory(first),checkpoint_survival_claimed=False,
            host_tracking_used=False,complete_inventory_claimed=False)
    return result


def validate_order_group(acceptance, rows):
    """A cancelled empty queue is never evidence of clearing an actual order."""
    group=acceptance['unit_order_group'];first=rows[0]['public'][0];fresh=rows[1]['public'][0]
    ledger=rows[0]['ledger'];commands=ledger['commands'];public={r['sequence']:r for r in rows[0]['public']}
    byseq={r['protocol_sequence']:r for r in commands};uid=group['unit_id']
    if (ledger['updates'] or rows[1]['ledger']['transitions']
            or any(first[k]!=fresh[k] for k in ('observation','world_input','queued_orders','unit_orders','turn_availability'))
            or type(uid) is not int or type(group['complete']) is not bool
            or type(group['poll_calls']) is not int or group['poll_calls']!=0
            or group['foundation_performed'] is not False or group['private_target_queries_used'] is not False
            or group['healing_over_turns_qualified'] is not False
            or group['initial_turn']!=first['turn'] or group['final_turn']!=first['turn']
            or any(r['turn_before']!=first['turn'] or r['turn_after']!=first['turn'] for r in commands)
            or acceptance['commands']!=[r['command_result'] for r in commands]):
        raise ValueError('Unit-order group lost its exact same-turn/public/reset boundary')
    def prior(seq):return public[max(s for s in public if s<seq)]
    def queue(view):return next(r['plot_id'] for r in view['queued_orders']['units'] if r['unit_id']==uid)
    def order_at(seq):
        row=byseq[seq]
        if row['action']['kind']!='unit_order':raise ValueError('Expected an actual native unit order')
        return row
    steps=group['orders'];attempts=group['click_attempts'];claims=[]
    if type(steps) is not list or not 1<=len(steps)<=7 or type(attempts) is not list or len(attempts)>4:
        raise ValueError('Unbounded unit-order acceptance group')
    for step in steps:
        row=order_at(step['sequence']);effect=row['ledger']['phase_receipt'];claims.append(step['sequence'])
        if (step['action']!=row['action'] or step['command_result']!=row['command_result']
                or step['unit_before']!=effect['unit_before'] or step['unit_after']!=effect['unit_after']):
            raise ValueError('Claimed rest/wake/cancel differs from the native unit-order event')
    rest=order_at(group['rest_sequence']);rest_effect=rest['ledger']['phase_receipt']
    if (rest is not commands[0] or rest['action']['unit_id']!=uid
            or rest['action']['item_type'] not in ('UNITOPERATION_SLEEP','UNITOPERATION_FORTIFY')
            or rest_effect['state_changed'] is not True):
        raise ValueError('Group lacks an actual rest/activity change')
    healing=group['healing'];heal_names=('UNITOPERATION_HEAL','UNITOPERATION_RELIGIOUS_HEAL')
    if type(healing) is not list or [h['item_type'] for h in healing]!=list(heal_names[:len(healing)]):
        raise ValueError('Optional healing orders lack their exact availability record')
    def summary():
        return dict(complete=group['complete'],incomplete_reason=group['incomplete_reason'],unit_id=uid,
            release_action=group['release_action'],
            executed_orders=[r['action']['item_type'] for r in commands if r['action']['kind']=='unit_order'],
            queued_destination_cleared=group['complete'],world_click_attempts=len(attempts),
            native_healing_orders=[h['item_type'] for h in healing if h['executed']],
            healing_over_turns_qualified=False,poll_calls=0,network_ack_inferred=False,complete_gameplay_qualified=False)
    def missing_release(reason,sequence):
        available=public[sequence]['unit_orders']['offers']
        if (group['complete'] is not False or group['incomplete_reason']!=reason
                or acceptance['status']!='native_capability_unit_order_group_incomplete'
                or group['selection_sequence'] is not None or group['deselection_sequence'] is not None
                or attempts or group['cancel'] is not None or commands[-1]['protocol_sequence']!=sequence
                or len(claims)!=len(set(claims)) or set(claims)!=set(byseq)
                or any(r['legal'] and r['action']['unit_id']==uid and r['action']['item_type'] in
                       ('UNITCOMMAND_WAKE','UNITCOMMAND_CANCEL') for r in available)):
            raise ValueError('Missing native release was invented or incomplete cleanup scope changed')
        return summary()
    def release_at(sequence,action,rest_row):
        row=order_at(sequence);effect=row['ledger']['phase_receipt'];previous=rest_row['ledger']['phase_receipt']
        if (row['action']!=action or row['action']['unit_id']!=uid
                or row['action']['item_type'] not in ('UNITCOMMAND_WAKE','UNITCOMMAND_CANCEL')
                or effect['unit_before']!=previous['unit_after']
                or effect['unit_after']['activity_type']!=previous['unit_before']['activity_type']
                or not any(r['legal'] and r['action']==action for r in prior(sequence)['unit_orders']['offers'])):
            raise ValueError('Native rest/healing release differs from its actual offered command/effect')
        return row
    if group['release_sequence'] is None:
        if group['release_action'] is not None or healing:
            raise ValueError('Unreleased rest claims later healing or release')
        return missing_release('native_rest_release_not_offered',group['rest_sequence'])
    release=release_at(group['release_sequence'],group['release_action'],rest)
    if release is not commands[1] or release['ledger']['phase_receipt']['state_changed'] is not True:
        raise ValueError('Rest release lacks its actual activity restoration')
    for h in healing:
        if h['executed'] is False:
            v=public[h['checked_sequence']]
            if h.get('reason')!='not_natively_offered_for_selected_unit' or any(
                    r['action']['unit_id']==uid and r['action']['item_type']==h['item_type'] and r['legal']
                    for r in v['unit_orders']['offers']):
                raise ValueError('Optional native healing offer was silently skipped')
        elif h['executed'] is True:
            heal=order_at(h['sequence'])
            if heal['action']['item_type']!=h['item_type'] or heal['action']['unit_id']!=uid:
                raise ValueError('Optional healing claim lacks its delivered order')
            if h['release_sequence'] is None:
                if h['release_action'] is not None or h is not healing[-1]:
                    raise ValueError('Unreleased healing claims later inputs')
                return missing_release('native_healing_release_not_offered',h['sequence'])
            release_at(h['release_sequence'],h['release_action'],heal)
        else:raise ValueError('Healing execution flag is not Boolean')
    if len(healing)!=2:raise ValueError('Completed rest/release omitted an optional-healing availability check')
    selected=byseq[group['selection_sequence']];deselected=byseq[group['deselection_sequence']]
    if (selected['action']!=dict(kind='world_select_unit',unit_id=uid)
            or deselected is not commands[-1] or deselected['action']!=dict(kind='world_deselect_unit')
            or public[group['deselection_sequence']]['world_input']['selected_unit_id'] is not None):
        raise ValueError('Unit-order group lacks explicit selection/deselection')
    claims.extend((group['selection_sequence'],group['deselection_sequence']))
    for attempt in attempts:
        seq=attempt['sequence'];row=byseq[seq];target=attempt['target'];claims.append(seq)
        before,current=prior(seq),public[seq]
        if (target not in before['observation']['plots'] or target['visible'] is not True
                or target['water'] or target['impassable']
                or row['action']!=dict(kind='world_plot_click',unit_id=uid,plot_id=target['index'],x=target['x'],y=target['y'])
                or attempt['command_result']!=row['command_result']
                or attempt['queued_before']!=queue(before) or attempt['queued_after']!=queue(current)):
            raise ValueError('Queue-building click differs from its actual public target/destination')
    if len(claims)!=len(set(claims)) or set(claims)!=set(byseq):
        raise ValueError('Unit-order group omitted or duplicated an actual command')
    cancel=group['cancel'];witness=bool(attempts and attempts[-1]['command_result']['status']=='completed'
        and attempts[-1]['queued_after']==attempts[-1]['target']['index'])
    if group['complete']:
        if (type(cancel) is not dict or not witness or group['incomplete_reason'] is not None
                or acceptance['status']!='native_capability_unit_order_group_reset_verified'):
            raise ValueError('Complete unit-order group lacks its nonempty queue/cancellation witness')
        row=order_at(cancel['sequence']);before,current=prior(cancel['sequence']),public[cancel['sequence']]
        click=byseq[attempts[-1]['sequence']]['ledger']['phase_receipt']
        if (row['action']['item_type']!='UNITCOMMAND_CANCEL' or row['action']['unit_id']!=uid
                or queue(before) is None or queue(current) is not None
                or cancel['queued_before']!=queue(before) or cancel['queued_after'] is not None
                or click['native_request_delivered'] is not True):
            raise ValueError('CANCEL did not clear an actually queued native MOVE_TO destination')
    else:
        expected='native_cancel_not_offered_for_witnessed_queue' if witness else 'native_queued_destination_not_witnessed'
        if (cancel is not None or group['incomplete_reason']!=expected
                or acceptance['status']!='native_capability_unit_order_group_incomplete'):
            raise ValueError('Incomplete unit-order group overstates cancellation')
        if witness and any(r['action']['unit_id']==uid and r['action']['item_type']=='UNITCOMMAND_CANCEL' and r['legal']
                           for r in public[attempts[-1]['sequence']]['unit_orders']['offers']):
            raise ValueError('Offered CANCEL was omitted after witnessing a queued destination')
    return summary()


def validate_world_group(acceptance, rows):
    """Authenticate the bounded public exercise; do not generalize MOVE_TO."""
    first,fresh=rows[0]['public'][0],rows[1]['public'][0]
    ledger=rows[0]['ledger'];commands=ledger['commands'];group=acceptance['world_input_group']
    if (ledger['updates'] or rows[1]['ledger']['transitions']
            or any(first[k]!=fresh[k] for k in ('observation','world_input','queued_orders','turn_availability'))
            or type(group['poll_calls']) is not int or group['poll_calls']!=0
            or group['foundation_performed'] is not False or group['private_target_queries_used'] is not False
            or group['all_grid_targets_offered'] is not True
            or group['initial_turn']!=first['turn'] or group['final_turn']!=first['turn']):
        raise ValueError('World-input group is not the bounded same-turn/reset exercise')
    attempts=group['click_attempts'];uid=group['unit_id']
    if (type(uid) is not int or type(attempts) is not list or not 1<=len(attempts)<=4
            or len(commands)!=len(attempts)+3
            or acceptance['commands']!=[r['command_result'] for r in commands]
            or commands[0]['action']!=dict(kind='world_select_unit',unit_id=uid)
            or commands[-1]['action']!=dict(kind='world_deselect_unit')
            or commands[0]['protocol_sequence']!=group['selection_sequence']
            or commands[-1]['protocol_sequence']!=group['deselection_sequence']):
        raise ValueError('World-input acceptance actions differ from the authenticated command group')
    public={r['sequence']:r for r in rows[0]['public']}
    for claim,command in zip(attempts,commands[1:-2]):
        seq=command['protocol_sequence'];prior=public[max(s for s in public if s<seq)];current=public[seq]
        action=command['action'];target=claim['target']
        before=next(u for u in prior['observation']['units'] if u['id']==uid)
        after=next(u for u in current['observation']['units'] if u['id']==uid)
        qb=next(r['plot_id'] for r in prior['queued_orders']['units'] if r['unit_id']==uid)
        qa=next(r['plot_id'] for r in current['queued_orders']['units'] if r['unit_id']==uid)
        moved=(before['x'],before['y'])!=(after['x'],after['y'])
        if (claim['sequence']!=seq or claim['command_result']!=command['command_result']
                or target not in prior['observation']['plots'] or target['visible'] is not True
                or target['water'] or target['impassable']
                or action!=dict(kind='world_plot_click',unit_id=uid,plot_id=target['index'],x=target['x'],y=target['y'])
                or claim['unit_before']!=before or claim['unit_after']!=after
                or claim['queued_before']!=qb or claim['queued_after']!=qa
                or claim['position_changed'] is not moved or claim['target_queued'] is not (qa==target['index'])):
            raise ValueError('World-input movement claim differs from its public target/unit/queue')
    witness=commands[-3]['ledger']['phase_receipt'];last=attempts[-1]
    if (witness['native_request_delivered'] is not True or witness['native_route']!='request'
            or not (last['position_changed'] or last['target_queued'])):
        raise ValueError('World-input group lacks a real delivered request and observed position/queue effect')
    own=commands[-2];seq=own['protocol_sequence'];prior=public[max(s for s in public if s<seq)]
    unit=next(u for u in prior['observation']['units'] if u['id']==uid)
    plot=unit['y']*prior['observation']['width']+unit['x']
    if (group['own_cell']!=dict(sequence=seq,plot_id=plot,command_result=own['command_result'])
            or own['action']!=dict(kind='world_plot_click',unit_id=uid,plot_id=plot,x=unit['x'],y=unit['y'])
            or public[commands[-1]['protocol_sequence']]['world_input']['selected_unit_id'] is not None
            or any(r['turn_before']!=first['turn'] or r['turn_after']!=first['turn'] for r in commands)):
        raise ValueError('Own-cell click/deselection or same-turn boundary differs from the public group')
    return dict(unit_id=uid,public_click_attempts=len(attempts),native_requests=sum(
        r['ledger']['phase_receipt']['native_request_delivered'] for r in commands),
        refused_inputs=sum(r['command_result']['status']=='refused' for r in commands),
        own_cell_native_route=own['ledger']['phase_receipt']['native_route'],
        final_selection_cleared=True,all_grid_targets_offered=True,poll_calls=0,
        full_movement_or_combat_qualified=False,network_ack_inferred=False)


def validate_turn_group(acceptance, rows):
    """Keep one captured turn distinct from general scheduling/complete gameplay."""
    first,fresh=rows[0]['public'][0],rows[1]['public'][0]
    if rows[1]['ledger']['transitions'] or first['turn_availability']!=fresh['turn_availability']:
        raise ValueError('Turn reset did not restore an untouched native turn boundary')
    transitions=rows[0]['ledger']['transitions'];updates=rows[0]['ledger']['updates']
    commands=rows[0]['ledger']['commands'];group=acceptance['turn_group']
    by_sequence={r['sequence']:r for r in rows[0]['public']}
    final=by_sequence[transitions[-1]['protocol_sequence']]
    controls=final['turn_controls']
    turn_commands=[r for r in commands if r['action']['kind'] in ('end_turn','force_end_turn','unready_turn')]
    repeated=group.get('repeated_forced_request')
    submitted=[r for r in turn_commands if r['ledger']['phase_receipt']['turn_request_status']=='submitted']
    if (not updates or not turn_commands or group['initial_turn']!=first['turn']
            or group['final_turn']!=first['turn']+1 or final['turn']!=group['final_turn']
            or type(group['poll_calls']) is not int or group['poll_calls']!=len(updates)
            or group['initial_request']!=turn_commands[0]['action']['kind']
            or group['final_controls']!=controls or controls['active'] is not True
            or controls['active_complete'] is not True or controls['can_unready'] is not False
            or any(r['ledger']['phase_receipt']['turn_request_status']!='completed'
                   for r in turn_commands if r not in submitted)):
        raise ValueError('Acceptance turn claim differs from authenticated native transitions')
    if repeated is None:
        if submitted:raise ValueError('Submitted request lacks its explicit acceptance receipt')
    else:
        previous_controls=by_sequence[max(seq for seq in by_sequence if seq<repeated['sequence'])]['turn_controls']
        if (len(submitted)!=1 or submitted[0]['protocol_sequence']!=repeated['sequence']
                or submitted[0] is turn_commands[0] or submitted[0]['action']!={'kind':'force_end_turn'}
                or repeated['before']!=repeated['after'] or repeated['before']['active'] is not False
                or repeated['before']!=previous_controls
                or repeated['after']!=by_sequence[repeated['sequence']]['turn_controls']
                or repeated['command_result']!=dict(status='submitted',reason='native_turn_controls_unchanged',
                                                    requested_action={'kind':'force_end_turn'})):
            raise ValueError('Repeated forced request differs from its authenticated submission')
    ready=by_sequence[turn_commands[0]['protocol_sequence']]
    if group['ready']!=ready['turn_controls']:
        raise ValueError('Acceptance readiness differs from the actual public reply')
    unready=[r for r in turn_commands if r['action']['kind']=='unready_turn']
    if (type(group['unready_executed']) is not bool or group['unready_executed'] is not bool(unready)
            or len(unready)>1 or (not unready and group['unready'] is not None)
            or (unready and group['unready']!=by_sequence[unready[0]['protocol_sequence']]['turn_controls'])
            or (not unready and ready['turn_availability']['unready_turn'] is True)):
        raise ValueError('Unready was claimed or omitted inconsistently with actual availability/delivery')
    return dict(initial_turn=first['turn'],final_turn=final['turn'],native_updates=len(updates),
        explicit_turn_requests=[r['action']['kind'] for r in turn_commands],
        submitted_without_confirmed_effect=len(submitted),
        unready_executed=bool(unready),local_transport_only=True,
        network_ack_inferred=False,long_continuations_qualified=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--acceptance',type=Path,required=True)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replay-stdout-parser-run',type=Path,
        help='Read-only additive review of this exact retained parser refusal')
    parser.add_argument('--retained-supervisor-sha256')
    parser.add_argument('--retained-archive-sha256')
    parser.add_argument('--replay-post-close-combat-information',action='store_true',
        help='Read-only review of the single hash-bound completed XP2 attack/reset query-after-close refusal')
    args=parser.parse_args()
    if any((args.replay_stdout_parser_run,args.retained_supervisor_sha256,args.retained_archive_sha256)):
        if not all((args.replay_stdout_parser_run,args.retained_supervisor_sha256,args.retained_archive_sha256)):
            parser.error('Parser refusal review requires run, supervisor hash and executed archive hash together')
        replay=dict(run=str(args.replay_stdout_parser_run.resolve()),
            supervisor_sha256=args.retained_supervisor_sha256,archive_sha256=args.retained_archive_sha256)
    else:replay=None
    result=review(args.acceptance,args.archive,stdout_parser_replay=replay,
                  replay_post_close_combat_information=args.replay_post_close_combat_information)
    with args.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    print(json.dumps(dict(reference=pin(args.output),status=result['status'],
        command_count=sum(len(r['ledger']['commands']) for r in result['runs']),
        elapsed=[r['elapsed_seconds'] for r in result['runs']],
        memory=[r['memory'] for r in result['runs']])))


if __name__=='__main__':main()
