# batchling

<div align="center">
<img src="./docs/assets/images/batchling.png" alt="batchling logo" width="500" role="img">
</div>
<p align="center">
    <em>batchling is the universal GenAI Batch API client. Create, manage and run experiments on any OpenAI-compatible provider.</em>
</p>
<p align="center">
<a href="https://github.com/vienneraphael/batchling/actions/workflows/ci.yml" target="_blank">
    <img src="https://github.com/vienneraphael/batchling/actions/workflows/ci.yml/badge.svg" alt="CI">
<a href="https://pypi.org/project/batchling" target="_blank">
    <img src="https://img.shields.io/pypi/v/batchling?color=%2334D058&label=pypi%20package" alt="Package version">
</a>
<a href="https://pypi.org/project/batchling" target="_blank">
    <img src="https://img.shields.io/pypi/pyversions/batchling.svg?color=%2334D058" alt="Supported Python versions">
</a>
</p>

---

batchling is a python library to abstract GenAI Batch API usage. It provides a simple interface to create, manage and run experiments on any OpenAI-compatible provider.

## What is a Batch API?

Batch APIs enable you to process large volumes of requests asynchronously (usually at 50% lower cost compared to real-time API calls). It's perfect for workloads that don't need immediate responses such as:

- Running evaluations and data analysis
- Classifying large datasets
- Offline summarization
- Synthetic data generation
- Dataset processing and transformations
- Structured Data Extraction

Compared to using standard endpoints directly, Batch API offers:

- Better cost efficiency: usually 50% cost discount compared to synchronous APIs
- Higher rate limits: Substantially more headroom with separate rate limit pools
- Large-scale support: Process thousands of requests per batch
- Flexible completion: Best-effort completion within 24 hours with progress tracking

## Why use batchling?

Batch APIs that are OpenAI-compatible offer clear and simple functionality. However, some aspects of managing batches are not straightforward:

- **File Management**: it's easy to get lost with tons of local files
- **Error Handling**: it's not easy to retrieve and re-run batch failed samples automatically
- **Structured Output Generation**: generating structured outputs with pydantic models in Batch APIs requires some tricks and is tiresome
- **Templating Prompts**: it can get scrappy very quickly when you have to do prompt injection in multiple scenarios

_batchling aims to solve these issues by providing a simple interface to create, manage and run experiments on any OpenAI-compatible provider._

## Features

Key features include:

- **Fully Local Batch Management**: Store experiments locally in a sqlite database and manage them with a CLI
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
