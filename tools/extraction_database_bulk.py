"""Explicit bulk row evidence through the existing table algorithms."""
def parameterize(name, raw):
    if name != 'civ6rl.database_capture_bundle993':
        return raw
    def change(old, new):
        nonlocal raw
        if raw.count(old) != 1:
            raise ValueError('Bulk table extraction seam changed: '+old[:100])
        raw=raw.replace(old,new)
    change('def _pass(exchange, connection, player, turn, limits, row_counter):',
           'def _pass(exchange, connection, player, turn, limits, row_counter, *, row_exchange=None, row_page_size=None):')
    change("            page, index = query('rows', table_name=name, offset=offset, limit=limits.page_size, **anchor)",
           """            if row_exchange is None:
                page, index = query('rows', table_name=name, offset=offset, limit=limits.page_size, **anchor)
            else:
                page, index = row_exchange(dict(connection=connection, operation='rows', expected_player_id=player, expected_turn=turn, table_name=name, offset=offset, limit=row_page_size, **anchor), columns)""")
    change('            if len(rows) < limits.page_size:',
           '            if len(rows) < (limits.page_size if row_exchange is None else row_page_size):')
    seam="    manifest = json.loads(_resolve_resource_path(directory / 'manifest.json').read_bytes())"
    change(seam,seam+"""
    if manifest.get('schema') == 'civ6-host.database_bulk_capture.v1':
        from civ6_host.runtime import database_bulk_capture
        return database_bulk_capture._verify_bundle(directory)""")
    helper='''def _is_verified_bundle(value):
    if type(value) is _VerifiedBundle and value in _VERIFIED_BUNDLES:
        return True
    from civ6_host.runtime import database_bulk_capture
    return database_bulk_capture.is_verified(value)

def _iter_captured_rows(verified, table):
    require(_is_verified_bundle(verified), 'Expected an authenticated capture evidence object')
    if type(verified) is not _VerifiedBundle:
        yield from verified.iter_rows(table)
        return
    manifest = verified.manifest
    for index in table['row_pages']:
        pin = manifest['journal'][index]['response']
        require(verified._files.get(pin['path']) == pin, 'Row response is not in verified pins')
        record = json.loads(_read_pinned_journal_bytes(verified.directory, pin['path'], pin))
        yield from record['diagnostics']['database_capture']['rows']

'''
    change('def compare_sqlite_export(',helper+'def compare_sqlite_export(')
    change('type(_verified) is _VerifiedBundle and _verified in _VERIFIED_BUNDLES and',
           '_is_verified_bundle(_verified) and')
    start=raw.index("            for index in table['row_pages']:",raw.index('def compare_sqlite_export('))
    end=raw.index("            require(cursor.fetchone() is None",start)
    old=raw[start:end];body=old[old.index('                    raw = cursor.fetchone()'):]
    change(old,'            for expected in _iter_captured_rows(_verified, table):\n'+''.join(line[4:]+'\n' for line in body.rstrip().splitlines()))
    start=raw.index("    require(type(preflight.get('journal_bytes'))",raw.index('def materialize_sqlite_export('))
    end=raw.index('    require(0 < _resolve_resource_path(template)',start)
    old=raw[start:end]
    change(old,"    if preflight.get('schema') != 'civ6-host.database_bulk_capture.v1':\n"+''.join('    '+line+'\n' for line in old.rstrip().splitlines()))
    change('    manifest = verify_bundle(directory)',
           '    _verified = _verify_bundle(directory)\n    manifest = _verified.manifest')
    start=raw.index("            for index in table['row_pages']:",raw.index('def materialize_sqlite_export('))
    end=raw.index('        db.commit()',start)
    old=raw[start:end];body=old[old.index("                    expressions = ['?']"):]
    change(old,"            for row in _iter_captured_rows(_verified, table):\n                require(time.monotonic() < deadline, 'Materialization time budget exhausted')\n"+''.join(line[4:]+'\n' for line in body.rstrip().splitlines()))
    change('comparison = compare_sqlite_export(directory, output, connection=connection)',
           'comparison = compare_sqlite_export(directory, output, connection=connection, _verified=_verified)')
    # These receipts already pin the source manifest. Expose its explicit kind
    # only for the new branch; legacy receipt dictionaries retain their shape.
    for schema in ('civ6rl.database_export_comparison993.v1','civ6rl.database_materialization993.v1'):
        change("return dict(schema='"+schema+"',", "return dict(**({'capture_schema': manifest['schema']} if manifest['schema'] != SCHEMA else {}), schema='"+schema+"',")
    return raw
