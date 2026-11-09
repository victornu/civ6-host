"""Static source and live-byte guards for the narrow XP2 host+20 route."""
import hashlib
import os
from pathlib import Path
import unittest

HOST_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("CIV6_HOST_RESOURCE_ROOT", str(HOST_ROOT.parent / "civ6-rl-lab"))

from civ6_host.runtime import xp2_host_slot20_source as source
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256


BASE = 0x180000000
HOST = 0x12345678
MODULE = source.CORE_MODULE


def admitted_frames():
    return [dict(module=MODULE, rva=rva) for rva in source.ACCEPTED_CORE_RETURN_PREFIX]


def proof_memory():
    proof = source.source()
    native02 = source.native02_source()
    memory = {}
    formation = source.formation_source()
    era = source.era_transition_source()
    raf30 = source.raf30_source()
    city_listener = source.city_listener_source()
    for body in (*proof["bodies"].values(), *native02["bodies"].values(), *formation["bodies"].values(),
                 *era["bodies"].values(), *raf30["bodies"].values(), *city_listener["bodies"].values()):
        for fragment in body.get("fragments", ()) or (body,):
            raw = bytes.fromhex(fragment["raw_hex"])
            start = BASE + int(fragment.get("start_rva", body.get("start_rva")), 16)
            for offset, value in enumerate(raw):
                address = start + offset
                previous = memory.setdefault(address, value)
                if previous != value:
                    raise AssertionError("captured bodies disagree at overlapping bytes")
    for offset, value in enumerate(HOST.to_bytes(8, "little")):
        memory[BASE + source.HOST_GLOBAL_RVA + offset] = value
    for offset, value in enumerate(b"NEW_ACHIEVEMENT_4_13\0"):
        memory[BASE + 0x9ceee0 + offset] = value
    for offset, value in enumerate((BASE + 0x17fa50).to_bytes(8, "little")):
        memory[BASE + 0x9d1020 + offset] = value
    for offset, value in enumerate(b"NEW_ACHIEVEMENT_4_20\0"):
        memory[BASE + 0x9ceb28 + offset] = value
    for offset, value in enumerate(b"RAF_ACHIEVEMENT_30\0"):
        memory[BASE + 0x9d0288 + offset] = value
    for offset, value in enumerate(b"NEW_ACHIEVEMENT_4_14\0"):
        memory[BASE + 0x9cee08 + offset] = value
    return memory


def reader_for(memory):
    def read(address, size):
        try:
            return bytes(memory[address + offset] for offset in range(size))
        except KeyError:
            return b""
    return read


class XP2HostSlot20SourceTests(unittest.TestCase):
    def test_source_profile_and_dependency_pins_are_exact(self):
        proof = source.source()
        self.assertEqual(proof["images"]["xp2"]["sha256"], XP2_CORE_SHA256)
        self.assertEqual(tuple(proof["contract"]["accepted_core_return_prefix"]),
                         source.ACCEPTED_CORE_RETURN_PREFIX)
        self.assertEqual(proof["contract"]["other_propagated_or_consumed_callers_admitted"], False)
        pins = source.source_dependencies()
        profile = source._path(source.SOURCE[0]).resolve()
        self.assertEqual(pins[str(profile)], source.SOURCE[1])
        supplement = source._path(source.FORMATION_SOURCE[0]).resolve()
        self.assertEqual(pins[str(supplement)], source.FORMATION_SOURCE[1])
        self.assertIn(str(Path(source.__file__).resolve()), pins)
        native02_profile = source._path(source.NATIVE02_SOURCE[0]).resolve()
        self.assertEqual(pins[str(native02_profile)], source.NATIVE02_SOURCE[1])
        for path, digest in pins.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), digest)

    def test_live_bytes_and_host_global_join(self):
        memory = proof_memory()
        receipt = source.verify_live(BASE, reader_for(memory), host_pointer=HOST)
        self.assertEqual(receipt["source_sha256"], source.SOURCE[1])
        self.assertEqual(receipt["native02_source_sha256"], source.NATIVE02_SOURCE[1])
        self.assertEqual(receipt["core_sha256"], XP2_CORE_SHA256)
        self.assertEqual(receipt["formation_source_sha256"], source.FORMATION_SOURCE[1])
        for rva in (0x17fa92, 0x226ed1, 0x1a33a0, 0x65a217, 0x408fc, 0x9ceee0, 0x9d1020, 0x177732, 0xda760, 0x284c48, 0x9ceb28, 0x17ad17, 0x285ab9, 0x9d0288, 0x178ecb, 0x9cee08):
            changed = dict(memory)
            changed[BASE + rva] ^= 1
            with self.subTest(rva=hex(rva)), self.assertRaises(ValueError):
                source.verify_live(BASE, reader_for(changed), host_pointer=HOST)
        self.assertGreater(receipt["verified_bytes"], 0)
        self.assertGreater(receipt["verified_spans"], 0)

        damaged = dict(memory)
        first = next(iter(source.source()["bodies"]["method_17b190"]["fragments"]))
        address = BASE + int(first["start_rva"], 16)
        damaged[address] ^= 1
        with self.assertRaises(ValueError):
            source.verify_live(BASE, reader_for(damaged), host_pointer=HOST)
        with self.assertRaises(ValueError):
            source.verify_live(BASE, reader_for(memory), host_pointer=HOST + 8)
        with self.assertRaises(ValueError):
            source.verify_live(BASE, lambda address, size: b"\0", host_pointer=HOST)

    def test_era_transition_admits_only_the_captured_return_chain(self):
        frames = [dict(module=MODULE, rva=rva) for rva in source.ERA_TRANSITION_PREFIX]
        self.assertEqual(source.select_contract(frames), source.ERA_TRANSITION_SOURCE[1])
        with self.assertRaises(ValueError):
            source.select_contract(frames[:-1])
        frames[-1]["rva"] = "0x284c4e"
        with self.assertRaises(ValueError):
            source.select_contract(frames)

    def test_raf30_admits_only_the_captured_return_chain(self):
        frames = [dict(module=MODULE, rva=rva) for rva in source.RAF30_PREFIX]
        self.assertEqual(source.select_contract(frames), source.RAF30_SOURCE[1])
        frames[-1]["rva"] = source.ERA_TRANSITION_PREFIX[-1]
        with self.assertRaises(ValueError):
            source.select_contract(frames)

    def test_city_listener_admits_only_the_captured_return_chain(self):
        frames = [dict(module=MODULE, rva=rva) for rva in source.CITY_LISTENER_PREFIX]
        self.assertEqual(source.select_contract(frames), source.CITY_LISTENER_SOURCE[1])
        with self.assertRaises(ValueError):
            source.select_contract(frames[:-1])

    def test_native02_admits_only_the_source_proved_null_ignored_callback_prefix(self):
        proof = source.native02_source()
        frames = [dict(module=MODULE, rva=rva)
                  for rva in proof["contract"]["observed_core_return_chain"]]
        self.assertEqual(source.select_contract(frames), source.NATIVE02_SOURCE[1])
        # Outer producer frames vary; the exact callback and its result-ignoring receiver do not.
        frames[3]["rva"] = "0x2eabdf"
        self.assertEqual(source.select_contract(frames), source.NATIVE02_SOURCE[1])
        for changed in (frames[:2], [dict(module=MODULE, rva="0x17f098"),
                                     dict(module=MODULE, rva="0x17feda"),
                                     dict(module=MODULE, rva="0x2e9e8d")],
                        [dict(module=MODULE, rva="0x17f098"),
                         dict(module=MODULE, rva="0x17b387"),
                         dict(module=MODULE, rva="0x2e9e8c")]):
            with self.subTest(frames=changed), self.assertRaises(ValueError):
                source.select_contract(changed)
        with self.assertRaisesRegex(ValueError, "uninstalled"):
            source.select_contract(frames, service_installed=True)

    def test_only_exact_four_frame_return_chain_is_selected(self):
        self.assertEqual(source.select_contract(admitted_frames(), service_installed=False),
                         source.SOURCE[1])
        invalid = [
            admitted_frames()[:3],
            [dict(module=MODULE, rva="0x17f098"),
             dict(module=MODULE, rva="0x17b386"), *admitted_frames()[2:]],
            [*admitted_frames()[:3], dict(module="GameCore_XP1_FinalRelease.dll",
                                          rva="0x24025b")],
            [admitted_frames()[1], admitted_frames()[0], *admitted_frames()[2:]],
            [*admitted_frames()[:3], dict(module=MODULE, rva="0x24025a")],
        ]
        for frames in invalid:
            with self.subTest(frames=frames), self.assertRaises(ValueError):
                source.select_contract(frames, service_installed=False)
        with self.assertRaises(ValueError):
            source.select_contract(admitted_frames(), service_installed=True)
        with self.assertRaises(ValueError):
            source.select_contract([dict(module=MODULE, rva="0x17F098")
                                    for _ in range(4)], service_installed=False)

    def test_only_exact_formation_prefix_is_selected(self):
        frames = [dict(module=MODULE,rva=rva) for rva in
                  ("0x17f098","0x17fa97","0x226ed4","0x1a33a5","0x65a217","0x3ed9e")]
        self.assertEqual(source.select_contract(frames),source.FORMATION_SOURCE[1])
        for index in range(5):
            changed = [dict(frame) for frame in frames]
            changed[index]["rva"] = hex(int(changed[index]["rva"],16)-1)
            with self.subTest(index=index), self.assertRaisesRegex(ValueError,"Unproved"):
                source.select_contract(changed)
        with self.assertRaisesRegex(ValueError,"Unproved"):
            source.select_contract(frames[:4])
        with self.assertRaisesRegex(ValueError,"uninstalled"):
            source.select_contract(frames,service_installed=True)


if __name__ == "__main__":
    unittest.main()
