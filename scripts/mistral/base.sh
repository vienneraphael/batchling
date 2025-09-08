batchling create\
 --id mistral\
 --model "mistral-small-latest"\
 --name "testing mistral-small-latest"\
 --description "experiment testing mistral-small-latest"\
 --raw-file-path tests/test_data/raw_file_countries.jsonl\
 --processed-file-path input_capitals_mistral.jsonl\
 --provider mistral\
 --endpoint /v1/chat/completions\
 --results-file-path output/result_capitals_mistral.jsonl
