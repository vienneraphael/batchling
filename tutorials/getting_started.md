# Batchling Getting Started Tutorial

In this tutorial, we will create a simple, end-to-end batch experiment using Batchling CLI.

## 0. Batchling introduction

Batchling uses a local database to store your experiments and results.

It works as follows:

1. You create an experiment. At this point the experiment is only created locally in db.
2. You setup the experiment. At this point the experiment is setup locally and the input file is written. All batch APIs require to send a `.jsonl` file to their server, this step writes the input file in the right format.
3. You start the experiment. At this point the experiment is started and the input file is sent to the provider.
4. You retrieve the results. After waiting for the experiment to complete, you can retrieve the results locally, they are automatically downloaded.

## 1. Install Batchling

```bash
pip install batchling
```

## 2. Prepare the data

Create a `raw_requests.jsonl` file with the following content:

```json
{"system_prompt": "You are a helpful assistant.", "messages": [{"role": "user", "content": "What is the capital of France?"}]}
{"system_prompt": "You are a helpful assistant.", "messages": [{"role": "user", "content": "What is the capital of Italy?"}]}
```

NOTE: if you use the `anthropic` provider, you will need to provide the `max_tokens` parameter as it is required by anthropic. You can set it to 100 for this tutorial.

```json
{"system_prompt": "You are a helpful assistant.", "messages": [{"role": "user", "content": "What is the capital of France?"}], "max_tokens": 100}
{"system_prompt": "You are a helpful assistant.", "messages": [{"role": "user", "content": "What is the capital of Italy?"}], "max_tokens": 100}
```

## 3. Create an experiment

Run this command to create an experiment, you can switch the provider for any of the supported providers and the model for the model of your choice that is supported by the provider you entered.
Make sure to call your API key in your `.env` file with the right name:

- openai <> `OPENAI_API_KEY`
- mistral <> `MISTRAL_API_KEY`
- together <> `TOGETHER_API_KEY`
- groq <> `GROQ_API_KEY`
- gemini <> `GEMINI_API_KEY`
- anthropic <> `ANTHROPIC_API_KEY`
- doubleword <> `DOUBLEWORD_API_KEY`

We recommend using a provider from which you already have an API key from to get started quickly.

```bash
batchling create\
 --name my-experiment-1\
 --model your-favorite-model\
 --title "exp name"\
 --description "exp description"\
 --raw-file-path raw_requests.jsonl\
 --provider your-provider\
 --endpoint /v1/chat/completions\
 --processed-file-path ./input_capitals_openai.jsonl\
 --results-file-path result_capitals.jsonl\
```

## 4. Start your experiment

Run this command to start your experiment:

```bash
batchling start my-experiment-1
```

## 5. Check experiment status

Run this command to check the experiment status:

```bash
batchling get my-experiment-1
```

For this tutorial, it should take a few seconds to a few minutes to complete because we only have 3 requests in the batch.

## 7. Retrieve the results

Once the experiment is completed (check that by checking the status), you can retrieve the results:

```bash
batchling results my-experiment-1
```

Take a look at the `result_capitals.jsonl` file to see the results.

You should see the corresponding results for each of your requests!

## Conclusion

Congratulations, you have created your first Batchling experiment, from start to finish!

Now you can:

- Explore the python SDK (see [README.md](../README.md))
- Trying other providers / use-cases (evaluation, batch structured outputs..)
- Give me some feedback, suggestions or ask questions!
