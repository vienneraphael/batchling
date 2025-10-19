#!/bin/bash

batchling create\
 --name openai_so\
 --model "gpt-4o"\
 --title "exp name"\
 --description "exp description"\
 --raw-file-path tests/test_data/raw_file_countries.jsonl\
 --processed-file-path input_capitals_openai_so.jsonl\
 --provider openai\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_openai_so.jsonl\
 --response-format-path tests/test_data/city_schema.json\
 --start
