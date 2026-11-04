"""Source boundary for shared controller effects in two A0 event families."""
from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from .configuration_profiles import XP1_CORE_SHA256,_source
from .a0_family_source import A0FamilyProfile,_path,verify_pinned_files,verify_extracted_sources

SOURCE=('work/host-extensions/a0-controller-static/a0-controller-xp1-source-v1.json',
        'be533607027644ca6df0c42dd055313db1f6c7ee243586610f904f1b3b4c65d5')
_UNIT_PANEL='../civ6-host/src/civ6_host/runtime/unit_panel_gate.py'


def source():
    p=_source(SOURCE);profile=p['profile']
    from .native.native_controller_code import SOURCE_SHA,EXE_SHA
    expected=dict(native_execution=False,product_modified=False,all_instruction_bytes_match_pinned_images=True,
        instruction_count=2507,receiver_rows_equal_existing_load_rows=True,controller_event_count=2)
    if (p['schema']!='civ6_host.a0_controller_xp1.static.v1' or dict(p['validation'])!=expected
            or profile['core_sha256']!=XP1_CORE_SHA256 or profile['exe_sha256']!=EXE_SHA
            or p['references']['native_controller']['sha256']!=SOURCE_SHA
            or profile['source_pins']!=p['source_pins']):
        raise ValueError('A0 controller source identity differs')
    if ({int(k):tuple(v) for k,v in profile['kind_to_record_types'].items()}!={0x21535587:(4,),0x8953F126:(15,)}
            or {int(k):v for k,v in profile['record_type_to_size'].items()}!={4:96,15:96}
            or set(profile['kind_values'])!={0x21535587,0x8953F126}):
        raise ValueError('A0 controller family membership differs')
    controller=profile['controller'];manager=profile['manager'];telemetry=profile['telemetry']
    if (controller['size']!=1200 or controller['flag_offset']!=13 or controller['fresh_flag']!=0
            or controller['constructor_rva']!='0xf4590' or controller['getter_rva']!='0xf54f0'
            or controller['setter_rva']!='0xf78f0'
            or manager['initial_value']!=0 or manager['clear_mask']!=0xBF or manager['flags_offset']!=4
            or telemetry['host_lane']!=0 or telemetry['maximum_retained_values']!=32768
            or telemetry['admission_count_before_append_lt']!=32768
            or telemetry['full_native_ring_reproduced'] is not False):
        raise ValueError('A0 controller/manager/telemetry state boundary differs')
    return p


def source_pins():
    p=source();refs=[{'path':SOURCE[0],'sha256':SOURCE[1]},*p['references'].values(),*p['source_pins'].values()]
    pins={}
    for ref in refs:
        path=(Path(__file__).resolve().with_name('unit_panel_gate.py')
              if ref['path']==_UNIT_PANEL else _path(ref['path']))
        key=str(path)
        if key in pins and pins[key]!=ref['sha256']:raise ValueError('Conflicting A0 controller sources')
        pins[key]=ref['sha256']
    return pins


def controller_profile():
    p=source();verify_pinned_files(source_pins())
    verify_extracted_sources(r for r in p['source_pins'].values() if r['path']!=_UNIT_PANEL)
    from .native.native_deferred_empty_profile import _ROWS
    profile=p['profile'];sizes={int(k):v for k,v in profile['record_type_to_size'].items()}
    for kind,size in sizes.items():
        expected=profile['receiver_rows'][str(kind)];row=_ROWS.get(kind)
        if (row is None or set(row['record_sizes'])!={size}
                or any(row[k]!=expected[k] for k in ('event_name','handler_va','handler_body_sha256'))):
            raise ValueError('A0 controller presentation receiver differs')
    return A0FamilyProfile(MappingProxyType({int(k):frozenset(v) for k,v in profile['kind_to_record_types'].items()}),
        MappingProxyType(sizes),SOURCE[1])
