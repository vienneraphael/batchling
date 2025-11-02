#!/bin/bash

batchling create\
 --name gemini_multimodal\
 --model "gemini-2.0-flash"\
 --title "exp name"\
 --description "exp description"\
 --raw-file-path tests/test_data/raw_file_multimodal.jsonl\
 --processed-file-path input_capitals_gemini_multimodal.jsonl\
 --provider gemini\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_gemini_multimodal.jsonl\
 --start
