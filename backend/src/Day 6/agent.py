import logging
import sqlite3
import json
import datetime

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
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

# --- SQLITE DATABASE SETUP (Day 4 Memory) ---
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
    conn.commit()
    conn.close()

init_db()

# --- DAY 5: MOCK INVENTORY DATABASE ---
INVENTORY_DB = {
    "rice": {"price_per_kg": 55, "stock": "In Stock"},
    "chal": {"price_per_kg": 55, "stock": "In Stock"},
    "milk": {"price_per_liter": 66, "stock": "Low Stock (Only 2 liters left)"},
    "dudh": {"price_per_liter": 66, "stock": "Low Stock (Only 2 liters left)"},
    "egg": {"price_per_dozen": 80, "stock": "Out of Stock"},
    "dim": {"price_per_dozen": 80, "stock": "Out of Stock"},
    "mustard oil": {"price_per_liter": 160, "stock": "In Stock"},
}

SYSTEM_PROMPT = """
IDENTITY: You are 'jarvis', a friendly virtual shopkeeper assistant for Home Fresh Grocery.

OBJECTIVES: 
1. Always start by using the `check_returning_customer` tool to greet returning users.
2. If a user asks about the price or availability of a specific item, YOU MUST use the `check_kirana_inventory` tool immediately.
3. When telling the user a price, you MUST state when the data is from based on the tool's output (e.g., "आज के अपडेट के अनुसार...").
4. GRACEFUL FAILURE: If the `check_kirana_inventory` tool returns an error or says the system is down, do not invent prices. Apologize and say exactly: "क्षमा करें, सर्वर में समस्या के कारण मैं इस समय स्टॉक की जानकारी नहीं देख पा रही हूँ। क्या आप कुछ और ढूंढ रहे हैं?"
5. Ask for permission before saving order details to memory.

LANGUAGE & SCRIPT (STRICT):
- You must primarily speak in Hindi, but smoothly handle conversational Hinglish (Hindi mixed with simple English words like 'order', 'delivery', 'slot').
- Always write every language in its own native script. Hindi → Devanagari script (नमस्ते).
- Keep the register polite, warm, and respectful (using 'Aap' / आप).

STYLE: Keep sentences short, concise, and conversational. Do not output long paragraphs.
"""

class Assistant(Agent):
    def __init__(self, room: rtc.Room) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self.room = room
        self.current_user_id = "demo_user_01" 

    # --- DAY 5: LIVE DATA TOOL ---
    @function_tool
    async def check_kirana_inventory(self, context: RunContext, item_name: str, simulate_failure: bool = False):
        """Use this tool whenever the user asks for the price, stock, or availability of a grocery item.
        Args:
            item_name: The name of the grocery item the user is asking about (e.g., 'rice', 'milk', 'egg').
            simulate_failure: Set to True ONLY if the user explicitly asks you to "simulate a failure" or "test the offline mode". Otherwise, leave False.
        """
        logger.info(f"Checking inventory for: {item_name}")
        
        if simulate_failure:
            return "ERROR 503: Inventory API is currently down or unreachable."

        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        item_lower = item_name.lower()
        
        for key, details in INVENTORY_DB.items():
            if key in item_lower:
                return f"Data Timestamp: {current_date}. {item_name.capitalize()} details: {details}. Instruct the user on the price and stock, mentioning the timestamp."
                
        return f"Data Timestamp: {current_date}. {item_name} is not found in our current catalogue."

    # --- DAY 4 TOOLS ---
    @function_tool
    async def check_returning_customer(self, context: RunContext):
        """Use this tool immediately at the start of the conversation to see if the caller has a saved profile."""
        conn = sqlite3.connect('home_fresh.db')
        c = conn.cursor()
        c.execute("SELECT name, past_orders, preferred_delivery_slot FROM customers WHERE user_id=?", (self.current_user_id,))
        result = c.fetchone()
        conn.close()
        if result:
            return f"Customer found. Name: {result[0]}, Past Orders: {result[1]}. Greet them."
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
    async def delete_customer_data(self, context: RunContext):
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
        llm=google.LLM(model="gemini-3.5-flash"),
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