#!/bin/bash

NETWORK_NAME="bsm_db_service" # <-- Change it for custom name

if ! docker network ls --format '{{.Name}}' | grep -qx "$NETWORK_NAME"; then
    docker network create -d bridge "$NETWORK_NAME"
else
    echo "Network '$NETWORK_NAME' already exists, skipping"
fi

docker compose -f compose.yml up -d
