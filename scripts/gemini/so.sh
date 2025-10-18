#!/bin/bash

batchling create\
 --name gemini_so\
 --model "gemini-2.0-flash"\
 --title "exp name"\
 --description "exp description"\
 --raw-file-path tests/test_data/raw_file_countries.jsonl\
 --processed-file-path input_capitals_gemini.jsonl\
 --provider gemini\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_gemini.jsonl\
 --response-format-path tests/test_data/city_schema.json\
 --start
