"""Retained-shape reviewer fixtures only: no native Save/Load or gameplay claim."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from civ6_host.contracts.placement_inventory import SCHEMA, SCOPE

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('inventory_review_fixture', REPO / 'tools/review_placement_inventory.py')
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
SOURCE = 'a' * 64
REFERENCE = dict(path='work/fixture/checkpoint.json', bytes=123, sha256='b' * 64)
PLACE = dict(kind='production_placement', city_id=23, category='district', index=1, hash=201,
             item_type='DISTRICT_HOLY_SITE', mode='place', plot_id=4, x=0, y=1)
ORDINARY = dict(kind='production', city_id=23, category='unit', index=0, hash=100, item_type='UNIT_SCOUT')
RESUME = dict(PLACE, kind='production_resume', mode='resume', plot_id=-1, x=-1, y=-1)
NATIVE_ROW = dict(city_id=23, category='district', index=1, hash=201, item_type='DISTRICT_HOLY_SITE',
                  plot_id=4, x=0, y=1, complete=False, district_id=45)


def view(episode, sequence, *, placed=False, district=False, candidates=()):
    observation = dict(player_id=0, turn=11, width=4, height=3,
        plots=[dict(index=4, x=0, y=1, visible=True, revealed=True, owner=0)],
        cities=[dict(id=23, owner=0)], units=[])
    inventory = dict(schema=SCHEMA, scope=SCOPE, player_id=0, turn=11,
                     rows=[copy.deepcopy(NATIVE_ROW)] if placed else [])
    head = dict(city_id=23, queue_size=1, kind='D' if district else 'U',
                item_index=1 if district else 0, hash=201 if district else 100, formation=None if district else 0)
    tracking = [dict(city_id=23, category='district', index=1, item_type='DISTRICT_HOLY_SITE',
        plot_id=4, x=0, y=1, placement_turn=11, observed_turn=11, exists=True, complete=False)] if placed else []
    decisions = dict(episode_id=episode, game_generation='generation-' + episode, sequence=sequence,
        decision_id=episode + '-' + str(sequence), candidates=[dict(candidate_id=str(i), action=copy.deepcopy(a))
            for i, a in enumerate(candidates)], placement_inventory=inventory,
        placements=tracking, choice_state=dict(production=[head]), production_queues={'fixture_native_queue': head})
    return dict(episode_id=episode, game_generation='generation-' + episode, sequence=sequence,
                observation=observation, decisions=decisions)


def event(v):
    return dict(stage='native_placement_inventory_readback', episode_id=v['episode_id'],
        game_generation=v['game_generation'], sequence=v['sequence'], player_id=0, turn=11,
        inventory=copy.deepcopy(v['decisions']['placement_inventory']), source_proof_sha256=SOURCE,
        host_tracking_used=False, native_gameplay_mutated=False)


def summary(v):
    return dict(episode_id=v['episode_id'], generation=v['game_generation'], sequence=v['sequence'], turn=11,
        observation=copy.deepcopy(v['observation']), decisions=copy.deepcopy(v['decisions']),
        **{k: copy.deepcopy(v['decisions'][k]) for k in
           ('candidates', 'placement_inventory', 'placements', 'choice_state', 'production_queues')})


def readbacks(views):
    return dict(scope=SCOPE, source_proof_sha256=SOURCE, host_tracking_used=False,
        native_gameplay_mutated=False, native_tracking_empty_witness=False, public_revision_count=len(views),
        records=[dict(sequence=v['sequence'], native={k: val for k, val in event(v).items() if k != 'stage'},
                      lines=[i + 1]) for i, v in enumerate(views)])


def command(action, seq, phase):
    return dict(protocol_sequence=seq, action=copy.deepcopy(action), turn_before=11, turn_after=11,
        command_result=dict(status='completed', reason=None, requested_action=copy.deepcopy(action)),
        ledger=dict(phase_receipt=phase))


def fixture():
    first = [view('a', 0, candidates=[PLACE]), view('a', 1, placed=True, district=True, candidates=[ORDINARY]),
             view('a', 2, placed=True, candidates=[RESUME])]
    second = [view('b', 0, placed=True, candidates=[RESUME]), view('b', 1, placed=True, district=True)]
    third = [view('c', 0, placed=True, candidates=[RESUME])]
    placed = command(PLACE, 1, dict(placement_status='completed', effect=dict(new_placement_verified=True)))
    ordinary = command(ORDINARY, 2, dict(explicit_choice_applied=True, kind='production'))
    resumed = command(RESUME, 1, dict(placement_status='completed', kind='production_resume', progress_before=7, progress_after=7))
    checkpoint = dict(manifest_reference=copy.deepcopy(REFERENCE), observed_game_turn=11, native_save_status=0,
        stream_closed=True, public_state_unchanged=True, continuation_not_advanced=True, native_load_of_pair_claimed=False)
    rows = []
    for i, (views, commands) in enumerate(((first, [placed, ordinary]), (second, [resumed]), (third, []))):
        ledger = dict(commands=commands, updates=[])
        if i == 0: ledger['checkpoint'] = dict(phase_receipt=checkpoint)
        marker = None if i == 0 else dict(checkpoint=[REFERENCE['path'], REFERENCE['sha256']], turn=11,
            public_observation_equal=True, public_decisions_equal=True, saved_decision_fields_equal=True,
            identity_rebound=True, catalogue_transition=None, complete_state_compared=False, strategic_training_ready=False)
        rows.append(dict(run='run-' + str(i), ledger=ledger, public=[summary(v) for v in views],
            inventory_receipts=readbacks(views), checkpoint_on_close=i == 0, checkpoint_reloaded=marker,
            checkpoint_input=None if i == 0 else {k: REFERENCE[k] for k in ('path', 'sha256')},
            normal_native_destroy_authenticated=True, all_source_pins_unchanged=True))
    def state(v):
        d = v['decisions']
        return dict(production=d['choice_state']['production'][0], placements=d['placements'], production_queues=d['production_queues'])
    steps = [dict(sequence=i + 1, action=copy.deepcopy(cmd['action']), command_result=copy.deepcopy(cmd['command_result']),
                  before=state(first[i]), after=state(first[i + 1])) for i, cmd in enumerate((placed, ordinary))]
    prep = dict(category='district', city_id=23, plot_id=4, item_type='DISTRICT_HOLY_SITE', steps=steps,
        initial_turn=11, final_turn=11, poll_calls=0, observation_scope='host_tracked', completion_witnessed=False,
        other_category_qualified=False, unobserved_placement_inventory_complete=False)
    acceptance = dict(status='native_placement_inventory_checkpoint_reset_verified', checkpoints=[copy.deepcopy(REFERENCE)],
        commands=[copy.deepcopy(cmd['command_result']) for cmd in (placed, ordinary, resumed)],
        inventory_group=dict(preparation=prep, checkpoint=copy.deepcopy(REFERENCE), resumed_episode='b', reset_episode='c',
            resume_action=copy.deepcopy(RESUME), resume_sequence=1, turn=11, native_row=copy.deepcopy(NATIVE_ROW),
            poll_calls=0, native_tracking_empty_witness=False))
    return acceptance, rows


class InventoryReadbacks(unittest.TestCase):
    def run_review(self, views, events):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); source_path = str(root / 'fixture-source.json')
            (root / 'closure.json').write_text(json.dumps(dict(pins={source_path: SOURCE},stdout_limit_bytes=67108864)), encoding='utf-8')
            (root / 'supervisor.json').write_text(json.dumps(dict(stdout_native_records=[])),encoding='utf-8')
            (root / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events), encoding='utf-8')
            public = {}
            for v in views:
                path = root / ('public-' + str(v['sequence']) + '.json')
                path.write_text(json.dumps(v), encoding='utf-8'); public[v['sequence']] = (path, v)
            with patch.object(review, '_source_reference', return_value=(source_path, SOURCE)):
                return review.validate_inventory_readback(root, public)

    def test_exact_native_copy_and_equal_duplicate_close_read(self):
        v = view('a', 0, placed=True)
        r = self.run_review([v], [event(v), dict(stage='unrelated'), event(v)])
        self.assertEqual(r['event_count'], 2); self.assertEqual(r['records'][0]['lines'], [1, 3])
        self.assertFalse(r['native_tracking_empty_witness'])

    def test_identity_source_scope_and_unknown_sequence_refused(self):
        v = view('a', 0, placed=True)
        for key, value in [('episode_id', 'foreign'), ('game_generation', 'foreign'), ('sequence', True),
                           ('sequence', 9), ('player_id', True), ('turn', True), ('source_proof_sha256', 'c' * 64),
                           ('host_tracking_used', True), ('native_gameplay_mutated', True)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.run_review([v], [dict(event(v), **{key: value})])

    def test_missing_divergent_or_hidden_inventory_is_not_empty_fallback(self):
        v = view('a', 0, placed=True)
        with self.assertRaises(ValueError): self.run_review([v], [])
        e = event(v); e['inventory']['rows'] = []
        with self.assertRaises(ValueError): self.run_review([v], [event(v), e])
        e = event(v); e['inventory'] = None
        with self.assertRaises(ValueError): self.run_review([v], [e])
        v['observation']['plots'][0]['visible'] = False
        with self.assertRaises(ValueError): self.run_review([v], [event(v)])


class InventoryGroup(unittest.TestCase):
    def test_authentic_shapes_preserve_native_inventory_with_tracking_retained(self):
        a, rows = fixture(); r = review.validate_inventory_group(a, rows)
        self.assertEqual((r['native_lifetimes'], r['save_count'], r['retained_progress']), (3, 1, 7))
        self.assertTrue(r['native_inventory_survives_load_and_reset'])
        self.assertFalse(r['native_tracking_empty_witness']); self.assertFalse(r['completion_qualified'])
        self.assertFalse(r['wonder_qualified'])

    def test_lifecycle_save_poll_and_unsupported_claims_refused(self):
        for mode in ('same_run', 'missing_save', 'poll', 'unclean', 'source_changed', 'empty_tracking_claim', 'extra_command'):
            a, rows = fixture()
            if mode == 'same_run': rows[2]['run'] = rows[1]['run']
            elif mode == 'missing_save': del rows[0]['ledger']['checkpoint']
            elif mode == 'poll': rows[1]['ledger']['updates'] = [{}]
            elif mode == 'unclean': rows[0]['normal_native_destroy_authenticated'] = False
            elif mode == 'source_changed': rows[0]['all_source_pins_unchanged'] = False
            elif mode == 'empty_tracking_claim': a['inventory_group']['native_tracking_empty_witness'] = True
            else: rows[2]['ledger']['commands'].append(rows[1]['ledger']['commands'][0])
            with self.subTest(mode=mode), self.assertRaises(ValueError): review.validate_inventory_group(a, rows)

    def test_checkpoint_reload_and_semantic_catalogue_tampering_refused(self):
        for mode in ('checkpoint', 'identity', 'catalogue', 'marker', 'saved_turn', 'save_return'):
            a, rows = fixture()
            if mode == 'checkpoint': rows[1]['checkpoint_input']['sha256'] = 'd' * 64
            elif mode == 'identity': rows[2]['public'][0]['generation'] = rows[1]['public'][0]['generation']
            elif mode == 'catalogue': rows[1]['public'][0]['decisions']['extra_information'] = 1
            elif mode == 'marker': rows[2]['checkpoint_reloaded']['public_decisions_equal'] = False
            elif mode == 'saved_turn': rows[0]['ledger']['checkpoint']['phase_receipt']['observed_game_turn'] = 12
            else: rows[0]['ledger']['checkpoint']['phase_receipt']['native_save_status'] = False
            with self.subTest(mode=mode), self.assertRaises(ValueError): review.validate_inventory_group(a, rows)

    def test_native_discovery_resumption_effect_and_progress_required(self):
        for mode in ('row', 'missing_readback', 'progress', 'unoffered', 'effect', 'reported_action', 'step'):
            a, rows = fixture()
            if mode == 'row': a['inventory_group']['native_row']['complete'] = True
            elif mode == 'missing_readback': rows[1]['inventory_receipts']['records'] = []
            elif mode == 'progress': rows[1]['ledger']['commands'][0]['ledger']['phase_receipt']['progress_after'] = 8
            elif mode == 'unoffered': rows[1]['public'][0]['candidates'] = []
            elif mode == 'effect': rows[0]['ledger']['commands'][0]['ledger']['phase_receipt']['effect']['new_placement_verified'] = False
            elif mode == 'reported_action': a['inventory_group']['resume_action']['hash'] = 555
            else: a['inventory_group']['preparation']['steps'][1]['before']['production']['hash'] = 999
            with self.subTest(mode=mode), self.assertRaises(ValueError): review.validate_inventory_group(a, rows)


if __name__ == '__main__':
    unittest.main()
