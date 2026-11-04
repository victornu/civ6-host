"""Parameterize shared post160 dispatch after existing path/import rewriting.

Integration adds this helper to extract_runtime; that pending file is not part
of this patch. The existing sequence and cache/ownership checks are preserved.
"""

BASE = 'd7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
CHANGES = {
    'civ6rl.native_checkpoint_postload160': (
        ('from civ6_host.runtime.native import native_checkpoint_postload_facades as facades',
         'from civ6_host.runtime.native import native_checkpoint_postload_facades as facades\n'
         'from civ6_host.runtime.postload160_source import profile_for_sha, require_runtime_admission'),
        ('def verify_source():',
         f"def verify_source(*, core_sha256='{BASE}'):\n"
         f"    if core_sha256 != '{BASE}':\n"
         '        from civ6_host.runtime.postload160_source import xp1_source\n'
         '        return xp1_source(core_sha256)'),
        ('def check_live_post160(base, read, proof):',
         f"def check_live_post160(base, read, proof, *, core_sha256='{BASE}'):\n"
         f"    if core_sha256 != '{BASE}':\n"
         '        from civ6_host.runtime.postload160_source import verify_xp1_live\n'
         '        return verify_xp1_live(base, read, proof, core_sha256=core_sha256)'),
        ('        load.validate_inputs(inputs)',
         '        self.post160_abi = require_runtime_admission(profile_for_sha(owner.load_abi.core_sha256))\n'
         '        load.validate_inputs(inputs)'),
        ('        self.proof = verify_source()',
         '        self.proof = verify_source(core_sha256=self.post160_abi.core_sha256)'),
        ('        check_live_post160(b.core._handle, b.runtime.read, self.proof)',
         '        check_live_post160(b.core._handle, b.runtime.read, self.proof, core_sha256=self.post160_abi.core_sha256)'),
        ('        if self.native_call_attempted or not b.busy or self._facade_attempt is None:',
         '        require_runtime_admission(self.post160_abi)\n'
         '        if self.native_call_attempted or not b.busy or self._facade_attempt is None:'),
        ('C.WINFUNCTYPE(None, C.c_void_p, C.c_uint8)(b.core._handle + POST160_RVA)(b.context, 1)',
         'C.WINFUNCTYPE(None, C.c_void_p, C.c_uint8)(b.core._handle + self.post160_abi.target_rva)(b.context, 1)'),
    ),
    'civ6rl.native_official_postload': (
        ('        self.proof = post160.verify_source()',
         '        self.post160_abi = post160.require_runtime_admission(post160.profile_for_sha(owner.load_abi.core_sha256))\n'
         '        self.proof = post160.verify_source(core_sha256=self.post160_abi.core_sha256)'),
        ('        post160.check_live_post160(b.core._handle, b.runtime.read, self.proof)',
         '        post160.check_live_post160(b.core._handle, b.runtime.read, self.proof, core_sha256=self.post160_abi.core_sha256)'),
    ),
}


def parameterize(name, raw):
    for before, after in CHANGES.get(name, ()):
        expected = 2 if before == '        check_live_post160(b.core._handle, b.runtime.read, self.proof)' else 1
        if raw.count(before) != expected:
            raise ValueError('Post160 extraction boundary changed: ' + before[:100])
        raw = raw.replace(before, after)
    return raw
