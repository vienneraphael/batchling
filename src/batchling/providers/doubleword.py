from batchling.providers.openai import OpenAIExperiment


class DoublewordExperiment(OpenAIExperiment):
    BASE_URL: str = "https://api.doubleword.ai/v1"
