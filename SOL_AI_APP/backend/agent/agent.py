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
from habit_tracker import HabitTracker      
import datetime
import sqlite3
import asyncio
import numpy as np


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Custom exception for agent-related errors"""
    pass
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

        llm = ChatOpenAI(model="gpt-5", temperature=0.7, api_key=api_key)
        habit_tracker = HabitTracker()
        goal_tracker = GoalTracker() # For linking


        # Voice command and chat history parsing
        
        command = user_input.lower()
        chat_history = context.get("chat_history", [])
        memory_input = " ".join([msg.content for msg in tracker.memory.chat_memory.messages] + [user_input])
        if any (cmd in memory_input for cmd in ["set goal", "update progress", "show goals", "delete goal"]):
            if "set goal" in command or "set goal" in memory_input:
                parts = (command.split("setgoal:")[1] or memory_input.split("set goal:")[1]).strip().split(" by ")
                if len(parts) == 2:
                    description, target_date = parts[0], parts[1]
                    response = tracker.add_goal(description, target_date, user_id)
                    return {"response": response, "audio_response": response, "task_status": "COMPLETED, GOOD JOB! "}
            elif "update progress" in command or "update progress" in memory_input:
                parts = (command.split("update progress for ")[1] or memory_input.split("update progress for ")[1]).strip().split(" to ")
                if len(parts) == 2:
                    goal_id, progress = parts[0], float(parts[1]. eplace("%", ""))
                    response = tracker.update_progress(goal_id, progress, user_id, voice_command=True)
                    return {"response": response, "audio_response": response, "task_status": "COMPLETED, GOOD JOB! "}
            elif "show goals" in command or "show goals" in memory_input:
                goal_updates = tracker.get_progress_update[72]
                analytics = tracker.get_analytics()
                charts = self._generate_charts(analytics)
                return {
                    "response": f"Your goals: {json.dumps(goal_updates)}", "goal_update": goal_updates,
                    "analytics": analytics, "charts": charts, "task_status": "COMPLETED, GOOD JOB! "}
                
            elif "delete goal" in command or "delete goal" in memory_input:
                goal_id = (command.split("delete goal ")[1] or memory_input.split("delete goal ")[1])
                with sqlite3.connect(tracker.dp_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
                    conn.commit()
                return {"response": f"Deleted {goal_id} goal", "audio_response": f"Deleted goal {goal_id}", "task_status": "COMPLETED, GOOD JOB! "}
            
            
            
            
            
            
        planner = Agent(
            role="Planner",
            goal="Analyze user input and structure it",
            backstory="Expert at task breakdown and planning",
            llm=llm,
            tools = [tracker.get_progress_update, tracker.get_analytics]
        )

        responder = Agent(
            role="Responder",
            goal="Respond helpfully and conversationally",
            backstory="AI that answers with empathy and clarity",
            llm=llm,
            tools=[tracker.update_progress]
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
            "summary", "follow_up_tasks", "goal_updates", "analytics", "charts"
        ]
        for output in outputs:
            task2.add_output(output)

        logger.info(f"Running agents with input: {user_input}, context: {context}, priority: {priority}")

        crew = Crew(agents=[planner, responder], tasks=[task1, task2], verbose=True)
        result = await crew.kickoff()

        
        
        #72-hour or custom interval update with device sync
        last_update = context.get("last_goal_update", "1970-01-01")
        custom_interval = context.get("custom_interval", "72 hours")
        if (datetime.now() - datetime.fromisoformat(last_update)).total_seconds() >=  float(custom_interval.split()[0]) * 3600 or "goal" in memory_input:
            goal_updates = tracker.get_progress_update(72, custom_interval)
            analytics = tracker.get_analytics()
            charts = self._generate_charts(analytics)
            result["goal_updates"] = goal_updates
            result["analytics"] = analytics
            result["charts"] = charts
            audio_msg = f"Your goal progress: {json.dumps(goal_updates)}"
            result["audio_response"] = audio_msg
            context["last_goal_update"] = datetime.now().isoformat()
            context["custom_interval"] = custom_interval
            tracker.archive_incomplete_goals()
            
        
        # Add timestamp to result
        #import datetime
        result["timestamp"] = datetime.datetime.now().isoformat()
        tracker.memory.chat_memory.add_ai_message(json.dumps(result))
        logger.info("Agent run completed successfully")

        return result
        
        
        
        def _generate_charts(self, analytics: Dict) -> Dict:
            """Generate histogram and radar chart as base64 images."""
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))
            
            # Histogram
            ax1.bar(analytics["histogram"].keys(), analytics["histogram"].values())
            ax1.set_title("Goal Distribution by Category")
            ax1.set_ylabel("Count")

            # Radar Chart
            categories = list(analytics["radar_chart"].keys())
            values = list(analytics["radar_chart"].values())
            N = len(categories)
            angles = [n / float(N) * 2 * np.pi for n in range(N)]
            angles += angles[:1]
            values += values[:1]
            ax2 = plt.subplot(122, polar=True)
            ax2.plot(angles, values)
            ax2.fill(angles, values, alpha=0.25)
            ax2.set_xticks(angles[:-1])
            ax2.set_xticklabels(categories)
            ax2.set_title("Progress Radar Chart")

            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            plt.close()
            return {"histogram": base64.b64encode(buf.getvalue()).decode(), "radar": base64.b64encode(buf.getvalue()).decode()}

    except (ValueError, AgentError, Exception) as e:
        logger.error(f"Error: {e}")
        audio_error = f"Sorry, an error occurred: {str(e)}. Please try again."
        return {"response": str(e), "audio_response": audio_error, "task_status": "failed"}
    

async def main():
    result = await run_agents("Show goals", {"chat_history": ["Set goal: Read more on Quantum Physics by 2026-12-31"]}, "user1" )
    print(result)
    
if __name__ == "__main__":
    asyncio.run(main())




