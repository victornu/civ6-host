"""Native Locale numeric arguments, without replacing the pinned host EXE."""
from civ6_host.runtime.provenance import historical_source_file as _historical_source_file, historical_module_file as _historical_module_file, worker_path as _worker_path, pin_key as _pin_key, installed_source_pins as _installed_source_pins
from civ6_host.runtime.resource_resolution import resolve_path as _resolve_resource_path
from pathlib import Path
import ctypes as C
import hashlib, math
from civ6_host.runtime.native.native_source_cache import load_pinned_json
from civ6_host.runtime.native.native_script_parameters import lua_string
ROOT = _resolve_resource_path(_resolve_resource_path(Path(_historical_source_file('civ6rl/native_locale_arguments.py')))).resolve().parents[1]
PROOF = ROOT / 'work/trade-route967/locale-source.json'
PROOF_SHA = 'a48a06e249165a4aec986110b244967810f9e8deb8465652d489527733369a95'
BUILD = ROOT / 'work/trade-route967/locale-module-r2/build.json'
BUILD_SHA = '2b12b199779e993d588e5e3016a66e3ada4aba7b9407e6cd50d163e3f9f649ea'
DLL = ROOT / 'work/trade-route967/locale-module-r2/civ6rl-locale-arguments.dll'
DLL_SHA = '356941013c3303136a221fbf54773963362f109a93badeef425f6350f134d8b2'

def digest(p):
    return hashlib.sha256(_resolve_resource_path(_resolve_resource_path(Path(p))).read_bytes()).hexdigest()

def verify_runtime_images(runtime, proof):
    """Match loaded files to their explicit runtime or historical ABI identity."""
    library = runtime.service_owner.localization_library
    pairs = ((runtime.library, proof['havok'], 'HavokScript_FinalRelease.dll'),
             (library, proof['images']['localization'], 'Localization_FinalRelease.dll'))
    shared = getattr(runtime, 'shared_dependency_profile', None)
    if shared is not None:
        from .native_shared_dependency_profiles import NativeSharedDependencyProfile
        from civ6_host.runtime.execution_images import known_path, select
        if type(shared) is not NativeSharedDependencyProfile:
            raise ValueError('Locale requires the explicit shared dependency profile')
        image = select('xp2-gamecore-current-092abfbb',
                       core_path=known_path('xp2-gamecore-current-092abfbb'))
        if (shared.actual_image_sha256, shared.interface_reference_sha256) != (
                image.image_sha256, image.reference_core_sha256):
            raise ValueError('Locale shared dependency image/reference pair differs')
        identities = {row.name: row for row in image.shared_dependencies}
        for loaded, reference, name in pairs:
            row = identities[name]
            if (reference['sha256'] != row.reference_sha256
                    or _resolve_resource_path(Path(reference['path'])).resolve()
                    != _resolve_resource_path(Path(row.path)).resolve()):
                raise ValueError('Locale source ABI reference differs from runtime profile')
            shared.verify_library_path(name, loaded._name)
        return image
    for loaded, identity, _ in pairs:
        if (_resolve_resource_path(Path(loaded._name)).resolve()
                != _resolve_resource_path(Path(identity['path'])).resolve()
                or digest(loaded._name) != identity['sha256']):
            raise RuntimeError('Locale/HKS loaded image differs')
    return None

def verified_files():
    p = load_pinned_json(PROOF, PROOF_SHA)
    b = load_pinned_json(BUILD, BUILD_SHA)
    if p['schema'] != 'civ6rl.locale_arguments967.source.v1' or p['instructions_rechecked'] != 206 or b['returncode'] != 0 or (b['host41_rebuilt'] is not False) or (b['dll']['sha256'] != DLL_SHA) or (_resolve_resource_path(ROOT / b['dll']['path']).resolve() != _resolve_resource_path(DLL).resolve()) or (digest(DLL) != DLL_SHA):
        raise RuntimeError('Unverified numeric Locale module')
    rows = {PROOF: PROOF_SHA, BUILD: BUILD_SHA, DLL: DLL_SHA}
    for r in b['sources']:
        for field in ('path', 'snapshot'):
            path = ROOT / r[field]
            if digest(path) != r['sha256']:
                raise RuntimeError('Numeric Locale source/build snapshot differs')
            rows[path] = r['sha256']
    return (rows, p)

def native_lookup(library, key, args):
    """Independent native String ABI oracle, never Python text formatting."""
    from civ6_host.runtime.native.native_locale_diagnostic import _LOOKUP
    from civ6_host.runtime.native.native_locale_diagnostic import _PUSH_STRING
    from civ6_host.runtime.native.native_locale_diagnostic import _TO_UTF8
    from civ6_host.runtime.native.native_locale_diagnostic import _DESTROY
    from civ6_host.runtime.native.native_locale_diagnostic import _EXPORT_RVAS
    if type(key) is not bytes or not key or len(key) > 65536 or (b'\x00' in key) or (len(args) > 16):
        raise ValueError('Invalid key/arity')
    for a in args:
        if type(a) is bytes:
            if len(a) > 65536 or b'\x00' in a:
                raise ValueError('Invalid text argument')
        elif type(a) in (float, int):
            if not math.isfinite(a) or not -1000000000000.0 <= a <= 1000000000000.0:
                raise ValueError('Invalid number')
        else:
            raise ValueError('Unsupported argument')
    numeric = '?PushArgument@String@Localization@@QEAA_NN@Z'
    functions = {}
    for name, rva in (_EXPORT_RVAS | {numeric: 55760}).items():
        f = getattr(library, name)
        if C.cast(f, C.c_void_p).value != library._handle + rva:
            raise RuntimeError('Locale export differs')
        functions[name] = f
    lookup = functions[_LOOKUP]
    lookup.argtypes, lookup.restype = ([C.c_void_p, C.c_char_p], C.c_void_p)
    push = functions[_PUSH_STRING]
    push.argtypes, push.restype = ([C.c_void_p, C.c_char_p], C.c_ubyte)
    number = functions[numeric]
    number.argtypes, number.restype = ([C.c_void_p, C.c_double], C.c_ubyte)
    utf8 = functions[_TO_UTF8]
    utf8.argtypes, utf8.restype = ([C.c_void_p, C.POINTER(C.c_uint), C.c_int], C.c_void_p)
    destroy = functions[_DESTROY]
    destroy.argtypes, destroy.restype = ([C.c_void_p], None)
    storage = C.create_string_buffer(128 + 15)
    obj = C.addressof(storage) + 15 & ~15
    if lookup(obj, key) != obj:
        raise RuntimeError('Locale hidden return differs')
    try:
        for a in args:
            (push if type(a) is bytes else number)(obj, a)
        n = C.c_uint()
        ptr = utf8(obj, C.byref(n), 1)
        if not ptr or n.value > 1048576:
            raise RuntimeError('Locale result outside bound')
        raw = C.string_at(ptr, n.value + 1)
        if raw[-1:] != b'\x00' or b'\x00' in raw[:-1]:
            raise RuntimeError('Locale result malformed')
        return raw[:-1]
    finally:
        destroy(obj)

def _diagnose(runtime, child, library):
    key = b'LOC_ROUTECHOOSER_YIELD_SOURCE_DISTRICTS'
    cases = []
    for value in (0, 1, 2.5, -2.25):
        args = (value, b'[ICON_Food]', b'LOC_YIELD_FOOD_NAME', b'Native city')
        expected = native_lookup(library, key, args)
        expression = ','.join((lua_string(a) if type(a) is bytes else repr(a) for a in args))
        raw = runtime.evaluate_text(child, f'assert(Locale.HasTextKey({lua_string(key)}));return Locale.Lookup({lua_string(key)},{expression})'.encode(), b'@numeric_locale_oracle')
        if raw != expected:
            raise RuntimeError('Native Locale bridge disagrees with independent native String call')
        cases.append(dict(value=value, output_sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw)))
    guard = b'local bad={\'{}\',\'true\',\'nil\',\'0/0\',\'math.huge\',\'1e13\',"\'a\'..string.char(0)..\'b\'"}\nfor _,a in ipairs(bad)do\n local f=assert(loadstring("return Locale.Lookup(\'LOC_ROUTECHOOSER_YIELD_SOURCE_DISTRICTS\',"..a..")"))\n local ok,msg=pcall(f);assert(not ok and type(msg)==\'string\' and string.find(msg,\'Civ6RL Locale\',1,true))\nend\nassert(not pcall(Locale.Lookup,\'x\',1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17))\nassert(type(Locale.Lookup(\'LOC_ROUTECHOOSER_YIELD_SOURCE_DISTRICTS\',2,\'[ICON_Food]\',\'LOC_YIELD_FOOD_NAME\',\'Native city\'))==\'string\')\nreturn \'numeric-locale-guards-ok\' '
    if runtime.evaluate_text(child, guard, b'@numeric_locale_guards') != b'numeric-locale-guards-ok':
        raise RuntimeError('Locale guards failed')
    runtime.emit('native_locale_numeric_verified', cases=cases, refusal_cases=8, native_dll_oracle=True, source_sha256=PROOF_SHA, module_sha256=DLL_SHA, gameplay_rules_reimplemented=False)

def attach(prefix):
    runtime = prefix.runtime
    if getattr(runtime, 'shared_dependency_profile', None) is not None:
        # The current profile uses the length-preserving revision of this same
        # native bridge; never reinstall the older C module over it.
        from civ6_host.runtime.locale_text import attach as attach_length_locale
        attach_length_locale(prefix)
        prefix.numeric_locale_child = prefix.ui_child
        return
    child = prefix.ui_child
    pointer = runtime.registry.validate(child)
    if not runtime.locale_bound:
        raise RuntimeError('Locale lifecycle is not initialized')
    if getattr(prefix, 'numeric_locale_child', None) == child:
        return
    rows, p = verified_files()
    library = runtime.service_owner.localization_library
    verify_runtime_images(runtime, p)
    runtime.namespaces.register(child, 'Locale')
    if not hasattr(runtime, 'locale_arguments_module'):
        module = C.WinDLL(str(DLL))
        runtime.locale_arguments_module = module
        f = module.LAB_LocaleArgumentsInstall
        f.argtypes, f.restype = ([C.c_void_p] * 3, C.c_int)
        runtime._status(runtime.root, f(runtime.library._handle, library._handle, runtime.root), 'install native numeric Locale')
        _diagnose(runtime, child, library)
    prefix.numeric_locale_child = child
    runtime.emit('native_trade_locale_attached', source_sha256=PROOF_SHA, module_sha256=DLL_SHA, child_registered=True, host41_unchanged=True, borrowed_localization=True, strategic_training_ready=False)
