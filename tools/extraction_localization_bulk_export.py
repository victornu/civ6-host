"""Admit explicit bulk artifacts through the existing capture/export consumers."""
import ast

MODULES=('civ6rl.native_localization_logical_export','civ6rl.native_official_bundle','tools.capture_phase1_bundle994')

def parameterize(name,raw):
    if name not in MODULES:return raw
    def change(old,new):
        nonlocal raw
        if raw.count(old)!=1:raise ValueError('Bulk export extraction boundary changed: '+old[:100])
        raw=raw.replace(old,new)
    if name=='civ6rl.native_localization_logical_export':
        change('    build = _build()\n    installed = _json(ref)', '    installed = _json(ref)')
        change("    registered = _json(installed.get('registration'))", """    registered = _json(installed.get('registration'))
    build = bulk_export.selected_build(registered.get('build'))
    build_reference = registered['build'] if build is not None else reference(BUILD_PATH)
    if build is None:
        build = _build()""")
        change("registered.get('build') == reference(BUILD_PATH)","registered.get('build') == build_reference")
        change("    manifest = _json(ref, parent=folder, limit=MAX_MANIFEST_BYTES)","""    manifest = _json(ref, parent=folder, limit=MAX_MANIFEST_BYTES)
    selected = bulk_export.tables_manifest(manifest,ref,folder,player,turn,with_evidence=with_evidence)
    if selected is not None:
        return selected""")
        change("    _require(comparison == report.get('comparison'), 'Retained logical comparison differs from replay')", """    _require(comparison == report.get('comparison'), 'Retained logical comparison differs from replay')
    bulk_export.validate_sources(report,verified_tables,build)""")
        change("    refs += producer_dependencies(report['producer_sources'])['dependency_references']", "    refs += bulk_export.extra_dependencies(report)\n    refs += producer_dependencies(report['producer_sources'])['dependency_references']")
        change("    target = folder / 'localization-export.json'", "    target = folder / 'localization-export.json'\n    bulk_export.declare_sources(client,build,report)")
        change("        _tables_manifest(report['tables_bundle'], folder, expected_player_id, expected_turn)", "        bulk_export.check_live_sources(client,build,report)\n        _tables_manifest(report['tables_bundle'], folder, expected_player_id, expected_turn)")
    elif name=='civ6rl.native_official_bundle':
        change("    refs += logical.producer_dependencies(report['producer_sources'])['dependency_references']", "    refs += bulk_export.extra_dependencies(report)\n    refs += logical.producer_dependencies(report['producer_sources'])['dependency_references']")
        change('type(verified_tables) is tables._VerifiedBundle and verified_tables in tables._VERIFIED_BUNDLES and',
               'tables._is_verified_bundle(verified_tables) and')
        change('    first, last = verified', '    first, last = verified\n    bulk_export.same_profile(first["manifest"],last["manifest"])')
    else:
        change("        source = _file(ROOT / 'mod' / relative, deadline, 4 * 1024 * 1024)",
               "        source = _file(bulk_export.bridge_source(relative,ROOT / 'mod' / relative,installed_mod / relative), deadline, 4 * 1024 * 1024)")
        change("            proxy = SimpleNamespace(inbox=paths['inbox'], read_active_database=database_reader)",
               "            proxy = bulk_export.capture_proxy(client,paths['inbox'],database_reader,record,remaining)")
        change("            before_db, after_db = (verified_exports['before']['database'], verified['database'])",
               "            bulk_export.same_profile(verified_exports['before']['manifest'],verified['manifest'])\n            before_db, after_db = (verified_exports['before']['database'], verified['database'])")
    tree=ast.parse(raw)
    idx=1 if isinstance(tree.body[0],ast.Expr) and isinstance(tree.body[0].value,ast.Constant) else 0
    while isinstance(tree.body[idx],ast.ImportFrom) and tree.body[idx].module=='__future__':idx+=1
    tree.body[idx:idx]=ast.parse('from civ6_host.runtime import localization_bulk_export as bulk_export').body
    if name=='civ6rl.native_localization_logical_export':
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='export_localization')
        calls=[n for n in ast.walk(fn) if isinstance(n,ast.Call) and ast.unparse(n.func)=='tables.capture_bundle']
        if len(calls)!=1:raise ValueError('Logical table capture call changed')
        call=calls[0];call.func=ast.parse('bulk_export.capture_tables',mode='eval').body
        for keyword,value in [('client','client'),('process','process'),('build','build'),('registered','registered'),('identity','expected'),('remaining','remaining')]:
            call.keywords.append(ast.keyword(arg=keyword,value=ast.Name(value,ast.Load())))
    return ast.unparse(ast.fix_missing_locations(tree))+'\n'
