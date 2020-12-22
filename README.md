# Tarantool Rocks Server

## Uploading new rocks

You can upload `.rockspec`, `.src.rock`, `.all.rock`,
but please don't upload any platform-dependent `.*.rock`.

```bash
curl --fail \
  -u $ROCKS_USERNAME:$ROCKS_PASSWORD https://rocks.tarantool.org \
  -X PUT -F "rockspec=@mymodule-scm-1.src.rock"
```

and delete it
```bash
curl --fail \
  -u $ROCKS_USERNAME:$ROCKS_PASSWORD https://rocks.tarantool.org \
  -H "Content-Type: application/json" \
  -X DELETE -d '{"file_name":"mymodule-scm-1.src.rock"}'
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
          script: curl --fail
            -u $ROCKS_USERNAME:$ROCKS_PASSWORD https://rocks.tarantool.org
            -X PUT -F rockspec=@$ROCK_NAME-scm-1.rockspec
        - on:
            tags: true
          provider: script
          script: cat $ROCK_NAME-scm-1.rockspec |
            sed -E
              -e "s/branch = '.+'/tag = '$TRAVIS_TAG'/g"
              -e "s/version = '.+'/version = '$TRAVIS_TAG-1'/g" |
            curl --fail
              -u $ROCKS_USERNAME:$ROCKS_PASSWORD https://rocks.tarantool.org
              -X PUT -F "rockspec=@-;filename=$ROCK_NAME-$TRAVIS_TAG-1.rockspec"
```

## Gitlab CI integration

Add `ROCKS_USERNAME` and `ROCKS_PASSWORD` build variables.

```yaml
stages:
  - test
  - publish

include:
  remote: https://tarantool.github.io/rocks.tarantool.org/helpers/gitlab-publish-rockspec.yml
```

That's it. For advanced usage see how to
[tune external tasks](https://docs.gitlab.com/ee/ci/yaml/#overriding-external-template-values).
