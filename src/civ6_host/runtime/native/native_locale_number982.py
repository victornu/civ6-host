"""Call the official Localization formatter used by Lua Locale.ToNumber."""
from __future__ import annotations
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
import ctypes as C
import hashlib
import math
import os
from collections.abc import Mapping
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
_CURRENT_LOCALIZATION_IMAGE_SHA256 = '8490e6694b966564f2f0baf6b685e6f23817c7348996511ce03891c0d14fe431'
_CURRENT_LOCALE_BODY_PROOF = ('work/official-capture/current-localization-number-string-bodies.json',
    'b0b318cfeebcbbb7813e2c4b3257ce326b1f6e4f83597e20b9f09d3d3eebdfa5')
_CURRENT_SHARED_INTERFACE_PROOF = ('work/bbg751-turn-source-scope/shared-dependencies/current-shared-dependency-interfaces-v1.json',
    'a4de406dfbbed460af4ed2b15b7cb4d75afc610e3f9268838b65a65fc9a069c9')
_CURRENT_LOCALIZATION_SOURCE_PROFILE = ('work/actual-core-092-integration/locale-current/source-profile.json',
    'cc6326899b99bfb54c92845ed368e51b88efbbce9bdf8cf4dab9a334f7a9645d')
_CURRENT_SHARED_BINDINGS_PROOF = ('work/official-capture/current-localization-shared-bindings.json',
    '2907bbb5b41e8c015c4779e1c49c3940b06b6a719ca815cec61eac41c1340823')
_CURRENT_EXECUTION_PROFILE_ID = 'xp2-gamecore-current-092abfbb'
_CURRENT_CORE_SHA256 = '092abfbb2176f8df04b5212f819dc269dd83aea866ff05aaf489904a1ff7c41f'
_REFERENCE_CORE_SHA256 = '324c51e9ea3531758842e16c69e6cddbefbb226c5b675c3d6e60111646c2e98c'
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

def _verified_current_files(execution_image) -> dict[Path, str]:
    from civ6_host.runtime.execution_images import identity, verify

    try:
        selected = identity(execution_image)
        if (selected['profile_id'] != _CURRENT_EXECUTION_PROFILE_ID
                or selected['image_sha256'] != _CURRENT_CORE_SHA256
                or selected['reference_core_sha256'] != _REFERENCE_CORE_SHA256):
            raise RuntimeError('Selected execution image is not the current XP2 profile')
        verify(execution_image)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        if isinstance(exc, RuntimeError) and str(exc) == 'Selected execution image is not the current XP2 profile':
            raise
        raise RuntimeError('Current Locale.ToNumber image failed its pinned verification') from exc

    proof = load_pinned_json(SOURCE_PROOF, SOURCE_PROOF_SHA256)
    if (proof.get('schema') != 'civ6rl.locale_number982.source.v1'
            or proof.get('exports') != {name: hex(rva) for name, rva in _EXPORT_RVAS.items()}):
        raise RuntimeError('Historical Locale.ToNumber export contract changed')
    files: dict[Path, str] = {SOURCE_PROOF: SOURCE_PROOF_SHA256}
    for source in proof.get('sources', []):
        path = _resolve_resource_path(ROOT / source['path']).resolve()
        expected = source['sha256']
        if _sha256(path) != expected:
            raise RuntimeError(f"Pinned Locale.ToNumber source changed: {source['path']}")
        files[path] = expected

    shared = load_pinned_json(ROOT / _CURRENT_SHARED_INTERFACE_PROOF[0], _CURRENT_SHARED_INTERFACE_PROOF[1])
    source_profile = load_pinned_json(ROOT / _CURRENT_LOCALIZATION_SOURCE_PROFILE[0],
                                      _CURRENT_LOCALIZATION_SOURCE_PROFILE[1])
    bindings = load_pinned_json(ROOT / _CURRENT_SHARED_BINDINGS_PROOF[0],
                                _CURRENT_SHARED_BINDINGS_PROOF[1])
    current = load_pinned_json(ROOT / _CURRENT_LOCALE_BODY_PROOF[0], _CURRENT_LOCALE_BODY_PROOF[1])
    interface = shared.get('localization_interface', {})
    current_localization = shared.get('libraries', {}).get('Localization_FinalRelease.dll', {})
    source_image = source_profile.get('localization', {})
    binding_image = bindings.get('source_images', {}).get('Localization_FinalRelease.dll', {})
    if (shared.get('schema') != 'civ6-host.shared-dependency-interface-current.v1'
            or shared.get('engine_pair') != {
                'actual_image_sha256': _CURRENT_CORE_SHA256,
                'interface_reference_sha256': _REFERENCE_CORE_SHA256}
            or interface.get('current_sha256') != _CURRENT_LOCALIZATION_IMAGE_SHA256
            or interface.get('reference_sha256') != _LOCALIZATION_IMAGE_SHA256
            or current_localization.get('current_sha256') != _CURRENT_LOCALIZATION_IMAGE_SHA256
            or current_localization.get('reference_sha256') != _LOCALIZATION_IMAGE_SHA256
            or source_profile.get('schema') != 'civ6-host.locale-current-exports.v1'
            or source_profile.get('actual_core_sha256') != _CURRENT_CORE_SHA256
            or source_profile.get('reference_core_sha256') != _REFERENCE_CORE_SHA256
            or source_image.get('sha256') != _CURRENT_LOCALIZATION_IMAGE_SHA256
            or binding_image.get('current_sha256') != _CURRENT_LOCALIZATION_IMAGE_SHA256
            or binding_image.get('historical_sha256') != _LOCALIZATION_IMAGE_SHA256):
        raise RuntimeError('Current Localization image profile differs from the registered shared dependency')
    if (current.get('schema') != 'civ6rl.locale_number_current_string_abi.v1'
            or current.get('classification') != 'Static PE export and complete .pdata body comparison; no DLL loaded or called.'
            or current.get('reference_image', {}).get('sha256') != _LOCALIZATION_IMAGE_SHA256
            or current.get('current_image', {}).get('sha256') != _CURRENT_LOCALIZATION_IMAGE_SHA256
            or current.get('current_image', {}).get('bytes') != 1718048
            or current.get('body_boundary_method') !=
                'Exact .pdata RUNTIME_FUNCTION range beginning at each named export RVA; full bytes decoded by Capstone with no gaps.'):
        raise RuntimeError('Current Locale.ToNumber String ABI body proof differs')
    current_path = _resolve_resource_path(Path(source_image.get('path', ''))).resolve()
    if (Path(current.get('current_image', {}).get('path', '')).resolve() != current_path
            or _sha256(current_path) != _CURRENT_LOCALIZATION_IMAGE_SHA256):
        raise RuntimeError('Installed current Localization image differs from its source profile')

    phase43 = load_pinned_json(ROOT / 'evidence/phase43-locale-string-abi.json',
        '9c4a8c23eafd6231cabc9e42ce6b9bc36b6d4ee525e1b1f2ae87b3a895b1271d')
    exports = current.get('exports')
    if not isinstance(exports, Mapping) or set(exports) != set(_EXPORT_RVAS):
        raise RuntimeError('Current Localization String exports are incomplete')
    for name, rva in _EXPORT_RVAS.items():
        row = exports[name]
        body = row.get('current_function', {})
        if (row.get('reference_rva') != hex(rva)
                or row.get('current_export_rva') != hex(rva)
                or body.get('start_rva') != hex(rva)
                or type(body.get('end_rva_exclusive')) is not str
                or type(body.get('bytes')) is not int or body['bytes'] <= 0
                or body.get('complete_pdata_body') is not True
                or body.get('capstone_decoded_bytes') != body.get('bytes')
                or len(body.get('body_hex', '')) != body.get('bytes') * 2
                or hashlib.sha256(bytes.fromhex(body['body_hex'])).hexdigest() != body.get('sha256')):
            raise RuntimeError(f'Current Localization String body/export proof differs: {name}')
    for key, name in (('constructor', _CTOR_CSTR), ('to_utf8', _TO_UTF8), ('destructor', _DESTRUCTOR)):
        expected = phase43.get('localization_exports', {}).get(key, {}).get('body', {}).get('raw_sha256')
        if expected != exports[name].get('reference_body_sha256'):
            raise RuntimeError(f'Historical String body comparison is incomplete: {name}')
    if (exports[_CTOR_SIZED].get('reference_body_sha256') is not None
            or exports[_PUSH_DOUBLE].get('reference_body_sha256') is not None):
        raise RuntimeError('Unretained historical String bodies were claimed as exact matches')

    for path, expected in ((_CURRENT_SHARED_INTERFACE_PROOF[0], _CURRENT_SHARED_INTERFACE_PROOF[1]),
                           (_CURRENT_LOCALIZATION_SOURCE_PROFILE[0], _CURRENT_LOCALIZATION_SOURCE_PROFILE[1]),
                           (_CURRENT_SHARED_BINDINGS_PROOF[0], _CURRENT_SHARED_BINDINGS_PROOF[1]),
                           (_CURRENT_LOCALE_BODY_PROOF[0], _CURRENT_LOCALE_BODY_PROOF[1])):
        resolved = _resolve_resource_path(ROOT / path).resolve()
        if _sha256(resolved) != expected:
            raise RuntimeError(f'Current Localization proof source changed: {path}')
        files[resolved] = expected
    files[current_path] = _CURRENT_LOCALIZATION_IMAGE_SHA256
    return files


def verified_files(*, execution_image=None) -> dict[Path, str]:
    """Return the exact source and DLL files pinning the formatter contract."""
    if execution_image is not None:
        return _verified_current_files(execution_image)
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

def _check_library(library, files: dict[Path, str], *, execution_image=None) -> None:
    name = getattr(library, '_name', None)
    if not isinstance(name, (str, bytes)):
        raise RuntimeError('Localization library has no verifiable loaded path')
    loaded_path = _resolve_resource_path(_resolve_resource_path(Path(os.fsdecode(name)))).resolve()
    if execution_image is None:
        proof = load_pinned_json(SOURCE_PROOF, SOURCE_PROOF_SHA256)
        official_path = _resolve_resource_path(
            _resolve_resource_path(Path(proof['localization_image']['path']))).resolve()
        expected_sha256 = _LOCALIZATION_IMAGE_SHA256
    else:
        source_profile = load_pinned_json(ROOT / _CURRENT_LOCALIZATION_SOURCE_PROFILE[0],
                                          _CURRENT_LOCALIZATION_SOURCE_PROFILE[1])
        official_path = _resolve_resource_path(
            _resolve_resource_path(Path(source_profile['localization']['path']))).resolve()
        expected_sha256 = _CURRENT_LOCALIZATION_IMAGE_SHA256
    if loaded_path != official_path or files.get(loaded_path) != expected_sha256:
        raise RuntimeError('Loaded Localization library path differs from pin')

def format_number(library, value, pattern: str | None=None, *, execution_image=None) -> str:
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
    files = verified_files(execution_image=execution_image)
    _check_library(library, files, execution_image=execution_image)
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
