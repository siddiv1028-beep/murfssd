import os
import logging
import sqlite3
import json
import datetime
import uuid  # Added for Day 7 ticket IDs

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentServer,
    AgentSession,
    JobContext,
    JobProcess,
    cli,
    tokenize,
    room_io,
    function_tool,
    RunContext
)
from livekit.plugins import murf, silero, openai, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# --- SQLITE DATABASE SETUP (Day 4 Memory & Day 7 Escalations) ---
def init_db():
    conn = sqlite3.connect('home_fresh.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            past_orders TEXT,
            preferred_delivery_slot TEXT,
            last_interaction TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Added Day 7 Escalation Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS escalations (
            ticket_id TEXT PRIMARY KEY,
            customer_name TEXT,
            issue_summary TEXT,
            what_was_checked TEXT,
            urgency TEXT,
            language TEXT,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- DAY 5: MOCK INVENTORY DATABASE ---
# --- DAY 5: MOCK INVENTORY DATABASE ---
INVENTORY_DB = {
    "rice": {"price_per_kg": 55, "stock": "In Stock"},
    "chal": {"price_per_kg": 55, "stock": "In Stock"},
    "चावल": {"price_per_kg": 55, "stock": "In Stock"}, # <-- Added Devanagari 
    "milk": {"price_per_liter": 66, "stock": "Low Stock (Only 2 liters left)"},
    "dudh": {"price_per_liter": 66, "stock": "Low Stock (Only 2 liters left)"},
    "दूध": {"price_per_liter": 66, "stock": "Low Stock (Only 2 liters left)"}, # <-- Added Devanagari
    "egg": {"price_per_dozen": 80, "stock": "Out of Stock"},
    "dim": {"price_per_dozen": 80, "stock": "Out of Stock"},
    "अंडे": {"price_per_dozen": 80, "stock": "Out of Stock"}, # <-- Added Devanagari
    "अंडा": {"price_per_dozen": 80, "stock": "Out of Stock"}, # <-- Added Devanagari
    "mustard oil": {"price_per_liter": 160, "stock": "In Stock"},
    "सरसों का तेल": {"price_per_liter": 160, "stock": "In Stock"}, # <-- Added Devanagari
}

SYSTEM_PROMPT = """
IDENTITY: You are 'jarvis', a friendly virtual shopkeeper assistant for Home Fresh Grocery.

OBJECTIVES: 
1. Always start by using the `check_returning_customer` tool to greet returning users.
2. If a user asks about the price or availability of a specific item, YOU MUST use the `check_kirana_inventory` tool immediately.
3. When telling the user a price, you MUST state when the data is from based on the tool's output (e.g., "आज के अपडेट के अनुसार...").
4. GRACEFUL FAILURE: If the inventory system is down, apologize and say: "क्षमा करें, मैं इस समय स्टॉक नहीं देख पा रही हूँ।"
5. HUMAN ESCALATION (DAY 7 RULES):
   - Situation A: The caller has a payment, refund, or order dispute.
   - Situation B: The caller requests a special bulk order or manager override.
   -> STRICT RULE 1: When you detect Situation A or B, you MUST STOP and ask the user for permission to log a ticket (e.g., "क्या मैं यह जानकारी हमारे स्टोर मैनेजर को भेजने के लिए नोट कर लूँ?").
   -> STRICT RULE 2: DO NOT call the `create_escalation` tool yet. You must wait for the user to reply "Yes".
   -> STRICT RULE 3: ONLY call `create_escalation` AFTER the user explicitly agrees. Once created, read out the Ticket ID.

LANGUAGE & SCRIPT:
- Speak primarily in Hindi, mixing simple English words naturally (Hinglish).
- Write in Devanagari script (नमस्ते).
- Keep sentences short, concise, and conversational.
"""

class Assistant(Agent):
    def __init__(self, room: rtc.Room) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self.room = room
        self.current_user_id = "demo_user_01" 

    # --- DAY 7: HUMAN ESCALATION TOOL ---
    @function_tool
    async def create_escalation(self, context: RunContext, customer_name: str, issue_summary: str, what_was_checked: str, urgency: str):
        """Create a human help support ticket. ONLY call this AFTER asking the user for permission and they have said 'Yes'."""
        
        ticket_id = f"HF-{uuid.uuid4().hex[:6].upper()}"
        language = "Hindi"

        logger.info(f"Creating escalation ticket {ticket_id} for {customer_name}")
        conn = sqlite3.connect('home_fresh.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO escalations (ticket_id, customer_name, issue_summary, what_was_checked, urgency, language)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (ticket_id, customer_name, issue_summary, what_was_checked, urgency, language))
        conn.commit()
        conn.close()

        return f"Support ticket created successfully. Reference Ticket ID: {ticket_id}. Read this ID out loud to the user."

    # --- DAY 5: LIVE DATA TOOL ---
    @function_tool
    async def check_kirana_inventory(self, context: RunContext, item_name: str):
        """Use this tool whenever the user asks for the price, stock, or availability of a grocery item."""
        logger.info(f"Checking inventory for: {item_name}")
        
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        item_lower = item_name.lower()
        
        for key, details in INVENTORY_DB.items():
            if key in item_lower:
                return f"Data Timestamp: {current_date}. {item_name.capitalize()} details: {details}. Instruct the user on the price and stock."
                
        return f"Data Timestamp: {current_date}. {item_name} is not found in our current catalogue."

    # --- DAY 4 TOOLS ---
    @function_tool
    async def check_returning_customer(self, context: RunContext, reason: str = "check"):
        """Use this tool immediately at the start of the conversation to see if the caller has a saved profile."""
        conn = sqlite3.connect('home_fresh.db')
        c = conn.cursor()
        c.execute("SELECT name, past_orders, preferred_delivery_slot FROM customers WHERE user_id=?", (self.current_user_id,))
        result = c.fetchone()
        conn.close()
        if result:
            return f"Customer found. Name: {result[0]}, Past Orders: {result[1]}. Greet them politely."
        return "New customer found."

    @function_tool
    async def save_customer_data(self, context: RunContext, name: str, past_orders: str, delivery_slot: str, permission_granted: bool):
        """Save customer details. ONLY call this tool if permission_granted is True."""
        if not permission_granted:
            return "Do not save."
        conn = sqlite3.connect('home_fresh.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO customers (user_id, name, past_orders, preferred_delivery_slot)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
            name=excluded.name, past_orders=excluded.past_orders, preferred_delivery_slot=excluded.preferred_delivery_slot
        ''', (self.current_user_id, name, past_orders, delivery_slot))
        conn.commit()
        conn.close()
        
        payload = json.dumps({"action": "toast", "message": "💾 Preferences Saved", "type": "success"}).encode('utf-8')
        await self.room.local_participant.publish_data(payload, reliable=True, topic="ui-events")
        return "Data saved."

    @function_tool
    async def delete_customer_data(self, context: RunContext, reason: str = "request"):
        """Use this tool if the customer asks you to forget them."""
        conn = sqlite3.connect('home_fresh.db')
        c = conn.cursor()
        c.execute("DELETE FROM customers WHERE user_id=?", (self.current_user_id,))
        conn.commit()
        conn.close()
        
        payload = json.dumps({"action": "toast", "message": "🗑️ Data Erased", "type": "error"}).encode('utf-8')
        await self.room.local_participant.publish_data(payload, reliable=True, topic="ui-events")
        return "Data deleted."

server = AgentServer()

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

server.setup_fnc = prewarm

@server.rtc_session(agent_name="my-agent")
async def my_agent(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="hi"), 
        llm=openai.LLM(
            model="llama-3.3-70b-versatile",
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY")
        ),
        tts=murf.TTS(
            voice="Karan", 
            locale="hi-IN",
            style="Conversational", 
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=Assistant(room=ctx.room),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: (
                    noise_cancellation.BVCTelephony()
                    if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                    else noise_cancellation.BVC()
                ),
            ),
        ),
    )
    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(server)