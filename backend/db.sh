#!/usr/bin/env bash
set -e

docker run --name hse-ai-news-postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=hse_ai_news \
  -p 5432:5432 \
  -d postgres:16