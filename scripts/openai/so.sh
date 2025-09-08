#!/bin/bash

batchling create\
 --id openai\
 --model "gpt-4o"\
 --name "exp name"\
 --description "exp description"\
 --raw-file-path tests/test_data/raw_file_countries.jsonl\
 --processed-file-path input_capitals_oai.jsonl\
 --provider openai\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_openai.jsonl\
 --response-format-path tests/test_data/city_schema.json
