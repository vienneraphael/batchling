#!/bin/bash

batchling create\
 --name mistral_so\
 --model "mistral-small-latest"\
 --title "testing mistral-small-latest"\
 --description "experiment testing mistral-small-latest"\
 --raw-file-path tests/test_data/raw_file_countries.jsonl\
 --processed-file-path input_capitals_mistral_so.jsonl\
 --provider mistral\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_mistral_so.jsonl\
 --response-format-path tests/test_data/city_schema.json\
 --start
