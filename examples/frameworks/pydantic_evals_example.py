import asyncio

from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_evals import Case, Dataset
from pydantic_evals.evaluators import Contains, EqualsExpected

from batchling import batchify

load_dotenv()


async def run_agent(text: str) -> str:
    """Run the pydantic-ai example."""
    agent = Agent(
        model="openai:gpt-5-nano",
        system_prompt="Convert the input text to uppercase.",
    )
    result = await agent.run(user_prompt=text)
    return result.output


async def evaluate() -> None:
    """Run the pydantic-evals example."""
    # Create a dataset with test cases
    dataset = Dataset(
        cases=[
            Case(
                name="uppercase_basic",
                inputs="hello world",
                expected_output="HELLO WORLD",
            ),
            Case(
                name="uppercase_with_numbers",
                inputs="hello 123",
                expected_output="HELLO 123",
            ),
        ],
        evaluators=[
            EqualsExpected(),  # Check exact match with expected_output
            Contains(value="HELLO", case_sensitive=True),  # Check contains "HELLO"
        ],
    )
    # Run the evaluation
    report = await dataset.evaluate(run_agent)

    # Print the results
    report.print(include_output=True)


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await evaluate()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
