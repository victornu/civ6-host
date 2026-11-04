from copy import deepcopy
from hashlib import sha256
import json
import unittest

from civ6_host.contracts import information, network_turn
from civ6_host.runtime import xp2_strategic_resources as resources
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.paths import resource_root


class StrategicResourceTests(unittest.TestCase):
    def test_public_inventory_rejects_hidden_or_wrong_boundary_rows(self):
        head = b'strategic-resources-v1|0|60|'
        iron = b'43|RESOURCE_IRON|1|50|0|2|0|2|-|-|-|-'
        result = resources._parse(head + b'1\n' + iron, 0, 60)
        self.assertEqual(result['resources'][0]['stockpile'], 1)
        self.assertIsNone(result['resources'][0]['power_demand'])
        for wire in (head + b'0\n' + iron, head + b'1\n' + iron.replace(b'|1|50|0|2|', b'|0|50|0|0|'),
                     head + b'1\n' + iron + b'\n' + iron):
            with self.assertRaises(ValueError):
                resources._parse(wire, 0, 60)
        with self.assertRaisesRegex(ValueError, 'Foreign'):
            resources._parse(head + b'1', 1, 60)

    def test_v24_resource_projection_does_not_rewrite_a_v23_checkpoint(self):
        path = resource_root() / ('work/xp2-client-sessions/'
            'run-0f6235f9432d4b6ab70bfc2617b7db15/checkpoint/checkpoint.json')
        if not path.is_file():
            self.skipTest('Retained private XP2 v23 witness required')
        raw = path.read_bytes()
        self.assertEqual(sha256(raw).hexdigest(),
                         '6fd90f7c566a951f2905f343863b39899fbd8565ca2442ed5f23145b73f4ab2c')
        saved = json.loads(raw)
        current = deepcopy(saved['decisions'])
        current['schema'] = network_turn.CAPABILITY_XP2_STRATEGIC_RESOURCES_SCHEMA
        current['strategic_resources'] = resources._parse(
            b'strategic-resources-v1|0|60|1\n43|RESOURCE_IRON|1|50|0|2|0|2|-|-|-|-', 0, 60)
        current.pop('decision_id')
        current['decision_id'] = network_turn.digest(current)
        projected, migration = network_turn.checkpoint_catalogue(
            current, saved['decisions'], saved['observation'], core_sha256=XP2_CORE_SHA256)
        self.assertEqual(projected, saved['decisions'])
        self.assertEqual(migration['added_public_fields'], ['strategic_resources'])
        detached = information.project('strategic_resources', saved['observation'], current)
        detached['resources'].clear()
        self.assertEqual(len(current['strategic_resources']['resources']), 1)
