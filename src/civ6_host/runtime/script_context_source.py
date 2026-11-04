"""Saved Load script-manager ABI; not admission of an expansion saved game."""
from __future__ import annotations

import ctypes as C
import hashlib
from pathlib import Path
import struct

from .configuration_profiles import _source, _body, XP1_CORE_SHA256
from .paths import resource_root
from .resource_resolution import resolve_path

SOURCE = ('work/host-extensions/script-context-static/script-context-saved-load-xp1-source-v1.json',
          '39943b7e857d89bccbc1149eed757ea643bd5ed34ac9e68fea5c3297296a6249')
NOTIFY_HOST_SHA = '11993e669bc00bbeab60414abc50466e388c9c589a70d3a8428c8873c8d16581'
NOTIFY_COMPONENT_SHA = 'c7001dfecee4a8513e47011b938f4ba91bd4718a675ec613386165a1b4a76c2b'
POSTLOAD_HOST_SHA = 'ef3d85f1baa913888a1c48802e0862592cecf1e1dffff0e6964ffba1f146411f'
POSTLOAD_BUILD = ('work/native-host-xp1-postload-build01/build.json',
                 '36edef5ffb199f080fa5b01dea0969377bc386844b166013d37dcd1fa5d35269')


def verify_notification_image(path):
    """Admit the unchanged notification component in explicit source builds.

    This is source association for the component, not full-host qualification.
    The category/NULL addition has its own native acceptance group.
    """
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest == NOTIFY_HOST_SHA:
        return
    from .source_build_identity import verify_source_build
    verify_source_build(path, required_components={'script_context_notify.inc':NOTIFY_COMPONENT_SHA})


def verify_notification_host(host):
    """An explicit new executable, containing the unchanged productive prefix.

    Old diagnostic builds retain their original verifier in the lab. The new
    executable excludes the private native-byte oracle, not its runtime checks.
    """
    kernel = C.WinDLL('kernel32', use_last_error=True)
    fn = kernel.GetModuleFileNameW
    fn.argtypes,fn.restype = [C.c_void_p,C.c_wchar_p,C.c_uint],C.c_uint
    output = C.create_unicode_buffer(32768)
    count = fn(host._handle,output,len(output))
    if not 0 < count < len(output):
        raise ValueError('Cannot identify context notification executable')
    path = Path(output.value).resolve(strict=True)
    verify_notification_image(path)


def source():
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6_host.script_context_saved_load_xp1_static.v1'
            or proof['images']['xp1']['sha256'] != XP1_CORE_SHA256
            or proof['contract']['saved_load']['receiver']['getter_rva'] != '0x51a9d0'
            or proof['contract']['saved_load']['cleanup']['clear_rva'] != '0x51b200'
            or proof['contract']['saved_load']['protected_callbacks_required']):
        raise ValueError('Script manager source contract differs')
    for ref in proof['references'].values():
        if hashlib.sha256(resolve_path(resource_root()/ref['path']).read_bytes()).hexdigest() != ref['sha256']:
            raise ValueError('Script manager source dependency changed')
    return proof


def live_bodies(proof):
    # Only the Saved Load loader/cleanup, not unrelated NewGame methods.
    result = {name:proof['functions']['xp1'][name] for name in (
        'release_all_contexts','manager_destructor','manager_reset',
        'filename_component','filename_stem','name_utf8_destination',
        'name_utf8_argument_wrapper','name_utf8_encoder','name_wcslen','name_last_dot')}
    cache = {}
    for name,row in proof['referenced_bodies'].items():
        if row['image'] != 'xp1':
            continue
        ref = proof['references'][row['reference']]
        if row['reference'] not in cache:
            cache[row['reference']] = _source((ref['path'],ref['sha256']))
        body = cache[row['reference']]
        for key in row['selector']:
            body = body[key]
        result[name] = body
    return result


def verify_xp1(base, read, *, inner, auxiliary):
    if any(type(v) is not int or not 0 < v < (1<<63) for v in (base,inner,auxiliary)):
        raise ValueError('Invalid script manager address')
    proof = source()
    for name,body in live_bodies(proof).items():
        for fragment in _body(body)['fragments']:
            for ins in fragment['instructions']:
                raw = bytes.fromhex(ins['bytes'])
                if read(base+int(ins['va'],16)-0x180000000,len(raw)) != raw:
                    raise ValueError('Script manager live code differs: '+name)
    for offset,pointer in ((0x9F2620,inner),(0x9F2648,auxiliary)):
        if read(base+offset,8) != struct.pack('<Q',pointer):
            raise ValueError('Script manager installed global differs')
    manager = struct.unpack('<Q',read(inner+0x1A58,8))[0]
    if not manager:
        raise ValueError('Script manager not constructed')
    read(manager,0x30)
    return manager
