#!/bin/bash

batchling create\
 --name openai-reasoning\
 --model "gpt-5-nano"\
 --title "OpenAI reasoning experiment"\
 --description "Testing gpt-5-nano with thinking-level"\
 --raw-file-path tests/test_data/raw_file_countries.jsonl\
 --processed-file-path input_capitals_oai_reasoning.jsonl\
 --provider openai\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_openai_reasoning.jsonl\
 --thinking-level "medium"\
 --start

