#!/bin/bash

batchling create\
 --name anthropic-reasoning\
 --model "claude-haiku-4-5-20251001"\
 --title "Anthropic reasoning experiment"\
 --description "Testing Anthropic with thinking-budget"\
 --raw-file-path tests/test_data/raw_file_countries_anthropic.jsonl\
 --processed-file-path input_capitals_anthropic_reasoning.jsonl\
 --provider anthropic\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_anthropic_reasoning.jsonl\
 --thinking-budget 1024\
 --start
