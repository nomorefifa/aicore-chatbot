#!/bin/bash
docker run -d \
  --name weaviate \
  --restart always \
  -p 8080:8080 \
  -p 50051:50051 \
  -v /home/weaviate_data:/var/lib/weaviate \
  -e QUERY_DEFAULTS_LIMIT=25 \
  -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED=true \
  -e PERSISTENCE_DATA_PATH=/var/lib/weaviate \
  -e DEFAULT_VECTORIZER_MODULE=none \
  -e CLUSTER_HOSTNAME=node1 \
  cr.weaviate.io/semitechnologies/weaviate:1.28.4
