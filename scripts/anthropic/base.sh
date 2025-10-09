#!/bin/bash

batchling create\
 --name anthropic\
 --model "claude-3-haiku-20240307"\
 --title "experiment haiku"\
 --description "experiment testing claude-3-haiku-20240307"\
 --raw-file-path tests/test_data/raw_file_countries.jsonl\
 --processed-file-path input_capitals_anthropic.jsonl\
 --provider anthropic\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_anthropic.jsonl\
 --start\
