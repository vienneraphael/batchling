#!/bin/bash

batchling create\
 --name groq_multimodal\
 --model "meta-llama/llama-4-maverick-17b-128e-instruct"\
 --title "testing llama-4-maverick-17b-128e-instruct"\
 --description "experiment testing llama-4-maverick-17b-128e-instruct"\
 --raw-file-path tests/test_data/raw_file_multimodal.jsonl\
 --processed-file-path input_capitals_groq_multimodal.jsonl\
 --provider groq\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_groq_multimodal.jsonl\
 --start
