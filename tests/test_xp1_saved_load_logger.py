from pathlib import Path
import ctypes as C
import hashlib, importlib.util, json, sys, unittest
from types import SimpleNamespace
from civ6_host.runtime import xp1_saved_load_logger as m
from civ6_host.runtime.native.native_host import DiagnosticHost
from civ6_host.runtime.native.native_logging import DisabledLogWriters
# Exercise the real immutable source cache, not a mutable JSON substitute.
PROOF=m._checked_source()

def backend():
 h=DiagnosticHost.__new__(DiagnosticHost)
 h.logger_vtable=(C.c_void_p*32)(*range(100,132))
 h.logger_object=(C.c_void_p*2)(C.addressof(h.logger_vtable),1)
 h.log_channels={0xC95E0BC4:{'filename':'GameEffects.log','flags':5,'enabled':1,'level':0xA1B2C3D4}}
 h.log_headers={};h.log_global_enabled=1;h.emit=lambda *a,**kw:None
 h._fatal=lambda *a,**kw:(_ for _ in ()).throw(ValueError(str(a)))
 w=DisabledLogWriters.__new__(DisabledLogWriters);w.host=h;w.active_sink=object();h.log_writers=w
 h._slot_bindings={}
 for slot in m.SLOTS:
  callback=h._unsupported('logger',slot)
  h._slot_bindings[C.addressof(h.logger_vtable),slot]=(h.logger_vtable[slot//8],callback)
 calls=[]
 def bind(table,slot,result,args,callback):
  calls.append((slot,result,args,callback))
  table[slot//8]=1000+slot
  h._slot_bindings[C.addressof(table),slot]=(table[slot//8],callback)
 h._bind=bind
 base=0x100000000
 mem={base+int(r['rva'],16):bytes.fromhex(r['bytes']) for r in PROOF['live_windows'].values()}
 mem[base+0x9F2650]=C.addressof(h.logger_object).to_bytes(8,'little')
 def read(address,size):return mem[address][:size]
 inputs=object()
 b=SimpleNamespace(_saved_load_candidate=True,profile=SimpleNamespace(core_sha256=m.XP1_CORE_SHA256),
    inputs=inputs,captured_bundle=SimpleNamespace(inputs=inputs),stage='prepared',prefix=None,
    game_flag=lambda:0,check_thread=lambda:None,host=h,core=SimpleNamespace(_handle=base),
    runtime=SimpleNamespace(read=read),emit=lambda *a,**kw:None)
 return b,calls,mem
class LoggerActivation(unittest.TestCase):
 def test_retained_proofs_and_implementations(self):
  self.assertEqual(m._checked_source(),PROOF)
 def test_cohesive_group_preserves_registry_and_unknown_slots(self):
  b,calls,_=backend();h=b.host
  state=json.dumps(h.log_channels);unrelated=[h.logger_vtable[i] for i in range(32) if i*8 not in m.SLOTS]
  m.install_saved_load_logger(b)
  self.assertEqual([x[0] for x in calls],list(m.SLOTS))
  self.assertEqual(json.dumps(h.log_channels),state)
  self.assertEqual([h.logger_vtable[i] for i in range(32) if i*8 not in m.SLOTS],unrelated)
  level=next(x for x in calls if x[0]==0x38)
  self.assertIs(level[1],C.c_uint32)
  self.assertEqual(level[3](C.addressof(h.logger_object),0xC95E0BC4),0xA1B2C3D4)
  self.assertEqual(level[3](C.addressof(h.logger_object),123),0)
  self.assertEqual(next(x for x in calls if x[0]==0x50)[3],h.log_writers.lookup)
 def test_repeated_activation_refused(self):
  b,calls,_=backend();m.install_saved_load_logger(b)
  with self.assertRaises(ValueError):m.install_saved_load_logger(b)
  self.assertEqual(len(calls),7)
 def test_owner_guard_mutations_refuse_before_binding(self):
  for field,value in [('_saved_load_candidate',False),('stage','initialized'),('prefix',object()),
                      ('inputs',object()),('game_flag',lambda:1)]:
   with self.subTest(field=field):
    b,calls,_=backend();setattr(b,field,value)
    with self.assertRaises(ValueError):m.install_saved_load_logger(b)
    self.assertEqual(calls,[])
 def test_other_engine_refused(self):
  b,calls,_=backend();b.profile.core_sha256='0'*64
  with self.assertRaises(ValueError):m.install_saved_load_logger(b)
  self.assertEqual(calls,[])
 def test_unknown_override_refused_atomically(self):
  b,calls,_=backend();key=(C.addressof(b.host.logger_vtable),0x50)
  b.host._slot_bindings[key]=(b.host.logger_vtable[10],lambda:None)
  with self.assertRaises(ValueError):m.install_saved_load_logger(b)
  self.assertEqual(calls,[])
 def test_live_caller_and_pointer_mutations_refused(self):
  b,_,mem=backend()
  for address in mem:
   with self.subTest(address=hex(address)):
    b,calls,mem2=backend();old=mem2[address];mem2[address]=bytes([old[0]^1])+old[1:]
    with self.assertRaises(ValueError):m.install_saved_load_logger(b)
    self.assertEqual(calls,[])
 def test_sink_and_callback_identity_required(self):
  for mutation in ('sink','slot','object'):
   with self.subTest(mutation=mutation):
    b,calls,_=backend()
    if mutation=='sink':b.host.log_writers.active_sink=None
    if mutation=='slot':b.host.logger_vtable[7]=3
    if mutation=='object':b.host.logger_object[0]=3
    with self.assertRaises(ValueError):m.install_saved_load_logger(b)
    self.assertEqual(calls,[])
if __name__=='__main__':unittest.main(verbosity=2)
