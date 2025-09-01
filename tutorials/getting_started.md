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

Create a `template_messages.jsonl` file with the following content:

```json
{"role": "system", "content": "You are a helpful assistant."}
{"role": "user", "content": "What is the capital of {country}?"}
```

Create a `placeholders.jsonl` file with the following content:

```json
{"name": "France"}
{"name": "Germany"}
{"name": "Italy"}
```

## 3. Create an experiment

Run this command to create an experiment, you can switch the provider for any of the supported providers, make sure to call your API key in your `.env` file with the right name:

- openai <> `OPENAI_API_KEY`
- mistral <> `MISTRAL_API_KEY`
- together <> `TOGETHER_API_KEY`
- groq <> `GROQ_API_KEY`
- gemini <> `GEMINI_API_KEY`
- anthropic <> `ANTHROPIC_API_KEY`

We recommend using a provider from which you already have an API key from to get started quickly.

```bash
batchling create\
 --id test\
 --model gpt-4o\
 --name "exp name"\
 --description "exp description"\
 --template-messages-path template_messages.jsonl\
 --placeholders-path placeholders.jsonl\
 --provider your-provider\
 --endpoint /v1/chat/completions\
 --input-file-path input_capitals_openai.jsonl\
 --output-file-path result_capitals.jsonl\
```

NOTE: if you use the `anthropic` provider, you will need to provide the `max-tokens-per-request` parameter as it is required by anthropic. You can set it to 100 for this tutorial.

## 4. Setup your experiment

Run this command to setup your experiment:

```bash
batchling setup test
```

## 5. Start your experiment

Run this command to start your experiment:

```bash
batchling start test
```

## 6. Poll for results

Run this command to poll for results:

```bash
batchling get test
```

For this tutorial, it should take a few seconds to a few minutes to complete because we only have 3 requests in the batch.

## 7. Retrieve the results

Once the experiment is completed (check that by polling), you can retrieve the results:

```bash
batchling results test
```

Take a look at the `result_capitals.jsonl` file to see the results.

You should see the corresponding results for each of your requests!

## Conclusion

Congratulations, you have created your first Batchling experiment, from start to finish!

Now you can:

- Explore the python SDK (see [README.md](../README.md))
- Trying other providers / use-cases (evaluation, batch structured outputs..)
- Give me some feedback, suggestions or ask questions!
