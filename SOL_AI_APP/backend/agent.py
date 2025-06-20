from crewai import Agent, Crew, Task
from langchain.chat_models import ChatOpenAI
from dotenv import load_dotenv
import os

load_dotenv()
llm = ChatOpenAI(model="gpt-4", temperature=0.7)

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

def run_agents(user_input: str):
    task1 = Task(description=f"Break this down: {user_input}", agent=planner)
    task2 = Task(description="Respond to the breakdown", agent=responder)
    crew = Crew(agents=[planner, responder], tasks=[task1, task2], verbose=True)
    return crew.kickoff()
