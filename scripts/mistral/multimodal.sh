#!/bin/bash

batchling create\
 --name mistral_multimodal\
 --model "mistral-small-2506"\
 --title "testing mistral-small-2506"\
 --description "experiment testing mistral-small-2506"\
 --raw-file-path tests/test_data/raw_file_multimodal.jsonl\
 --processed-file-path input_capitals_mistral_multimodal.jsonl\
 --provider mistral\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_mistral_multimodal.jsonl\
 --start
