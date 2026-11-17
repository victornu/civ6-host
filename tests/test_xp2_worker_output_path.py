"""Run the entire worker opener with real file writes and a saved owner.

Native loading/lifecycle and source admission are explicit boundary doubles;
the worker function, closure digest, dependency loops and write-once receipts
are the installed implementations. No AST-extracted worker or native process.
"""
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from civ6_host.runtime import execution_images, provenance, xp1_session_admission
from civ6_host.runtime import xp1_session_inputs as inputs
from civ6_host.runtime import xp1_prophet_activation_source, xp1_religion_founding_source
from civ6_host.runtime import xp1_religion_beliefs_source, xp1_pantheon_source
from civ6_host.runtime import xp2_great_people_source
from civ6_host.runtime.capture_admission import XP2_LAUNCH_FIELD
from civ6_host.runtime.saved_load_services import SavedLoadServices
from civ6_host.runtime.xp1_saved_load_owner import SavedLoadOwner
from civ6_host.runtime.xp2_bundle_inputs import REFERENCE
from civ6_host.runtime.workers import network_worker


FLAGS = ('xp2_great_people', 'xp2_prophet_activation', 'xp2_religion_founding',
         'xp2_religion_beliefs', 'xp2_pantheon')
SOURCES = (xp2_great_people_source, xp1_prophet_activation_source, xp1_religion_founding_source,
           xp1_religion_beliefs_source, xp1_pantheon_source)
FILES = ('raw-load-result.json', 'cache-result.json', 'post160-result.json',
         'publication-result.json', 'player-view-result.json')
METHODS = ('populate_caches', 'postload', 'publish', 'observe_initial', 'begin_commands')


class XP2WorkerOutputPathTests(unittest.TestCase):
    def test_full_opener_keeps_each_run_directory_for_every_selected_reader(self):
        with TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            dependency_dir = root / 'retained-source'
            dependency_dir.mkdir()
            dependencies = {}
            for name in ('first-source.json', 'last-source.json'):
                path = dependency_dir / name
                path.write_bytes(b'{}\n')
                dependencies[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
            # Reproduce an already retained receipt without touching real
            # evidence. A wrong output directory must hit write-once refusal.
            retained = dependency_dir / FILES[0]
            retained_bytes = b'preserved historical receipt\n'
            retained.write_bytes(retained_bytes)
            emitted = []
            cases = [(), *((flag,) for flag in FLAGS), FLAGS]
            for number, (enabled, commands) in enumerate([*((case, False) for case in cases), (FLAGS, True)]):
                run = root / ('run-' + str(number)); run.mkdir()
                closure = dict(input_profile='xp2-lan', lifetime_seconds=60,
                    official_bundle=dict(zip(('path', 'sha256'), REFERENCE)),
                    execution_image={'fixture': 'selected at native boundary'},
                    pins=dict(dependencies), **{XP2_LAUNCH_FIELD: {'fixture': True}},
                    xp2_great_people_actions=commands,
                    **{name: True for name in ('raw_only_candidate', 'post160_candidate',
                        'publish_cache_candidate', 'close_loaded_candidate',
                        'observe_player_candidate', 'unit_commands_candidate')},
                    **{flag: flag in enabled for flag in FLAGS})
                path = run / 'closure.json'
                raw = (json.dumps(closure, ensure_ascii=False) + '\n').encode('utf-8')
                path.write_bytes(raw)
                saved = SavedLoadOwner.__new__(SavedLoadOwner)
                saved.prefix = SavedLoadServices.__new__(SavedLoadServices)
                saved.inputs = SimpleNamespace(checkpoint=None)
                saved.raw_result = dict(fixture_run=number, phase='raw')
                calls = []
                def emit(stage, **payload):
                    emitted.append((run, stage, payload))
                def lifecycle(method):
                    def invoke(actual):
                        self.assertIs(actual, saved)
                        calls.append(method)
                        return dict(fixture_run=number, phase=method)
                    return invoke
                def opened(actual_closure, actual_emit, actual_win):
                    self.assertIs(actual_closure, closure)
                    self.assertIs(actual_emit, emit)
                    self.assertIsNone(actual_win)
                    return saved
                with ExitStack() as stack:
                    stack.enter_context(patch.dict(os.environ, {
                        inputs.SAVED_LOAD_CLOSURE_ENV: hashlib.sha256(raw).hexdigest()}))
                    stack.enter_context(patch.object(provenance, 'verify_installation'))
                    stack.enter_context(patch.object(execution_images, 'from_identity',
                        return_value=execution_images._PROFILE))
                    stack.enter_context(patch.object(inputs, 'saved_load_build_pins',
                        return_value=Path(sys.executable).resolve()))
                    stack.enter_context(patch.object(SavedLoadOwner, 'open', side_effect=opened))
                    for method in METHODS:
                        stack.enter_context(patch.object(SavedLoadOwner, method, autospec=True,
                            side_effect=lifecycle(method)))
                    binding = stack.enter_context(patch.object(xp1_session_admission, 'bind'))
                    queried = []
                    for flag, source in zip(FLAGS, SOURCES):
                        # Profile selection/support remains real. Only the
                        # previously qualified source payload is substituted.
                        if source is not xp2_great_people_source:
                            stack.enter_context(patch.object(source, 'require_actions'))
                        def dependency_rows(image, *, reference=None, include_actions=False, current_flag=flag):
                            self.assertIs(image, execution_images._PROFILE)
                            self.assertEqual(reference, REFERENCE)
                            self.assertIs(include_actions, commands and current_flag == 'xp2_great_people')
                            queried.append(current_flag)
                            return dict(dependencies)
                        stack.enter_context(patch.object(source, 'source_dependencies', side_effect=dependency_rows))
                    result, compare = network_worker._open_xp1(closure, path, emit, None)
                    self.assertIs(result, saved); self.assertIsNone(compare)
                    binding.assert_called_once_with(saved)
                    self.assertEqual(queried, list(enabled))
                self.assertEqual(calls, list(METHODS))
                self.assertEqual(path.read_bytes(), raw)
                receipts = [payload['receipt'] for output_run, stage, payload in emitted
                            if output_run == run and 'receipt' in payload]
                self.assertEqual([Path(row['path']) for row in receipts], [run/name for name in FILES])
                for row in receipts:
                    receipt_path = Path(row['path'])
                    data = receipt_path.read_bytes()
                    self.assertEqual(len(data), row['bytes'])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), row['sha256'])
                    self.assertEqual(json.loads(data.decode('utf-8'))['fixture_run'], number)
                for flag in FLAGS:
                    self.assertIs(getattr(saved, flag), flag in enabled)
                self.assertIs(saved.xp2_great_people_actions, commands)
                self.assertEqual(retained.read_bytes(), retained_bytes)
            self.assertEqual(set(p.name for p in dependency_dir.iterdir()),
                             {'first-source.json', 'last-source.json', FILES[0]})


if __name__ == '__main__': unittest.main()
