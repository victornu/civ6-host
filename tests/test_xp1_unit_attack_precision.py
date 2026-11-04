"""Real composed owner preserves raw guards and exposes detached UI precision."""
from copy import deepcopy
import json
import unittest
from test_xp1_unit_attack_owner import Fixture as ExistingFixture
from civ6_host.runtime import xp1_unit_attacks as adapter


class Fixture(ExistingFixture):
    def __init__(self):
        super().__init__();self.city_target=True;self.raw_strength=20.5
        self.observation['visible_enemy_units']=[];self.token.observation=deepcopy(self.observation)
    def evaluate(self,child,source,name,**kw):
        result=super().evaluate(child,source,name,**kw)
        if name==b'@explicit_visible_city_targets':
            parsed=json.loads(result)
            for row in parsed['cities']:row['defense_strength']=self.raw_strength
            return json.dumps(parsed).encode()
        return result


class UnitAttackPrecisionTests(unittest.TestCase):
    def test_public_raw_and_effect_channels_keep_separate_precision(self):
        f=Fixture();self.addCleanup(f.close);read=f.prepare();action=read['actions'][0]
        self.assertEqual(read['unit_attacks']['cities'][0]['defense_strength'],21)
        self.assertEqual(f.token.explicit_combat_cities[0]['defense_strength'],20.5)
        event=adapter.administrative_readback(f.saved,f.token.observation,13)
        self.assertEqual(event['cities'][0]['defense_strength'],20.5)
        self.assertEqual(event['sequence'],13);self.assertNotEqual(event['sequence'],f.token.sequence)
        self.assertFalse(event['actor_channel'])
        event['cities'][0]['defense_strength']=99
        self.assertEqual(f.token.explicit_combat_cities[0]['defense_strength'],20.5)
        f.saved._running=False;result=f.saved.execute(action)
        self.assertEqual(result['effect']['receipt']['effect']['visible_cities_before'][0]['defense_strength'],20.5)
        self.assertEqual(result['effect']['receipt']['effect']['visible_cities_after'][0]['defense_strength'],20.5)
        self.assertEqual(f.token.publication_count,1)

    def test_projection_invariant_offers_and_raw_snapshot_revision_guards(self):
        f=Fixture();self.addCleanup(f.close);first=f.prepare()
        f.raw_strength=20+129/256;second=f.prepare()
        self.assertEqual(second,first)
        event=adapter.administrative_readback(f.saved,f.token.observation,3)
        self.assertEqual(event['cities'][0]['defense_strength'],f.raw_strength)
        before=deepcopy(f.token.observation);before['turn']+=1
        with self.assertRaises(ValueError):adapter.administrative_readback(f.saved,before,3)
        with self.assertRaises(ValueError):adapter.administrative_readback(f.saved,f.token.observation,True)
        f.token.sequence+=1
        with self.assertRaises(ValueError):adapter.administrative_readback(f.saved,f.token.observation,3)
        self.assertEqual(f.machine,[])


if __name__=='__main__':unittest.main()
