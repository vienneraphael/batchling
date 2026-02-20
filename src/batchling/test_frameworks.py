import asyncio

from dotenv import load_dotenv
from langchain.agents import create_agent
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


async def langchain_tasks():
    agent = create_agent(
        model="openai:gpt-4.1-mini",
    )
    return [
        agent.ainvoke(
            {
                "messages": [
                    {"role": "user", "content": "What is the best French painter?"},
                ]
            }
        ),
        agent.ainvoke(
            {
                "messages": [
                    {"role": "user", "content": "Where does 'hello world' come from?"},
                ]
            }
        ),
    ]


async def main(framework: str):
    match framework:
        case "pydantic_ai":
            tasks = await pydantic_ai_tasks()
        case "langchain":
            tasks = await langchain_tasks()
    responses = await asyncio.gather(*tasks)
    print(responses)
