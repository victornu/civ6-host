"""Length-preserving Locale bridge revision; the official formatter is unchanged."""
import ctypes as C
import hashlib
import json
from pathlib import Path

SOURCE=('work/host-simultaneous/city-management/locale-length-source-v2.json','25eb41e58ab92390e0a5cb7f92bdca79a72be594264f70c461197571d3c0cf4f')


def source_files():
    from .provenance import resource_root
    from .resource_resolution import resolve_path
    path=resolve_path(resource_root()/SOURCE[0]);raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=SOURCE[1]:raise ValueError('Locale length proof changed')
    proof=json.loads(raw);pins={str(path):SOURCE[1]}
    for row in proof['files']:
        p=resolve_path(resource_root()/row['path'])
        if hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('Locale length dependency changed')
        pins[str(p)]=row['sha256']
    return pins,proof


def attach(prefix):
    runtime=prefix.runtime;child=prefix.ui_child
    if getattr(prefix,'length_locale_child',None)==child:return
    from .native import native_locale_arguments as legacy
    from .native.native_locale_diagnostic import _native_lookup
    from .native.native_script_parameters import lua_string
    from .provenance import resource_root
    from .resource_resolution import resolve_path
    runtime.registry.validate(child)
    if not runtime.locale_bound:raise RuntimeError('Locale lifecycle is not initialized')
    _,proof=source_files();_,original=legacy.verified_files()
    library=runtime.service_owner.localization_library
    for loaded,identity in ((runtime.library,original['havok']),(library,original['images']['localization'])):
        if (Path(loaded._name).resolve()!=resolve_path(Path(identity['path'])).resolve()
                or hashlib.sha256(Path(loaded._name).read_bytes()).hexdigest()!=identity['sha256']):
            raise RuntimeError('Length-aware Locale loaded image differs from its ABI proof')
    if not hasattr(runtime,'locale_text_module'):
        module=C.WinDLL(str(resolve_path(resource_root()/proof['dll']['path'])))
        runtime.locale_text_module=module
        install=module.LAB_LocaleArgumentsInstall
        install.argtypes,install.restype=([C.c_void_p]*3,C.c_int)
        runtime._status(runtime.root,install(runtime.library._handle,library._handle,runtime.root),'install length-aware Locale')
        cases=[]
        for key in (b'LOC_UNIT_BUILDER_NAME',b'LOC_UNIT_SCOUT_NAME',b'LOC_BUILDING_MONUMENT_NAME',b'LOC_TYPE_TRAIT_HOUSING'):
            expected=_native_lookup(library,key,explicit_length=True)
            text=(f'local s=Locale.Lookup({lua_string(key)});return (string.gsub(s,".",function(c) return string.format("%02x",string.byte(c)) end))').encode('ascii')
            actual=runtime.evaluate_text(child,text,b'@locale_length_oracle',capacity=2*1048576+1)
            if actual!=expected.hex().encode('ascii'):raise RuntimeError('Locale adapter differs from native String bytes')
            cases.append(dict(key=key.decode(),bytes=len(expected),sha256=hashlib.sha256(expected).hexdigest(),embedded_nul=b'\0' in expected))
        legacy._diagnose(runtime,child,library)
        runtime.emit('native_locale_length_verified',source_sha256=SOURCE[1],dll_sha256=proof['dll']['sha256'],
                     cases=cases,native_string_oracle=True,official_formatter_unchanged=True)
    prefix.length_locale_child=child
