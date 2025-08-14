# Merged Microservice-Ready Agent with Future Integration Support
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
import importlib
import asyncio
import json
import sqlite3
import logging
import io
import base64
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt

# CrewAI and LangChain imports
from crewai import Agent, Crew, Task
from langchain.chat_models import ChatOpenAI
from dotenv import load_dotenv
import os

# HTTP and error handling
from tenacity import retry, stop_after_attempt, wait_exponential
from requests.exceptions import RequestException
import httpx

# Your existing trackers
from goal_tracker import GoalTracker
from habit_tracker import HabitTracker

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


# =================== MICROSERVICE ARCHITECTURE ===================

class BaseService(ABC):
    """Abstract base class for all microservices - ensures consistent interface"""
    
    def __init__(self, name: str, tracker_instance, user_id: str):
        self.name = name
        self.tracker = tracker_instance
        self.user_id = user_id
        self.priority = 0
    
    @abstractmethod
    def get_command_triggers(self) -> List[str]:
        """Return list of command keywords this service handles"""
        pass
    
    @abstractmethod
    def can_handle(self, command: str, memory_input: str, context: Dict) -> bool:
        """Determine if this service can handle the given command"""
        pass
    
    @abstractmethod
    async def process_command(self, command: str, memory_input: str, context: Dict) -> Optional[Dict]:
        """Process the command and return response"""
        pass
    
    @abstractmethod
    def get_memory_input(self, user_input: str) -> str:
        """Generate memory input for this service"""
        pass
    
    def get_tools(self) -> List:
        """Return tools that this service provides for CrewAI agents"""
        return []


class GoalTrackerService(BaseService):
    """Goal tracking microservice with CrewAI integration"""
    
    def __init__(self, goal_tracker: GoalTracker, user_id: str):
        super().__init__("goal_tracker", goal_tracker, user_id)
        self.priority = 10  # Higher priority - more specific commands
    
    def get_command_triggers(self) -> List[str]:
        return ["set goal", "update progress", "show goals", "delete goal"]
    
    def can_handle(self, command: str, memory_input: str, context: Dict) -> bool:
        return any(cmd in memory_input for cmd in self.get_command_triggers())
    
    def get_memory_input(self, user_input: str) -> str:
        return " ".join([msg.content for msg in self.tracker.memory.chat_memory.messages] + [user_input])
    
    def get_tools(self) -> List:
        """Return CrewAI tools for this service"""
        return [
            self.tracker.get_progress_update,
            self.tracker.get_analytics,
            self.tracker.update_progress
        ]
    
    async def process_command(self, command: str, memory_input: str, context: Dict) -> Optional[Dict]:
        try:
            if "set goal" in command or "set goal" in memory_input:
                parts = (command.split("set goal:")[1] if "set goal:" in command 
                        else memory_input.split("set goal:")[1]).strip().split(" by ")
                if len(parts) == 2:
                    description, target_date = parts[0], parts[1]
                    response = self.tracker.add_goal(description, target_date, self.user_id)
                    return {"response": response, "audio_response": response, "task_status": "completed"}
            
            elif "update progress" in command or "update progress" in memory_input:
                parts = (command.split("update progress for ")[1] if "update progress for " in command 
                        else memory_input.split("update progress for ")[1]).split(" to ")
                if len(parts) == 2:
                    goal_id, progress = parts[0], float(parts[1].replace("%", ""))
                    response = self.tracker.update_progress(goal_id, progress, self.user_id, voice_command=True)
                    return {"response": response, "audio_response": response, "task_status": "completed"}
            
            elif "show goals" in command or "show goals" in memory_input:
                goal_updates = self.tracker.get_progress_update(72)
                analytics = self.tracker.get_analytics()
                charts = self._generate_charts(analytics)
                return {
                    "response": f"Your goals: {json.dumps(goal_updates)}", 
                    "goal_update": goal_updates,
                    "analytics": analytics, 
                    "charts": charts, 
                    "task_status": "COMPLETED, GOOD JOB!"
                }
            
            elif "delete goal" in command or "delete goal" in memory_input:
                goal_id = (command.split("delete goal ")[1] if "delete goal " in command 
                          else memory_input.split("delete goal ")[1])
                with sqlite3.connect(self.tracker.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
                    conn.commit()
                return {"response": f"Deleted goal {goal_id}", 
                       "audio_response": f"Deleted goal {goal_id}", "task_status": "completed"}
            
        except Exception as e:
            logger.error(f"Error in GoalTrackerService: {e}")
            return {"response": f"Error processing goal command: {str(e)}", "task_status": "failed"}
        
        return None
    
    def _generate_charts(self, analytics: Dict) -> Dict:
        """Generate histogram and radar chart as base64 images"""
        try:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))
            
            # Histogram
            if analytics.get("histogram"):
                ax1.bar(analytics["histogram"].keys(), analytics["histogram"].values())
                ax1.set_title("Goal Distribution by Category")
                ax1.set_ylabel("Count")
            
            # Radar Chart
            if analytics.get("radar_chart"):
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
            chart_b64 = base64.b64encode(buf.getvalue()).decode()
            return {"histogram": chart_b64, "radar": chart_b64}
            
        except Exception as e:
            logger.error(f"Error generating charts: {e}")
            return {"error": f"Chart generation failed: {str(e)}"}


class HabitTrackerService(BaseService):
    """Habit tracking microservice with CrewAI integration"""
    
    def __init__(self, habit_tracker: HabitTracker, user_id: str):
        super().__init__("habit_tracker", habit_tracker, user_id)
        self.priority = 5  # Lower priority - broader triggers
    
    def get_command_triggers(self) -> List[str]:
        return ["add habit", "log habit", "check habits"]
    
    def can_handle(self, command: str, memory_input: str, context: Dict) -> bool:
        repeated_words = self._check_repeated_words(memory_input)
        return repeated_words >= 5 or "log habit" in memory_input
    
    def get_memory_input(self, user_input: str) -> str:
        return " ".join([msg.content for msg in self.tracker.memory.chat_memory.messages] + [user_input])
    
    def get_tools(self) -> List:
        """Return CrewAI tools for this service"""
        return [
            self.tracker.get_analytics,
            self.tracker.get_streak,
            self.tracker.log_habit,
            self.tracker.add_habit
        ]
    
    async def process_command(self, command: str, memory_input: str, context: Dict) -> Optional[Dict]:
        try:
            if "add habit" in command or "add habit" in memory_input:
                parts = (command.split("add habit:")[1] if "add habit:" in command 
                        else memory_input.split("add habit:")[1]).strip().split(" category ")
                if len(parts) == 2:
                    description, category = parts[0], parts[1]
                    response = self.tracker.add_habit(description, category, "daily", self.user_id)
                    return {"response": response, "audio_response": response, "task_status": "completed"}
            
            elif "log habit" in command or "log habit" in memory_input:
                parts = (command.split("log habit for ")[1] if "log habit for " in command 
                        else memory_input.split("log habit for ")[1]).split(" note ")
                habit_id = parts[0]
                note = parts[1] if len(parts) > 1 else None
                response = self.tracker.log_habit(habit_id, self.user_id, completed=True, note=note, voice_command=True)
                return {"response": response, "audio_response": response, "task_status": "completed"}
            
            elif "check habits" in command or "check habits" in memory_input:
                analytics = self.tracker.get_analytics(self.user_id)
                return {"response": f"Your habits analytics: {json.dumps(analytics)}", 
                       "analytics": analytics, "task_status": "completed"}
                
        except Exception as e:
            logger.error(f"Error in HabitTrackerService: {e}")
            return {"response": f"Error processing habit command: {str(e)}", "task_status": "failed"}
        
        return None
    
    def _check_repeated_words(self, memory_input: str) -> int:
        """Check for repeated words in memory input"""
        words = memory_input.lower().split()
        word_counts = {}
        for word in words:
            word_counts[word] = word_counts.get(word, 0) + 1
        return max(word_counts.values()) if word_counts else 0


# FUTURE MICROSERVICES CAN BE EASILY ADDED:

class TaskTrackerService(BaseService):
    """Example future microservice - Task/Todo tracking"""
    
    def __init__(self, task_tracker, user_id: str):
        super().__init__("task_tracker", task_tracker, user_id)
        self.priority = 7
    
    def get_command_triggers(self) -> List[str]:
        return ["add task", "complete task", "list tasks", "delete task"]
    
    def can_handle(self, command: str, memory_input: str, context: Dict) -> bool:
        return any(cmd in memory_input for cmd in self.get_command_triggers())
    
    def get_memory_input(self, user_input: str) -> str:
        return " ".join([msg.content for msg in self.tracker.memory.chat_memory.messages] + [user_input])
    
    async def process_command(self, command: str, memory_input: str, context: Dict) -> Optional[Dict]:
        # Task processing logic would go here
        return {"response": "Task feature coming soon!", "task_status": "pending"}


class BudgetTrackerService(BaseService):
    """Example future microservice - Budget/Expense tracking"""
    
    def __init__(self, budget_tracker, user_id: str):
        super().__init__("budget_tracker", budget_tracker, user_id)
        self.priority = 6
    
    def get_command_triggers(self) -> List[str]:
        return ["add expense", "set budget", "check spending", "budget report"]
    
    def can_handle(self, command: str, memory_input: str, context: Dict) -> bool:
        return any(cmd in memory_input for cmd in self.get_command_triggers())
    
    def get_memory_input(self, user_input: str) -> str:
        return " ".join([msg.content for msg in self.tracker.memory.chat_memory.messages] + [user_input])
    
    async def process_command(self, command: str, memory_input: str, context: Dict) -> Optional[Dict]:
        # Budget processing logic would go here
        return {"response": "Budget feature coming soon!", "task_status": "pending"}


class ServiceRegistry:
    """Registry to manage all available microservices"""
    
    def __init__(self):
        self.services: List[BaseService] = []
        self.service_configs = {}
    
    def register_service(self, service: BaseService):
        """Register a service and sort by priority"""
        self.services.append(service)
        self.service_configs[service.name] = {"service": service, "priority": service.priority}
        # Sort by priority (highest first)
        self.services.sort(key=lambda s: s.priority, reverse=True)
        logger.info(f"Registered service: {service.name} with priority {service.priority}")
    
    def get_services(self) -> List[BaseService]:
        return self.services
    
    def get_all_tools(self) -> List:
        """Get all tools from all services for CrewAI agents"""
        tools = []
        for service in self.services:
            tools.extend(service.get_tools())
        return tools
    
    def add_service_from_config(self, service_config: Dict):
        """Dynamically load and register a service from configuration"""
        try:
            module_name = service_config.get("module")
            class_name = service_config.get("class")
            service_params = service_config.get("params", {})
            
            module = importlib.import_module(module_name)
            service_class = getattr(module, class_name)
            service = service_class(**service_params)
            self.register_service(service)
            logger.info(f"Dynamically loaded service: {class_name}")
        except Exception as e:
            logger.error(f"Failed to load service from config: {e}")


class AgentOrchestrator:
    """Main orchestrator that routes commands to appropriate services and manages CrewAI"""
    
    def __init__(self, user_id: str, llm_model: str = "gpt-4"):
        self.user_id = user_id
        self.registry = ServiceRegistry()
        self.llm = None
        self.llm_model = llm_model
        
    async def setup_services(self, habit_tracker: HabitTracker, goal_tracker: GoalTracker):
        """Initialize and register all services"""
        # Register core services
        self.registry.register_service(GoalTrackerService(goal_tracker, self.user_id))
        self.registry.register_service(HabitTrackerService(habit_tracker, self.user_id))
        
        # Future services can be registered here:
        # self.registry.register_service(TaskTrackerService(task_tracker, self.user_id))
        # self.registry.register_service(BudgetTrackerService(budget_tracker, self.user_id))
        
        logger.info(f"Registered {len(self.registry.get_services())} services")
    
    def setup_llm(self):
        """Initialize LLM for CrewAI"""
        load_dotenv()
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise AgentError("OpenAI API key not found")
        self.llm = ChatOpenAI(model=self.llm_model, temperature=0.7, api_key=api_key)
    
    async def process_with_microservices(self, user_input: str, context: Dict) -> Optional[Dict]:
        """Try to handle command with microservices first"""
        command = user_input.lower()
        
        # Try each service in priority order
        for service in self.registry.get_services():
            try:
                memory_input = service.get_memory_input(user_input)
                
                if service.can_handle(command, memory_input, context):
                    logger.info(f"Service {service.name} handling command: {command}")
                    result = await service.process_command(command, memory_input, context)
                    if result:  # Service successfully processed the command
                        return result
            except Exception as e:
                logger.error(f"Error in service {service.name}: {e}")
                continue
        
        return None  # No service could handle the command
    
    async def process_with_crewai(self, user_input: str, context: Dict, priority: int = 1) -> Dict:
        """Process with CrewAI agents when microservices can't handle it"""
        if not self.llm:
            self.setup_llm()
        
        # Get all tools from registered services
        all_tools = self.registry.get_all_tools()
        
        # Create CrewAI agents with tools from all services
        planner = Agent(
            role="Planner",
            goal="Analyze user input and structure it using available tracking tools",
            backstory="Expert at task breakdown and planning with access to goal and habit tracking",
            llm=self.llm,
            tools=all_tools
        )
        
        responder = Agent(
            role="Responder", 
            goal="Respond helpfully and conversationally using tracking data",
            backstory="AI that answers with empathy and clarity, leveraging user's goals and habits",
            llm=self.llm,
            tools=all_tools
        )
        
        # Create tasks
        task1 = Task(
            description=f"Analyze and break down this request: {user_input}",
            agent=planner,
            expected_output="Structured analysis of the user's request with relevant data"
        )
        
        task2 = Task(
            description="Provide a helpful response based on the analysis and available tools",
            agent=responder,
            expected_output="Clear, empathetic response addressing the user's needs"
        )
        
        # Run CrewAI
        crew = Crew(agents=[planner, responder], tasks=[task1, task2], verbose=True)
        result = crew.kickoff()
        
        # Format result for consistency
        return {
            "response": str(result),
            "audio_response": str(result),
            "task_status": "completed",
            "processed_by": "crewai",
            "timestamp": datetime.now().isoformat()
        }
    
    async def handle_periodic_updates(self, context: Dict, goal_tracker: GoalTracker) -> Dict:
        """Handle 72-hour goal updates and other periodic tasks"""
        try:
            last_update = context.get("last_goal_update", "1970-01-01")
            custom_interval = context.get("custom_interval", "72 hours")
            
            time_since_update = (datetime.now() - datetime.fromisoformat(last_update)).total_seconds()
            interval_seconds = float(custom_interval.split()[0]) * 3600
            
            if time_since_update >= interval_seconds:
                goal_updates = goal_tracker.get_progress_update(72, custom_interval)
                analytics = goal_tracker.get_analytics()
                
                # Generate charts using the service
                goal_service = next((s for s in self.registry.get_services() if s.name == "goal_tracker"), None)
                charts = goal_service._generate_charts(analytics) if goal_service else {}
                
                context["last_goal_update"] = datetime.now().isoformat()
                goal_tracker.archive_incomplete_goals()
                
                return {
                    "goal_updates": goal_updates,
                    "analytics": analytics,
                    "charts": charts,
                    "audio_response": f"Your goal progress: {json.dumps(goal_updates)}",
                    "periodic_update": True
                }
        except Exception as e:
            logger.error(f"Error in periodic updates: {e}")
        
        return {}


async def run_agents(user_input: str, context: dict = None, user_id: str = "default_user", priority: int = 1) -> Dict[str, Any]:
    """Main entry point - enhanced with microservice architecture"""
    try:
        if not user_input:
            raise ValueError("User input cannot be empty")
        
        context = context or {}
        
        # Initialize trackers
        habit_tracker = HabitTracker()
        goal_tracker = GoalTracker()
        
        # Initialize orchestrator
        orchestrator = AgentOrchestrator(user_id)
        await orchestrator.setup_services(habit_tracker, goal_tracker)
        
        logger.info(f"Processing input: {user_input}")
        
        # 1. Try microservices first (faster, more direct)
        microservice_result = await orchestrator.process_with_microservices(user_input, context)
        if microservice_result:
            logger.info("Command handled by microservice")
            
            # Add periodic updates
            periodic_updates = await orchestrator.handle_periodic_updates(context, goal_tracker)
            microservice_result.update(periodic_updates)
            
            # Add memory
            goal_tracker.memory.chat_memory.add_ai_message(json.dumps(microservice_result))
            microservice_result["timestamp"] = datetime.now().isoformat()
            
            return microservice_result
        
        # 2. Fall back to CrewAI for complex queries
        logger.info("Falling back to CrewAI for complex processing")
        crewai_result = await orchestrator.process_with_crewai(user_input, context, priority)
        
        # Add periodic updates
        periodic_updates = await orchestrator.handle_periodic_updates(context, goal_tracker)
        crewai_result.update(periodic_updates)
        
        # Add memory
        goal_tracker.memory.chat_memory.add_ai_message(json.dumps(crewai_result))
        
        return crewai_result
        
    except (ValueError, AgentError, Exception) as e:
        logger.error(f"Error in run_agents: {e}")
        return {
            "response": f"Sorry, an error occurred: {str(e)}",
            "audio_response": f"Sorry, an error occurred: {str(e)}. Please try again.",
            "task_status": "failed",
            "timestamp": datetime.now().isoformat()
        }


# Example of how to add new services dynamically
SERVICE_CONFIGS = [
    {
        "module": "services.task_tracker",
        "class": "TaskTrackerService", 
        "params": {"task_tracker": None, "user_id": "default"}
    },
    {
        "module": "services.budget_tracker",
        "class": "BudgetTrackerService",
        "params": {"budget_tracker": None, "user_id": "default"}
    }
]

async def load_future_services(orchestrator: AgentOrchestrator):
    """Load future services from configuration"""
    for config in SERVICE_CONFIGS:
        try:
            orchestrator.registry.add_service_from_config(config)
        except Exception as e:
            logger.warning(f"Could not load service {config.get('class')}: {e}")


async def main():
    """Test function"""
    result = await run_agents(
        "Show goals", 
        {"chat_history": ["Set goal: Read more on Quantum Physics by 2026-12-31"]}, 
        user_id="user1"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
    