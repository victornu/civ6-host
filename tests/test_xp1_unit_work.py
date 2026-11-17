from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.contracts import information, network_turn, unit_work_state
from civ6_host.runtime import unit_work_info, xp1_session_view, xp1_unit_work_profile
from civ6_host.runtime.execution_images import _XP1_PROFILE
from civ6_host.runtime.paths import resource_root
from test_session_capabilities import seal


class RiseAndFallUnitWorkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = resource_root()
        proof = json.loads((root/'evidence/host-xp1-stock-building-unit-purchase-save-reload-native.json').read_bytes())
        ref = proof['saved']['output_checkpoint']
        data = (root/ref['path']).read_bytes()
        if sha256(data).hexdigest() != ref['sha256']:
            raise ValueError('Retained Rise and Fall purchase checkpoint differs')
        cls.checkpoint = json.loads(data)

    def test_unit_work_query_shares_existing_purchases_and_exact_action_selection(self):
        obs = self.checkpoint['observation']
        saved = self.checkpoint['decisions']
        view = deepcopy(saved)
        pid, turn = obs['player_id'], obs['turn']
        units = [dict(unit_id=u['id'], plot_id=u['x']+u['y']*obs['width'],
                      charges=3 if u['moves'] > 0 else 0, moves_token=format(u['moves'], '.17g'),
                      improvement=-1, route=-1, improvement_pillaged=False, route_pillaged=False)
                 for u in obs['units']]
        row = next(u for u in units if float(u['moves_token']) > 0)
        x, y = row['plot_id'] % obs['width'], row['plot_id'] // obs['width']
        # Exercise serialization and selection only. No native offer is fabricated for the saved game.
        action = dict(kind='build_improvement', unit_id=row['unit_id'], x=x, y=y, plot_id=row['plot_id'],
                      charges=row['charges'], moves_token=row['moves_token'], index=1, hash=168372657,
                      item_type='IMPROVEMENT_FARM', selector=1)
        disabled = dict(kind='terrain_operation', unit_id=row['unit_id'], x=x, y=y, plot_id=row['plot_id'],
                        charges=row['charges'], moves_token=row['moves_token'], operation='REPAIR', hash=3)
        catalogue = dict(player_id=pid, turn=turn, enabled=True,
                         offers=[dict(action=action, legal=True), dict(action=disabled, legal=False)])
        state = dict(schema=unit_work_state.PLOT_SCHEMA, player_id=pid, turn=turn, units=units)
        targets = [{k: v for k, v in u.items() if k not in ('charges', 'moves_token')} for u in units]
        details = dict(schema=unit_work_info.SCHEMA, player_id=pid, turn=turn, targets=targets,
                       offers=[dict(action=deepcopy(a), legal=legal, action_name=None, feature=None,
                                    descriptions=[], failure_reasons=[])
                               for a, legal in ((action, True), (disabled, False))])

        with patch.object(unit_work_info, 'read_catalog', return_value=(catalogue, details)), \
                patch('civ6_host.runtime.unit_work_state.observe', return_value=state):
            xp1_session_view._add_unit_work(SimpleNamespace(prefix=object()), obs, view, actions_closed=False)
        seal(view)
        projected, transition = network_turn.checkpoint_xp1_unit_work_projection(view, saved, obs)
        self.assertEqual(projected, saved)
        self.assertEqual(transition['added_action_families'], ['build_improvement', 'terrain_operation'])
        self.assertEqual(view['city_purchases'], saved['city_purchases'])
        public = information.project('unit_work', obs, view)
        self.assertEqual(public['schema'], information.UNIT_WORK_DETAILED_GROUP_SCHEMA)
        self.assertEqual(public['catalogue'], catalogue)
        self.assertEqual(network_turn.select_capability(view, dict(decision_id=view['decision_id'],
            candidate_id=network_turn.digest(action))), action)
        with self.assertRaises(ValueError):
            network_turn.select_capability(view, dict(decision_id=view['decision_id'],
                candidate_id=network_turn.digest(disabled)))
        already_enabled = deepcopy(view)
        view['unit_work_state']['units'][0]['charges'] += 1
        seal(view)
        unchanged, transition = network_turn.checkpoint_xp1_unit_work_projection(view, already_enabled, obs)
        self.assertIsNone(transition)
        self.assertNotEqual(unchanged, already_enabled)

    def test_installed_bindings_and_sources_match_the_exact_file(self):
        import pefile
        from civ6_host.runtime.a0_family_source import verify_pinned_files

        profile = xp1_unit_work_profile
        verify_pinned_files(profile.source_dependencies(_XP1_PROFILE))
        pe = pefile.PE(str(Path(_XP1_PROFILE.path)), fast_load=True)
        try:
            core = SimpleNamespace(_handle=pe.OPTIONAL_HEADER.ImageBase, _civ6_host_execution_image=_XP1_PROFILE)
            read = lambda address, size: pe.get_data(address-core._handle, size)
            profile.verify_live(core, read)
            saved = SimpleNamespace(backend=SimpleNamespace(core=core, runtime=SimpleNamespace(read=read)),
                                    inputs=SimpleNamespace(official_bundle=profile.REFERENCE))
            saved.continuation = SimpleNamespace(owner=saved.backend)
            with self.assertRaisesRegex(ValueError, 'verified'):
                profile.require_owner(saved)
            profile.bind(saved)
            profile.require_owner(saved)
            with self.assertRaisesRegex(ValueError, 'binding'):
                profile.verify_live(core, lambda address, size: bytes(size))
        finally:
            pe.close()
