# Tarantool Rocks Server

## Uploading new rocks

You can upload `.rockspec`, `.src.rock`, `.all.rock`
and any other platform-dependent `.*.rock`.

```bash
curl -X PUT -F "rockspec=@mymodule-scm-1.src.rock" https://LOGIN:PASSWORD@rocks.tarantool.io
```

