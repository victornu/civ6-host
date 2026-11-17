"""Source supplement for PlayerEraScoreChanged following a historical moment."""
from functools import lru_cache
import hashlib
import re
from .configuration_profiles import XP1_CORE_SHA256,_source
from . import game_history_event_profile as history

SOURCE=('work/host-extensions/xp1-production-placement-static/history-score-source-supplement-v1.json',
        '3f43fe7d4631122f6c0eb786722fab1ec71001febd369c200ffceeb4be3f8d03')
INSTALLED_SHORT_SOURCE = ('evidence/host-xp1-installed-era-score-short-source.json',
                          '1d097d6f04fb8242b5984d3abfd0cd1ea834d4746e83b3129b198998e2e40318')
EVENT_KIND=0x788b7534
SPEC=(0x10a,6,0x14b8d0,0x120000,0xc6220,0xd4ed0)
SELECTOR_KEY = 0xA1E5A149
VALUE_KEY = 0xD6FCF3E4
SHORT_KEYS = frozenset((SELECTOR_KEY, VALUE_KEY))


def _normalized(body,writer=None):
    rows=body['instructions'];addresses={int(r['va'],16):i for i,r in enumerate(rows)};result=[]
    for r in rows:
        s=re.sub(r'rip [+-] 0x[0-9a-f]+','rip OFFSET',r['text'])
        s=re.sub(r'(mov dword ptr \[rbx \+ 4\], )0x[0-9a-f]+',r'\1RECORD',s)
        match=re.fullmatch(r'(j\w+) (0x[0-9a-f]+)',s)
        if match and int(match[2],16) in addresses:s=match[1]+' label'+str(addresses[int(match[2],16)])
        if writer and s==f'call {hex(0x140000000+writer)}':s='call WRITER'
        result.append(s)
    return result


def _verify_rip_targets(actual,reference,*,hook_relocation=None):
    left=actual['instructions'];right=reference['instructions']
    if len(left)!=len(right):raise ValueError('Era-score instruction count differs')
    differences=0
    for a,b in zip(left,right):
        targets_a=tuple(a.get('rip_targets',()));targets_b=tuple(b.get('rip_targets',()))
        if targets_a==targets_b:continue
        if (hook_relocation is None or (targets_b,targets_a)!=hook_relocation
                or not a['text'].startswith('lea rax, [rip ')
                or not b['text'].startswith('lea rax, [rip ')):
            raise ValueError('Era-score shared queue/counter RIP target changed')
        differences+=1
    if differences!=int(hook_relocation is not None):
        raise ValueError('Era-score event hook relocation differs')


@lru_cache(maxsize=1)
def verify_source():
    from .native.native_host_event_registry import EXE_EVENT_CALLBACKS
    original,_=history.verify_source();p=_source(SOURCE)
    if (p['schema']!='civ6-host.xp1-history-score-followup.static.v1'
            or p['native_execution'] is not False or p['process_memory_read'] is not False
            or p['images']['xp1']['sha256']!=XP1_CORE_SHA256 or p['images']['exe']['sha256']!=history.EXE_SHA
            or (p['event_kind'],p['record_type'],p['record_size'],p['metadata_flag'])!=(EVENT_KIND,0x10a,96,6)
            or EXE_EVENT_CALLBACKS.get(EVENT_KIND)!=SPEC[2]
            or 0x0c19b649 in EXE_EVENT_CALLBACKS
            or p['validation']['all_instruction_bytes_match_image'] is not True
            or p['validation']['bounded_switch_targets_checked'] is not True):
        raise ValueError('Era-score source identity changed')
    for ref in p['references']:_source((ref['path'],ref['sha256']))
    f=p['functions']['exe'];ref=original['neighbors'][0]['functions']
    if (_normalized(f['0x14b8d0'],SPEC[3])!=_normalized(ref['0x147200'],0x11f4e0)
            or _normalized(f['0x120000'])!=_normalized(ref['0x11f4e0'])):
        raise ValueError('Era-score no longer matches the exact scalar producer/writer')
    # Callback hook is row+0x10 for this event, not another global. Every
    # thread-index, queue and lock reference remains exactly the same.
    _verify_rip_targets(f['0x14b8d0'],ref['0x147200'],
        hook_relocation=(('0x1412c9980',),('0x1412c9aa0',)))
    _verify_rip_targets(f['0x120000'],ref['0x11f4e0'])
    receiver=p['receiver']
    if (receiver['event_name']!='GameCoreEvent::PlayerEraScoreChanged'
            or int(receiver['row_va'],16)-0x1412c68b0!=0x10a*48
            or receiver['destructor_rva']!=0xea0e0
            or not {'xor ebx, ebx','lea ecx, [rbx + 0x38]','mov qword ptr [rcx], rbx',
                    'mov qword ptr [rcx + 8], rbx','mov qword ptr [rcx + 0x10], rbx',
                    'mov qword ptr [rcx + 0x18], rdx','mov qword ptr [rax + 8], rbx',
                    'mov dword ptr [rax + 0x20], ebx','and byte ptr [rax + 0x30], 0xfc'}
                   <=set(history._texts(f['0xc6220']))
            or [r for r in history._texts(f['0xd4ed0']) if r.startswith('call ')]
                !=['call 0x14098a780','call 0x1400dc0d0','call 0x14098a7b0']):
        raise ValueError('Era-score receiver state or effects changed')
    xp=p['functions']['xp1'];body=xp['0x18ff70'];texts=set(history._texts(body))
    if not {'mov qword ptr [rbp - 0x10], 0x788b7534','call 0x180519650',
            'test r13d, r13d','lea eax, [r13 - 1]','cmp eax, 0x10','ja 0x180190364'}<=texts:
        raise ValueError('Era-score producer path changed')
    addresses={int(r['va'],16)-0x180000000 for r in body['instructions']}
    if any(t not in addresses for t in body['jump_table']['target_rvas']):
        raise ValueError('Era-score switch target is outside captured instructions')
    return p


def source_dependencies(*,execution_image=None):
    from .paths import resource_root
    from .resource_resolution import resolve_path
    from .xp1_saved_load_logger import source_dependencies as logger_sources
    p=verify_source();refs=[dict(path=SOURCE[0],sha256=SOURCE[1]),*p['references']]
    history_pins=history.source_dependencies()
    pins={**history_pins,
          **logger_sources(),
          **{str(resolve_path(resource_root()/r['path']).resolve()):r['sha256'] for r in refs}}
    if execution_image is None:
        pins.update({str(resolve_path(resource_root()/r['path']).resolve()):r['sha256']
                     for r in p['images'].values()})
    else:
        from .runtime_source_dependencies import materialize_runtime_source_pins
        pins=materialize_runtime_source_pins(pins,execution_image=execution_image,
                                             provenance_images=(*history.verify_source()[0]['images'].values(),
                                                                *p['images'].values()))
    return pins


def uses_installed_short_shape(kind, fields, execution_image):
    from .execution_images import _XP1_PROFILE
    return (execution_image is _XP1_PROFILE and kind == EVENT_KIND
            and type(fields) is dict and set(fields) == SHORT_KEYS)


def decode_missing_second(fields):
    from .native.native_scalar_event_encoder import _read_u32_variant
    from .native.native_two_value_event_family import verify_missing_b_source_evidence

    if type(fields) is not dict or set(fields) != SHORT_KEYS:
        raise ValueError('Era-score short Core argument keys differ')
    verify_missing_b_source_evidence()
    selector = _read_u32_variant(fields[SELECTOR_KEY], 3, 'selector')
    if selector != 0:
        raise ValueError('Era-score requires the common selector-zero normalizer route')
    # The EXE initializes both normalized DWORDs before applying the present
    # keys. Only D6 is written by this producer. There is no raw second field.
    return selector, _read_u32_variant(fields[VALUE_KEY], 2, 'value A'), 0


@lru_cache(maxsize=1)
def _installed_short_source():
    from .execution_images import _XP1_PROFILE, identity
    from .native.native_two_value_event_family import verify_missing_b_source_evidence

    proof = _source(INSTALLED_SHORT_SOURCE)
    if (proof['schema'] != 'civ6-host.xp1-era-score-short.static.v1'
            or proof['image'] != identity(_XP1_PROFILE)
            or proof['contract'] != {
                'kind': EVENT_KIND, 'selector': 0, 'scalar_flags': 0,
                'key_tags': {hex(SELECTOR_KEY): 3, hex(VALUE_KEY): 2},
                'native_default_second': 0, 'normalizer_offsets': (0x50, 0x54),
                'installed_writer_record': 0x109, 'retained_host_record': SPEC[0],
                'record_size': 96, 'metadata_flag': SPEC[1]}):
        raise ValueError('Installed XP1 era-score source identity changed')
    verify_missing_b_source_evidence()
    return proof


def installed_short_source_dependencies(execution_image):
    from pathlib import Path
    from .execution_images import _XP1_PROFILE
    from .native.native_two_value_event_family import MISSING_B_PROOF_SHA256, _MISSING_B_PROOF_PATH
    from .paths import resource_root
    from .resource_resolution import resolve_path

    if execution_image is not _XP1_PROFILE:
        raise ValueError('Short era-score sources require the exact installed XP1 image')
    exe = _installed_short_source()['executable']
    return {
        str(resolve_path(resource_root() / INSTALLED_SHORT_SOURCE[0]).resolve()): INSTALLED_SHORT_SOURCE[1],
        str(_MISSING_B_PROOF_PATH.resolve()): MISSING_B_PROOF_SHA256,
        str(Path(exe['path']).resolve()): exe['sha256'],
    }


def receiver_row():
    body=verify_source()['functions']['exe']['0xd4ed0']
    return dict(record_sizes={96},event_name='GameCoreEvent::PlayerEraScoreChanged',handler_va='0x1400d4ed0',
        handler_body_sha256=hashlib.sha256(b''.join(bytes.fromhex(r['bytes']) for r in body['instructions'])).hexdigest(),
        source_sha256=SOURCE[1])


def bind_owner(backend,core,read):
    backend.check_thread()
    if backend.core is not core or backend.load_abi.core_sha256!=XP1_CORE_SHA256:
        raise ValueError('Era-score has a foreign native owner')
    p=verify_source()
    for body in p['functions']['xp1'].values():
        for r in body['instructions']:
            raw=bytes.fromhex(r['bytes'])
            if read(core._handle+int(r['va'],16)-0x180000000,len(raw))!=raw:
                raise ValueError('XP1 era-score native source changed')
    table=p['functions']['xp1']['0x18ff70']['jump_table'];raw=bytes.fromhex(table['raw_hex'])
    if read(core._handle+int(table['rva'],16),len(raw))!=raw:raise ValueError('Era-score switch table changed')
    from .execution_images import _XP1_PROFILE
    if getattr(core, '_civ6_host_execution_image', None) is _XP1_PROFILE:
        for span in _installed_short_source()['core'].values():
            raw = read(core._handle + span['rva'], span['bytes'])
            if hashlib.sha256(raw).hexdigest() != span['sha256']:
                raise ValueError('Installed XP1 short era-score native source changed')
    from .native.native_deferred_empty_profile import resolve_empty_receiver_row
    if resolve_empty_receiver_row(SPEC[0])!=receiver_row():raise ValueError('Era-score receiver differs')
    return SOURCE[1]
