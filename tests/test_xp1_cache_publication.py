"""Shared publication routing on retained native-layout fixtures; no DLL run."""
import ctypes as C
import importlib.util
from pathlib import Path
import sys,types,unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock,patch
from civ6_host.runtime.configuration_profiles import BASE_CORE_SHA256,XP1_CORE_SHA256
from civ6_host.runtime.loaded_cache_profiles import loaded_cache_abi
import test_loaded_cache_publication as cache_fixtures
import test_xp1_postload_candidate as post_fixtures

from civ6_host.runtime import xp1_cache_publication as candidate
from civ6_host.runtime.native import native_player_view as view

class PublicationTests(unittest.TestCase):
 def fixture(self,base=False):
  f,a,facades=cache_fixtures.LoadedCacheTests().fixture();a=loaded_cache_abi(BASE_CORE_SHA256 if base else XP1_CORE_SHA256)
  # The same publishing method uses each engine's actual member offsets/targets.
  f.q(f.owner,a.cache_owner_vtable_rva+f.core_base);f.q(f.owner+a.map_view_offset,f.member);f.q(f.member,a.map_view_vtable_rva+f.core_base)
  buffers={};actual=C.create_string_buffer
  def buffer(*args):
   value=actual(*args);buffers[C.addressof(value)]=value;return value
  def read(address,size):return C.string_at(address,size) if address in buffers else f.read(address,size)
  p=view.NativePlayerViewPublisher(NS(_handle=f.core_base),f.outer,Mock(),read=read,core_sha256=a.core_sha256)
  p._validate=Mock(return_value=(f.service,f.game))
  p._facades=facades;calls=[]
  def virtual(core,receiver,slot,target,restype,*argtypes):
   calls.append((slot,target,restype,argtypes))
   if slot==0x80:return lambda receiver:f.owner
   return Mock(return_value=None)
  return f,a,p,calls,buffer,virtual

 def test_base_targets_unchanged_and_void_publication(self):
  f,a,p,calls,buffer,virtual=self.fixture(base=True)
  with patch.object(view.C,'create_string_buffer',side_effect=buffer),patch.object(view,'virtual',side_effect=virtual):
   self.assertEqual(p.publish(),(74,46,3404))
  self.assertEqual([(r[0],r[1]) for r in calls],[(8,0x85a0),(0x80,0x7339c0),(0x190,0x42f660)])
  self.assertIsNone(calls[-1][2]);self.assertEqual(calls[-1][3],(C.c_void_p,C.c_uint8))

 def test_xp1_uses_only_its_profile_and_retains_closed_public_gates(self):
  f,a,p,calls,buffer,virtual=self.fixture();owner=object()
  with patch.object(view.C,'create_string_buffer',side_effect=buffer),patch.object(view,'virtual',side_effect=virtual), \
       patch.object(candidate,'validate_publisher',return_value=0x4be760) as validate, \
       patch.object(candidate,'before_native') as before,patch.object(candidate,'after_native') as after:
   self.assertEqual(p.publish(publication_owner=owner),(74,46,3404))
   validate.assert_called_once_with(p,owner);before.assert_called_once_with(p,owner);after.assert_called_once_with(p,owner,(74,46,3404))
  self.assertEqual([(r[0],r[1]) for r in calls],[(8,0x9750),(0x80,0x94c0),(0x190,0x4be760)])
  self.assertFalse(p.native_cache_gate);self.assertFalse(p.full_facade_initialization_reproduced)

 def test_xp1_without_owner_fails_before_any_native_call(self):
  f,a,p,calls,buffer,virtual=self.fixture()
  with patch.object(view,'virtual',side_effect=virtual):
   with self.assertRaisesRegex(ValueError,'exact private saved owner'):p.publish()
  self.assertEqual(calls,[])

 def test_missing_xp1_visibility_never_enters_base_initializer(self):
  f,a,p,calls,buffer,virtual=self.fixture();f.q(f.owner+0x58,0);f.put(f.owner+0x38,b'\0')
  with patch.object(view,'virtual',side_effect=virtual),patch.object(candidate,'validate_publisher',return_value=0x4be760):
   with self.assertRaisesRegex(ValueError,'populated visibility'):p.publish(publication_owner=object())
  self.assertEqual(len(calls),2);self.assertFalse(p.full_facade_initialization_reproduced)

 def test_live_sources_reject_tampered_kind4_instruction(self):
  p=candidate.source();memory={};base=0x180000000
  for name in ('outer190','service_factory','game_getter','kind4_refresh'):
   for frag in candidate._body(p['functions'][name])['fragments']:
    for i in frag['instructions']:
     memory.update((int(i['va'],16)+n,v) for n,v in enumerate(bytes.fromhex(i['bytes'])))
  for r in p['slots'][:2]:memory.update((base+r['vtable_rva']+r['slot']+n,v) for n,v in enumerate((base+r['target_rva']).to_bytes(8,'little')))
  b=NS(core=NS(_handle=base),runtime=NS(read=lambda a,n:bytes(memory[a+i] for i in range(n))),
       load_abi=NS(core_sha256=XP1_CORE_SHA256))
  with patch.object(candidate,'verify_xp1_live'):
   candidate.verify_live(b);memory[base+0x80e30]^=1
   with self.assertRaisesRegex(ValueError,'kind4_refresh'):candidate.verify_live(b)

class PublicationOwnershipTests(unittest.TestCase):
 def graph(self):
  b,a,lease,post=post_fixtures.Post160CandidateTests().graph()
  b.stage=candidate.FINISHED_STAGE;b.busy=False
  lease.post160_attempt=post;lease.post160_finished=True
  post.attempted=post.native_call_attempted=True;post.candidate_diagnostics={'void_return_ignored':True}
  a.publisher._facades=object()
  return b,a,lease,post

 def test_exact_completed_postload_and_single_owner(self):
  b,a,lease,post=self.graph();lease.post160_finished=False
  with self.assertRaisesRegex(ValueError,'finished postload'):candidate.SavedCachePublication(post)
  self.assertFalse(hasattr(b,'_xp1_publication_attempt'))
  lease.post160_finished=True;attempt=candidate.SavedCachePublication(post)
  self.assertIs(attempt.lease,lease);self.assertIs(attempt.facades,a.publisher._facades)
  with self.assertRaisesRegex(ValueError,'finished postload'):candidate.SavedCachePublication(post)
  with self.assertRaisesRegex(ValueError,'exact private'):candidate.validate_publisher(a.publisher,object())

 def test_native_return_cannot_be_fabricated_repeated_or_change_dimensions(self):
  b,a,lease,post=self.graph();attempt=candidate.SavedCachePublication(post);attempt.check_active=Mock()
  with self.assertRaisesRegex(ValueError,'out of order'):candidate.after_native(a.publisher,attempt,(74,46,3404))
  candidate.before_native(a.publisher,attempt)
  with self.assertRaisesRegex(ValueError,'cannot retry'):candidate.before_native(a.publisher,attempt)
  with self.assertRaisesRegex(ValueError,'dimensions differ'):candidate.after_native(a.publisher,attempt,(75,46,3450))
  self.assertFalse(attempt.native_returned)
  candidate.after_native(a.publisher,attempt,(74,46,3404))
  with self.assertRaisesRegex(ValueError,'out of order'):candidate.after_native(a.publisher,attempt,(74,46,3404))
  self.assertFalse(a.publisher.native_cache_gate);self.assertFalse(a.publisher.full_facade_initialization_reproduced)

if __name__=='__main__':unittest.main(verbosity=2)
