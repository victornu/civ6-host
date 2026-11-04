"""Select the expansion logger ABI without changing its shared channel state.

The module name is retained for existing XP1 consumers. XP2 selection only
admits the source-checked interface, not saved Load or gameplay.
"""
from __future__ import annotations

import ctypes as C
import hashlib
from pathlib import Path

from .configuration_profiles import XP1_CORE_SHA256, XP2_CORE_SHA256, _source, _body

SOURCE = ('work/host-extensions/xp1-load-logger-static/xp1-load-logger-source-v1.json',
          '16d3d479d2280784ba5063bf4f29308d6b2e8ab9280da6d5de736199e83c8af7')
SLOTS = (0x10, 0x18, 0x20, 0x28, 0x38, 0x40, 0x50)
XP2_SOURCE = ('work/host-extensions/xp2-load-logger-static/source-profile-v1.json',
              '075ec1f5fdd8102544391d6c50858dc4895c7081b15083ea6999fdfee9b3bc30')
XP2_SUPPLEMENT = ('work/host-extensions/xp2-load-logger-static/source-profile-v2.json',
                  '649871fac8c0536bd160cc003d08690791dabdb14342a131d6ea95afe7e4d9c7')
XP2_EXTRA_SLOTS = (0x30,)
HOST_LIFETIME_COMPATIBILITY = (
    'work/host-extensions/xp1-loaded-lifetime-static/logger-host-compatibility.json',
    'a73c10133e4baeea6c5a88c726f2d461a14a859241541050eef52c0f2d86473e')
HOST_INIT_COMPATIBILITY = (
    'work/host-extensions/xp2-load-logger-static/host-compatibility-v1.json',
    '61ec408a7953499c7095c9682c01e0beb67e348705294e2cc45b424962dd5f95')


def source_dependencies(core_sha256=XP1_CORE_SHA256):
    from .paths import resource_root
    from .resource_resolution import resolve_path
    proof = _source(SOURCE)
    rows = [dict(path=SOURCE[0], sha256=SOURCE[1]),
            dict(path=HOST_LIFETIME_COMPATIBILITY[0], sha256=HOST_LIFETIME_COMPATIBILITY[1]),
            dict(path=HOST_INIT_COMPATIBILITY[0], sha256=HOST_INIT_COMPATIBILITY[1]),
            *proof['references'].values()]
    if core_sha256 == XP2_CORE_SHA256:
        selected = _checked_source(core_sha256)
        rows.extend([dict(path=XP2_SOURCE[0], sha256=XP2_SOURCE[1]),
                     *selected['references'], *selected['extractors'], selected['generator']])
        supplement = _checked_xp2_supplement()
        rows.extend([dict(path=XP2_SUPPLEMENT[0], sha256=XP2_SUPPLEMENT[1]),
                     supplement['parent_profile'], supplement['exe_parent_proof'],
                     *supplement['extractors'], supplement['generator']])
    elif core_sha256 != XP1_CORE_SHA256:
        raise ValueError('Unknown saved-Load logger engine')
    return {str(resolve_path(resource_root()/r['path']).resolve()): r['sha256'] for r in rows}


def _checked_xp1_source():
    from .native import native_host, native_logging
    proof = _source(SOURCE)
    if (proof['schema'] != 'civ6_host.xp1_load_logger.static.v1'
            or proof['xp1_sha256'] != XP1_CORE_SHA256
            or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or proof['native_execution'] is not False
            or tuple(proof['admitted_slots']) != tuple(hex(x) for x in SLOTS)):
        raise ValueError('XP1 logger source identity changed')
    for ref in proof['references'].values():
        _source((ref['path'], ref['sha256']))
    for module in (native_host, native_logging):
        path = Path(module.__file__)
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        expected = proof['host_callback_sources'][path.name]
        if actual == expected:
            continue
        if module is native_host:
            migration = _source(HOST_LIFETIME_COMPATIBILITY)
            if (migration['schema'] == 'civ6_host.logger_lifetime_compatibility.v1'
                    and migration['original_host_sha256'] == expected
                    and migration['current_host_sha256'] == actual
                    and migration['exact_original_reconstructed'] is True):
                continue
            init = _source(HOST_INIT_COMPATIBILITY)
            if (migration['schema'] == 'civ6_host.logger_lifetime_compatibility.v1'
                    and migration['original_host_sha256'] == expected
                    and migration['exact_original_reconstructed'] is True
                    and init['schema'] == 'civ6-host.logger-expansion-init-compatibility.v1'
                    and init['prior_compatibility']['sha256'] == HOST_LIFETIME_COMPATIBILITY[1]
                    and init['original_logger_host_sha256'] == expected
                    and init['prior_host_sha256'] == migration['current_host_sha256']
                    and init['current_host_sha256'] == actual
                    and init['exact_prior_reconstructed'] is True
                    and init['replacement_function'] == 'initialize_context'
                    and init['diagnostic_host_class_byte_identical'] is True):
                continue
        if actual != expected:
            raise ValueError('Shared logger implementation changed: ' + path.name)
    return proof


def _checked_source(core_sha256=XP1_CORE_SHA256):
    if core_sha256 not in (XP1_CORE_SHA256, XP2_CORE_SHA256):
        raise ValueError('Unknown saved-Load logger engine')
    shared = _checked_xp1_source()
    if core_sha256 == XP1_CORE_SHA256:
        return shared
    proof = _source(XP2_SOURCE)
    if (proof['schema'] != 'civ6-host.xp2-load-logger-source.v1'
            or proof['image_sha256'] != XP2_CORE_SHA256
            or proof['exe_sha256'] != shared['exe_sha256']
            or proof['native_execution'] is not False
            or proof['logger_global_rva'] != '0xb8aa90'
            or tuple(proof['admitted_slots']) != tuple(hex(x) for x in SLOTS)
            or dict(proof['contracts']) != dict(shared['contracts'])
            or dict(proof['shared_host_callback_sources']) != dict(shared['host_callback_sources'])):
        raise ValueError('XP2 logger source identity/ABI changed')
    for ref in proof['references']:
        _source((ref['path'], ref['sha256']))
    from .paths import resource_root
    from .resource_resolution import resolve_path
    for ref in (*proof['extractors'], proof['generator']):
        path = resolve_path(resource_root()/ref['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != ref['sha256']:
            raise ValueError('XP2 logger source extractor changed')
    for value in proof['bodies'].values():
        for body in (value['body'], *(t['body'] for t in value['out_of_line_tail_jumps'])):
            for fragment in _body(body)['fragments']:
                raw = bytes.fromhex(fragment['raw_hex'])
                if (len(raw) != fragment['length']
                        or raw != b''.join(bytes.fromhex(r['bytes']) for r in fragment['instructions'])
                        or hashlib.sha256(raw).hexdigest() != fragment['sha256']):
                    raise ValueError('XP2 logger source body is incomplete')
    for assertion in proof['assertions']:
        body = proof['bodies'][assertion['body']]['body']
        rows = [r for f in _body(body)['fragments'] for r in f['instructions']]
        if not any(r['rva'] == assertion['rva'] and r['text'] == assertion['text'] for r in rows):
            raise ValueError('XP2 logger ABI callsite changed')
    return proof


def _checked_xp2_supplement():
    proof = _source(XP2_SUPPLEMENT)
    if (proof['schema'] != 'civ6-host.xp2-load-logger-source-supplement.v2'
            or proof['image_sha256'] != XP2_CORE_SHA256
            or proof['exe_sha256'] != 'e7450823cc8e00468cff7b9d7b97c63140eae38ae1d774ba4efa437556c42d63'
            or proof['parent_profile'] != {'path': XP2_SOURCE[0], 'sha256': XP2_SOURCE[1],
                                           'bytes': proof['parent_profile'].get('bytes')}
            or proof['exe_vtable_targets'] != {'0x30': '0x14015b830', '0x48': '0x14015ac90'}
            or proof['contracts']['0x30'] != {
                'this': 'logger object in RCX', 'channel': 'uint32 in EDX',
                'level': 'uint32 in R8D', 'return': 'void',
                'existing_channel': 'writes the full uint32 level at channel value +0x14c',
                'missing_channel': 'level zero does not create; nonzero creates a channel with flags zero and enabled byte one, then stores the level',
                'locking': 'enters and leaves the EXE logger critical section around its tree/state update'}):
        raise ValueError('XP2 logger slot +0x30 source identity/ABI changed')
    for row in (proof['parent_profile'], proof['exe_parent_proof']):
        _source((row['path'], row['sha256']))
    from .paths import resource_root
    from .resource_resolution import resolve_path
    for row in (*proof['extractors'], proof['generator']):
        path = resolve_path(resource_root() / row['path'])
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('XP2 logger supplement extractor changed')
    for name, value in proof['bodies'].items():
        bodies = [value] if 'fragments' in value else [value['body'],
            *(tail['body'] for tail in value.get('out_of_line_tail_jumps', []))]
        for body in bodies:
            for fragment in body['fragments']:
                decoded = b''.join(bytes.fromhex(row['bytes']) for row in fragment['instructions'])
                raw = bytes.fromhex(fragment['raw_hex']) if 'raw_hex' in fragment else decoded
                expected_hash = fragment.get('sha256', fragment.get('raw_sha256'))
                if (len(raw) != fragment['length'] or raw != decoded
                        or hashlib.sha256(raw).hexdigest() != expected_hash):
                    raise ValueError('XP2 logger supplement body is incomplete: ' + name)
    for assertion in proof['callsite_assertions']:
        if assertion['body'] == 'parent_profile.enabled_queries':
            parent = _source(XP2_SOURCE)
            rows = [row for fragment in parent['bodies']['enabled_queries']['body']['fragments']
                    for row in fragment['instructions']]
        else:
            body = proof['bodies']['xp2_level_roundtrip']['body']
            rows = [row for fragment in body['fragments'] for row in fragment['instructions']]
        if not any(row['rva'] == assertion['rva'] and row['text'] == assertion['text'] for row in rows):
            raise ValueError('XP2 logger supplement callsite changed')
    return proof


def _xp2_log_level_setter(host):
    def set_level(this, channel, level):
        if this != C.addressof(host.logger_object):
            host._fatal('unverified XP2 logger level-set arguments')
        entry = host.log_channels.get(channel)
        created = False
        if entry is None:
            if level:
                entry = {'filename': None, 'flags': 0, 'enabled': 1, 'level': int(level)}
                host.log_channels[channel] = entry
                created = True
        else:
            entry['level'] = int(level)
        host.emit('host_log_level_set', channel=hex(channel), found=entry is not None,
                  created=created, level=int(level))
    return set_level


def install_saved_load_logger(backend):
    """Restore source-backed methods on one owned prepared expansion instance."""
    from .native import native_host
    from .native.native_host import DiagnosticHost
    from .native.native_logging import DisabledLogWriters
    backend.check_thread()
    core_sha256 = backend.profile.core_sha256
    if core_sha256 not in (XP1_CORE_SHA256, XP2_CORE_SHA256):
        raise ValueError('Unknown saved-Load logger engine')
    engine = 'xp1' if core_sha256 == XP1_CORE_SHA256 else 'xp2'
    activation = '_' + engine + '_load_logger_activation'
    if (getattr(backend, '_saved_load_candidate', False) is not True
            or backend.inputs is not backend.captured_bundle.inputs
            or backend.stage != 'prepared' or backend.prefix is not None
            or backend.game_flag() != 0 or hasattr(backend, activation)):
        raise ValueError('Logger activation requires one owned prepared expansion candidate')
    host = backend.host
    if (not isinstance(host, DiagnosticHost)
            or not isinstance(host.log_writers, DisabledLogWriters)
            or host.log_writers.host is not host
            or host.log_writers.active_sink is None
            or host.logger_object[0] != C.addressof(host.logger_vtable)):
        raise ValueError('Logger requires the existing retained registry and native sink')
    proof = _checked_source(core_sha256)
    supplement = _checked_xp2_supplement() if engine == 'xp2' else None
    base = backend.core._handle
    read = backend.runtime.read
    # Check interface identity and the source caller bytes before binding
    # the host-owned callbacks. Core code and simulation memory are not patched.
    expected = C.addressof(host.logger_object).to_bytes(8, 'little')
    if read(base + int(proof['logger_global_rva'], 16), 8) != expected:
        raise ValueError('Core does not own this exact logger interface')
    for name, row in proof['live_windows'].items():
        raw = bytes.fromhex(row['bytes'])
        if read(base + int(row['rva'], 16), len(raw)) != raw:
            raise ValueError('Logger caller bytes changed: ' + name)
    if supplement is not None:
        for fragment in supplement['bodies']['xp2_level_roundtrip']['body']['fragments']:
            raw = bytes.fromhex(fragment['raw_hex'])
            if read(base + int(fragment['start_rva'], 16), len(raw)) != raw:
                raise ValueError('XP2 logger level caller differs from exact source')
    bindings = (
        (0x10, C.c_uint8, (C.c_void_p, C.c_uint32), host._log_enabled),
        (0x18, C.c_uint8, (C.c_void_p,), host._log_global_enabled),
        (0x20, None, (C.c_void_p, C.c_uint8), host._log_global_enable),
        (0x28, None, (C.c_void_p, C.c_uint32, C.c_uint8), host._log_enable),
        (0x38, C.c_uint32, (C.c_void_p, C.c_uint32), host._log_level),
        (0x40, None, (C.c_void_p, C.c_uint32, C.c_wchar_p, C.c_uint32, C.c_void_p), host._log_register),
        (0x50, C.c_void_p, (C.c_void_p, C.c_uint32), host.log_writers.lookup),
    )
    if supplement is not None:
        bindings += ((0x30, None, (C.c_void_p, C.c_uint32, C.c_uint32),
                      _xp2_log_level_setter(host)),)
    table = C.addressof(host.logger_vtable)
    # Validate the entire group before changing the first callback. Preserve
    # any unknown override by refusing, never by replacing it silently.
    for slot, _, _, callback in bindings:
        address, prior = host._slot_bindings[table, slot]
        if (address != host.logger_vtable[slot // 8]
                or (prior != callback and getattr(prior, '_native_unavailable', None) != ('logger', slot))):
            raise ValueError('Logger callback has an unknown owner: ' + hex(slot))
    for slot, result, args, callback in bindings:
        host._bind(host.logger_vtable, slot, result, list(args), callback)
    receipt = {'source_sha256': (SOURCE if engine == 'xp1' else XP2_SOURCE)[1],
               'supplement_source_sha256': XP2_SUPPLEMENT[1] if supplement is not None else None,
               'core_sha256': core_sha256,
               'host_lifetime_compatibility_sha256': HOST_LIFETIME_COMPATIBILITY[1],
               'executed_shared_host_sha256': hashlib.sha256(Path(native_host.__file__).read_bytes()).hexdigest(),
               'slots': [hex(x) for x in (SLOTS + (XP2_EXTRA_SLOTS if supplement is not None else ()))],
               'reused_shared_registry': True,
               'reused_native_sink': True, 'channel_state_modified': False,
               'unknown_slots_enabled': False, 'native_load_success_claimed': False}
    setattr(backend, activation, receipt)
    backend.emit(engine + '_saved_load_logger_activated', **receipt)
    return receipt
