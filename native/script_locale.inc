/* Static Locale/Achievements namespace subset. Include after the HKS imports
 * and namespace_create_* declarations in gamecore_python_host.c. This binds
 * pointers from an already loaded Localization module; it does not load the
 * module or call its Initialize/Shutdown lifecycle. */
static uintptr_t locale_module = 0;
typedef void* (__cdecl *LocaleGetDictionary)(void);
typedef unsigned char (__cdecl *LocaleIsValidKey)(void*, const char*);
typedef unsigned int (__cdecl *LocaleCurrentLanguageIndex)(void*);
typedef unsigned char (__cdecl *LocaleHasKey)(void*, const char*, unsigned int, unsigned int);
typedef void* (__cdecl *LocaleLookup)(void*, const char*);
typedef unsigned char (__cdecl *LocalePushStringArgument)(void*, const char*);
typedef const char* (__cdecl *LocaleStringToUtf8)(void*, unsigned int*, unsigned int);
typedef void (__cdecl *LocaleStringDestroy)(void*);
static LocaleGetDictionary locale_get_dictionary = NULL;
static LocaleIsValidKey locale_is_valid_key_fn = NULL;
static LocaleCurrentLanguageIndex locale_current_language_index = NULL;
static LocaleHasKey locale_has_key = NULL;
static LocaleLookup locale_lookup = NULL;
static LocalePushStringArgument locale_push_string_argument = NULL;
static LocaleStringToUtf8 locale_string_to_utf8 = NULL;
static LocaleStringDestroy locale_string_destroy = NULL;

typedef struct LocalePushTextRequest { const char* text; } LocalePushTextRequest;
static int __cdecl locale_push_text_inner(LuaState* state) {
    LocalePushTextRequest* request = (LocalePushTextRequest*)th_userdata(state, LUA_UPVALUE(1));
    if (!request || !request->text)
        return th_lerror(state, "Civ6RL Locale Lookup protected push has no text");
    LuaStackResult result;
    th_pushstring(state, &result, request->text);
    return 1;
}

static int __cdecl locale_refused(LuaState* state) {
    return th_lerror(state, "Civ6RL Locale diagnostic explicitly refuses this native service");
}
static int __cdecl achievements_refused(LuaState* state) {
    return th_lerror(state, "Civ6RL Achievements diagnostic explicitly refuses this native service");
}

static int __cdecl locale_starts_with(LuaState* state) {
    size_t text_length = 0, prefix_length = 0;
    const char* text = th_checkstring(state, 1, &text_length);
    const char* prefix = th_checkstring(state, 2, &prefix_length);
    LuaStackResult result;
    th_pushbool(state, &result, prefix_length <= text_length &&
                memcmp(text, prefix, prefix_length) == 0);
    return 1;
}

static int __cdecl locale_is_valid_key(LuaState* state) {
    if (!locale_module || !locale_get_dictionary || !locale_is_valid_key_fn)
        return th_lerror(state, "Civ6RL Locale Localization module is not bound");
    size_t length = 0;
    const char* key = th_checkstring(state, 1, &length);
    if (!key || length > 65536)
        return th_lerror(state, "Civ6RL Locale key bound refused");
    void* dictionary = locale_get_dictionary();
    if (!dictionary) return th_lerror(state, "Civ6RL Locale dictionary is unavailable");
    LuaStackResult result;
    th_pushbool(state, &result, locale_is_valid_key_fn(dictionary, key) != 0);
    return 1;
}

static int __cdecl locale_has_text_key(LuaState* state) {
    if (!locale_module || !locale_get_dictionary || !locale_current_language_index || !locale_has_key)
        return th_lerror(state, "Civ6RL Locale Localization module is not bound");
    size_t length = 0;
    const char* key = th_checkstring(state, 1, &length);
    if (!key || length > 65536)
        return th_lerror(state, "Civ6RL Locale key bound refused");
    void* dictionary = locale_get_dictionary();
    if (!dictionary) return th_lerror(state, "Civ6RL Locale dictionary is unavailable");
    unsigned int language = locale_current_language_index(dictionary);
    LuaStackResult result;
    th_pushbool(state, &result, locale_has_key(dictionary, key, (unsigned int)length, language) != 0);
    return 1;
}

/* The EXE's Lookup path constructs a 0x80-byte Localization
 * String via the hidden Win64 return pointer, converts it with toUTF8(...,1),
 * pushes the returned text, and runs the virtual destructor. Positional string
 * arguments use the verified PushArgument(char const*) overload. Other Lua
 * types and named/table arguments are refused explicitly. */
static int __cdecl locale_lookup_key(LuaState* state) {
    if (!locale_module || !locale_lookup || !locale_push_string_argument ||
        !locale_string_to_utf8 || !locale_string_destroy)
        return th_lerror(state, "Civ6RL Locale Localization module is not bound");
    int top = th_gettop(state);
    if (top < 1 || top > 17)
        return th_lerror(state, "Civ6RL Locale Lookup diagnostic supports one key and at most 16 string arguments");
    size_t key_length = 0;
    const char* key = th_checkstring(state, 1, &key_length);
    if (!key || key_length > 65536 || memchr(key, 0, key_length))
        return th_lerror(state, "Civ6RL Locale key bound refused");
    const char* arguments[16];
    for (int i = 2; i <= top; ++i) {
        if (th_type(state, i) != 4)
            return th_lerror(state, "Civ6RL Locale Lookup diagnostic accepts only string format arguments");
        size_t length = 0;
        arguments[i - 2] = th_checkstring(state, i, &length);
        if (!arguments[i - 2] || length > 65536 || memchr(arguments[i - 2], 0, length))
            return th_lerror(state, "Civ6RL Locale format argument bound refused");
    }
    /* Allocate every Lua-side temporary before constructing the native String.
     * The inner push runs under pcall so Lua allocation errors cannot bypass
     * the C++ destructor in this outer frame. */
    LocalePushTextRequest* request = (LocalePushTextRequest*)th_newuserdata(state, sizeof(*request));
    if (!request) return th_lerror(state, "Civ6RL Locale Lookup request allocation failed");
    request->text = NULL;
    th_closure(state, locale_push_text_inner, 1, "Locale.Lookup protected string push", 0);
    __declspec(align(16)) unsigned char string_object[0x80];
    unsigned int text_length = 0;
    (void)locale_lookup(string_object, key);
    for (int i = 0; i < top - 1; ++i)
        (void)locale_push_string_argument(string_object, arguments[i]);
    const char* text = locale_string_to_utf8(string_object, &text_length, 1);
    if (!text || text_length > 1048576 || strnlen(text, (size_t)text_length + 1) != text_length) {
        locale_string_destroy(string_object);
        return th_lerror(state, "Civ6RL Locale Lookup returned invalid UTF-8 storage");
    }
    request->text = text;
    int status = th_pcall(state, 0, 1, 0);
    locale_string_destroy(string_object);
    if (status) return th_error(state);
    return 1;
}

static int __cdecl namespace_create_locale(LuaState* state) {
    static const struct { const char* key; const char* debug; LuaCallback callback; } methods[] = {
        {"Bundle", "lBundle", locale_refused}, {"LookupBundle", "lLookupBundle", locale_refused},
        {"GetLanguages", "lGetLanguages", locale_refused}, {"GetAudioLanguages", "lGetAudioLanguages", locale_refused},
        {"GetLanguageDisplayName", "lGetLanguageDisplayName", locale_refused},
        {"GetLanguageCoverage", "lGetLanguageCoverage", locale_refused},
        {"IsValidKey", "lIsValidKey", locale_is_valid_key}, {"HasTextKey", "lHasTextKey", locale_has_text_key},
        {"Compose", "lCompose", locale_refused}, {"Lookup", "lLookup", locale_lookup_key},
        {"LookupLanguage", "lLookupLanguage", locale_refused},
        {"StartsWith", "lStartsWith", locale_starts_with}, {"EndsWith", "lEndsWith", locale_refused},
        {"IsNilOrEmpty", "lIsNilOrEmpty", locale_refused},
        {"IsNilOrWhitespace", "lIsNilOrWhitespace", locale_refused}, {"Length", "lLength", locale_refused},
        {"SubString", "lSubString", locale_refused}, {"SplitString", "lSplitString", locale_refused},
        {"StripTags", "lStripTags", locale_refused}, {"ToUpper", "lToUpper", locale_refused},
        {"ToLower", "lToLower", locale_refused}, {"ToNumber", "lToNumber", locale_refused},
        {"ToPercent", "lToPercent", locale_refused}, {"ToRomanNumeral", "lToRomanNumeral", locale_refused},
        {"ToSpellout", "lToSpellout", locale_refused}, {"ToOrdinal", "lToOrdinal", locale_refused},
        {"Compare", "lCompare", locale_refused}, {"GetCurrentLanguage", "lGetCurrentLanguage", locale_refused},
        {"IsASCII", "lIsASCII", locale_refused}, {"IsUTF8", "lIsUTF8", locale_refused},
    };
    th_newtable(state, 0, (int)(sizeof(methods)/sizeof(methods[0])));
    for (size_t i = 0; i < sizeof(methods)/sizeof(methods[0]); ++i) {
        th_closure(state, methods[i].callback, 0, methods[i].debug, 0);
        th_setfield(state, -2, methods[i].key);
    }
    return 1;
}

static int __cdecl namespace_create_achievements(LuaState* state) {
    static const char* const methods[][2] = {
        {"IsAchievementUnlocked", "lIsAchievementUnlocked"}, {"GetStat", "lGetStat"},
        {"GetAchievementHash", "lGetAchievementHash"}, {"GetAchievementName", "lGetAchievementName"},
        {"GetAchievementDisplayName", "lGetAchievementDisplayName"},
        {"GetAchievementDescription", "lGetAchievementDescription"},
        {"GetAchievementData", "lGetAchievementData"}, {"DeleteAchievementData", "lDeleteAchievementData"},
    };
    th_newtable(state, 0, 8);
    for (size_t i = 0; i < 8; ++i) {
        th_closure(state, achievements_refused, 0, methods[i][1], 0);
        th_setfield(state, -2, methods[i][0]);
    }
    return 1;
}

__declspec(dllexport) int __cdecl LAB_LocaleBind(LuaState* root, void* module) {
    if (!root || root != thread_registry_root) return -1600;
    if (!module) {
        locale_module = 0; locale_get_dictionary = NULL; locale_is_valid_key_fn = NULL;
        locale_current_language_index = NULL; locale_has_key = NULL; locale_lookup = NULL;
        locale_push_string_argument = NULL;
        locale_string_to_utf8 = NULL; locale_string_destroy = NULL; return 0;
    }
    uintptr_t base = (uintptr_t)module;
#define LOCALE_EXPORT(symbol, rva, type, dst) do { \
    FARPROC proc = GetProcAddress((HMODULE)module, symbol); \
    if (!proc || (uintptr_t)proc != base + (rva)) return -1601; \
    memcpy(&(dst), &proc, sizeof(proc)); \
} while (0)
    LocaleGetDictionary get_dictionary = NULL;
    LocaleIsValidKey valid_key = NULL;
    LocaleCurrentLanguageIndex current_language = NULL;
    LocaleHasKey has_key = NULL;
    LocaleLookup lookup = NULL;
    LocalePushStringArgument push_string = NULL;
    LocaleStringToUtf8 to_utf8 = NULL;
    LocaleStringDestroy destroy = NULL;
    LOCALE_EXPORT("?GetStringDictionary@Localization@@YAAEBVStringDictionary@1@XZ", 0x192e0, LocaleGetDictionary, get_dictionary);
    LOCALE_EXPORT("?IsValidKey@StringDictionary@Localization@@QEBA_NPEBD@Z", 0x12cd0, LocaleIsValidKey, valid_key);
    LOCALE_EXPORT("?GetCurrentLanguageIndex@StringDictionary@Localization@@QEBAIXZ", 0x12570, LocaleCurrentLanguageIndex, current_language);
    LOCALE_EXPORT("?HasKey@StringDictionary@Localization@@QEBA_NPEBDII@Z", 0x12a00, LocaleHasKey, has_key);
    LOCALE_EXPORT("?Lookup@Localization@@YA?AVString@1@PEBD@Z", 0x196d0, LocaleLookup, lookup);
    LOCALE_EXPORT("?PushArgument@String@Localization@@QEAA_NPEBD@Z", 0xda70, LocalePushStringArgument, push_string);
    LOCALE_EXPORT("?toUTF8@String@Localization@@QEAAPEBDAEAIH@Z", 0xecb0, LocaleStringToUtf8, to_utf8);
    LOCALE_EXPORT("??1String@Localization@@UEAA@XZ", 0xc130, LocaleStringDestroy, destroy);
#undef LOCALE_EXPORT
    locale_get_dictionary = get_dictionary; locale_is_valid_key_fn = valid_key;
    locale_current_language_index = current_language; locale_has_key = has_key;
    locale_lookup = lookup; locale_push_string_argument = push_string;
    locale_string_to_utf8 = to_utf8; locale_string_destroy = destroy;
    locale_module = base;
    return 0;
}
