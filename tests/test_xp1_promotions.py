from copy import deepcopy
from hashlib import sha256
from struct import pack
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.contracts import network_turn
from civ6_host.runtime import xp1_promotions, xp1_session_view, xp2_dedications
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from test_session_capabilities import seal
from test_xp1_dedications import expansion_catalogue


class RiseAndFallPromotionTests(unittest.TestCase):
    def test_promotion_archive_uses_hash_and_xp1_slot(self):
        action = dict(kind='promote_unit',unit_id=131073,index=7,hash=3461640876,
                      item_type='PROMOTION_BATTLECRY')
        packet = pack('<IHH6I',0x493830af,0,1,131073,14,0,1,0,3461640876)
        self.assertEqual(xp1_promotions.validate_archive(packet,0,action),sha256(packet).hexdigest())
        for fields in ((13,3461640876),(14,7)):
            invalid = pack('<IHH6I',0x493830af,0,1,131073,fields[0],0,1,0,fields[1])
            with self.assertRaisesRegex(ValueError,'differs from the selected promotion'):
                xp1_promotions.validate_archive(invalid,0,action)

    def test_promotion_catalogue_and_offers_survive_additive_schema(self):
        observation, old = expansion_catalogue()
        pid,turn = (observation[k] for k in ('player_id','turn'))
        dedication = xp2_dedications.parse_state(f'{pid}|{turn}|0|normal|0'.encode(),pid,turn)
        with patch.object(xp2_dedications,'catalogue',return_value=dedication):
            xp1_session_view._add_dedications(None,observation,old,actions_closed=False,
                previous_schema=network_turn.CAPABILITY_XP1_UNIT_LEVIES_SCHEMA,
                target_schema=network_turn.CAPABILITY_XP1_DEDICATIONS_SCHEMA)
        seal(old)
        current = deepcopy(old)
        current['schema'] = network_turn.XP1_PROMOTION_SCHEMA_BY_BASE[old['schema']]
        units = sorted(observation['units'],key=lambda row:row['id'])
        action = dict(kind='promote_unit',unit_id=units[0]['id'],index=7,hash=3461640876,
                      item_type='PROMOTION_BATTLECRY')
        read = Mock(return_value=dict(player_id=pid,turn=turn,offers=[action],units=[
            dict(unit_id=row['id'],experience_points=15,promotions=[]) for row in units]))
        xp1_session_view._add_promotions(SimpleNamespace(),observation,current,read,
                                        acting=True,actions_closed=False)
        seal(current)
        self.assertEqual(network_turn.select_capability(current,dict(
            decision_id=current['decision_id'],candidate_id=network_turn.digest(action))),action)
        projected,receipt = network_turn.checkpoint_catalogue(current,old,observation,core_sha256=XP1_CORE_SHA256)
        self.assertEqual(projected,old)
        self.assertEqual(receipt['added_action_families'],['promote_unit'])

    def test_waiting_has_no_promotions_query(self):
        saved = SimpleNamespace(explicit_promotions={})
        state = dict(families={},candidates=[])
        query = Mock()
        xp1_session_view._add_promotions(saved,{},state,query,acting=False,actions_closed=False)
        query.assert_not_called()
        self.assertIsNone(saved.explicit_promotions)
        self.assertIsNone(state['unit_promotions'])
        self.assertEqual(state['families']['promote_unit']['status'],'unqualified')


if __name__=='__main__':
    unittest.main()
