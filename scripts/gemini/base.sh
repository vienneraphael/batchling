#!/bin/bash

batchling create\
 --id gemini\
 --model "gemini-2.0-flash"\
 --name "exp name"\
 --description "exp description"\
 --raw-file-path tests/test_data/raw_file_countries.jsonl\
 --processed-file-path input_capitals_gemini.jsonl\
 --provider gemini\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_gemini.jsonl
