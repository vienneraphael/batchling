#!/bin/bash

batchling create\
 --name anthropic_multimodal\
 --model "claude-3-haiku-20240307"\
 --title "experiment haiku"\
 --description "experiment testing claude-3-haiku-20240307"\
 --raw-file-path tests/test_data/raw_file_multimodal.jsonl\
 --processed-file-path input_capitals_anthropic_multimodal.jsonl\
 --provider anthropic\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_anthropic_multimodal.jsonl\
 --start\
