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

To use this action one must set the `ROCKS_AUTH` secret in the
repository that contains the workflow.

```yaml
env:
  ROCK_NAME: mymodule

jobs:
  publish-scm-1:
    steps:
      - uses: actions/checkout@v2
      - uses: tarantool/rocks.tarantool.org/github-action@master
        with:
          auth: ${{ secrets.ROCKS_AUTH }}
          files: ${{ env.ROCK_NAME }}-scm-1.rockspec

  publish-tag:
    if: startsWith(github.ref, 'refs/tags/')
    steps:
      - uses: actions/checkout@v2
      - uses: rosik/setup-tarantool@v1
        with:
          tarantool-version: '2.5'

      - run: echo "TAG=${GITHUB_REF##*/}" >> $GITHUB_ENV
      - run: tarantoolctl rocks new_version --tag ${{ env.TAG }}
      - run: tarantoolctl rocks install ${{ env.ROCK_NAME }}-${{ env.TAG }}-1.rockspec
      - run: tarantoolctl rocks pack ${{ env.ROCK_NAME }}-${{ env.TAG }}-1.rockspec
      - run: tarantoolctl rocks pack ${{ env.ROCK_NAME }} ${{ env.TAG }}

      - uses: tarantool/rocks.tarantool.org/github-action@master
        with:
          auth: ${{ secrets.ROCKS_AUTH }}
          files: |
            ${{ env.ROCK_NAME }}-${{ env.TAG }}-1.rockspec
            ${{ env.ROCK_NAME }}-${{ env.TAG }}-1.src.rock
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
