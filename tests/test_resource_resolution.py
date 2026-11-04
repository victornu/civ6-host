"""Relocation keeps immutable references and rejects old-root reads."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

REPO=Path(__file__).resolve().parents[1]


class ResourceResolutionTests(unittest.TestCase):
    def test_relocation_and_original_read_boundary(self):
        code=r'''
import sys,os,json,hashlib
from pathlib import Path
sys.path.insert(0,sys.argv[1]);base=Path(sys.argv[2]);old=base/'old';new=base/'new'
old.mkdir();(old/'work').mkdir();source=old/'work/proof.json';source.write_bytes(b'{"unchanged":true}')
from civ6_host.runtime.resource_bundle import export_resources
ref=export_resources(source_root=old,destination=new,files={'work/proof.json':hashlib.sha256(source.read_bytes()).hexdigest()})
os.environ['CIV6_HOST_RESOURCE_ROOT']=str(new)
from civ6_host.runtime.resource_resolution import configure,resolve_path,enable_read_boundary,configure_closure,validate_closure,historical_reference
configure(ref);target=resolve_path(source)
assert target==new/'work/proof.json' and target.read_bytes()==source.read_bytes()
assert target.stat().st_mtime_ns==source.stat().st_mtime_ns
row={'path':str(target),'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
assert historical_reference(row)==dict(row,path=str(source))
try:historical_reference(dict(row,sha256='0'*64))
except ValueError:pass
else:raise AssertionError('Changed bytes received the original provenance identity')
assert resolve_path(base/'external')==base/'external'
try:resolve_path(old/'unlisted')
except ValueError:pass
else:raise AssertionError('Unlisted original path accepted')
closure={'pins':{}};configure_closure(closure);validate_closure(closure)
broken=dict(closure,private_resources=None)
try:validate_closure(broken)
except ValueError:pass
else:raise AssertionError('Worker accepted different resources')
enable_read_boundary()
assert target.read_bytes()==b'{"unchanged":true}'
for path in (source,old):
 try:source.read_bytes() if path==source else list(old.iterdir())
 except RuntimeError as exc:assert 'Historical resource read forbidden' in str(exc)
 else:raise AssertionError('Historical read was permitted')
try:configure(None)
except ValueError:pass
else:raise AssertionError('Resource configuration changed')
print('relocation, reference binding and no historical reads verified')
'''
        with tempfile.TemporaryDirectory(dir=REPO) as directory:
            result=subprocess.run([sys.executable,'-I','-B','-c',code,str(REPO/'src'),directory],
                capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
