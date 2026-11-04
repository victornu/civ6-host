"""Join exact XP1/XP2 profiles to shared manifest and captured checkpoint Load.

This transformation changes engine/profile selection only. The original native
Save, bounded streams and fresh saved-Load pipeline stay in their existing owners.
"""
import ast


def change(raw, before, after):
    if raw.count(before) != 1:
        raise ValueError('Session checkpoint extraction anchor changed: '+before[:90])
    return raw.replace(before, after, 1)


def parameterize(name, raw):
    if name == 'civ6rl.native_session_checkpoint':
        raw = change(raw, "        profile = self.inputs.profile\n        manifest = dict(",
            "        profile = self.inputs.profile\n        from civ6_host.runtime.xp1_session_checkpoint import manifest_sources\n        selected_core, selected_sources = manifest_sources(self, reference)\n        manifest = dict(")
        raw = change(raw, 'core_sha256=provider.CORE_SHA256, source_proofs=[reference(stream.PROOF_PATH), reference(ROOT / \'work/native-checkpoint-stream-contract341.json\'), reference(ROOT / \'evidence/native-checkpoint-configuration-stream-v3\' / (provider.PROOF_SHA256 + \'.json\')), reference(jobs.PROOF_PATH)]',
            'core_sha256=selected_core, source_proofs=selected_sources')
        raw = change(raw, "getattr(self.owner, 'explicit_placements', {})",
            "getattr(getattr(self, 'host_state_owner', self.owner), 'explicit_placements', {})")
        raw = change(raw, 'if self.inputs.profile is official.LAN_PROFILE:',
            "if self.inputs.profile.name in ('base-lan-official-capture', 'xp1-lan-official-capture-inputs', 'xp2-lan-official-capture-inputs'):")
    elif name == 'civ6rl.native_official_bundle':
        raw = change(raw, "    if closure.get('input_profile') == 'lan':\n",
            "    if closure.get('input_profile') in ('lan', 'xp1-lan'):\n")
        # Bind the checkpoint identity too; hashes alone cannot distinguish
        # legitimate component ancestry from a changed reference.
        raw = change(raw, 'map_values=inputs.map_values, official_bundle=inputs.official_bundle)',
            'map_values=inputs.map_values, official_bundle=inputs.official_bundle, checkpoint=inputs.checkpoint)')
    elif name == 'tools.run_official_postload909':
        # Keep the raw bundle reader byte-identical. The existing captured
        # adapter selects its separate administrative checkpoint closure.
        raw = change(raw,
            'from civ6_host.runtime.native.native_official_bundle import validate_closure_profile',
            'from civ6_host.runtime.captured_saved_load import validate_closure_profile')
        raw = change(raw,
            "            if closure.get('network_checkpoint') is not None or closure.get('resume_checkpoint') is not None:\n                raise ValueError('XP1 candidate does not admit checkpoint resume')",
            "            if closure.get('resume_checkpoint') is not None:\n                raise ValueError('XP1 cannot inherit a historical Base checkpoint')")
    else:
        return raw
    return ast.unparse(ast.parse(raw))+'\n'
