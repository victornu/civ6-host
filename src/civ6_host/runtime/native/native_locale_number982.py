"""Call the official Localization formatter used by Lua Locale.ToNumber."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import math
import os
from pathlib import Path
from civ6_host.runtime.native.native_source_cache import load_pinned_json
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_locale_number982.py')))).resolve().parents[1]
SOURCE_PROOF = ROOT / 'work/phase1-learning982/locale-number-source.json'
SOURCE_PROOF_SHA256 = 'e9e329adfaa7e5e422994618bcf0f09ae851de771c2da2ec0a75fc352be62502'
MAX_ABS_VALUE = 1000000000000.0
MAX_PATTERN_BYTES = 128
MAX_RESULT_BYTES = 1048576
ALLOWED_PATTERNS = (None, '#,###.#', '+#,###.#;-#,###.#')
_LOCALIZATION_IMAGE_SHA256 = '0becd5c425a3d6edc88f5315c01af3dd30dd7cb158271d56f4bba7ff2bb4e056'
_CTOR_CSTR = '??0String@Localization@@QEAA@PEBD@Z'
_CTOR_SIZED = '??0String@Localization@@QEAA@PEBDI@Z'
_PUSH_DOUBLE = '?PushArgument@String@Localization@@QEAA_NN@Z'
_TO_UTF8 = '?toUTF8@String@Localization@@QEAAPEBDAEAIH@Z'
_DESTRUCTOR = '??1String@Localization@@UEAA@XZ'
_EXPORT_RVAS = {_CTOR_CSTR: 48752, _CTOR_SIZED: 49072, _PUSH_DOUBLE: 55760, _TO_UTF8: 60592, _DESTRUCTOR: 49456}

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with _resolve_resource_path(_resolve_resource_path(Path(path))).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def verified_files() -> dict[Path, str]:
    """Return the exact source and DLL files pinning the formatter contract."""
    if not SOURCE_PROOF_SHA256:
        raise RuntimeError('Locale.ToNumber source proof has not been frozen')
    proof = load_pinned_json(SOURCE_PROOF, SOURCE_PROOF_SHA256)
    if proof.get('schema') != 'civ6rl.locale_number982.source.v1':
        raise RuntimeError('Unexpected Locale.ToNumber source proof schema')
    files: dict[Path, str] = {SOURCE_PROOF: SOURCE_PROOF_SHA256}
    for source in proof.get('sources', []):
        path = _resolve_resource_path(ROOT / source['path']).resolve()
        expected = source['sha256']
        if _sha256(path) != expected:
            raise RuntimeError(f"Pinned Locale.ToNumber source changed: {source['path']}")
        files[path] = expected
    image = proof.get('localization_image', {})
    image_path = _resolve_resource_path(Path(image.get('path', '')))
    if image.get('sha256') != _LOCALIZATION_IMAGE_SHA256 or image_path.name != 'Localization_FinalRelease.dll' or _sha256(image_path) != _LOCALIZATION_IMAGE_SHA256:
        raise RuntimeError('Pinned Localization DLL differs')
    files[_resolve_resource_path(image_path).resolve()] = _LOCALIZATION_IMAGE_SHA256
    expected_exports = proof.get('exports', {})
    if expected_exports != {name: hex(rva) for name, rva in _EXPORT_RVAS.items()}:
        raise RuntimeError('Pinned Localization String export map differs')
    return files

def _bind(library, name: str, rva: int, argtypes, restype):
    function = getattr(library, name)
    address = C.cast(function, C.c_void_p).value
    if address != library._handle + rva:
        raise RuntimeError(f'Localization export RVA differs: {name}')
    function.argtypes = argtypes
    function.restype = restype
    return function

def _check_library(library, files: dict[Path, str]) -> None:
    name = getattr(library, '_name', None)
    if not isinstance(name, (str, bytes)):
        raise RuntimeError('Localization library has no verifiable loaded path')
    loaded_path = _resolve_resource_path(_resolve_resource_path(Path(os.fsdecode(name)))).resolve()
    proof = load_pinned_json(SOURCE_PROOF, SOURCE_PROOF_SHA256)
    official_path = _resolve_resource_path(_resolve_resource_path(Path(proof['localization_image']['path']))).resolve()
    if loaded_path != official_path or files.get(loaded_path) != _LOCALIZATION_IMAGE_SHA256:
        raise RuntimeError('Loaded Localization library path differs from pin')

def format_number(library, value, pattern: str | None=None) -> str:
    """Format a finite number with the official Locale.ToNumber String ABI.

    ``pattern`` is deliberately restricted to the exact public formats used by
    the current observer. ``None`` follows the EXE's one-argument ToNumber
    branch; the two explicit patterns follow its format-string branch.
    """
    if type(value) not in (int, float) or abs(value) > MAX_ABS_VALUE or (not math.isfinite(value)):
        raise ValueError('Locale.ToNumber value is outside the verified numeric bounds')
    if pattern is not None and type(pattern) is not str:
        raise ValueError('Locale.ToNumber pattern must be a string or None')
    if pattern not in ALLOWED_PATTERNS:
        raise ValueError('Locale.ToNumber pattern is not in the verified public allowlist')
    files = verified_files()
    _check_library(library, files)
    if pattern is None:
        constructor_name = _CTOR_CSTR
        template = b'{1 : number}'
    else:
        try:
            pattern_bytes = pattern.encode('ascii', 'strict')
        except UnicodeError as exc:
            raise ValueError('Locale.ToNumber pattern must be ASCII') from exc
        template = b'{1: number ' + pattern_bytes + b'}'
        constructor_name = _CTOR_SIZED
    if len(template) > MAX_PATTERN_BYTES or b'\x00' in template:
        raise ValueError('Locale.ToNumber template exceeds verified bounds')
    ctor_cstr = _bind(library, _CTOR_CSTR, _EXPORT_RVAS[_CTOR_CSTR], [C.c_void_p, C.c_char_p], C.c_void_p)
    ctor_sized = _bind(library, _CTOR_SIZED, _EXPORT_RVAS[_CTOR_SIZED], [C.c_void_p, C.c_char_p, C.c_uint], C.c_void_p)
    push_double = _bind(library, _PUSH_DOUBLE, _EXPORT_RVAS[_PUSH_DOUBLE], [C.c_void_p, C.c_double], C.c_ubyte)
    to_utf8 = _bind(library, _TO_UTF8, _EXPORT_RVAS[_TO_UTF8], [C.c_void_p, C.POINTER(C.c_uint), C.c_int], C.c_void_p)
    destroy = _bind(library, _DESTRUCTOR, _EXPORT_RVAS[_DESTRUCTOR], [C.c_void_p], None)
    allocation = C.create_string_buffer(128 + 15)
    object_pointer = C.addressof(allocation) + 15 & ~15
    object_arg = C.c_void_p(object_pointer)
    constructor_called = False
    try:
        if constructor_name == _CTOR_CSTR:
            returned = ctor_cstr(object_arg, template)
        else:
            returned = ctor_sized(object_arg, template, len(template))
        if returned != object_pointer:
            raise RuntimeError('Localization::String constructor hidden return differs')
        constructor_called = True
        push_double(object_arg, float(value))
        length = C.c_uint(0)
        pointer = to_utf8(object_arg, C.byref(length), 1)
        if not pointer or length.value > MAX_RESULT_BYTES:
            raise RuntimeError('Localization::String::toUTF8 exceeded output bound')
        raw = C.string_at(pointer, length.value + 1)
        if raw[-1:] != b'\x00' or b'\x00' in raw[:-1]:
            raise RuntimeError('Localization::String::toUTF8 returned malformed text')
        return raw[:-1].decode('utf-8', 'strict')
    finally:
        if constructor_called:
            destroy(object_arg)
