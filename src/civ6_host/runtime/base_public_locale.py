"""Owned UI formatting for the installed Base shared-library profile."""

import ctypes as C
import math
from pathlib import Path

from . import locale_text
from .base_capture_inputs import locale_number_source_pins
from .execution_images import _BASE_PROFILE, select_pair
from .native import native_locale_number982 as number
from .native.native_script_parameters import lua_string


def selected_image(runtime):
    shared = getattr(runtime, 'shared_dependency_profile', None)
    if shared is None or shared.actual_image_sha256 != _BASE_PROFILE.image_sha256:
        return None
    return select_pair(shared.actual_image_sha256, shared.interface_reference_sha256)


def source_files(image):
    locale_pins, _ = locale_text.source_files(execution_image=image)
    return {**locale_number_source_pins(image), **{Path(path): digest for path, digest in locale_pins.items()}}


def number_template(pattern):
    if pattern not in number.ALLOWED_PATTERNS:
        raise ValueError('Locale number pattern is outside the verified Base UI formats')
    return b'{1 : number}' if pattern is None else ('{1: number ' + pattern + '}').encode('ascii')


class Formatter:
    """Use the same String constructors and length-aware Locale as the public UI."""

    def __init__(self, prefix):
        runtime = prefix.runtime
        if selected_image(runtime) is not _BASE_PROFILE:
            raise ValueError('Base formatter requires the installed Base runtime')
        self.runtime = runtime
        self.child = prefix.ui_child
        locale_text.attach(prefix)
        self.library = runtime.service_owner.localization_library
        self.cstr = self._bind(number._CTOR_CSTR, [C.c_void_p, C.c_char_p], C.c_void_p)
        self.sized = self._bind(number._CTOR_SIZED, [C.c_void_p, C.c_char_p, C.c_uint], C.c_void_p)
        self.push = self._bind(number._PUSH_DOUBLE, [C.c_void_p, C.c_double], C.c_ubyte)
        self.text = self._bind(number._TO_UTF8, [C.c_void_p, C.POINTER(C.c_uint), C.c_int], C.c_void_p)
        self.destroy = self._bind(number._DESTRUCTOR, [C.c_void_p], None)

    def _bind(self, name, args, result):
        return number._bind(self.library, name, number._EXPORT_RVAS[name], args, result)

    def _check(self, library, value):
        if (library is not self.library or not self.runtime.locale_bound or self.runtime.closed
                or not self.runtime.service_owner.localization_initialized
                or self.runtime.service_owner.localization_library is not library):
            raise RuntimeError('Base formatter no longer owns the observed player UI context')
        self.runtime.registry.validate(self.child)
        if type(value) not in (int, float) or abs(value) > number.MAX_ABS_VALUE or not math.isfinite(value):
            raise ValueError('Locale number value is outside the verified numeric bounds')

    def number(self, library, value, pattern=None):
        self._check(library, value)
        template = number_template(pattern)
        allocation = C.create_string_buffer(128 + 15)
        address = (C.addressof(allocation) + 15) & ~15
        returned = self.cstr(address, template) if pattern is None else self.sized(address, template, len(template))
        if returned != address:
            raise RuntimeError('Localization::String constructor returned a foreign object')
        try:
            self.push(address, float(value))
            length = C.c_uint()
            pointer = self.text(address, C.byref(length), 1)
            if not pointer or length.value > number.MAX_RESULT_BYTES:
                raise RuntimeError('Localization::String::toUTF8 exceeded output bound')
            raw = C.string_at(pointer, length.value)
            if b'\x00' in raw:
                raise RuntimeError('Localization returned an embedded NUL in a public number')
            return raw.decode('utf-8', 'strict')
        finally:
            self.destroy(address)

    def lookup(self, library, key, args):
        if len(args) != 1 or key not in tuple(number_template(p) for p in number.ALLOWED_PATTERNS):
            raise ValueError('Base number lookup requires an exact official number template')
        value = args[0]
        self._check(library, value)
        expression = 'return Locale.Lookup(' + lua_string(key) + ',' + repr(value) + ')'
        return self.runtime.evaluate_text(self.child, expression.encode('ascii'),
                                          b'@base_public_locale_number', capacity=number.MAX_RESULT_BYTES)
