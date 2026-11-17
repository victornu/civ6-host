"""Actual Congress dependency loops with bounded file hashing; no engine."""
from contextlib import ExitStack
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from civ6_host.runtime import configuration_profiles, xp2_world_congress_source
from civ6_host.runtime.execution_images import _PROFILE
from civ6_host.runtime.paths import resource_root
from civ6_host.runtime.resource_resolution import resolve_path
from civ6_host.runtime.native import native_world_congress_review as review
from civ6_host.runtime.native import native_world_congress_active_effects as active

REFERENCES=(review.SOURCE,review.PRIVATE_SOURCE,review.NUMERIC_SOURCE,active.SOURCE,active.UI_SOURCE)
UPSTREAM={'fixture-upstream-pin':'e'*64}


def proof_rows(proofs, effects):
    if effects:
        p,u=proofs[active.SOURCE],proofs[active.UI_SOURCE]
        return [*p['inputs'].values(),*p['files'].values(),*u['inputs'].values()]
    p,q,n=(proofs[r] for r in REFERENCES[:3])
    return [p['parent'],*p['files'],p['provider_implementation'],p['topology_reference'],
            *q['parents'],*q['files'],*n['parents'].values(),*n['images'].values(),n['ui']]


class TrackedReader:
    def __init__(self, stream, row):self.stream,self.row=stream,row
    def __enter__(self):self.stream.__enter__();return self
    def __exit__(self,*args):return self.stream.__exit__(*args)
    def readable(self):return self.stream.readable()
    def read(self,*args):raise AssertionError('Hashing used a whole-file read')
    def readinto(self, buffer):
        size=len(buffer)
        if not 0<size<=256*1024:raise AssertionError('Unbounded hash buffer')
        count=self.stream.readinto(buffer)
        self.row['buffer_sizes'].append(size);self.row['bytes_read']+=count
        return count


class CongressDependencyStreamingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Real pinned source documents, immutable caller metadata and original
        # file hashes. Shared upstream graphs alone are isolated below.
        cls.proofs={reference:configuration_profiles._source(reference) for reference in REFERENCES}

    def walk(self, *, effects=False, proofs=None):
        proofs=self.proofs if proofs is None else proofs
        module=active if effects else review
        targets={resolve_path(Path(row['path'])) for row in proof_rows(proofs,effects)}
        opened=[];real_open=Path.open
        def tracked(path,*args,**kwargs):
            stream=real_open(path,*args,**kwargs)
            if path not in targets:return stream
            row=dict(path=str(path),bytes_read=0,buffer_sizes=[]);opened.append(row)
            return TrackedReader(stream,row)
        with ExitStack() as stack:
            upstream=stack.enter_context(patch.object(
                review if effects else xp2_world_congress_source,'source_dependencies',return_value=dict(UPSTREAM)))
            cards=stack.enter_context(patch.object(active.cards,'source_dependencies',return_value={})) if effects else None
            stack.enter_context(patch.object(configuration_profiles,'_source',side_effect=proofs.__getitem__))
            stack.enter_context(patch.object(Path,'open',tracked))
            stack.enter_context(patch.object(Path,'read_bytes',side_effect=AssertionError('Whole-file bytes forbidden')))
            result=module.source_dependencies(execution_image=_PROFILE)
        upstream.assert_called_once_with(execution_image=_PROFILE)
        if cards is not None:cards.assert_called_once_with()
        return result,opened

    def expected(self, effects):
        result=dict(UPSTREAM)
        for reference in REFERENCES[3:] if effects else REFERENCES[:3]:
            result[str(resolve_path(resource_root()/reference[0]).resolve())]=reference[1]
        for row in proof_rows(self.proofs,effects):
            result[str(resolve_path(Path(row['path'])).resolve())]=row['sha256']
        return result

    def verify_walk(self,effects):
        result,opened=self.walk(effects=effects)
        self.assertEqual(result,self.expected(effects))
        self.assertEqual(len(opened),len(proof_rows(self.proofs,effects)))
        self.assertTrue(any(row['bytes_read']>256*1024 for row in opened))
        for row in opened:
            self.assertEqual(row['bytes_read'],Path(row['path']).stat().st_size)
            self.assertTrue(row['buffer_sizes'])
            self.assertLessEqual(max(row['buffer_sizes']),256*1024)

    def test_review_three_real_loops_keep_every_digest_and_read_all_bytes_in_blocks(self):
        self.verify_walk(False)

    def test_active_effects_two_real_loops_keep_every_digest_and_read_all_bytes_in_blocks(self):
        self.verify_walk(True)

    def test_all_five_loops_reject_last_byte_mutation_after_first_block(self):
        # Change one referenced test file per real loop, preserving each proof's
        # own schema, scope, correspondence and metadata admission checks.
        cases=((review.SOURCE,'files',0,False,'installed caller'),
               (review.PRIVATE_SOURCE,'files',0,False,'own-target caller'),
               (review.NUMERIC_SOURCE,'images',None,False,'numeric source dependency'),
               (active.SOURCE,'files',None,True,'active effects source dependency'),
               (active.UI_SOURCE,'inputs','proposal_source',True,'emergency UI dependency'))
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'dependency.bin'
            raw=b'authored-test-dependency\0'+bytes(range(256))*4096+b'final-byte!'
            expected=hashlib.sha256(raw).hexdigest()
            for reference,field,key,effects,message in cases:
                with self.subTest(source=reference[0],field=field):
                    path.write_bytes(raw)
                    proofs=dict(self.proofs);proof=dict(proofs[reference]);proofs[reference]=proof
                    container=proof[field]
                    if hasattr(container,'items'):
                        container=dict(container);key=next(iter(container)) if key is None else key
                    else:container=list(container)
                    row=dict(container[key]);row.update(path=str(path),sha256=expected)
                    container[key]=row;proof[field]=container
                    result,opened=self.walk(effects=effects,proofs=proofs)
                    self.assertEqual(result[str(path.resolve())],expected)
                    self.assertTrue(any(r['path']==str(path) and r['bytes_read']==len(raw) for r in opened))
                    with path.open('r+b') as stream:
                        stream.seek(-1,2);stream.write(b'?')
                    with self.assertRaisesRegex(ValueError,message):self.walk(effects=effects,proofs=proofs)

    def test_primary_source_metadata_and_exact_upstream_argument_are_still_checked(self):
        for module,effects in ((review,False),(active,True)):
            proofs=dict(self.proofs);proofs[module.SOURCE]=dict(proofs[module.SOURCE],schema='foreign')
            with self.subTest(module=module.__name__),self.assertRaises(ValueError):
                self.walk(effects=effects,proofs=proofs)


if __name__=='__main__':unittest.main()
