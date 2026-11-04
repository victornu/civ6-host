"""Profile the existing publisher; retain Base body and default admission."""
BASE='d7ed520e1334947fc7b3be50b00c78eea55e69eb079583f24d87742e90f2a5c3'
def replace(raw,old,new):
    if raw.count(old)!=1:raise ValueError('Publication extraction anchor changed: '+old[:100])
    return raw.replace(old,new)
def parameterize(name,raw):
    if name!='civ6rl.native_player_view':return raw
    raw=replace(raw,'    def publish(self):','    def publish(self, *, publication_owner=None):')
    raw=replace(raw,"        if self.cache_abi.core_sha256 != '"+BASE+"':\n            raise ValueError('XP1 dynamic kind4/public cache publication is not qualified')",'''        target_rva = OUTER_PUBLISH_RVA
        if self.cache_abi.core_sha256 != 'BASE':
            from civ6_host.runtime.xp1_cache_publication import validate_publisher
            target_rva = validate_publisher(self, publication_owner)
        elif publication_owner is not None:
            raise ValueError('Base publication does not accept an XP1 candidate owner')'''.replace('BASE',BASE))
    for old,new in (
        ('SERVICE_ENSURE_CACHE_SLOT, SERVICE_ENSURE_CACHE_RVA','SERVICE_ENSURE_CACHE_SLOT, self.cache_abi.service_ensure_rva'),
        ('SERVICE_CACHE_OWNER_SLOT, SERVICE_CACHE_OWNER_GETTER_RVA','SERVICE_CACHE_OWNER_SLOT, self.cache_abi.service_owner_rva'),
        ('owner_vtable != self.core._handle + CACHE_GAME_VTABLE_RVA','owner_vtable != self.core._handle + self.cache_abi.cache_owner_vtable_rva'),
        ('owner + CACHE_GAME_MAP_VIEW_OFFSET','owner + self.cache_abi.map_view_offset'),
        ('view_vtable != self.core._handle + CACHE_MAP_VIEW_VTABLE_RVA','view_vtable != self.core._handle + self.cache_abi.map_view_vtable_rva'),
        ('OUTER_PUBLISH_SLOT, OUTER_PUBLISH_RVA, None, C.c_void_p, C.c_uint8','OUTER_PUBLISH_SLOT, target_rva, None, C.c_void_p, C.c_uint8'),
    ):raw=replace(raw,old,new)
    raw=replace(raw,'        if not table:\n', '''        if not table:
            if publication_owner is not None:
                raise ValueError('XP1 publication needs the native populated visibility table')
''')
    raw=replace(raw,'        publish(self.context, pointer, 1)', '''        if publication_owner is not None:
            from civ6_host.runtime.xp1_cache_publication import before_native
            before_native(self, publication_owner)
        publish(self.context, pointer, 1)''')
    raw=replace(raw,'        return (width, height, plot_count)', '''        result = (width, height, plot_count)
        if publication_owner is not None:
            from civ6_host.runtime.xp1_cache_publication import after_native
            after_native(self, publication_owner, result)
        return result''')
    return raw
