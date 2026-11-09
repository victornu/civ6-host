-- Inserted into the existing file transport's lexical scope by the preparer.
-- Only a retained installed native provider is called; no source transaction
-- changes, native SQL through DB.Query, fallback or gameplay action.
  local function streamText(chunks,maximum)
    if type(chunks)~="table" or #chunks<1 or #chunks>math.ceil(maximum/64) then error("invalid_stream_chunks") end
    local count=0
    for key,value in pairs(chunks) do
      if type(key)~="number" or key~=math.floor(key) or key<1 or key>#chunks
        or type(value)~="string" or #value<2 or #value>128 or #value%2~=0
        or not value:match("^[0-9a-f]+$") then error("invalid_stream_hex") end
      count=count+1
    end
    if count~=#chunks then error("sparse_stream_chunks") end
    local encoded=table.concat(chunks)
    if #encoded>maximum*2 then error("stream_string_bound") end
    local text=encoded:gsub("..",function(pair)return string.char(tonumber(pair,16)) end)
    if text:find("%z") then error("stream_string_nul") end
    return text
  end

  local function databaseRowStream(command)
    local request=command.bulk
    if type(request)~="table" or not hex32(request.nonce) or request.nonce~=command.command_id
      or not hex32(request.provider_nonce) then status(command,false,"invalid_row_stream_request");return end
    local fields={nonce=true,provider_nonce=true,sql_hex=true,path_hex=true,expected_player_id=true,expected_turn=true}
    for key in pairs(request) do if not fields[key] then status(command,false,"unknown_row_stream_field");return end end
    local ready,reason=adminReady(request)
    if not ready then status(command,false,reason);return end
    if type(UI.IsGameCoreBusy)~="function" or UI.IsGameCoreBusy() then
      status(command,false,"row_stream_engine_not_idle");return
    end
    local callback=Civ6RL_LocalizationRowStream
    if type(callback)~="function" or request.provider_nonce~=Civ6RL_LocalizationRowStreamIdentity then
      status(command,false,"row_stream_provider_unavailable");return
    end
    local decoded,sql,path=pcall(function()
      return streamText(request.sql_hex,65536),streamText(request.path_hex,2047)
    end)
    if not decoded then status(command,false,"invalid_row_stream_encoding");return end
    local ok,receipt=pcall(callback,sql,path,request.nonce)
    if not ok or type(receipt)~="string" or #receipt==0 or #receipt>8192 then
      status(command,false,"row_stream_native_failed");return
    end
    ready,reason=adminReady(request)
    if not ready or UI.IsGameCoreBusy() or callback~=Civ6RL_LocalizationRowStream
      or request.provider_nonce~=Civ6RL_LocalizationRowStreamIdentity then
      status(command,false,"row_stream_boundary_changed");return
    end
    -- Python validates the native JSON string, exact query hash, source owners,
    -- complete file and receipt outcome. Lua does not reinterpret its fields.
    status(command,true,"database_row_stream_read",{native_receipt=receipt,request_id=command.command_id,
      provider_nonce=request.provider_nonce,completion="read_only_active_connection",native_game_core_busy=false})
  end
