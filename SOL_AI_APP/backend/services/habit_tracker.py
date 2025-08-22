import sqlite3
from datetime import datetime, timedelta
import logging 
import json
import os
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List
import matplotlib.pyplot as plt
import io
import base64
import numpy as np 
from langchain.vectorstores import FAISS
from langchain.embeddings import OpenAIEmbeddings
from langchain.memory import ConversationBufferMemory
import asyncio
from smtplib import SMTP
from calender import monthcalender
from goal_tracker import GoalTracker 

# Configure logging
logging.baseConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HabitTracker:
    def __init__(self, db_path: str = "habits.db", vector_db_path: str = "vector_habits"):
        """Initialize with SQLite, vector DB, and memory."""
        load_dotenv()
        self.db_path = db_path
        self.vector_db_path = vector_db_path
        self._setup_database()
        self.vector_store = self._setup_vector_db()
        self.memory = ConversationBufferMemory(return_messages=True)
        self.mqtt_client =self._setup_mqtt()
        self.goal_tracker = GoalTracker() # Link to goal_tracker.py 
        self.last_notification = datetime.now()
        
        
    def _setup_database(self):
        """Set up SQLite database with habits table."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                    CREATE TABLE IF NOT EXISTS habits (
                    id INTEGER PRIMARY KEY,
                    description TEXT NOT NULL,
                    category TEXT,
                    frequency TEXT,
                    target_date TEXT,
                    progress REAL,
                    created_at TEXT,
                    last_updated TEXT,
                    status TEXT DEFAULT 'active',
                    collaborators TEXT,
                    notes TEXT,
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS habit_logs (
                    habit_id TEXT,
                    log_date TEXT,
                    completed INTEGER DEFAULT 0,
                    FOREIGN KEY (habit_id) REFERENCES habits (id)
                )
            ''')
            conn.commit()
            
    def _setup_vector_db(self):
        """Set up FAISS for habit pattern recognition. """
        embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
        try:
            return FAISS.load_local(self.vector_db_path, embeddings)
        except:
            return FAISS.from_text([], embeddings)
        
    
    def _setup_mqtt(self):
        """Set up MQTT for device notification and integrations. """
        client = mqtt.Client()
        client.username_pw_set(os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD"))
        client.connect(os.getenv("MQTT_BROKER", "localhost"), 1883, 60)
        return client
    
    def add_habit(self, description: str, category: str = "healthy", frequency: str = "daily",
                user_id: str = "default_user", collaborators: List[str] = None) -> str:
        """ Add a customizable habit with links to goals. """
        habit_id = f"habit_{datetime.now().strftime('%Y%m%d%H%M%S')}_{user_id}"
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO habits (id, user_id, description, category, frequency, created_at, collaborators)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (habit_id, user_id, description, category, frequency, datetime.now().isoformat(), json.dumps(collaborators or [])))
            conn.commit()
        self.vector_store.add_texts([f"{description} habit for {user_id} at {frequency}"])
        self.memory.chat_memory.add_user_message(f"Added habit: {description}")    
        self._link_to_goal(category, habit_id)
        self._send_notification(f"New habit '{description}' added.", user_id, priority="high")
        return f"Habit '{description}' added successfully with ID {habit_id}."
    
    
    def _link_to_goal(self, category: str, habit_id: str):
        """ Link habit to relevant goal from goal_tracker.py. """
        goal_updates = self.goal_tracker.get_progress_update()                                    
        for goal_id, goal_data in goal_updates.items():
            if habit_category in goal_data.get("category", "").lower():
                logger.info(f"Linking habit {habit_id} to goal {goal_id}")
                
    
    def log_habit(self, habit_id: str, user_id: str, completed: bool = True, note: str = None, voice_command: bool = False):
        """ Log habit completion with strak update and journaling. """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT streak, last_logged, collaborators, notes FROM habits WHERE id = ?", (habit_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Habit ID {habit_id} not found.")
            current_streak, last_logged, collabs_json, current_notes = row
            collabs = json.loads(collabs_json)
            
            if user_id not in [user_id] + collabs and user_id != "admin":
                raise ValueError("Habit already logged today")
            new_streak = current_streak + 1 if completed else 0 
            updated_notes = json.loads(current_notes or "[]") + [note] if note else json.loads(current_notes or "[]")
            cursor.execute('''
                INSERT INTO habit_logs (habit_id, log_date, completed)
                VALUES (?, ?, ?)
            ''', (habit_id, today, 1 if completed else 0))
            conn.commit()
            self.vector_store.add_texts([f"Logged {habit_id} as {'completed' if completed else 'missed'} with note: {note or 'none'}"])
            self.memory.chat_memory.add_ai_message(f"Habit {habit_id} logged: {completed}")
            message = f"Habit {habit_id} logged. Streak: {new_streak}"
            if voice_command:
                self._send_notification(message, user_id, priority="high")
                if new_streak > 0:
                    self._motivate_with_ai(habit_id, user_id)
            return message
        
    def _motivate_with_ai(self, habit_id: str, user_id: str):
        """ Use AI to generate motivational message based on habit progress using LLM."""
        from langchain.chat_models import ChatOpenAI
        llm = ChatOpenAI(model="gpt-5", temperature=0.7)
        prompt = f"Generate motivational message for user {user_id} on habit {habit_id} streak."
        motivation = llm.predict(prompt)
        self._send_notification(motivation, user_id, priority="high")
        
    def _send_notification(self, message: str, user_id: str, priority: str = "high"):
        """Send high-priority notifications via MQTT, email, or in-app."""
        self.mqtt_client.publish("sol/habits/notification", message, qos=1 if priority == "high" else 0)
        # Email example (configure SMTP in .env)
        if os.getenv("EMAIL_ENABLED"):
            smtp = SMTP(os.getenv("SMTP_SERVER"), os.getenv("SMTP_PORT"))
            smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
            msg = MIMEText(message)
            msg['Subject'] = "SOL Habit Notification"
            msg['From'] = os.getenv("SMTP_USER")
            msg['To'] = f"user_{user_id}@example.com"  # Placeholder
            smtp.sendmail(os.getenv("SMTP_USER"), msg['To'], msg.as_string())
            smtp.quit()
            
            
    def get_streak(self, habit_id: str) -> int:
        """Get current streak for a habit."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT streak FROM habits WHERE id = ?", (habit_id,))
            streak = cursor.fetchone()
            return streak[0] if streak else 0

    def get_analytics(self, user_id: str) -> Dict:
        """Generate analytics with charts and trends."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT description, category, streak, status FROM habits WHERE user_id = ? AND status = 'active'
            """, (user_id,))
            data = cursor.fetchall()
            categories = ["healthy", "reading", "exercise", "productivity"]
            hist_data = {cat: 0 for cat in categories}
            pie_data = {cat: 0 for cat in categories}
            line_data = []  # For trends
            for desc, cat, streak, status in data:
                hist_data[cat] = hist_data.get(cat, 0) + 1
                pie_data[cat] += streak
            # Line chart for trends (simulated from logs)
            cursor.execute("SELECT log_date, completed FROM habit_logs WHERE habit_id IN (SELECT id FROM habits WHERE user_id = ?)", (user_id,))
            logs = cursor.fetchall()
            dates = [datetime.fromisoformat(log[0]).date() for log in logs]
            completions = [log[1] for log in logs]
            line_data = {"dates": dates, "completions": completions}
            charts = self._generate_charts(hist_data, pie_data, line_data)
            return {
                "histogram": hist_data,
                "pie_chart": pie_data,
                "line_chart": line_data,
                "calendar_tracker": self._generate_calendar_tracker(user_id),
                "trends": self._calculate_trends(completions)
            }
            
    def _generate_charts(self, hist_data: Dict, pie_data: Dict, line_data: Dict) -> Dict:
        """Generate base64-encoded charts."""
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))
        
        # Histogram
        ax1.bar(hist_data.keys(), hist_data.values())
        ax1.set_title("Habit Distribution")

        # Pie
        ax2.pie(pie_data.values(), labels=pie_data.keys(), autopct='%1.1f%%')
        ax2.set_title("Streak Breakdown")

        # Line
        ax3.plot(line_data["dates"], line_data["completions"], marker='o')
        ax3.set_title("Completion Trends")

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        return {"base64": base64.b64encode(buf.getvalue()).decode()}

    def _generate_calendar_tracker(self, user_id: str) -> Dict:
        """Generate colored calendar tracker."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT log_date, completed FROM habit_logs WHERE habit_id IN (SELECT id FROM habits WHERE user_id = ?)", (user_id,))
            logs = cursor.fetchall()
            calendar = {}
            for date, completed in logs:
                calendar[date] = "green" if completed else "red"
            return calendar

    def _calculate_trends(self, completions: List) -> Dict:
        """Calculate improvement/decline trends."""
        if not completions:
            return {"rate": 0}
        rate = (sum(completions[-10:]) - sum(completions[:10])) / len(completions) * 100 if len(completions) > 10 else 0
        return {"rate": rate, "status": "improved" if rate > 0 else "declined"}

    def archive_inactive_habits(self):
        """Archive missed habits with motivational notification."""
        now = datetime.now()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE habits SET status = 'archived'
                WHERE last_logged < ? AND streak = 0
            """, ( (now - timedelta(days=7)).isoformat(), ))  # Archive after 7 missed days
            conn.commit()
        self._send_notification("Archived inactive habits. Let's start new ones!", "default_user", "high")

# Example usage 
# where is this needed the (if __name__ == "__main__":) block
if __name__ == "__main__":
    tracker = HabitTracker()
    print(tracker.add_habit("Daily meditation", "healthy", "daily"))
    print(tracker.log_habit("habit_20250801031300_default_user", "default_user", completed=True, note="Felt relaxed"))
    print(tracker.get_analytics("default_user"))
    
    
    
    