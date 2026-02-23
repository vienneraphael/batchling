import asyncio

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.messages import AIMessage

from batchling import batchify

load_dotenv()


async def build_tasks() -> list:
    """Build LangChain requests."""
    agent = create_agent(
        model="openai:gpt-4.1-mini",
    )
    questions = [
        "Who is the best French painter? Answer in one short sentence.",
        "What is the capital of France?",
    ]
    return [
        agent.ainvoke(
            input={
                "messages": [
                    {"role": "user", "content": question},
                ]
            }
        )
        for question in questions
    ]


async def main() -> None:
    """Run the LangChain example."""
    tasks = await build_tasks()
    responses = await asyncio.gather(*tasks)
    for response in responses:
        for message in response["messages"]:
            if isinstance(message, AIMessage):
                print(f"{message.response_metadata['model_name']} answer:\n{message.content}\n")


async def run_with_batchify() -> None:
    """Run `main` inside `batchify` for direct script execution."""
    async with batchify():
        await main()


if __name__ == "__main__":
    asyncio.run(run_with_batchify())
