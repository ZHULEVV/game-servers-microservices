#!/bin/sh
# Локальный запуск GitHub Actions workflow утилитой act (https://github.com/nektos/act) с кратким выводом.
#   scripts/act.sh test  <сервис>     — тесты сервиса (unit + компонентные)
#   scripts/act.sh build <сервис>     — сборка образа и smoke-проверка
#   scripts/act.sh push  <сервис>     — отправка образа в локальный реестр localhost:5001 (имитация DockerHub)
#   scripts/act.sh all                — весь конвейер, итог по каждому job
ACT="act -W .github/workflows/ci-cd.yml -P ubuntu-latest=catthehacker/ubuntu:act-latest --container-architecture linux/arm64"
PUSH="--var DOCKERHUB_PUSH=true --var DOCKERHUB_USERNAME=localhost:5001/ikbo-63-23 --env REGISTRY=localhost:5001"
FILTER='Run Main|passed|failed|image OK|digest|refers to|Job succeeded|Job failed|Failure'
case "$1" in
  test)  $ACT -j test  --matrix service:"$2" 2>&1 | grep -E "$FILTER" | sed 's/^\[[^]]*\] *//' ;;
  build) $ACT -j build --matrix service:"$2" 2>&1 | grep -E "$FILTER" | sed 's/^\[[^]]*\] *//' ;;
  push)  $ACT -j push-to-dockerhub --matrix service:"$2" $PUSH 2>&1 | grep -E "$FILTER" | sed 's/^\[[^]]*\] *//' ;;
  all)   $ACT $PUSH 2>&1 | grep -E "Job succeeded|Job failed" | sed 's/^\[\([^]]*\)\].*Job \(succeeded\|failed\)/\2: \1/' ;;
  *) echo "usage: scripts/act.sh test|build|push <service> | all"; exit 1 ;;
esac
