# Tarantool Rocks Server

## Uploading new rocks

You can upload `.rockspec`, `.src.rock`, `.all.rock`
and any other platform-dependent `.*.rock`.

```bash
curl -X PUT -F "rockspec=@mymodule-scm-1.src.rock" https://LOGIN:PASSWORD@rocks.tarantool.io
```

and delete it
```bash
curl -X DELETE -d '{"file_name":"mymodule-scm-1.src.rock"}' -H "Content-Type: application/json" https://LOGIN:PASSWORD@rocks.tarantool.io
```
