"""Real installed PE source correspondence plus substituted registry memory."""
import hashlib
import struct
import unittest

import pefile

from civ6_host.runtime import xp2_statement_factory as factory
from civ6_host.runtime import xp2_statement_source as statement
from civ6_host.runtime.execution_images import known_path, select

PROFILE_ID = "xp2-gamecore-current-092abfbb"
IMAGE = select(PROFILE_ID, core_path=known_path(PROFILE_ID))
BASE = 0x180000000
BUCKETS = 0x200000000
NODE = BUCKETS + 0x1000
OTHER = NODE + 0x1000


class Memory:
    def __init__(self, image):
        self.image = bytearray(image)
        self.blocks = {
            BASE+0xb635c0: struct.pack("<Q", BUCKETS),
            BASE+0xb635c8: struct.pack("<I", 7),
            BUCKETS+7*8: struct.pack("<Q", 0),
            BUCKETS+(factory.REQUEST_HASH % 7)*8: struct.pack("<Q", NODE),
            NODE: struct.pack("<I", factory.REQUEST_HASH),
            NODE+8: struct.pack("<Q", BASE+factory.FACTORY_RVA),
            NODE+16: struct.pack("<Q", 0),
        }
        self.reads = []

    def read(self, pointer, size):
        self.reads.append((pointer, size))
        if pointer in self.blocks:
            return self.blocks[pointer][:size]
        offset = pointer-BASE
        if 0 <= offset <= len(self.image)-size:
            return bytes(self.image[offset:offset+size])
        raise ValueError("Unmapped fixture read")


class StatementFactoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = known_path(PROFILE_ID)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != IMAGE.image_sha256:
            raise ValueError("Installed PE changed after profile selection")
        pe = pefile.PE(data=raw)
        cls.image = pe.get_memory_mapped_image()
        pe.close()

    def verify(self, memory, **kwargs):
        return factory.verify_request(BASE, memory.read, execution_image=IMAGE, **kwargs)

    def test_independent_pe_matches_registry_factory_and_both_virtual_targets(self):
        memory = Memory(self.image)
        result = self.verify(memory)
        self.assertTrue(result["registry_entry_verified"])
        self.assertFalse(result["native_factory_invoked"])
        self.assertFalse(result["native_memory_modified"])
        self.assertFalse(result["gameplay_effect_verified"])
        self.assertEqual(result["start_virtual_rva"], "0x189db0")
        self.assertEqual(result["field_builder_virtual_rva"], "0x189950")
        self.assertEqual(len(factory.source(execution_image=IMAGE)["bindings"]), 21)

    def test_chained_bucket_follows_native_next_pointer(self):
        memory = Memory(self.image)
        memory.blocks[NODE] = struct.pack("<I", 123)
        memory.blocks[NODE+16] = struct.pack("<Q", OTHER)
        memory.blocks[OTHER] = struct.pack("<I", factory.REQUEST_HASH)
        memory.blocks[OTHER+8] = struct.pack("<Q", BASE+factory.FACTORY_RVA)
        self.assertTrue(self.verify(memory)["registry_entry_verified"])

    def test_changed_constructor_or_virtual_pointer_is_refused(self):
        for offset in (factory.FACTORY_RVA, factory.VTABLE_RVA+0x10,
                       factory.VTABLE_RVA+0x28):
            with self.subTest(offset=offset):
                memory = Memory(self.image)
                memory.image[offset] ^= 1
                with self.assertRaisesRegex(ValueError, "code changed|virtual targets changed"):
                    self.verify(memory)

    def test_missing_registry_cyclic_bucket_and_foreign_factory_are_refused(self):
        for change, message in (
            ({NODE: struct.pack("<I", 123)}, "not registered"),
            ({NODE: struct.pack("<I", 123), NODE+16: struct.pack("<Q", NODE)}, "Cyclic"),
            ({NODE+8: struct.pack("<Q", BASE+factory.FACTORY_RVA+16)}, "differs"),
            ({BASE+0xb635c8: struct.pack("<I", 0)}, "Uninitialized"),
            ({BASE+0xb635c8: struct.pack("<I", factory.MAX_BUCKETS+1)}, "unbounded"),
            ({BASE+0xb635c0: struct.pack("<Q", 7)}, "pointer"),
            ({NODE: b"\0"}, "Short"),
        ):
            with self.subTest(message=message):
                memory = Memory(self.image)
                memory.blocks.update(change)
                with self.assertRaisesRegex(ValueError, message):
                    self.verify(memory)

    def test_another_statement_is_refused_before_memory_access(self):
        memory = Memory(self.image)
        with self.assertRaisesRegex(ValueError, "Unqualified statement"):
            self.verify(memory, request_name="MAKE_DEAL")
        self.assertEqual(memory.reads, [])

    def test_missing_or_forged_execution_image_cannot_admit_factory(self):
        for image in (None, object()):
            with self.subTest(image=image), self.assertRaises((TypeError, ValueError)):
                factory.verify_request(BASE, Memory(self.image).read, execution_image=image)

    def test_factory_proof_is_part_of_existing_statement_dependency_closure(self):
        pins = statement.source_dependencies(execution_image=IMAGE)
        factory_pins = factory.source_dependencies(execution_image=IMAGE)
        self.assertTrue(factory_pins.items() <= pins.items())


if __name__ == "__main__":
    unittest.main()
