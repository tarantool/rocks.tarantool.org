# Tarantool Rocks Server

## Uploading new rocks

You can upload `.rockspec`, `.src.rock`, `.all.rock`
and any other platform-dependent `.*.rock`.

```bash
curl -X PUT -F "rockspec=@mymodule-scm-1.src.rock" https://LOGIN:PASSWORD@rocks.tarantool.org
```

and delete it
```bash
curl -X DELETE -d '{"file_name":"mymodule-scm-1.src.rock"}' -H "Content-Type: application/json" https://LOGIN:PASSWORD@rocks.tarantool.org
```

## Travis CI integration

```yaml
env:
  global:
    - ROCK_NAME=...
    
jobs:
  include:
    # - tests
    - stage: deploy
      script: skip
      deploy:
        - provider: script
          script: curl -X PUT -F rockspec=@$ROCK_NAME-scm-1.rockspec
            https://$ROCKS_USERNAME:$ROCKS_PASSWORD@$ROCKS_SERVER
        - on:
            tags: true
          provider: script
          script: cat $ROCK_NAME-scm-1.rockspec |
            sed -E
              -e "s/branch = '.+'/tag = '$TRAVIS_TAG'/g"
              -e "s/version = '.+'/version = '$TRAVIS_TAG-1'/g" |
            curl -X PUT -F "rockspec=@-;filename=$ROCK_NAME-$TRAVIS_TAG-1.rockspec"
              https://$ROCKS_USERNAME:$ROCKS_PASSWORD@$ROCKS_SERVER
```
