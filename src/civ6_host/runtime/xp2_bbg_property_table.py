"""Private XP2 AUX B8 ownership for the pinned BBG property-table producer."""
import ctypes as C

from .configuration_profiles import _source
from .profile_script_binding import _current_executable
from .source_build_identity import (XP2_HOST_COMPONENT_SHA, verify_source_build,
    xp2_component_requirements, xp2_source_component, CURRENT_HAVOK_BUILD_PROFILE,
    CURRENT_STRINGS_BUILD_PROFILE)
from .saved_load_profiles import XP2_CORE_SHA256
from . import xp2_bbg_inputs

BUILD_PROFILE = 'xp2-bbg-private-property-table'
WRAPPER_SHA256 = 'c8458ffabf522d5d35528815a2d3e64b9102755beee6b6c83cafd38a8a4bd956'
NESTED_WRAPPER_SHA256 = '813b92546ef6c7d0c3c87a156b9206ad99f160ae185ae6112929538723585fce'
COMPONENT_SHA256 = 'c0ac0d25360cb9509f0f886961fafa671db15075b5332d79e4610ae442ca700e'
SCALAR_COMPONENT_SHA256 = '4dbb70603b94ba654f074e37968fa92e1c42e2991d97e5dd200b200cb10e1771'
SOURCES = (
    ('work/native-xp2-bbg751/run-45a1133f4bd2/aux-b8-static.json',
     '7bae64359dd17a6ace723d40eee507e38e7072838b6c661c4fa417af35fd4de1'),
    ('work/native-xp2-bbg751/run-45a1133f4bd2/aux-b8-xp2-variant-static.json',
     '9bca197599a8216915f2c00f900205a0b83edba74aafdbb068bce9d1f99e99ea'),
    ('work/native-xp2-bbg751/run-45a1133f4bd2/aux-b8-serializer-static.json',
     '183138f1ce1c8bf79f407f47f4944837ee639e4bffd11de0dcc0bf1a4a20a5a9'),
)


def dispatch_wrapper_sha256(build):
    if 'script_bbg_nested_game_events.inc' in build['sources']:
        return NESTED_WRAPPER_SHA256
    return WRAPPER_SHA256


def property_component_sha256(build):
    if build['profile'] in (CURRENT_HAVOK_BUILD_PROFILE, CURRENT_STRINGS_BUILD_PROFILE):
        return xp2_source_component(build, 'script_aux_b8.inc', SCALAR_COMPONENT_SHA256)
    if build['host_sha256'] == xp2_bbg_inputs.UI_HOST[1]:
        return SCALAR_COMPONENT_SHA256
    return COMPONENT_SHA256


class PropertyTableWriter:
    def __init__(self, services):
        backend, runtime = services.backend, services.runtime
        if (not xp2_bbg_inputs.is_reference(backend.captured_bundle.reference)
                or services.core_sha256 != XP2_CORE_SHA256 or runtime.service_owner is not services.host):
            raise ValueError('AUX B8 is scoped to the admitted private BBG candidate')
        executable = _current_executable()
        build = verify_source_build(executable, required_components=xp2_component_requirements(executable, {
            'gamecore_python_host.c': XP2_HOST_COMPONENT_SHA,
        }))
        if (build['profile'] not in (BUILD_PROFILE, CURRENT_HAVOK_BUILD_PROFILE, CURRENT_STRINGS_BUILD_PROFILE)
                or build['sources'].get('script_aux_b8.inc') != property_component_sha256(build)
                or build['sources'].get('script_game_event_dispatch.inc') != dispatch_wrapper_sha256(build)):
            raise ValueError('AUX B8 requires its exact private native build')
        base, read = backend.core._handle, backend.runtime.read
        for reference in SOURCES:
            source = _source(reference)
            for body in source['bodies']:
                if body['image'] != 'xp2':
                    continue
                if body['sha256'] != XP2_CORE_SHA256:
                    raise ValueError('AUX B8 source image differs')
                for row in body['instructions']:
                    expected = bytes.fromhex(row['raw'])
                    if read(base + int(row['rva'], 16), len(expected)) != expected:
                        raise ValueError('AUX B8 caller or Variant ownership bytes differ')

        self.runtime, self.host = runtime, services.host
        self.key = (C.addressof(self.host.aux_vtable), 0xb8)
        self.owner = C.addressof(self.host.aux_object)
        self.previous = self.host._slot_bindings[self.key]
        if (self.host.aux_vtable[0xb8//8] != self.previous[0]
                or getattr(self.previous[1], '_native_unavailable', None) != ('auxiliary', 0xb8)):
            raise ValueError('AUX B8 needs the original refused callback')

        bind, self.unbind = runtime.host.LAB_XP2AuxB8Bind, runtime.host.LAB_XP2AuxB8Unbind
        bind.argtypes, bind.restype = [C.c_void_p] * 3, C.c_int
        self.unbind.argtypes, self.unbind.restype = [C.c_void_p] * 2, C.c_int
        target = runtime.host.LAB_XP2AuxB8Table
        self.installed = (C.cast(target, C.c_void_p).value, target)
        if not self.installed[0] or bind(runtime.root, self.owner, base) != 1:
            raise ValueError('AUX B8 native ownership could not be bound')
        self.host.aux_vtable[0xb8//8] = self.installed[0]
        self.host._slot_bindings[self.key] = self.installed
        self.closed = False
        backend.emit('xp2_bbg_property_table_writer_bound', slot='0xb8', native_host_sha256=build['host_sha256'])

    def close(self):
        self.runtime.registry._check()
        if (self.closed or self.host.aux_vtable[0xb8//8] != self.installed[0]
                or self.host._slot_bindings[self.key] != self.installed
                or self.unbind(self.runtime.root, self.owner) != 1):
            raise ValueError('AUX B8 writer lifetime or ownership differs')
        self.host.aux_vtable[0xb8//8] = self.previous[0]
        self.host._slot_bindings[self.key] = self.previous
        self.closed = True

