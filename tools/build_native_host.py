"""Build the retained native host from its reviewed, immutable source manifest.

Derived from the lab's build_native_host.py. No game or old lab tree is read.
The local reference profile preserves its executable hash by normalizing only
the declared PE timestamp fields, followed by an exact whole-file hash check.
Raw compiler output is retained. Different machine code is never admitted.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import re
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
PROFILE_MANIFESTS = {
    'base': 'native/source-manifest.json',
    'xp1': 'native/profiles/xp1/source-manifest.json',
    'xp1-current': 'native/source-current.json',
    'xp1-postload': 'native/profiles/xp1-postload/source-manifest.json',
    'xp1-jobs': 'native/profiles/xp1-jobs/source-manifest.json',
    'xp1-ui': 'native/profiles/xp1-ui/source-manifest.json',
    'xp2-jobs': 'native/profiles/xp2-jobs/source-manifest.json',
    'xp2-ui': 'native/profiles/xp2-ui/source-manifest.json',
    'xp2-script-api': 'native/profiles/xp2-script-api/source-manifest.json',
    'xp2-mutable-map': 'native/profiles/xp2-mutable-map/source-manifest.json',
    'xp2-script-contexts': 'native/profiles/xp2-script-contexts/source-manifest.json',
}


def sha(data):return hashlib.sha256(data).hexdigest()


def staging_paths(root,manifest):
    """Map reviewed shared/variant sources into one private compile tree."""
    source_root=(root/'native').resolve()
    paths={};names=set()
    for row in manifest['sources']:
        path=(root/row['path']).resolve()
        if not path.is_relative_to(source_root):raise ValueError('Native source escapes source directory')
        name=row.get('build_path',path.relative_to(source_root).as_posix())
        if (type(name) is not str or not name or '\\' in name or ':' in name
                or any(part in ('','.', '..') for part in name.split('/'))):
            raise ValueError('Invalid relative native build path')
        staged=PurePosixPath(name)
        if staged.is_absolute():raise ValueError('Native build path must be relative')
        key=staged.as_posix().casefold()
        if path in paths or key in names:raise ValueError('Duplicate native source or build path')
        names.add(key);paths[path]=staged
    if 'gamecore_python_host.c' not in names:raise ValueError('Native build lacks its main source')
    return paths


def source_inputs(root,manifest):
    paths=staging_paths(root,manifest)
    by_build={name.as_posix().casefold():path for path,name in paths.items()}
    entries={}
    for row in manifest['sources']:
        path=(root/row['path']).resolve()
        data=path.read_bytes()
        if len(data)!=row['bytes'] or sha(data)!=row['sha256']:raise ValueError('Native source changed: '+row['path'])
        if path in entries:raise ValueError('Duplicate native source')
        entries[path]=data
    pending=[by_build['gamecore_python_host.c']];seen=set()
    while pending:
        path=pending.pop().resolve()
        if path in seen:continue
        if path not in entries:raise ValueError('Unmanifested native include: '+str(path))
        seen.add(path)
        for name in re.findall(r'^\s*#\s*include\s*"([^"\n]+)"',entries[path].decode('utf-8'),re.M):
            if '\\' in name or ':' in name or any(p in ('','.', '..') for p in name.split('/')):
                raise ValueError('Native include escapes or aliases its staged source')
            key=(paths[path].parent/PurePosixPath(name)).as_posix().casefold()
            if key not in by_build:raise ValueError('Unmanifested native include: '+name)
            pending.append(by_build[key])
    if seen!=set(entries):raise ValueError('Source manifest differs from transitive include closure')
    return entries


def timestamp_fields(data):
    if data[:2]!=b'MZ':raise ValueError('Native artifact is not PE')
    pe=struct.unpack_from('<I',data,0x3c)[0]
    if data[pe:pe+4]!=b'PE\0\0' or struct.unpack_from('<H',data,pe+4)[0]!=0x8664:
        raise ValueError('Native artifact must be x64 PE')
    optional=pe+24
    if struct.unpack_from('<H',data,optional)[0]!=0x20b:raise ValueError('Expected PE32+')
    export=struct.unpack_from('<I',data,optional+112)[0]
    table=optional+struct.unpack_from('<H',data,pe+20)[0]
    sections=[]
    for i in range(struct.unpack_from('<H',data,pe+6)[0]):
        _,rva,size,raw=struct.unpack_from('<IIII',data,table+40*i+8)
        sections.append((rva,size,raw))
    def file_offset(address,size):
        for rva,length,raw in sections:
            if rva<=address and address+size<=rva+length:return raw+address-rva
        raise ValueError('PE directory falls outside file-backed sections')
    fields={'COFF.TimeDateStamp':pe+8,'ExportDirectory.TimeDateStamp':file_offset(export,40)+4}
    debug,size=struct.unpack_from('<II',data,optional+112+6*8)
    if debug or size:
        if not debug or not size or size%28:raise ValueError('Malformed PE debug directory')
        offset=file_offset(debug,size)
        for i in range(size//28):fields[f'DebugDirectory[{i}].TimeDateStamp']=offset+28*i+4
    return fields


def canonicalize(raw,reference):
    if len(raw)!=reference['bytes']:raise ValueError('Rebuilt executable size differs from qualified reference')
    actual=timestamp_fields(raw);rows=reference['canonical_metadata_fields']
    if set(actual)!={r['name'] for r in rows} or len(rows)!=len(actual):
        raise ValueError('Only the declared PE timestamp fields may be canonicalized')
    result=bytearray(raw);edits=[]
    for row in rows:
        if row['bytes']!=4 or actual[row['name']]!=row['offset']:
            raise ValueError('PE timestamp location differs from reference')
        before=struct.unpack_from('<I',raw,row['offset'])[0]
        struct.pack_into('<I',result,row['offset'],row['value'])
        edits.append(dict(name=row['name'],offset=row['offset'],before=before,after=row['value']))
    if sha(result)!=reference['sha256']:
        raise ValueError('Rebuilt machine code/data differ; refusing reference compatibility')
    return bytes(result),edits


def finalize_executable(raw, manifest):
    """Keep reproduction separate from a new, not-yet-qualified source build."""
    reference = manifest.get('reference_executable')
    if reference is not None:
        data, edits = canonicalize(raw, reference)
        return data, edits, 'reference_executable_reproduced', True
    if manifest.get('qualification') != 'unqualified_source_build':
        raise ValueError('New native source build must explicitly remain unqualified')
    result = bytearray(raw)
    edits = []
    for name, offset in timestamp_fields(raw).items():
        before = struct.unpack_from('<I', raw, offset)[0]
        struct.pack_into('<I', result, offset, 0)
        edits.append(dict(name=name, offset=offset, before=before, after=0))
    return bytes(result), edits, 'source_build_unqualified', False


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--profile',choices=PROFILE_MANIFESTS,default='base',
                        help='Build an explicit source profile; only reference profiles imply reproduced bytes')
    args=parser.parse_args()
    if os.name!='nt' or struct.calcsize('P')!=8:parser.error('Windows x64 is required')
    manifest_path=ROOT/PROFILE_MANIFESTS[args.profile]
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('schema')!='civ6-host.native-source.v1':parser.error('Unknown source manifest')
    if '.'.join(map(str,sys.version_info[:2]))!=manifest['toolchain']['python_version']:
        parser.error('This retained profile requires Python '+manifest['toolchain']['python_version'])
    inputs=source_inputs(ROOT,manifest)
    version=manifest['toolchain']['compiler_version_directory']
    candidates=sorted(Path(os.environ['ProgramFiles']).glob('Microsoft Visual Studio/*/*/VC/Tools/MSVC/'+version))
    vc=next((p for p in candidates if (p/'bin/Hostx64/x64/cl.exe').is_file()),None)
    sdk_root=Path(os.environ['ProgramFiles(x86)'])/'Windows Kits/10'
    sdk=sdk_root/'Include'/manifest['toolchain']['sdk']
    if vc is None or not (sdk/'um/Windows.h').is_file():
        parser.error('The retained MSVC '+version+' and Windows SDK '+sdk.name+' are required')
    python_root=Path(sys.base_prefix)
    output=args.output_dir.resolve()
    if output.is_relative_to(ROOT/'native'):parser.error('Build outputs must stay outside native source')
    if output.exists() and any(output.iterdir()):parser.error('Use a new empty build directory')
    output.mkdir(parents=True,exist_ok=True)
    raw_dir=output/'raw';raw_dir.mkdir()
    staged=staging_paths(ROOT,manifest);snapshots=[]
    for path,data in inputs.items():
        target=output/'inputs'/Path(staged[path])
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        snapshots.append(dict(path=str(target),source_path=str(path),build_path=staged[path].as_posix(),sha256=sha(data)))
    name=(manifest.get('reference_executable') or manifest['artifact'])['name']
    if Path(name).name!=name or not name.endswith('.exe'):
        raise ValueError('Native executable name must be a local .exe filename')
    exe=raw_dir/name
    compiler=vc/'bin/Hostx64/x64/cl.exe'
    env=os.environ.copy()
    env['INCLUDE']=';'.join(map(str,[vc/'include',sdk/'ucrt',sdk/'shared',sdk/'um',python_root/'include']))
    env['LIB']=';'.join(map(str,[vc/'lib/x64',sdk_root/'Lib'/sdk.name/'ucrt/x64',sdk_root/'Lib'/sdk.name/'um/x64',python_root/'libs']))
    command=[str(compiler),*manifest['toolchain']['flags'],f'/Fo{output / "host.obj"}',f'/Fe{exe}',
             str(output/'inputs/gamecore_python_host.c'),'/link',*manifest['toolchain']['link_flags']]
    report=dict(schema='civ6-host.native-build.v1',status='building',profile=manifest['profile'],
        source_manifest_sha256=sha(manifest_path.read_bytes()),sources=snapshots,command=command,
        compiler_sha256=sha(compiler.read_bytes()),sdk=sdk.name,python_home=str(python_root),
        wall_limit_seconds=60,memory_limit_mib=1024,gamecore_loaded=False,original_lab_required=False)
    sys.path.insert(0,str(ROOT/'src'))
    from civ6_host.runtime.windows_process import WindowsProcessRuntime
    runtime=WindowsProcessRuntime();process=job=None
    try:
        with (output/'compiler.log').open('wb') as log:
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,
                cwd=output,env=env,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            job=runtime.job(process,1024*1024*1024)
            report['compiler_exit_code']=process.wait(timeout=60)
        if report['compiler_exit_code']!=0:raise RuntimeError('Native compilation failed; see compiler.log')
        raw=exe.read_bytes();report['raw_executable']=dict(path=str(exe),bytes=len(raw),sha256=sha(raw))
        canonical,edits,status,compatible=finalize_executable(raw,manifest)
        target=output/name;target.write_bytes(canonical)
        report.update(status=status,canonical_metadata_edits=edits,
            executable=dict(path=str(target),bytes=len(canonical),sha256=sha(canonical)),
            exact_reference_bytes=compatible,compatibility_admitted=compatible)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));raise
    finally:
        if job is not None:
            if process is not None and process.poll() is None:runtime.terminate_job(job,99)
            runtime.close_job(job)
        if process is not None:
            if process.poll() is None:process.kill()
            process.wait(timeout=10);report['compiler_reaped']=True
        (output/'build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({k:report[k] for k in ('status','error','executable','compiler_reaped') if k in report}))
    return 0


if __name__=='__main__':raise SystemExit(main())
