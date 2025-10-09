#!/bin/bash

batchling create\
 --name together\
 --model "deepseek-ai/DeepSeek-V3"\
 --title "testing DeepSeek-V3"\
 --description "experiment testing DeepSeek-V3"\
 --raw-file-path tests/test_data/raw_file_countries.jsonl\
 --processed-file-path input_capitals_together.jsonl\
 --provider together\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_together.jsonl\
 --response-format-path tests/test_data/city_schema.json\
 --start
