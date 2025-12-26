#!/bin/bash

# Test gemini-3-pro-preview with thinking-level
batchling create\
 --name gemini-reasoning-level\
 --model "gemini-3-pro-preview"\
 --title "Gemini reasoning experiment with thinking-level"\
 --description "Testing gemini-3-pro-preview with thinking-level"\
 --raw-file-path tests/test_data/raw_file_countries.jsonl\
 --processed-file-path input_capitals_gemini_reasoning_level.jsonl\
 --provider gemini\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_gemini_reasoning_level.jsonl\
 --thinking-level high\
 --start

# Test gemini-2.5-flash with thinking-budget
batchling create\
 --name gemini-reasoning-budget\
 --model "gemini-2.5-flash"\
 --title "Gemini reasoning experiment with thinking-budget"\
 --description "Testing gemini-2.5-flash with thinking-budget"\
 --raw-file-path tests/test_data/raw_file_countries.jsonl\
 --processed-file-path input_capitals_gemini_reasoning_budget.jsonl\
 --provider gemini\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_gemini_reasoning_budget.jsonl\
 --thinking-budget 1000\
 --start
