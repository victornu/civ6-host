from copy import deepcopy
from hashlib import sha256
from struct import pack
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from civ6_host.contracts import network_turn, unit_upgrades
from civ6_host.runtime import xp1_session_view, xp1_unit_upgrades, xp2_dedications
from civ6_host.runtime.configuration_profiles import XP1_CORE_SHA256
from test_session_capabilities import seal
from test_xp1_dedications import expansion_catalogue


class RiseAndFallUpgradeTests(unittest.TestCase):
    def test_archive_matches_the_source_unit_and_has_no_stockpile_selector(self):
        action=dict(kind='upgrade_unit',unit_id=327683,hash=unit_upgrades.COMMAND,target_type=23,cost=40)
        binary=pack('<IHH7I',0x493830af,0,1,327683,16,0,1,0xffffd8f1,0xffffd8f1,0)
        self.assertEqual(xp1_unit_upgrades.validate_archive(binary,0,action),sha256(binary).hexdigest())
        for offset in (4,8,12,24,32):
            changed=bytearray(binary)
            changed[offset]^=1
            with self.assertRaisesRegex(ValueError,'differs from the selected unit'):
                xp1_unit_upgrades.validate_archive(bytes(changed),0,action)

    def test_upgrade_catalogue_does_not_change_saved_actions(self):
        obs,prior=expansion_catalogue()
        pid,turn=(obs[k] for k in ('player_id','turn'))
        dedication=xp2_dedications.parse_state(f'{pid}|{turn}|0|normal|0'.encode(),pid,turn)
        with patch.object(xp2_dedications,'catalogue',return_value=dedication):
            xp1_session_view._add_dedications(None,obs,prior,actions_closed=False,
                previous_schema=network_turn.CAPABILITY_XP1_UNIT_LEVIES_SCHEMA,
                target_schema=network_turn.CAPABILITY_XP1_DEDICATIONS_SCHEMA)
        seal(prior)
        current=deepcopy(prior)
        current['schema']=network_turn.XP1_UPGRADE_SCHEMA_BY_BASE[prior['schema']]
        offer=dict(unit_id=obs['units'][0]['id'],hash=unit_upgrades.COMMAND,target_type=23,cost=40,
                   resource_type=None,resource_cost=None,legal=True)
        read=Mock(return_value=dict(player_id=pid,turn=turn,offers=[offer]))
        xp1_session_view._add_upgrades(SimpleNamespace(),obs,current,read,acting=True,actions_closed=False)
        seal(current)
        projected,receipt=network_turn.checkpoint_catalogue(current,prior,obs,core_sha256=XP1_CORE_SHA256)
        self.assertEqual(projected,prior)
        self.assertEqual(receipt['added_action_families'],['upgrade_unit'])
        current['unit_upgrades']['offers'][0].update(resource_type=1,resource_cost=20)
        seal(current)
        with self.assertRaisesRegex(ValueError,'cannot contain Gathering Storm'):
            network_turn.checkpoint_catalogue(current,prior,obs,core_sha256=XP1_CORE_SHA256)


if __name__=='__main__':
    unittest.main()
