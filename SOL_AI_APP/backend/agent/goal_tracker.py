import sqlite3
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any, Optional
import numpy as np
from crewai.utilities.paths import db_storage_path
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
import os
from dotenv import load_dotenv
import json
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.memory import ConversationBufferMemory
import asyncio
import paho.mqtt.client as mqtt

# configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GoalTracker:
    def __init__(self, db_ptah: str = "goals.db", vector_db: str = "vector_goals"):
        """ Initialize GoalTracker with a database (SQLite, vector DB, and device integration.) and Google class credentials."""
        load_dotenv()
        self.db_path = db_path
        self.vector_db_path = vector_db_path
        self.setup_database()
        self.vector_store = self._setup_vector_db()
        self.google_tasks_service = self._setup_google_tasks()
        self.memory = ConversationBufferMemory(return_messages=True)
        self.mqtt_client = self._setup_mqtt()
        self.last_update = datetime.now()

    def _setup_database(self):
        """ Set up the SQLite database with enhanced goals schema/table"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS goals (
                    id INTEGER PRIMARY KEY, 
                    description TEXT NOT NULL,
                    category TEXT,
                    priority INTEGER,
                    target_date  TEXT,
                    progress REAL,
                    created_at TEXT,
                    last_updated TEXT,
                    status TEXT DEFAULT 'active' 
                    collaborators TEXT
                )    
                    ''')
            conn.commit()


    def _setup_vector_db(self):
        """ Set up FAISS vector database for memory and learning """
        embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
        try:
            return FAISS.load_local(self.vector_db_path, embeddings)
        except:
            return FAISS.from_texts([], embeddings)




    def _setup_google_tasks(self):
        # Set up Google Tasks API client.
        creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
        if not creds_json:
            logger.warning('Google Credentials not found, Google Tasks sync disabled')
            return None
        credentials = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json))
        return build ('tasks', 'v1', credentials=credentials)


    def _setup_mqtt(self):
        """ Set up MQTT for device integration."""
        client = mqtt.Client()
        client.username_pw_set(os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD"))
        client.connect(os.getenv("MQTT_BROKER", "localhost"), 1883, 60)
        return client


    def add_goal(self, description: str, target_date: str, user_id: str = "personal",priority: int =1, progress: float = 0.0, collaborators: List[str] = None) -> str:
        """ Add a goal with collaboration and vector storage."""
        goal_id = f" goal_{datetime.now().strftime('%y%m%d%H%M%S')}-{user_id}"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO goals (is, user_id, description, category,priority,target_date, progress, created_at, last_updated, collaborators)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)  
        """,  (goal_id, user_id. description, category, priority, target_date, progress,
                datetime.now().isoformat(), datetime.now().isoformat(), json.dumps(collaborators or [])))
            conn.commit()

        self.vector_store.add_texts([f" {description} for {user_id} at {target_date}"])
        self.memory.chat_memory.add_user_message(f"Set goal: {description} by {target_date}")
        if self.google_tasks_service:
            self._sync_to_google_tasks(goal_id, description, target_date)
        self._notify_devices(f" New goal '{description}' set for {target_date}")
        return f"Goal '{description}' set for {target_date} with ID {goal_id}."

    def _sync_to_google_tasks(self, goal_id, description, target_date):
        """ Sync goal to Google Tasks."""
        task = {
            'title': description,
            'due': target_date + 'T23:59:59Z', 'status': 'needsAction',}
        self.google_tasks_service.tasks().insert(tasklist= '@default', body=task).execute()

    def _notify_devices(self, message: str):
        """ Send notification to connected devices via MQTT."""
        self.mqtt_client.publish("sol/goal/notification", message, qos=1)

    def update_progress(self, goal_id: str, progress: float, user_id: str, voice_command: bool = False) -> str:
        """ Update progress with collaboration and learning."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(" SELECT progress, status, collaborators FROM goals WHERE id = ?", (goal_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError (f"Goal {goal_id} not found.")
            current_progress, status, collabs_json = row
            collabs = json.loads(collabs_json)
            if user_id not in [user_id] + collabs and user_id != "admin":
                raise ValueError(f"User {user_id} not authorized to update {goal_id}.")
            if status != 'active':
                raise ValueError (f"Goal {goal_id} is {status}, cannot update progress.")
            new_progress = min(max(progress, 0.0), 100.0)
            cursor.execute("""
            UPDATE goals SET progress = ?, last_updated = ? WHERE id = ? 
            """, (new_progress, datetime.now().isoformat(), goal_id))
            conn.commit()
            self.memory.chat_memory.add_ai_message(f" Progress for {goal_id} updated to {new_progress}%")
            self._learn_from_update(goal_id, new_progress)
            message = f"Progress for {goal_id} updated to {new_progress}%"
            if voice_command and new_progress >= 50:
                self._notify_devices(f"Milestone reached: {message}")
            return message

    def _learn_from_update(self, goal_id: str, progress: float):
        """ Update Vector DB with learning from progress updates."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(" SELECT description FROM goals WHERE id = ?", (goal_id,))
            desc = cursor.fetchone()[0]
        self.vector_store.add_texts([f"Updated {desc} to {progress}%"])

    def get_progress_update(self, interval_hours:int = 72, custom_interval: Optional[str]= None) -> Dict:
        """ Get progress updates with customizable intervals and analytics. """
        now = datetime.now()
        interval = timedelta(hours=float(custom_interval.split()[0])) if custom_interval else timedelta(hours = interval_hours)
        updates = {}
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(""" 
                SELECT id, description, progress, target_date, status, category
                FROM goals WHERE last_updated >= ? AND status = 'active'
            """, (now - interval,))
            for row in cursor.fetchall():
                goal_id, desc, prog, target, status, cat = row
                days_left = max((datetime.fromisoformat(target) - now).days, 0)
                updates[goal_id] = {
                    "description": desc,
                    "progress": prog,
                    "target_date": target,
                    "status": status,
                    "category": cat,
                    "days_left": days_left
                }
        return updates


    def archive_incomplete_goals(self):
        """ Archive overdue or stalled goals with notification."""
        now = datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE goals SET status = 'archived'
                WHERE target_date < ? AND progress < 100
            """, (now.isoformat(),))
            conn.commit()
        self._notify_devices("Archived incomplete goals")

    def get_analytics(self) -> Dict:
        """
        :return: Advanced analytics with histogram and radar chart data
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT progress, category FROM goals WHERE status = 'active'
            """)
            data = cursor.fetchall()
            categories = ["personal", "work", "health", "finance", "career", "diet", "fitness", "family", "others"]
            hist_data[cat] = {cat: 0 for cat in categories}
            radar_data[cat] = {cat: 0 for cat in categories}
            for prog, cat in data:
                hist_data[cat] = hist_data.get(cat, 0) + 1
                radar_data[cat] += prog / len(data) if data else 0
            return {
                "histogram": hist_data,
                "radar": radar_data,
                "average_progress": round(sum(d[0] for d in data) / len(data) if data else 0, 2),
                "total_active_goals": len(data)
            }
# Example usage:
if __name__ == "__main__":
    tracker = GoalTracker()
    print(tracker.add_goal("Learn Python", "2024-12-31", user_id="user123", priority=2))
    print(tracker.update_progress("goal_241231123456-user123", 50, "user123"))
    print(tracker.get_progress_update())
    print(tracker.get_analytics())
    tracker.archive_incomplete_goals()
    
    

