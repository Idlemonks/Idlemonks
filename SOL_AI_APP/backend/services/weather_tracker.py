from datetime import datetime, timedelta
import sqlite3 
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeatherTracker:
    
    """ Weather Tracker Service Provides weather updates 
    and forecasts, weather notification 
    """
    def __init__(self, db_path: str ='weather_data.db', vector_db_path: str = "vector_weather"):
        """Initialize with SQLite, vector DB, memory, and weather API."""
        load_dotenv()
        self.db_path = db_path
        self.vector_db_path = vector_db_path
        self._setup_database()
        self.veciro_store = self._setup_vector_db()
        self.memory = ConversationBufferMemory(return_messages=True)
        self.mqtt_client = self._setup_mqtt()
        self.goal_tracker = GoalTracker()
        self.last_update = datetime.now()
        self.update_interval = timedelta(hours=48) # Default 48 hours auto referesh for  update
        self.location = os.getenv("DEFAULT_LOCATION", Lagos,Nigeria)
        self.api_key = os.getenv("WEATHER_API_KEY") # e.g ... OpenWeatherMap API key
        self.last_notification = datetime.now()
        
        
    def _setup_database(self):
        """ Set up SQlite database with weather table for easy caching."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weather_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location TEXT NOT NULL,
                    timestamp TEXT,
                    temperature REAL,
                    air_quality INTEGER,
                    severe_alerts TEXT,
                    forecast TEXT,
                    status TEXT DEFAULT 'cached'
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS weather_logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    location TEXT,
                    log_date TEXT,
                    notes TEXT,
                    weather_impact TEXT
                )
            """)
            conn.commit()
            
            
    def _setup_vector_db(self):
        
        """ Set up FAISS for weather pattern recognition."""
        embeddings = OpenAIEmbeddings(api_key=os.getenv("OPENAI_API_KEY"))
        try:
            return FAISS.load_local(self.vector_db_path, embeddings)
        except:
            return FAISS.from_texts([], embeddings)

    def _setup_mqtt(self):
        """ Set up MQTT for device notifications."""
        client = mqtt.Client()
        client.username_pw_set(os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD"))
        client.connect(os.getenv("MQTT_BROKER", "localhost"), 1883, 60)
        return client 
    
    async def _fetch_weather(self, location: str) -> Dict:
        """Fetch weather data from API (simulated; replace with real API call)."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={self.api_key}"
                )
                response.raise_for_status()
                data = response.json()
                return {
                    "temperature": data["main"]["temp"] - 273.15,  # Convert from Kelvin to Celsius
                    "air_quality": 50, # Placeholder; use AirQuality API
                    "severe_alerts": "None" if data ["weather"][0]["main"] not in ["Tornado", "Rain", "snow"] else data ["weather"][0]["main"],
                    "forecast": data.get("weather", [{}])[0].get("description", ""),
                    "timestamp": datetime.now().isoformat()
                }   
            except httpx.HTTPError as e:
                logger.error(f"Weather API error: {e}")
                return self._get_cached_weather(location)
            
    
    def _get_cached_weather(self, location: str) -> Dict:
        """ Retrieve cached weather data for offline access. """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("selectb* FROM weather_data WHERE location = ? ORDER BY timestamp DESC LIMIT 1", (location,))
            row = cursor.fetchone()
            return {
                "temperature": row[2] if row else 25.0,
                "air_quality": row[3] if row else 50,
                "severe_alerts": row[4] if row else "None",
                "forecast": row[5] if row else "Sunny",
                "timestamp": row[1] if row else datetime.now().isoformat()
            }
            
            
    def update_weather(self, location: str = None, manual: bool = False) -> Dict:
        """ Update weather data automatically or manually . """
        if not manual and (datetime.now() - self.last_update) < self.update_interval and not os.getenv("WEATHER_UPDATE_OFF"):
            return self._get_cached_weather(location or self.location)
        weather = asyncio.run(self._fetch_weather(location or self.location))
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO weather_data (location, timestamp, temperature, air_quality, severe_alerts, forecast)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (location or self.location, weather["timestamp"], weather["temperature"],
                    weather["air_quality"], weather["severe_alerts"], weather["forecast"]))
            conn.commit()
            self.last_update = datetime.now()
            self.vector_store.add_texts([f"Weather at {location or self.location}: {json.dumps(weather)}"])
            self._check_notifications(weather)
            return weather
        
    def _check_notification(self, weather: Dict):
        """ Check for good weather or severe alerts and notify. """
        if weather ["severe_alerts"] != "None":
            self._send_severe_alert(weather)
        elif weather["temprature"] > 20 and weather["air_quality"] < 75: # Good weather condition
            self._send_good_weather_notification(weather)
            
            
    def _send_good_weather_notification(self, weather: Dict):
        """ Notify user of good weather for habits/goals """
        message = f"Today is a lovely day to workout, with {weather['temperature']}°C. Remember your exercise goals and habit formation!"
        self._send_notification(message, os.getenv("DEFAULT_USER"), priority = "medium")
        
    def _send_severe_alert(self, weather: Dict):
        """Send severe alert with AI summary and 911 option."""
        llm = ChatOpenAI(model="gpt-4o", api_key=os.getenv("OPEN_API_KEY"))
        summary = llm.predict(f'Summarize in layman terms: Severe weather alert - {weather["severe_alerts"]} at {self.location}')
        message = f"Severe Alert: {weather['severe_alerts']} detected! {summary}. Dial 911 if needed."
        self._send_notification(message, os.getenv("DEFAULT_USER"), PRIORITY = 10)
        
        
        
    def _send_notification(self, message: str, user_id: str, priority: str = "meduim"):
        """ Send notifications via MQTT and email. """
        self.mqtt_client.publish(f"sol/weather/notification/{user_id}", message, qos=int(priority) if priority.isdigit() else 1)
        if os.getenv("EMAIL_ENABLED") and priority in ["high", "10"]:
            smtp = SMTP(os.getenv("SMTP_SERVER"), os.getenv("SMTP_PORT"))
            smtp.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
            msg = MIMEText(message)
            msg['Subject'] = "SOL Weather Notification"
            msg['FROM'] = os.getenv("SMTP_USER")
            msg['TO'] = f"user_{user_id}@example.com"
            smtp.sendmail(os.getenv("SMTP_USER"), msg['To'], msg.as_string())
            smtp.quit()
            
    def get_analytics(self, location: str = None) -> Dict:
        """ Generate weather analytics with visualization."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT timestamp, temperature, air_quality, severe_alerts FROM weather_data WHERE location = ? ORDER BY timestamp DESC LIMIT 10",
                            (location or self.location,))
            data = cursor.fetchall()
            if not data:
                return {"error": "No data available"}
            timestamps = [datetime.fromisoformat(row[0]).date() for row in data]
            temperatures = [row[1] for row in data]
            air_qualities = [row[2] for row in data]
            severe_counts = {"Tornado": 0, "Rain": 0, "snow": 0}
            for row in data:
                if row[3] in severe_counts:
                    severe_counts[row[3]] += 1
            charts = self._generate_charts(timestamps, temperatures, air_qualities, severe_counts)
            return {
                "temperature_trend": {"dates": timestamps, "values": temperatures},
                "air_quality_trend": {"dates": timestamps, "values": air_qualities},
                "severe_alerts": severe_counts,
                "calendar_tracker": self._generate_calendar_tracker(location or self.location),
                "summary": self._generate_summary(timestamps, temperatures)
            }
            
            
    def _generate_charts(self, timestamps: List, temperatures: List, air_qualities: List, severe_counts: Dict):
        """ Generate base64-encoded weather charts. """
        fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15, 5))
        ax1.plot(timestamps, temperature, marker='o', color = 'blue')
        ax1.set_title("Temperature Trend")
        ax2.pot(timestamps, air_qualities, marker = 'o', color = 'green')
        ax2.set_title("Air Auality Trend")
        ax3.pie(severe_counts.values(), labels = severe_counts.key(), autopct = '%1.1f%%', colors = ['red', 'gray', 'white'])
        ax3.set_title("Severe Alerts")
        buf = io.BytesIO()
        plt.savefig(buf, format = 'png')
        plt.close()
        return {"base64": base64.b64encode(buf.getvalue()).decode()}
    
    def _generate_calendar_tracker(self, location: str) -> Dict:
        """ Generate colore calendar tracker for weather. """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(" Select timestamp, severe_alerts FROM weather_data WHERE location = ?", (location,))
            logs = cursor.fetchall()
            calender = {}
            for timestamp, alert in logs:
                date = datetime.fromisoformat(timestamp).date()
                calender[date.isoformat()] = "red" if alert != "None" else "green"
            return calender 
    
    def _generate_summary(self, timestamps: List, temperatures: List) -> str:
        """ Generate AI-driven weather summary. """
        llm = ChatOpenAI(model = "gpt-4o", api_key=os.getenv("OPENAI_API_KEY"))
        trend = "warming" if temperatures[-1] > tempeatures[0] else "cooling"
        return llm.predict(f'Summarize weather trend in layman terms: {trend} over {len(timestamps)} days at {self.location}')
    
    def log_weather_impact(self, location: str, note: str, voice_command: bool = False):
        """ Log weather impact eith journaling and AI conversation. """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO weather_logs (location, log_date, notes, weather_impact)
                VALUES (?, ?, ?, ?)
            """, (location, datetime.now().isoformat(), note, "affected"))
            conn.commit()
            self.vector_store.add_texts([f" Weather impact logged at {location}: {note}"])
            if voice_command:
                self._start_ai_conversation(location, note)
                
                
    def _start_ai_conversation(self, location: str, note: str):
        """ Initiate AI_driven conversation on weather impact. """
        llm = ChatOpenAI(model="gpt-4o", api_key = os.getenv("OPENAI_API_KEY"))
        questions = [
            "Did the weather influence your decision to skip your walk exercise today?",
            "Should I update your goal_tracker, stating the weather is to be blamed for missing today?"
        ]
        for question in questions:
            response = (f"Ask user: {question} based on note '{note}' at {location} ")
            self._send_notifications(response, os.getenv("DEFAULT_USER"), priority = "High")
            
            
    def integrate_with_microservices(self, service: str, data: Dict):
        """Sync weather data with other microservices."""
        if service == "goal_tracker":
            self.goal_tracker.update_progress(data.get("goal_id"), data.get("progress", 0), os.getenv("DEFAULT_USER"))
        elif service == "habit_tracker":
            from habit_tracker import HabitTracker
            habit_tracker = HabitTracker()
            habit_tracker.log_habit(data.get("habit_id"), os.getenv("DEFAULT_USER"), completed=False, note=f"Weather impact: {data.get('note')}")
        self.mqtt_client.publish(f"sol/{service}/weather_update", json.dumps(data))
        
# Example usage
if __name__ == "__main__":
    tracker = WeatherTracker()
    weather = tracker.update_weather()
    print(f"Current weather: {weather}")
    tracker.log_weather_impact("Lagos,Nigeria", "Rainy day, skipped walk", voice_command=True)
    print(tracker.get_analytics())
    

        