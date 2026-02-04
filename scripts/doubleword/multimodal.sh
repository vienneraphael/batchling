#!/bin/bash

batchling create\
 --name doubleword_multimodal\
 --model "Qwen/Qwen3-VL-235B-A22B-Instruct-FP8"\
 --title "exp name"\
 --description "exp description"\
 --raw-file-path tests/test_data/raw_file_multimodal.jsonl\
 --processed-file-path input_capitals_dbw_multimodal.jsonl\
 --provider doubleword\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_dbw_multimodal.jsonl\
 --start
