"""One explicit larger diagnostic bound; no weakening of memory or Base limits."""
import unittest
from test_xp1_network_session import Fixture
from civ6_host.runtime.native.native_saved_session import validate_episode_budget_closure, MEMORY_LIMIT
from civ6_host.runtime.session_limits import standard_lifetime_limit


class LifetimeTests(unittest.TestCase):
    def test_constructor_and_worker_closure_share_exact_scoped_bound(self):
        with Fixture() as f:
            s=f.session(lifetime_seconds=1500)
            self.assertEqual(s.lifetime_seconds,1500)
            self.assertIsNone(s.episode_budget)
            for bad in (0,1501,True,1500.0):
                with self.subTest(bad=bad),self.assertRaises(ValueError):f.session(lifetime_seconds=bad)
            self.assertFalse(f.spawns)
        self.assertEqual(MEMORY_LIMIT,512*1024*1024)
        for profile,limit in (('xp1-lan',1500),('xp2-lan',1800),('lan',180),('single',180),('hotseat-four',180)):
            self.assertEqual(standard_lifetime_limit(profile),limit)
            self.assertIsNone(validate_episode_budget_closure(dict(input_profile=profile,lifetime_seconds=limit)))
            for bad in (limit+1,0,True,float(limit)):
                with self.subTest(profile=profile,bad=bad),self.assertRaises(ValueError):
                    validate_episode_budget_closure(dict(input_profile=profile,lifetime_seconds=bad))
            with self.assertRaises(ValueError):
                validate_episode_budget_closure(dict(input_profile=profile,lifetime_seconds=limit,stdout_limit_bytes=513*1024*1024))


if __name__=='__main__':unittest.main()
