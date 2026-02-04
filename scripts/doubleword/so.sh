#!/bin/bash

batchling create\
 --name doubleword_so\
 --model "Qwen/Qwen3-VL-235B-A22B-Instruct-FP8"\
 --title "exp name"\
 --description "exp description"\
 --raw-file-path tests/test_data/raw_file_countries.jsonl\
 --processed-file-path input_capitals_dbw_so.jsonl\
 --provider doubleword\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_dbw_so.jsonl\
 --response-format-path tests/test_data/city_schema.json\
 --start
