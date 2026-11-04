"""XP2-specific roster joins in the shared later-stage ledger, no DLL calls."""
import copy
import unittest
import qualify_xp1_configuration as q
import test_xp2_saved_load_supervision as raw_fixtures


class XP2PostloadSupervisionTests(unittest.TestCase):
    setUp=raw_fixtures.XP2SavedLoadSupervision.setUp
    write=raw_fixtures.XP2SavedLoadSupervision.write
    persist=raw_fixtures.XP2SavedLoadSupervision.persist
    def test_publication_uses_exact_xp2_roster_without_xp1_substitution(self):
        expected=dict(current_game_turn=1,width=44,height=26,major_player_ids=[0,1],
            scope='privileged diagnostic; no learner observation',game_update_called=False)
        result=dict(post190_called=True,native_return_ignored=True,public_runtime_admitted=False,
            public_player_observation=False,game_update_called=False,context_destroyed=False,
            jobs_before=self.after,jobs_after=self.after,jobs_final=self.after,
            readback=expected,cache_dimensions=[44,26,44*26])
        q.saved_load_validate_publication(result,[],self.after,self.readback,xp2=True)
        changed=copy.deepcopy(result);changed['readback']['major_player_ids']=list(range(6))
        with self.assertRaisesRegex(ValueError,'readback'):
            q.saved_load_validate_publication(changed,[],self.after,self.readback,xp2=True)
        with self.assertRaisesRegex(ValueError,'readback'):
            q.saved_load_validate_publication(result,[],self.after,self.readback)

    def test_unknown_postload_mode_and_mutually_exclusive_lifetimes_refused(self):
        with self.assertRaisesRegex(ValueError,'mutually exclusive'):
            q.saved_load_validate_lifetime({}, {}, {}, {},xp2_raw=True,xp2_loaded=True)
        with self.assertRaisesRegex(ValueError,'Unqualified XP2 continuation'):
            q.saved_load_reconcile_later({}, {}, {}, {}, {}, {},phase='unit_commands',lifetime_seconds=120,xp2=True)


if __name__=='__main__':unittest.main()
