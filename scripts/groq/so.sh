#!/bin/bash

batchling create\
 --name groq\
 --model "openai/gpt-oss-20b"\
 --title "testing openai/gpt-oss-20b"\
 --description "experiment testing openai/gpt-oss-20b"\
 --raw-file-path tests/test_data/raw_file_countries.jsonl\
 --processed-file-path input_capitals_groq.jsonl\
 --provider groq\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_groq.jsonl\
 --response-format-path tests/test_data/city_schema.json\
 --start
