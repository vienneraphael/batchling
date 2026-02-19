import asyncio

from dotenv import load_dotenv
from pydantic_ai import Agent

load_dotenv()


async def pydantic_ai_tasks():
    agent = Agent(
        model="openai:gpt-5-nano",
        tools=[],
    )
    return [
        agent.run("What is the best French painter?"),
        agent.run("Where does 'hello world' come from?"),
    ]


async def main(framework: str):
    match framework:
        case "pydantic_ai":
            tasks = await pydantic_ai_tasks()
    responses = await asyncio.gather(*tasks)
    print(responses)
