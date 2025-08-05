from crewai import Agent, Crew, Task
from langchain.chat_models import ChatOpenAI
from dotenv import load_dotenv
import os
from tenacity import retry, stop_after_attempt, wait_exponential
from requests.exceptions import RequestException
import logging
import httpx
from typing import Dict, Any, Optional
from datetime import datetime
import json
import matplotlib.pyplot as plt
import io
import base64
from goal_tracker import GoalTracker


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Custom exception for agent-related errors"""
    pass
'''
my_dict = {"name": 'Dan',
           "age": 12,
           "educated": 'no'
           }
print (my_dict.key)

new_list = list[my_dict.key()]

print (new_list[2])
'''
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry_error_callback=lambda _: None
)
async def make_api_request(url: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Make HTTP request with retry logic and error handling"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=data, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.error("Request timed out")
            raise AgentError("Request timed out")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise AgentError(f"HTTP error: {e}")


async def run_agents(user_input: str, context: dict = None, priority: int = 1) -> Dict[str, Any]:
    """Run agents with error handling and logging"""
    try:
        if not user_input:
            raise ValueError("User input cannot be empty")

        context = context or {}

        # Load environment variables safely
        load_dotenv()
        if not os.getenv("OPENAI_API_KEY"):
            raise AgentError("OpenAI API key not found")

        llm = ChatOpenAI(model="gpt-4", temperature=0.7)
        tracker = GoalTracker()


        # Voice command and chat history parsing

        planner = Agent(
            role="Planner",
            goal="Analyze user input and structure it",
            backstory="Expert at task breakdown and planning",
            llm=llm
        )

        responder = Agent(
            role="Responder",
            goal="Respond helpfully and conversationally",
            backstory="AI that answers with empathy and clarity",
            llm=llm
        )

        # Create and configure tasks with error checking
        task1 = Task(
            description=f"Break this down: {user_input}",
            agent=planner,
            metadata={"priority": priority, "context": context}
        )
        task2 = Task(
            description="Respond to the breakdown",
            agent=responder,
            metadata={"priority": priority, "context": context}
        )

        # Configure task dependencies and inputs
        task1.add_dependency(task2)
        task1.add_input(user_input)
        task1.add_input(context)
        task2.add_input(task1.output)
        task2.add_input(context)

        # Configure task outputs
        outputs = [
            "response", "audio_response", "transcription", "audio_file",
            "text_response", "metadata", "task_status", "task_id",
            "summary", "follow_up_tasks"
        ]
        for output in outputs:
            task2.add_output(output)

        logger.info(f"Running agents with input: {user_input}, context: {context}, priority: {priority}")

        crew = Crew(agents=[planner, responder], tasks=[task1, task2], verbose=True)
        result = crew.kickoff()

        # Add timestamp to result
        import datetime
        result["timestamp"] = datetime.datetime.now().isoformat()
        logger.info("Agent run completed successfully")

        return result

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise
    except AgentError as e:
        logger.error(f"Agent error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise AgentError(f"Unexpected error occurred: {e}")




