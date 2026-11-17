"""Build the separately pinned XP2 deal-value companion with the retained toolchain."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def pin(path):
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def main(output):
    if os.name != 'nt' or sys.maxsize <= 2**32:
        raise RuntimeError('Windows x64 is required')
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = ROOT / 'native/profiles/xp2-current-strings/source-manifest.json'
    tools = json.loads(manifest.read_bytes())['toolchain']
    version = tools['compiler_version_directory']
    vc = next(p for p in sorted(Path(os.environ['ProgramFiles']).glob(
        'Microsoft Visual Studio/*/*/VC/Tools/MSVC/'+version)) if (p/'bin/Hostx64/x64/cl.exe').is_file())
    compiler = vc/'bin/Hostx64/x64/cl.exe'
    kit = Path(os.environ['ProgramFiles(x86)'])/'Windows Kits/10'
    sdk = tools['sdk']
    include, lib = kit/'Include'/sdk, kit/'Lib'/sdk
    env = os.environ.copy()
    env['INCLUDE'] = ';'.join(map(str,[vc/'include',include/'ucrt',include/'shared',include/'um']))
    env['LIB'] = ';'.join(map(str,[vc/'lib/x64',lib/'ucrt/x64',lib/'um/x64']))
    source = ROOT/'native/xp2_deal_value_bridge.c'
    staged = output/source.name
    staged.write_bytes(source.read_bytes())
    artifact = output/'xp2-deal-value.dll'
    argv = [str(compiler),'/nologo','/O2','/MT','/W4','/WX','/wd5105','/LD','/std:c11',str(staged),
            '/link','/NOLOGO','/Brepro',f'/OUT:{artifact}','kernel32.lib']
    with (output/'compiler.log').open('wb') as log:
        subprocess.run(argv, env=env, cwd=output, stdout=log, stderr=subprocess.STDOUT,
                       stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW,
                       timeout=60, check=True)
    receipt = dict(schema='civ6-host.xp2-deal-value-bridge.build.v1', source=pin(staged),
                   toolchain=pin(manifest),compiler=pin(compiler),sdk=sdk,artifact=pin(artifact),
                   gamecore_loaded=False)
    (output/'build.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt['artifact']))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
