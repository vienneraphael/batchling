#!/bin/bash

batchling create\
 --name openai_multimodal\
 --model "gpt-4o"\
 --title "exp name"\
 --description "exp description"\
 --raw-file-path tests/test_data/raw_file_multimodal.jsonl\
 --processed-file-path input_capitals_openai_multimodal.jsonl\
 --provider openai\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_openai_multimodal.jsonl\
 --start
