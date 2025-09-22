#!/bin/bash

./scripts/anthropic/base.sh
./scripts/mistral/base.sh
./scripts/openai/base.sh
./scripts/together/base.sh
./scripts/groq/base.sh
./scripts/gemini/base.sh

batchling start anthropic
batchling start mistral
batchling start openai
batchling start together
batchling start groq
batchling start gemini
