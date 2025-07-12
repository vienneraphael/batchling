# batchling

<div align="center">
<img src="./docs/assets/images/batchling.png" alt="batchling logo" width="500" role="img">
</div>

batchling is a python library to abstract GenAI Batch API usage. It provides a simple interface to create, manage and run experiments on any OpenAI-compatible provider.

Key features include:

- **Fully Local Batch Management**: Store experiments locally in a sqlite database
- **Multi-provider support**: Support for any OpenAI batch API compatible provider (OpenAI, Groq, Gemini, etc.)
- **Structured output generation**: Generate structured outputs with pydantic models in Batch APIs
- **Error handling**: Easily retrieve and re-run batch failed samples
- **Batch visualization**: Visualize any experiment alone or in a group
- **Ease of Use**: Messages and placeholders formatting for easy batching
- **Smart RPM/TPM**: Automatically calculate the RPM/TPM of the experiments and manages batch splitting/merging

## Installation

```bash
pip install batchling
```

## Quick Start

### Create a simple experiment

```python
from batchling import ExperimentManager

em = ExperimentManager()

messages = [
    {
        "role": "system",
        "content": "You are a helpful assistant."
    },
    {
        "role": "user",
        "content": "What is your name? Mine is {name}"
    }
]

placeholders = [
    {"name": "John Doe"},
    {"name": "Jane Doe"},
]

experiment = em.start_experiment(
    experiment_id="my-experiment-1",
    model="gpt-4o-mini",
    name="My first experiment",
    description="Experimenting with gpt-4o-mini",
    template_messages=messages,
    placeholders=placeholders,
    input_file_path="path/to/write/input.jsonl",
)

# write the input file with right format
experiment.setup()

# submit file and batch to provider
experiment.start()

# monitor experiment status
print(experiment.status)

# get results
results = experiment.get_results()

```
