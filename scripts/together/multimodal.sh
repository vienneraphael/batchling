#!/bin/bash

batchling create\
 --name together_multimodal\
 --model "google/gemma-3n-E4B-it"\
 --title "testing gemma-3n-E4B-it"\
 --description "experiment testing gemma-3n-E4B-it"\
 --raw-file-path tests/test_data/raw_file_multimodal.jsonl\
 --processed-file-path input_capitals_together_multimodal.jsonl\
 --provider together\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_together_multimodal.jsonl\
 --start
