function(initial_manifest, initial_rockspec, initial_action)
   initial_action = initial_action or 'add'

   local function default_sort(a, b)
      local ta = type(a)
      local tb = type(b)
      if ta == "number" and tb == "number" then
         return a < b
      elseif ta == "number" then
         return true
      elseif tb == "number" then
         return false
      else
         return tostring(a) < tostring(b)
      end
   end
   local function keys(tbl)
      local ks = {}
      for k,_ in pairs(tbl) do
         table.insert(ks, k)
      end
      return ks
   end
   local function sorted_pairs(tbl, sort_function)
      sort_function = sort_function or default_sort
      local keys = keys(tbl)
      local sub_orders = {}

      if type(sort_function) == "function" then
         table.sort(keys, sort_function)
      else
         local order = sort_function
         local ordered_keys = {}
         local all_keys = keys
         keys = {}

         for _, order_entry in ipairs(order) do
            local key, sub_order
            if type(order_entry) == "table" then
               key = order_entry[1]
               sub_order = order_entry[2]
            else
               key = order_entry
            end

            if tbl[key] then
               ordered_keys[key] = true
               sub_orders[key] = sub_order
               table.insert(keys, key)
            end
         end

         table.sort(all_keys, default_sort)
         for _, key in ipairs(all_keys) do
            if not ordered_keys[key] then
               table.insert(keys, key)
            end
         end
      end

      local i = 1
      return function()
         local key = keys[i]
         i = i + 1
         return key, tbl[key], sub_orders[key]
      end
   end

   local write_table

   local function write_value(out, v, level, sub_order)
      if type(v) == "table" then
         write_table(out, v, level + 1, sub_order)
      elseif type(v) == "string" then
         if v:match("[\r\n]") then
            local open, close = "[[", "]]"
            local equals = 0
            local v_with_bracket = v.."]"
            while v_with_bracket:find(close, 1, true) do
               equals = equals + 1
               local eqs = ("="):rep(equals)
               open, close = "["..eqs.."[", "]"..eqs.."]"
            end
            out:write(open.."\n"..v..close)
         else
            out:write(("%q"):format(v))
         end
      else
         out:write(tostring(v))
      end
   end

   write_table = function(out, tbl, level, field_order)
      out:write("{")
      local sep = "\n"
      local indentation = "   "
      local indent = true
      local i = 1
      for k, v, sub_order in sorted_pairs(tbl, field_order) do
         out:write(sep)
         if indent then
            for n = 1,level do out:write(indentation) end
         end

         if k == i then
            i = i + 1
         else
            if type(k) == "string" and k:match("^[a-zA-Z_][a-zA-Z0-9_]*$") then
               out:write(k)
            else
               out:write("[")
               write_value(out, k, level)
               out:write("]")
            end

            out:write(" = ")
         end

         write_value(out, v, level, sub_order)
         if type(v) == "number" then
            sep = ", "
            indent = false
         else
            sep = ",\n"
            indent = true
         end
      end
      if sep ~= "\n" then
         out:write("\n")
         for n = 1,level-1 do out:write(indentation) end
      end
      out:write("}")
   end

   local function write_table_as_assignments(out, tbl, field_order)
      for k, v, sub_order in sorted_pairs(tbl, field_order) do
         out:write(k.." = ")
         write_value(out, v, 0, sub_order)
         out:write("\n")
      end
   end

   local function run_string(str, env)
      if not str then
         return nil, err, "open"
      end
      str = str:gsub("^#![^\n]*\n", "")
      local chunk, ran
      if _VERSION == "Lua 5.1" then
         chunk, err = loadstring(str, "manifest")
         if chunk then
            setfenv(chunk, env)
            ran, err = pcall(chunk)
         end
      else
         chunk, err = load(str, "manifest", "t", env)
         if chunk then
            ran, err = pcall(chunk)
         end
      end
      if not chunk then
         return nil, "Error loading file: "..err, "load"
      end
      if not ran then
         return nil, "Error running file: "..err, "run"
      end
      return true, err
   end

   local function eval_lua_string(eval_str)
      assert(type(eval_str) == "string")

      local result = {}
      local globals = {}
      local globals_mt = {
         __index = function(t, k)
            globals[k] = true
         end
      }
      local save_mt = getmetatable(result)
      setmetatable(result, globals_mt)

      run_string(eval_str, result)

      setmetatable(result, save_mt)
      return result
   end

   local function dump(o)
      if type(o) == 'table' then
         local s = '{ '
         for k,v in pairs(o) do
            if type(k) ~= 'number' then k = '"'..k..'"' end
            s = s .. '['..k..'] = ' .. dump(v) .. ','
         end
         return s .. '} '
      else
         return tostring(o)
      end
   end

   local function get_rockspec_version(rockspec)
      local result = eval_lua_string(rockspec)
      return result['package'], result['version']
   end

   local function patch_manifest(manifest, rockspec, action)
      local result = eval_lua_string(manifest)
      local package, ver = get_rockspec_version(rockspec)
      if not package or not ver then
         return 'rockspec parsing error. Couldn\'t find package or version section', nil
      end
      local msg
      local arch = {
         {
            arch = "rockspec"
         }
      }

      if action == 'add' then
         if result.repository[package] ~= nil then
            result.repository[package][ver] = arch
         else
            result.repository[package] = {
               [ver] = arch
            }
         end
         msg = 'rockspec was successfully added to manifest'
      elseif action == 'remove' then
         result.repository[package][ver] = nil
         if next(result.repository[package]) == nil then
            result.repository[package] = nil
         end
         msg = 'rockspec was successfully removed from manifest'
      else
         msg = 'action is not supported'
         return msg, nil
      end

      local out = {buffer = {}}
      function out:write(data) table.insert(self.buffer, data) end
      write_table_as_assignments(out, result)

      return msg, table.concat(out.buffer)
   end

   return patch_manifest(initial_manifest, initial_rockspec, initial_action)
end
