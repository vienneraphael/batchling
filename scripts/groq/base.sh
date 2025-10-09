#!/bin/bash

batchling create\
 --name groq\
 --model "llama-3.1-8b-instant"\
 --title "testing llama-3.1-8b-instant"\
 --description "experiment testing llama-3.1-8b-instant"\
 --raw-file-path tests/test_data/raw_file_countries.jsonl\
 --processed-file-path input_capitals_groq.jsonl\
 --provider groq\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_groq.jsonl\
 --start
