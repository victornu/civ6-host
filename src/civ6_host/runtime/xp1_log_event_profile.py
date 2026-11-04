"""Source admission for reusing the shared event recorder with XP1.

No callback is installed or executed by this module. Actual private-file output
uses NativeEventRecorder through the already compiled setter/getter exports.
"""
import hashlib
import json
from pathlib import Path
from .configuration_profiles import XP2_CORE_SHA256

from civ6_host.runtime.unit_operation_ui_profile import instruction_spans

CORE_SHA256='259b90a473a256aff6a7d621a4f3717e46f6921c59b9817475375c88b97e8c83'
EXE_SHA256='e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
SOURCE=('work/host-extensions/xp1-log-event-static/log-event-source-v1.json',
        'e13cad522675bda9a656e4e760f08f01457e5e160e94203e49340f9aaff629a9')


def source(root=None,*,core_sha256=CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_action_transport_source import source as selected
        return selected(root)
    if core_sha256!=CORE_SHA256:raise ValueError('Unknown event-log source engine')
    if root is None:
        from civ6_host.runtime.provenance import resource_root
        root=resource_root()
    path=Path(root)/SOURCE[0]
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE[1]:
        raise ValueError('XP1 log-event source changed')
    proof=json.loads(raw)
    if (proof['schema']!='civ6_host.xp1_log_event_source.v1'
            or proof['images']['xp1']['sha256']!=CORE_SHA256
            or proof['images']['exe']['sha256']!=EXE_SHA256
            or proof['targets']['event_wrapper']!='0x837ae0'
            or proof['abi']['wrapper_tail_calls_callback'] is not True
            or proof['abi']['callback_return_consulted_by_request'] is not False
            or proof['recommendation']['c_change_required'] is not False):
        raise ValueError('Unexpected XP1 log-event contract')
    return proof


def source_dependencies(root=None,*,core_sha256=CORE_SHA256):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_action_transport_source import source_dependencies as selected
        return selected(root)
    if core_sha256!=CORE_SHA256:raise ValueError('Unknown event-log source engine')
    if root is None:
        from civ6_host.runtime.provenance import resource_root
        root=resource_root()
    proof=source(root)
    result={str(Path(root)/SOURCE[0]):SOURCE[1]}
    for row in [*proof['source_dependencies'],proof['extractor'],*proof['images'].values()]:
        path,digest=row['path'],row['sha256']
        if path in result and result[path]!=digest:
            raise ValueError('Conflicting event source dependency')
        result[path]=digest
    return result


def verify_live(base,read,*,core_sha256=CORE_SHA256,root=None):
    if core_sha256==XP2_CORE_SHA256:
        from .xp2_action_transport_source import verify_live as selected
        receipt=selected(base,read,family='log',root=root)
        receipt['receiver']='civ6_host.runtime.native.native_events.NativeEventRecorder'
        receipt['native_callback_invoked']=False
        return receipt
    if core_sha256!=CORE_SHA256 or type(base) is not int or base<=0:
        raise ValueError('Log-event profile requires exact XP1')
    proof=source(root)
    spans=instruction_spans(proof)
    for rva,expected in spans:
        if read(base+rva,len(expected))!=expected:
            raise ValueError('XP1 log-event instruction bytes changed at '+hex(rva))
    for row,encoding in ((proof['data']['name_utf16'],'utf-16-le'),
                         (proof['data']['callback_export'],'ascii')):
        expected=(row['text']+'\0').encode(encoding)
        if read(base+int(row['rva'],16),len(expected))!=expected:
            raise ValueError('XP1 log-event source string changed')
    return dict(source_sha256=SOURCE[1],instruction_spans_verified=len(spans),
        native_callback_installed=False,native_callback_invoked=False,actions_admitted=False,
        receiver='civ6_host.runtime.native.native_events.NativeEventRecorder')
