"""Read-only preparer metadata seams; these tests execute no native engine."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import review_xp1_session as reviewer


HOST=Path(__file__).resolve().parents[1]
ACCEPTANCE=HOST/'work/xp1-unit-attacks/scenario-preparation07/result.json'
ARCHIVE=HOST/'work/xp1-turn-integration/native-session32/executed-sources.zip'


class PreparerReviewTests(unittest.TestCase):
    def setUp(self):
        if not ACCEPTANCE.is_file() or not ARCHIVE.is_file():
            self.skipTest('Private retained preparer witness absent')
        self.raw=ACCEPTANCE.read_bytes();self.value=json.loads(self.raw)

    def test_projection_preserves_original_and_exact_selector_archive_identity(self):
        projected,proof=reviewer.project_preparer_receipt(self.value,ARCHIVE)
        self.assertEqual(projected['status'],'native_unit_attack_preparation_checkpoint_saved')
        self.assertNotIn('runs',projected)
        self.assertEqual(projected['supervised_runs'],self.value['runs'])
        self.assertEqual(proof['source_selector']['sha256'],self.value['selector_sha256'])
        self.assertEqual(proof['executed_sources_archive']['sha256'],
                         '7ab9fd43e58e7226265e6047a5dcdbb98dd1275aa29b931809f38cd29d8dcb00')
        self.assertGreater(proof['executed_host_python_source_count'],0)
        self.assertEqual(ACCEPTANCE.read_bytes(),self.raw)
        self.assertEqual(self.value,json.loads(self.raw))

    def test_unfinished_refused_mixed_or_mismatched_shapes_are_not_promoted(self):
        for mode in ('refused','partial','extra_error','missing_report','two_runs','no_checkpoint',
                     'training','no_offers','bad_turn_type','bad_public_type','other_run_public','input_hash'):
            bad=deepcopy(self.value)
            if mode=='refused':bad['status']='refused'
            elif mode=='partial':bad['status']='partial_public_exploration_checkpoint_retained'
            elif mode=='extra_error':bad['error']='failure'
            elif mode=='missing_report':bad['runs'][0].pop('report')
            elif mode=='two_runs':bad['runs']*=2
            elif mode=='no_checkpoint':bad['runs'][0]['checkpoint']=None
            elif mode=='training':bad['training']=True
            elif mode=='no_offers':bad['offered_attacks']=[]
            elif mode=='bad_turn_type':bad['turns_advanced']=True
            elif mode=='bad_public_type':bad['prepared_public']=False
            elif mode=='other_run_public':bad['prepared_public']=str(ACCEPTANCE)
            else:bad['input_checkpoint']['sha256']='0'*64
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                reviewer.project_preparer_receipt(bad,ARCHIVE)

    def test_selector_and_executed_source_bytes_cannot_be_substituted(self):
        for member in ('tools/unit_attack_preparation.py','src/civ6_host/contracts/network_turn.py'):
            with self.subTest(member=member),tempfile.TemporaryDirectory() as directory:
                altered=Path(directory)/'altered.zip'
                with zipfile.ZipFile(ARCHIVE) as old,zipfile.ZipFile(altered,'w') as new:
                    for item in old.infolist():
                        raw=old.read(item.filename)
                        new.writestr(item,raw+b'\n# changed\n' if item.filename==member else raw)
                with self.assertRaisesRegex(ValueError,'selector/archive'):
                    reviewer.project_preparer_receipt(self.value,altered)

    def test_declared_public_offers_and_checkpoint_join_the_final_reviewed_boundary(self):
        prepared=Path(self.value['prepared_public']);view=json.loads(prepared.read_bytes())
        final=dict(reference=reviewer.pin(prepared),sequence=view['sequence'],
            turn=view['observation']['turn'],decisions=view['decisions'],candidates=view['decisions']['candidates'])
        row=dict(public=[final],ledger=dict(checkpoint=dict(phase_receipt=dict(
            manifest_reference=self.value['checkpoint']))))
        proof=reviewer.review_prepared_attack_boundary(self.value,[row])
        self.assertEqual(proof['offered_attacks'],self.value['offered_attacks'])
        self.assertFalse(proof['attack_execution_claimed'])
        for mode in ('public','offers','checkpoint','duplicate_candidate','empty_native_offers'):
            acceptance=deepcopy(self.value);rows=deepcopy([row])
            if mode=='public':acceptance['prepared_public']=str(prepared.parent/'public-0000.json')
            elif mode=='offers':acceptance['offered_attacks'][0]['plot_id']+=1
            elif mode=='checkpoint':acceptance['checkpoint']['sha256']='0'*64
            elif mode=='duplicate_candidate':
                action=acceptance['offered_attacks'][0]
                rows[0]['public'][0]['candidates'].append(next(
                    c for c in rows[0]['public'][0]['candidates'] if c['action']==action))
            else:rows[0]['public'][0]['decisions']['unit_attacks']['offers']=[]
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                reviewer.review_prepared_attack_boundary(acceptance,rows)


if __name__=='__main__':unittest.main()
