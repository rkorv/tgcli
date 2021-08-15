#!/bin/bash
cd "$(dirname "$0")"

cd ../

docker build -f ./dockers/Dockerfile.tgcli --tag tgcli .
docker build -f ./dockers/Dockerfile.toolbox --tag tgcli_toolbox .
