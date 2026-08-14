import os
import logging
import sqlite3
import json
import datetime
import uuid
import threading
from flask import Flask, render_template_string

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

logger = logging.getLogger("agent")
load_dotenv(".env.local")

# --- SQLITE DATABASE SETUP ---
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
    c.execute('''
        CREATE TABLE IF NOT EXISTS call_analytics (
            call_id TEXT PRIMARY KEY,
            status TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

INVENTORY_DB = {
    "rice": {"price_per_kg": 55, "stock": "In Stock"},
    "chal": {"price_per_kg": 55, "stock": "In Stock"},
    "चावल": {"price_per_kg": 55, "stock": "In Stock"},
    "milk": {"price_per_liter": 66, "stock": "Low Stock (Only 2 liters left)"},
    "dudh": {"price_per_liter": 66, "stock": "Low Stock (Only 2 liters left)"},
    "दूध": {"price_per_liter": 66, "stock": "Low Stock (Only 2 liters left)"},
    "egg": {"price_per_dozen": 80, "stock": "Out of Stock"},
    "dim": {"price_per_dozen": 80, "stock": "Out of Stock"},
    "अंडे": {"price_per_dozen": 80, "stock": "Out of Stock"},
    "अंडा": {"price_per_dozen": 80, "stock": "Out of Stock"},
    "mustard oil": {"price_per_liter": 160, "stock": "In Stock"},
    "सरसों का तेल": {"price_per_liter": 160, "stock": "In Stock"},
}

# ==========================================
# DAY 9: SPECIALIST AGENT (RETURNS & REFUNDS)
# ==========================================
REFUND_SPECIALIST_PROMPT = """
IDENTITY: You are the Returns and Refunds Specialist for Home Fresh Grocery.

OBJECTIVES:
1. You take over conversations when users have issues with payments, refunds, or returning items.
2. Introduce yourself IMMEDIATELY upon taking over (e.g., "नमस्ते, मैं होम फ्रेश का रिफंड स्पेशलिस्ट हूँ।").
3. Use the `process_refund` tool to securely handle refund requests.
4. Keep responses empathetic, professional, and concise in Hindi/Hinglish.
5. NEVER narrate tool usage or output raw JSON. Just talk naturally.
"""

class RefundSpecialist(Agent):
    def __init__(self, room: rtc.Room) -> None:
        super().__init__(instructions=REFUND_SPECIALIST_PROMPT)
        self.room = room

    @function_tool
    async def process_refund(self, context: RunContext, issue_summary: str):
        """Use this tool to securely process a refund for a customer."""
        logger.info(f"Processing refund for: {issue_summary}")
        ticket_id = f"REF-{uuid.uuid4().hex[:6].upper()}"
        return f"Refund initiated successfully. Reference Ticket ID: {ticket_id}. Read this ID out loud to the user and assure them the money will reflect in 3-5 days."

# ==========================================
# MAIN AGENT
# ==========================================
SYSTEM_PROMPT = """
IDENTITY: You are 'jarvis', a friendly virtual shopkeeper assistant for Home Fresh Grocery.

OBJECTIVES: 
1. Always start by using the `check_returning_customer` tool to greet returning users.
2. If a user asks about the price or availability of a specific item, YOU MUST use the `check_kirana_inventory` tool immediately.
3. When telling the user a price, you MUST state when the data is from based on the tool's output.
4. GRACEFUL FAILURE: If the inventory system is down, apologize.

DAY 9 HANDOFF RULES (CRITICAL):
- If the caller has a payment, refund, or order dispute, YOU MUST HAND THEM OFF TO THE SPECIALIST.
- FIRST, politely tell the user: "मैं आपको हमारे रिफंड स्पेशलिस्ट से कनेक्ट कर रहा हूँ।" (I will connect you to our returns specialist).
- THEN, IMMEDIATELY call the `transfer_to_refund_specialist` tool. Do not try to solve the refund issue yourself.

LANGUAGE & SCRIPT:
- Speak primarily in Hindi, mixing simple English words naturally (Hinglish).
- Write in Devanagari script (नमस्ते).
- Keep sentences short.
- NEVER output raw XML, JSON, or `<function>` tags. Execute tools silently.
"""

class MainAssistant(Agent):
    def __init__(self, room: rtc.Room) -> None:
        super().__init__(instructions=SYSTEM_PROMPT)
        self.room = room
        self.current_user_id = "demo_user_01" 
        self.call_successful = False
        self.call_id = f"CALL-{uuid.uuid4().hex[:6].upper()}"

    # --- DAY 9 HANDOFF TOOL ---
    @function_tool
    async def transfer_to_refund_specialist(self, context: RunContext, issue_summary: str):
        """Use this tool to transfer the user to the Returns and Refunds Specialist. Pass the summary of their problem."""
        logger.info(f"Handing off to Refund Specialist with context: {issue_summary}")
        self.call_successful = True 
        
        # Returning the specialist agent transfers the conversation context seamlessly
        return RefundSpecialist(self.room)

    # --- EXISTING TOOLS ---
    @function_tool
    async def check_kirana_inventory(self, context: RunContext, item_name: str):
        """Use this tool whenever the user asks for the price, stock, or availability of a grocery item."""
        self.call_successful = True
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        item_lower = item_name.lower()
        for key, details in INVENTORY_DB.items():
            if key in item_lower:
                return f"Data Timestamp: {current_date}. {item_name.capitalize()} details: {details}."
        return f"Data Timestamp: {current_date}. {item_name} is not found."

    @function_tool
    async def check_returning_customer(self, context: RunContext, reason: str = "check"):
        """Use this tool immediately at the start of the conversation."""
        conn = sqlite3.connect('home_fresh.db')
        c = conn.cursor()
        c.execute("SELECT name, past_orders, preferred_delivery_slot FROM customers WHERE user_id=?", (self.current_user_id,))
        result = c.fetchone()
        conn.close()
        if result:
            return f"Customer found. Name: {result[0]}, Past Orders: {result[1]}."
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

    assistant = MainAssistant(room=ctx.room)

    @ctx.room.on("disconnected")
    def on_disconnected(*args, **kwargs):
        conn = sqlite3.connect('home_fresh.db')
        c = conn.cursor()
        status = "SUCCESS" if assistant.call_successful else "FAILED"
        c.execute("INSERT INTO call_analytics (call_id, status) VALUES (?, ?)", (assistant.call_id, status))
        conn.commit()
        conn.close()
        logger.info(f"Call {assistant.call_id} ended with status: {status}")

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="hi"), 
        llm=openai.LLM(
            # Using Gemma 2 explicitly prevents Llama's <function> tag leak issue
            model="openai/gpt-oss-20b", 
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
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    await session.start(
        agent=assistant, 
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


# --- DAY 8 DASHBOARD SETUP ---
app = Flask(__name__)

@app.route("/")
def dashboard():
    conn = sqlite3.connect('home_fresh.db')
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM call_analytics")
    total_row = c.fetchone()
    total = total_row[0] if total_row else 0
    
    c.execute("SELECT COUNT(*) FROM call_analytics WHERE status='SUCCESS'")
    success_row = c.fetchone()
    success = success_row[0] if success_row else 0
    
    c.execute("SELECT COUNT(*) FROM call_analytics WHERE status='FAILED'")
    failed_row = c.fetchone()
    failed = failed_row[0] if failed_row else 0
    
    c.execute("SELECT call_id, status, timestamp FROM call_analytics ORDER BY timestamp DESC")
    all_calls = c.fetchall()
    
    conn.close()
    
    html = """
    <html>
    <head>
        <title>Jarvis Call Analytics</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #f4f4f9; text-align: center; margin: 0; padding: 50px; }
            .cards { display: flex; justify-content: center; gap: 30px; margin-top: 40px; margin-bottom: 50px; }
            .card { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); width: 200px; }
            table { width: 80%; max-width: 800px; margin: 0 auto; border-collapse: collapse; background: white; box-shadow: 0 4px 8px rgba(0,0,0,0.1); border-radius: 8px; overflow: hidden; }
            th, td { padding: 15px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #007bff; color: white; font-weight: bold; }
            .status-SUCCESS { color: #28a745; font-weight: bold; }
            .status-FAILED { color: #dc3545; font-weight: bold; }
        </style>
    </head>
    <body>
        <h1 style="color: #333;">📞 Home Fresh Analytics Dashboard</h1>
        
        <div class="cards">
            <div class="card">
                <h2 style="margin: 0; color: #555;">Total Calls</h2>
                <p style="font-size: 40px; font-weight: bold; color: #007bff; margin: 10px 0 0 0;">{{ total }}</p>
            </div>
            <div class="card">
                <h2 style="margin: 0; color: #555;">Successful</h2>
                <p style="font-size: 40px; font-weight: bold; color: #28a745; margin: 10px 0 0 0;">{{ success }}</p>
            </div>
            <div class="card">
                <h2 style="margin: 0; color: #555;">Failed</h2>
                <p style="font-size: 40px; font-weight: bold; color: #dc3545; margin: 10px 0 0 0;">{{ failed }}</p>
            </div>
        </div>

        <h2 style="color: #333; margin-bottom: 20px;">Detailed Call Logs</h2>
        <table>
            <thead>
                <tr>
                    <th>Call ID</th>
                    <th>Status</th>
                    <th>Timestamp (UTC)</th>
                </tr>
            </thead>
            <tbody>
                {% for call in calls %}
                <tr>
                    <td style="color: #555;">{{ call[0] }}</td>
                    <td class="status-{{ call[1] }}">{{ call[1] }}</td>
                    <td style="color: #777;">{{ call[2] }}</td>
                </tr>
                {% else %}
                <tr>
                    <td colspan="3" style="text-align: center; color: #999;">No calls recorded yet.</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </body>
    </html>
    """
    return render_template_string(html, total=total, success=success, failed=failed, calls=all_calls)

def run_dashboard():
    app.run(host="0.0.0.0", port=8080, use_reloader=False)

if __name__ == "__main__":
    threading.Thread(target=run_dashboard, daemon=True).start()
    cli.run_app(server)