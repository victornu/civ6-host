"""Re-pinned park-designation native descriptor for the 4de40abf XP2 image.

Static re-derivation only: `rea-civ6/evidence/designate_park-rea.md` §2.1-2.6 and
`designate_park-rea.json` (DP-02…DP-12). The expected values here are the derived
ones for image `4de40abf…`; the staged `324c51e9` numbers (resolver `0x668810` with
95 B, constructor `0x668950`, vtable `0xa29110`) must stay refused.
"""

from unittest import TestCase
from unittest.mock import patch

from civ6_host.runtime import xp2_designate_park as parks
from civ6_host.runtime.execution_images import _PROFILE


EXPECTED_SLOTS = (
    (0xA290B0, 0x668C30), (0xA290B8, 0x683310), (0xA290C0, 0x668600), (0xA290C8, 0x9B10A0),
    (0xA290D0, 0x3FA100), (0xA290D8, 0x6648D0), (0xA290E0, 0x3FA100), (0xA290E8, 0x9B10A0),
    (0xA290F0, 0x668A10), (0xA290F8, 0x3FA100))
EXPECTED_SPANS = (
    (0x668850, 314, 'b53124b6ec9fac6ef896497ac814a8e9ba2268917e07c04273ae7093ef89a38f'),
    (0x668990, 122, 'd80322a55e8f6710ae2562a1d89c59d85287eeccb28f2f8789f78e6756a55448'))
STAGED_SLOTS = (  # the 324c51e9 table the staged artefact pinned
    (0xA29110, 0x668BF0), (0xA29118, 0x6832D0), (0xA29120, 0x6685C0), (0xA29128, 0x9B1280),
    (0xA29130, 0x3FA0E0), (0xA29138, 0x664810), (0xA29140, 0x3FA0E0), (0xA29148, 0x9B1280),
    (0xA29150, 0x668990), (0xA29158, 0x3FA0E0))
STAGED_SPANS = (  # a 95-byte .pdata fragment that never covered the resolver
    (0x668810, 95, '2f93123773c4d112d50780791720f7b5626a0a73870d2686432dcd9ee5709e3a'),
    (0x668950, 122, '69aca877641a6af90961367a3b1193d8239ba16ac6bb010971be13d8ef9f0055'))


def proof(slots=EXPECTED_SLOTS, spans=EXPECTED_SPANS, **overrides):
    value = dict(schema='civ6-host.xp2-designate-park.source.v1',
                 image_sha256=_PROFILE.image_sha256, operation=1031611255,
                 parameterless_unit_panel=True,
                 plot_getters=dict(path=parks.expansion_national_parks.SOURCE[0],
                                   sha256=parks.expansion_national_parks.SOURCE[1]),
                 slots=[list(pair) for pair in slots],
                 spans=[dict(rva=rva, bytes=size, sha256=digest) for rva, size, digest in spans])
    value.update(overrides)
    return value


class RepinTests(TestCase):
    def test_rederived_constants_are_the_4de40abf_ones(self):
        self.assertEqual(parks.OPERATION, 0x3D7D2377)
        self.assertEqual((parks.RESOLVER_RVA, parks.RESOLVER_BYTES, parks.RESOLVER_SHA256),
                         EXPECTED_SPANS[0])
        self.assertEqual((parks.CONSTRUCTOR_RVA, parks.CONSTRUCTOR_BYTES, parks.CONSTRUCTOR_SHA256),
                         EXPECTED_SPANS[1])
        self.assertEqual((parks.RESOLVER_OPERATION_SITE, parks.CONSTRUCTOR_OPERATION_SITE),
                         (0x668871, 0x6689DA))
        self.assertEqual((parks.RESOLVER_CALLER_SITE, parks.CONSTRUCTOR_CALLER_SITE),
                         (0x4BEF6B, 0x750A17))
        self.assertEqual(parks.DESCRIPTOR_VTABLE, 0xA290B0)
        self.assertEqual(parks.FAMILY_STRING_RVA, 0xA29170)
        self.assertEqual(parks.SLOTS, EXPECTED_SLOTS)
        self.assertEqual(parks.SPANS, tuple(dict(rva=rva, bytes=size, sha256=digest)
                                            for rva, size, digest in EXPECTED_SPANS))

    def test_rederived_descriptor_is_admitted(self):
        with patch.object(parks, '_source', return_value=proof()):
            self.assertEqual(parks._proof(_PROFILE)['operation'], 0x3D7D2377)

    def test_staged_vtable_and_resolver_fragment_are_refused(self):
        for slots, spans in ((STAGED_SLOTS, EXPECTED_SPANS), (EXPECTED_SLOTS, STAGED_SPANS),
                             (STAGED_SLOTS, STAGED_SPANS),
                             (EXPECTED_SLOTS[:9], EXPECTED_SPANS),
                             (EXPECTED_SLOTS, EXPECTED_SPANS[:1])):
            with self.subTest(slots=slots[0][0], spans=spans[0][0]):
                with patch.object(parks, '_source', return_value=proof(slots, spans)):
                    with self.assertRaisesRegex(ValueError, 're-derived spans and slots'):
                        parks._proof(_PROFILE)

    def test_rekeyed_schema_rows_are_still_enforced(self):
        for row in (dict(operation=0x3D7D2376), dict(parameterless_unit_panel=False),
                    dict(image_sha256='0' * 64)):
            with self.subTest(row=row):
                with patch.object(parks, '_source', return_value=proof(**row)):
                    with self.assertRaisesRegex(ValueError, 'exact installed Gathering Storm source'):
                        parks._proof(_PROFILE)

    def test_absent_capture_and_ui_rows_stay_fail_closed(self):
        from civ6_host.runtime.xp2_bbg_inputs import REFERENCE as bbg
        with patch.object(parks, '_source', return_value=proof()):
            with self.assertRaises(KeyError):
                parks.source_dependencies(bbg, _PROFILE)
