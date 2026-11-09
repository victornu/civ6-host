"""Current Congress null-service route on existing real owner/FIFO fixtures."""
import ctypes as C
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve()
STAGED=HERE.parents[2].name=='congress-achievement-staging'
if STAGED:
    STAGE=HERE.parents[2];LAB=STAGE.parents[2];HOST=LAB.parent/'civ6-host'
else:
    HOST=HERE.parents[1];LAB=Path(os.environ['CIV6_HOST_RESOURCE_ROOT'])
sys.path[:0]=[str(HOST/'src'),str(HOST/'tests'),str(HOST/'tools')]
import civ6_host.runtime
if STAGED:civ6_host.runtime.__path__.insert(0,str(STAGE/'files/src/civ6_host/runtime'))
from civ6_host.runtime import xp2_host_slot20_source as source
from civ6_host.runtime import xp2_host_achievement_service as service
from civ6_host.runtime import xp1_session_inputs as inputs
from civ6_host.runtime.configuration_profiles import XP2_CORE_SHA256
from civ6_host.runtime.execution_images import select,known_path
from civ6_host.runtime.native import native_action_transport as calls
import test_xp2_turn_services as owners
import test_xp2_host_slot20_source as legacy


def image():
    name='xp2-gamecore-current-092abfbb'
    return select(name,core_path=known_path(name))


def frames():
    return [dict(module=source.CORE_MODULE,rva=r) for r in source.CONGRESS_PREFIX]


def memory():
    result=legacy.proof_memory()
    proof=source.congress_source(image())
    for body in proof['bodies'].values():
        for part in body.get('fragments',()) or (body,):
            at=legacy.BASE+int(part.get('start_rva',body.get('start_rva')),16)
            result.update((at+i,b) for i,b in enumerate(bytes.fromhex(part['raw_hex'])))
    for row in proof['data']:
        at=legacy.BASE+int(row['rva'],16)
        raw=((legacy.BASE+int(row['target_rva'],16)).to_bytes(8,'little')
             if 'target_rva' in row else bytes.fromhex(row['raw_hex']))
        result.update((at+i,b) for i,b in enumerate(raw))
    return result


class CongressAchievementServiceTests(unittest.TestCase):
    def fixture(self):
        f=owners.Fixture();self.addCleanup(f.close)
        f.backend._xp1_commands_requested=True
        f.memory.bytes.update(memory())
        f.memory.put(f.memory.base+source.HOST_GLOBAL_RVA,struct.pack('<Q',f.host.pointer))
        f.host.achievement_service_installed=False
        f.host._bind(f.host.vtable,0x20,C.c_void_p,[C.c_void_p],f.host._unsupported('host',0x20))
        return f

    def test_current_proof_transitive_dependencies_and_historical_route_separation(self):
        proof=source.congress_source(image())
        self.assertEqual(tuple(proof['contract']['accepted_core_return_prefix']),source.CONGRESS_PREFIX)
        old=source.source_dependencies()
        self.assertNotIn(source.CONGRESS_SOURCE[1],old.values())
        pins=inputs.command_source_dependencies(XP2_CORE_SHA256,execution_image=image())
        self.assertIn(source.CONGRESS_SOURCE[1],pins.values())
        self.assertEqual(pins[str(Path(image().path).resolve())],image().image_sha256)
        for path,digest in source.source_dependencies(execution_image=image()).items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(),digest)

    def test_exact_current_prefix_refuses_neighbor_unknown_image_and_installed_sink(self):
        self.assertEqual(source.select_contract(frames(),execution_image=image()),source.CONGRESS_SOURCE[1])
        for bad in (frames()[:-1],frames()[:3]+[dict(module=source.CORE_MODULE,rva='0x1cf7ef')],
                    frames()[:3]+[dict(module=source.CORE_MODULE,rva='0x3bf935')]):
            with self.assertRaisesRegex(ValueError,'Unproved'):
                source.select_contract(bad,execution_image=image())
        with self.assertRaises(ValueError):source.select_contract(frames())
        with self.assertRaises(ValueError):source.select_contract(frames(),execution_image=replace(image()))
        with self.assertRaises(ValueError):source.select_contract(frames(),execution_image=image(),service_installed=True)
        legacy_frames=[dict(module=source.CORE_MODULE,rva=r) for r in source.ACCEPTED_CORE_RETURN_PREFIX]
        self.assertEqual(source.select_contract(legacy_frames),source.SOURCE[1])

    def test_current_live_guards_cover_full_consumer_tail_delegate_and_owner(self):
        data=memory();read=legacy.reader_for(data)
        receipt=source.verify_live(legacy.BASE,read,host_pointer=legacy.HOST,execution_image=image())
        self.assertEqual(receipt['congress_source_sha256'],source.CONGRESS_SOURCE[1])
        self.assertEqual(receipt['execution_image_sha256'],image().image_sha256)
        for rva in (0x17cdc1,0x3bc6b6,0x3bf934,0x3bfb30,0x17fac7,0x16bd00,
                    0x17ec73,0x9d0678,0x9d12f0):
            with self.subTest(rva=hex(rva)):
                data[legacy.BASE+rva]^=1
                with self.assertRaises(ValueError):
                    source.verify_live(legacy.BASE,read,host_pointer=legacy.HOST,execution_image=image())
                data[legacy.BASE+rva]^=1
        with self.assertRaises(ValueError):
            source.verify_live(legacy.BASE,read,host_pointer=legacy.HOST+8,execution_image=image())

    def test_existing_owner_fifo_calls_only_null_sink_and_preserves_queue_delivery(self):
        f=self.fixture();b=f.backend
        f.stack.enter_context(patch('civ6_host.runtime.native.native_absent_achievements.capture_stack',
                                    return_value=frames()))
        before=dict(f.host._slot_bindings)
        receipt=service.install(b) # Real prepared-owner, source, and live guards.
        changed={k for k,v in f.host._slot_bindings.items() if before.get(k)!=v}
        self.assertEqual(changed,{(C.addressof(f.host.vtable),0x20)})
        self.assertEqual(receipt['source_verification']['congress_source_sha256'],source.CONGRESS_SOURCE[1])
        callback=b._xp2_host20[1]
        transport=f.install();transport.request_end_turn(0,player_ids=(0,))
        payload=transport.pending[0];original=f.memory.virtual;seen=[]
        def virtual(core,ptr,slot,rva,result,*args):
            native=original(core,ptr,slot,rva,result,*args)
            if rva==transport.transport_abi.drain_rva:
                def drain(context):
                    self.assertNotEqual(int.from_bytes(f.memory.read(f.memory.sentinel,8),'little'),f.memory.sentinel)
                    self.assertIsNone(callback(f.host.pointer));seen.append('null')
                    return native(context)
                return drain
            return native
        with patch('civ6_host.runtime.native.native_absent_achievements.capture_stack',return_value=frames()), \
                patch.object(calls,'virtual',side_effect=virtual):
            calls.NativeActionTransport.deliver_one(transport)
        self.assertEqual(seen,['null']);self.assertEqual(transport.pending,[])
        transport.require_empty_native_queue()
        event=next(e for e in f.events if e['stage']=='native_optional_achievement_service_absent')
        self.assertEqual(event['source_proof_sha256'],source.CONGRESS_SOURCE[1])
        self.assertEqual(event['execution_image_sha256'],image().image_sha256)
        for flag in ('platform_service_installed','platform_request_submitted','platform_success_reported'):
            self.assertIs(event[flag],False)
        delivered=[e for e in f.events if e['stage']=='native_command_received_in_core_queue']
        self.assertEqual(delivered[-1]['archive_hex'],payload.hex())
        original_image=b.core._civ6_host_execution_image
        b.core._civ6_host_execution_image=replace(original_image)
        with patch('civ6_host.runtime.native.native_absent_achievements.capture_stack',return_value=frames()):
            with self.assertRaisesRegex(ValueError,'owner changed'):callback(f.host.pointer)
        b.core._civ6_host_execution_image=original_image
        f.host.achievement_service_installed=True
        with self.assertRaisesRegex(ValueError,'owner changed'):callback(f.host.pointer)


if __name__=='__main__':unittest.main()
