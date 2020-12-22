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

## Github Actions integration

```yaml
env:
  ROCK_NAME: mymodule

jobs:
  publish-scm-1:
    steps:
      - uses: actions/checkout@v2
      - uses: tarantool/rocks.tarantool.org/github-action
        with:
          auth: ${{ secrets.ROCKS_USERNAME }}:${{ secrets.ROCKS_PASSWORD }}
          files: ${{ env.ROCK_NAME }}-scm-1.rockspec

  publish-tag:
    if: startsWith(github.ref, 'refs/tags/')
    steps:
      - uses: actions/checkout@v2
      - run: echo "TAG=${GITHUB_REF##*/}" >> $GITHUB_ENV

      - run: cat ${{ env.ROCK_NAME }}-scm-1.rockspec |
          sed -E
            -e "s/branch = '.+'/tag = '$TAG'/g"
            -e "s/version = '.+'/version = '$TAG-1'/g" |
          tee ${{ env.ROCK_NAME }}-$TAG-1.rockspec

      - uses: tarantool/rocks.tarantool.org/github-action
        with:
          auth: ${{ secrets.ROCKS_USERNAME }}:${{ secrets.ROCKS_PASSWORD }}
          files: |
            ${{ env.ROCK_NAME }}-${{ env.TAG }}-1.rockspec
            # ${{ env.ROCK_NAME }}-${{ env.TAG }}-1.src.rock
```

## Travis CI integration

```yaml
env:
  global:
    - ROCK_NAME=mymodule

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
            all_branches: true
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
