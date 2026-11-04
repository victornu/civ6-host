"""Exercise the extracted event-reader method without loading a DLL."""
import ast
import io
import json
from pathlib import Path
import queue
import tempfile
from types import SimpleNamespace
import unittest

from civ6_host.runtime.information_store import InformationStore
from civ6_host.runtime.native.native_stdout_transport import CORE_SHA256, HOST_SHA256
from test_information_store import (PRODUCTION_PIN, GROWTH_PIN, production_event,
                                    growth_event, growth_public, response)


class InformationStreamTests(unittest.TestCase):
    def reader(self):
        path = Path(__file__).resolve().parents[1] / 'src/civ6_host/runtime/native/native_saved_session.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
                   and node.name == 'NativeSavedSession')
        method = next(node for node in cls.body if isinstance(node, ast.FunctionDef)
                      and node.name == '_read_stream')
        module = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
        namespace = {'MAX_LINE': 1024**2, 'json': json, '_resolve_resource_path': lambda p:p}
        exec(compile(module, str(path), 'exec'), namespace)
        return namespace['_read_stream']

    def test_actual_extracted_reader_seals_before_response_is_delivered(self):
        events = [production_event(sequence=0), growth_event(sequence=0)]
        reply = response(sequence=0, growth=growth_public())
        reply['operation'] = 'reset'
        events.append(reply)
        raw = b''.join(json.dumps(e).encode()+b'\n' for e in events)
        failures = []
        with tempfile.TemporaryDirectory() as directory:
            store = InformationStore({'production':PRODUCTION_PIN,'growth':GROWTH_PIN})
            owner = SimpleNamespace(run=Path(directory), event_line_limit_bytes=1024**2,
                stdout_identity=dict(core_sha256=CORE_SHA256, host_sha256=HOST_SHA256),
                stdout_native_records=[],
                _information_store=store, responses=queue.Queue(),
                _fail=lambda *args:failures.append(args))
            self.reader()(owner, io.BytesIO(raw), 'events.jsonl', len(raw)+1, True)
            self.assertEqual(failures, [])
            accepted = owner.responses.get_nowait()
            self.assertEqual(store.read('production', accepted), events[0])
            self.assertEqual(store.read('growth', accepted), events[1])
            self.assertEqual((Path(directory)/'events.jsonl').read_bytes(), raw)

    def test_capture_disabled_preserves_original_response_delivery(self):
        reply = response()
        raw = json.dumps(reply).encode()+b'\n'
        failures = []
        with tempfile.TemporaryDirectory() as directory:
            owner = SimpleNamespace(run=Path(directory), event_line_limit_bytes=1024**2,
                stdout_identity=dict(core_sha256=CORE_SHA256, host_sha256=HOST_SHA256),
                stdout_native_records=[],
                responses=queue.Queue(), _fail=lambda *args:failures.append(args))
            self.reader()(owner, io.BytesIO(raw), 'events.jsonl', len(raw)+1, True)
            self.assertEqual(failures, [])
            self.assertEqual(owner.responses.get_nowait(), reply)


if __name__ == '__main__':
    unittest.main()
