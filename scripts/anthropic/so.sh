#!/bin/bash

batchling create\
 --name anthropic_so\
 --model "claude-haiku-4-5-20251001"\
 --title "experiment haiku"\
 --description "experiment testing claude-3-haiku-20240307"\
 --raw-file-path tests/test_data/raw_file_countries_anthropic.jsonl\
 --processed-file-path input_capitals_anthropic_so.jsonl\
 --provider anthropic\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_anthropic_so.jsonl\
 --response-format-path tests/test_data/city_schema.json\
 --start
