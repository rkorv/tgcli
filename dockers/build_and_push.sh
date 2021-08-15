#!/bin/bash
cd "$(dirname "$0")"

cd ../

# docker buildx create --name tgcli_builder
# docker buildx use tgcli_builder
# docker login

docker buildx build --push -f ./dockers/Dockerfile.tgcli --platform linux/arm/v7,linux/arm64/v8,linux/amd64 --tag rkorv/tgcli:latest .
docker buildx build --push -f ./dockers/Dockerfile.toolbox --platform linux/amd64 --tag rkorv/tgcli_toolbox:latest .
