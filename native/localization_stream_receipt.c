/* Keep the frozen stream kernel; use the already audited LuaPlus string push.
 * HKS lua_pushfstring truncates formatted output at 511 bytes in the installed
 * runtime. The kernel's complete bounded JSON receipt must cross intact.
 */
#include "localization_query.c"

static const char *row_stream_push_receipt(lua_State *L, const char *format,
                                         const char *text) {
    StackResult result;
    if (strcmp(format, "%s") || strnlen_s(text, 8193) > 8192) {
        qlerror(L, "Row receipt format/bound differs");
        return NULL;
    }
    /* Same qualified ABI used by push_bounded in localization_query.c. */
    qtext(L, &result, text);
    return text;
}

#define qformat row_stream_push_receipt
#include "database_row_stream.inc"
#undef qformat
