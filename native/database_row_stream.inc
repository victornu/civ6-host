/* Bounded read-only result rows written without per-row Lua objects.
 * Included after the source-pinned localization query helper. It reuses that
 * helper's DatabaseDLL ABI and creates/releases only its own result cursor.
 * The caller owns the borrowed connection and an exclusively created file.
 * Deadlines are cooperative between native steps, never cancellation of one.
 */
#include <math.h>

#define RS_MAX_BYTES (32ULL * 1024 * 1024)
#define RS_MAX_ROWS 8192
#define RS_MAX_COLUMNS 257
#define RS_MAX_TEXT 131074

static int rs_query_digest(const char *sql,char hex[65]) {
    BCRYPT_ALG_HANDLE alg=NULL;BCRYPT_HASH_HANDLE hash=NULL;unsigned char digest[32];int ok=0;
    if(BCryptOpenAlgorithmProvider(&alg,BCRYPT_SHA256_ALGORITHM,NULL,0)<0)goto end;
    if(BCryptCreateHash(alg,&hash,NULL,0,NULL,0,0)<0)goto end;
    if(BCryptHashData(hash,(PUCHAR)sql,(ULONG)strlen(sql),0)<0 || BCryptFinishHash(hash,digest,32,0)<0)goto end;
    for(int i=0;i<32;++i)sprintf_s(hex+2*i,3,"%02x",digest[i]);ok=1;
end:
    if(hash)BCryptDestroyHash(hash);if(alg)BCryptCloseAlgorithmProvider(alg,0);return ok;
}

typedef struct {
    uint64_t rows, bytes, elapsed;
    int status, statement_error, cursor_released, cursor_live;
    const char *error;
    unsigned char buffer[65536];size_t pending;
} RowStreamResult;

static int rs_flush(HANDLE file, RowStreamResult *r) {
    DWORD written;
    if(r->pending && (!WriteFile(file,r->buffer,(DWORD)r->pending,&written,NULL)||written!=r->pending)) {
        r->error="write_failed";return 0;
    }
    r->pending=0;return 1;
}
static int rs_write(HANDLE file, RowStreamResult *r, const void *data, size_t size) {
    const unsigned char *next=(const unsigned char *)data;size_t remaining=size;
    if (size > RS_MAX_BYTES - r->bytes) {r->error="byte_bound";return 0;}
    while(remaining) {
        size_t part=sizeof(r->buffer)-r->pending;
        if(part>remaining)part=remaining;
        memcpy(r->buffer+r->pending,next,part);r->pending+=part;next+=part;remaining-=part;
        if(r->pending==sizeof(r->buffer)&&!rs_flush(file,r))return 0;
    }
    r->bytes += size;return 1;
}
static int rs_text(HANDLE file, RowStreamResult *r, const char *text, size_t maximum, int empty) {
    size_t n;uint32_t length;
    if (!text) {r->error="null_text";return 0;}
    n=strnlen_s(text,maximum+1);
    if (n>maximum || (!empty && !n)) {r->error="text_bound";return 0;}
    /* Generated SQL represents stored TEXT/BLOB as uppercase hex, so embedded
       zero bytes never reach this NUL-terminated result getter. */
    for(size_t i=0;i<n;++i) if((unsigned char)text[i]>127) {r->error="non_ascii_result";return 0;}
    length=(uint32_t)n;
    return rs_write(file,r,&length,4) && rs_write(file,r,text,n);
}

static int database_row_stream(void *connection, uint64_t sqlite, const char *sql,
        HANDLE file, uint32_t max_rows, uint32_t milliseconds, RowStreamResult *r) {
    void *cursor=NULL;uint64_t statement=0,owner=0,handle=0;
    ULONGLONG started=GetTickCount64();int columns=0,kind,col,success=0;
    unsigned char has_row;char tag;
    memset(r,0,sizeof(*r));r->error="arguments";r->statement_error=-1;
    if (!max_rows || max_rows>RS_MAX_ROWS || !milliseconds || milliseconds>2000
        || !sql || strlen(sql)>65536 || !query_sql(sql) || file==INVALID_HANDLE_VALUE) goto end;
    r->error="source_abi";
    if (!connection || !slot(connection,0x18,0x23a0)
        || !pointer((uintptr_t)connection+0x10,&handle) || handle!=sqlite) goto end;
    r->error="prepare_failed";
    cursor=DBFN(QueryNew,0x23a0)(connection,sql,-1);
    if(!cursor) goto end;
    r->cursor_live=1;r->error="release_abi";
    /* An unrecognized destructor is never guessed. Retain that owner on the
       refusal path and report it so the caller can quarantine the process. */
    if(!slot(cursor,8,0x4600)) goto end;
    r->error="getter_abi";
    if(!slot(cursor,0x20,0x4e10)||!slot(cursor,0xb8,0x4400)||!slot(cursor,0xc0,0x4410)
        ||!slot(cursor,0xd0,0x4480)||!slot(cursor,0xf0,0x4a60)||!slot(cursor,0x110,0x4930)
        ||!slot(cursor,0x130,0x49c0)) goto release;
    r->error="statement_not_readonly";
    if(!pointer((uintptr_t)cursor+0x18,&statement)||!qword(statement,&owner)||owner!=sqlite
        || DBFN(Count,0x16e70)((void *)(uintptr_t)statement)!=1) goto release;
    columns=DBFN(Count,0x4400)(cursor);r->error="column_bound";
    if(columns<1 || columns>RS_MAX_COLUMNS) goto release;
    if(!rs_write(file,r,"C6RS01\r\n",8) || !rs_write(file,r,&columns,4)) goto release;
    for(col=0;col<columns;++col) if(!rs_text(file,r,DBFN(CellText,0x4410)(cursor,col),256,0)) goto release;
    for(;;) {
        r->error="time_bound";
        if(GetTickCount64()-started>=milliseconds) goto release;
        has_row=DBFN(Advance,0x4e10)(cursor);
        r->status=DBFN(Count,0x15120)((void *)(uintptr_t)sqlite);
        r->error="step_failed";
        if(!memory(statement+0x84,&r->statement_error,4)||r->statement_error!=0
            ||r->status!=(has_row?100:101)) goto release;
        r->error="time_bound";
        if(GetTickCount64()-started>=milliseconds) goto release;
        if(!has_row) break;
        r->error="row_bound";
        if(r->rows>=max_rows) goto release;
        tag='R';if(!rs_write(file,r,&tag,1)) goto release;
        for(col=0;col<columns;++col) {
            kind=DBFN(CellInt,0x4480)(cursor,col);
            switch(kind) {
            case 5: tag='n';if(!rs_write(file,r,&tag,1)) goto release;break;
            case 1: {
                int32_t value=DBFN(CellInt,0x4930)(cursor,col);
                tag='i';if(!rs_write(file,r,&tag,1)||!rs_write(file,r,&value,4)) goto release;break;
            }
            case 2: {
                double value=DBFN(CellReal,0x49c0)(cursor,col);
                r->error="nonfinite_real";if(!isfinite(value)) goto release;
                tag='f';if(!rs_write(file,r,&tag,1)||!rs_write(file,r,&value,8)) goto release;break;
            }
            case 3:
                tag='t';if(!rs_write(file,r,&tag,1)||!rs_text(file,r,DBFN(CellText,0x4a60)(cursor,col),RS_MAX_TEXT,1)) goto release;break;
            default:r->error="unsupported_result_type";goto release;
            }
        }
        ++r->rows;
    }
    /* A terminal marker is written only after explicit SQLITE_DONE and the
       statement error check. File truncation/limits never masquerade as EOF. */
    tag='D';
    if(!rs_write(file,r,&tag,1)||!rs_write(file,r,&r->rows,8)||!rs_flush(file,r)) goto release;
    success=1;r->error="";
release:
    DBFN(Release,0x4600)(cursor);r->cursor_released=1;r->cursor_live=0;
end:
    r->elapsed=GetTickCount64()-started;return success;
}

/* Same explicit UI/Locale.Lookup scope as the existing query callback. This is
 * an additional opt-in producer, not a replacement of old capture receipts.
 * It never calls Backup, changes a source transaction, or creates a thread. */
__declspec(dllexport) int __cdecl civ6rl_localization_row_stream(lua_State *L) {
    State before,after;RowStreamResult result;
    char sql[65537],path[2048],nonce[33],pid_text[32],created_text[32],digest[65]="",query_digest[65]="";
    char before_json[2048],after_json[2048],receipt[8192];uint64_t pid,created,size=0;
    HANDLE output=INVALID_HANDLE_VALUE;int success=0;const char *error="arguments";
    memset(&result,0,sizeof(result));
    if(!qready)return 0;
    if(qactive)return qlerror(L,"Localization stream reentrancy refused");
    if(qt(L)!=6 || !lua_string(L,1,qstring,qtype,sql,sizeof(sql)) || !query_sql(sql)
        || !lua_string(L,2,qstring,qtype,path,sizeof(path))
        || !lua_string(L,3,qstring,qtype,nonce,sizeof(nonce)) || strlen(nonce)!=32
        || !lua_string(L,4,qstring,qtype,pid_text,sizeof(pid_text)) || !decimal(pid_text,&pid)
        || !lua_string(L,5,qstring,qtype,created_text,sizeof(created_text)) || !decimal(created_text,&created)
        || pid!=qpid || created!=qcreation || qpid!=GetCurrentProcessId()
        || qfunction(L,6)!=(LuaC)((uintptr_t)qexe+0x4ca5d0) || !lua_scope(L,(uintptr_t)qexe)) goto end;
    for(int i=0;i<32;++i) if(!((nonce[i]>='0'&&nonce[i]<='9')||(nonce[i]>='a'&&nonce[i]<='f'))) goto end;
    error="module_identity";
    if(GetModuleHandleW(NULL)!=qexe || GetModuleHandleW(L"Localization_FinalRelease.dll")!=qloc
        || GetModuleHandleW(L"DatabaseDLL_FinalRelease.dll")!=qdb || GetModuleHandleW(L"HavokScript_FinalRelease.dll")!=qhv) goto end;
    error="source_before";
    if(!state((uintptr_t)qloc,(uintptr_t)qdb,&before)) goto end;
    error="query_digest";if(!rs_query_digest(sql,query_digest))goto end;
    error="fresh_private_destination";
    if(!destination_path(path)) goto end;
    output=CreateFileA(path,GENERIC_READ|GENERIC_WRITE,FILE_SHARE_READ,NULL,CREATE_NEW,
        FILE_ATTRIBUTE_NORMAL|FILE_FLAG_OPEN_REPARSE_POINT,NULL);
    if(output==INVALID_HANDLE_VALUE) goto end;
    qactive=1;
    success=database_row_stream((void *)(uintptr_t)before.connection,before.sqlite,sql,output,RS_MAX_ROWS,2000,&result);
    /* A cursor whose destructor was refused invalidates this shared helper.
       Both old query and stream entrypoints now refuse further calls. */
    qactive=result.cursor_live?1:0;error=result.error;
    if(!success)goto end;
    success=0;error="source_after";
    if(!state((uintptr_t)qloc,(uintptr_t)qdb,&after)||memcmp(&before,&after,sizeof(before))||!lua_scope(L,(uintptr_t)qexe))goto end;
    error="file_receipt";
    if(!FlushFileBuffers(output)||!file_digest(output,digest,RS_MAX_BYTES,&size)||size!=result.bytes)goto end;
    if(!state_json(before_json,sizeof(before_json),&before)||!state_json(after_json,sizeof(after_json),&after))goto end;
    if(sprintf_s(receipt,sizeof(receipt),
        "{\"schema\":\"civ6-host.localization_row_stream_native.v1\",\"status\":\"ok\",\"nonce\":\"%s\","
        "\"pid\":%lu,\"creation_filetime\":%llu,\"thread_id\":%lu,\"lua_state\":\"0x%llx\","
        "\"source_before\":%s,\"source_after\":%s,\"query_sha256\":\"%s\",\"rows\":%llu,\"bytes\":%llu,\"sha256\":\"%s\","
        "\"milliseconds\":%llu,\"sqlite_status\":%d,\"statement_error\":%d,\"cursor_released\":true,"
        "\"source_transactions_modified\":false,\"atomic_snapshot_proven\":false,\"backup_called\":false}",
        nonce,qpid,qcreation,GetCurrentThreadId(),(uint64_t)(uintptr_t)L,before_json,after_json,
        query_digest,result.rows,result.bytes,digest,result.elapsed,result.status,result.statement_error)<=0)goto end;
    success=1;
end:
    if(output!=INVALID_HANDLE_VALUE)CloseHandle(output);
    if(!success)sprintf_s(receipt,sizeof(receipt),
        "{\"schema\":\"civ6-host.localization_row_stream_native.v1\",\"status\":\"error\",\"error\":\"%s\","
        "\"cursor_released\":%s,\"cursor_live\":%s}",error,result.cursor_released?"true":"false",result.cursor_live?"true":"false");
    qformat(L,"%s",receipt);return 1;
}
