# importing the Flask from the flask module
from flask import Flask, render_template, request, jsonify, session
import os
import uuid
import time
import re
from dotenv import load_dotenv
from google import genai
from google.genai import types
from elevenlabs.client import ElevenLabs
from elevenlabs import save
from datetime import datetime
from supabase import create_client, Client


# Global Variables Scope
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client()

#Supabse Data Initialization
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

#ElevenLabs Voice Configuration
#Load ElevenLabs credentials From .env environment variables
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID =os.getenv("ELEVENLABS_VOICE_ID")

#initialize the ElevenLabs Client Instance
eleven_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)

#Ensure the static audio folder exists so Flask can save and serve MP3 files
os.makedirs("static/audio", exist_ok=True)

#Cleanup helper
def cleanup_old_audio(max_age_seconds=3600):
    for name in os.listdir("static/audio"):
        path = os.path.join("static/audio", name)
        try:
            if time.time() - os.path.getmtime(path) > max_age_seconds:
                os.remove(path)
        except OSError:
            pass

# List of conversational memory trigger phrases
memory_triggers = ["remember that",
                   "just so you know",
                   "fyi",
                   "by the way",
                   "keep in mind that",
                   "don't forget that",
                   "make a note that",
                   ]

# List of name introduction triggers
name_triggers = ["my name is",
                 "call me",
                 "name's",
                 "name is", ]

#-----CONTEXT HANDLER HELPER FUNCTION---
def context_handler(memory, history):
    #This rebakes the system prompt using current memory state and instantiates a new Gemini chat session.
    current_user = memory.get("name", "Guest")
    saved_facts = " ".join(memory.get("facts", []))
    memory_context = f"The user's verified name is {current_user}. Known profile facts: {saved_facts}"

    system_prompt = ("You are Maximus, a friendly personal AI assistant. "
                     "You were built by Kazibwe Augustine Maxwell, a software engineering student, "
                     "as a personal project. "
                     "Be helpful, calm and clear. Keep answers short unless the user asks for more detail"
                    )
                     

    return client.chats.create(
        model="gemini-3.1-flash-lite",
        config=types.GenerateContentConfig(system_instruction=system_prompt),
        history=history,
    )

# --- HELPER FUNCTIONS FOR NAME TRIGGERS ---
def is_likely_a_name(text):

    words = text.split()

    if not words:
        return False

    # check 1: too many words to be a name
    if len(words) > 3:
        return False

    # check 2: starts with an article
    if words[0].lower() in ["a", "an", "the"]:
        return False

    # check 3: contains an "ing" word
    if any(word.lower().endswith("ing") for word in words):
        return False

    # Passed all checks and is probably a name
    return True

#PER USER MEMORY HELPER FUNCTIONS
# --- PER-USER MEMORY HELPERS ---
def load_user_memory(user_id):
    if not user_id:
        return guest_memories.get(get_guest_key(), {"name": "Guest", "facts": []})

    try:
        result = supabase.table("memories").select("*").eq("uid", user_id).execute()

        if result.data:
            row = result.data[0]
            return {"name": row.get("name") or "Friend",
                    "facts": row.get("facts") or []}

        starter = {"name": session.get("user_name", "Friend"), "facts": []}
        save_user_memory(user_id, starter)
        return starter

    except Exception as e:
        print(f"load_user_memory error: {e}")
        return {"name": session.get("user_name", "Friend"), "facts": []}


def save_user_memory(user_id, mem):
    if not user_id:
        guest_memories[get_guest_key()] = mem
        return

    try:
        supabase.table("memories").upsert({
            "uid": user_id,
            "name": mem.get("name", "Friend"),
            "facts": mem.get("facts", []),
            "updated_at": datetime.now().isoformat(),
        }, on_conflict="uid").execute()
    except Exception as e:
        print(f"save_user_memory error: {e}")
#GUEST CONVERSATION STORAGE (in memory, cleared on restart)
guest_histories = {}
guest_memories = {}

def get_guest_key():
    if 'guest_id' not in session:
        session['guest_id'] = str(uuid.uuid4())
    return session['guest_id']

#PER-USER CONVERSATION HELPERS
def list_conversations(user_id):
    if not user_id:
        return []
    try:
        result = (supabase.table('conversations')
                  .select("id, preview, updated_at")
                  .eq("uid", user_id)
                  .order("updated_at", desc=True)
                  .execute())
        return result.data or []
    except Exception as e:
        print(f"list_conversations error: {e}")
        return []

def load_conversation(user_id, conv_id):
    if not user_id or not conv_id:
        return []
    try:
        result = (supabase.table('conversations')
                  .select("messages")
                  .eq("uid", user_id)
                  .eq("id", conv_id)
                  .execute())
        if result.data:
            return result.data[0].get("messages") or []
        return []
    except Exception as e:
        print(f"load_conversation error: {e}")
        return []

def save_conversation(user_id, conv_id, messages):
    if not user_id or not conv_id:
        return

    preview = "New conversation"
    if messages:
        first_text = messages[0].get("parts", [{}])[0].get("text", "")
        preview = first_text[:30] + "..." if len(first_text) > 30 else first_text

    try:
        supabase.table("conversations").upsert({
            "id": conv_id,
            "uid": user_id,
            "preview": preview,
            "messages": messages,
            "updated_at": datetime.now().isoformat(),
        }, on_conflict="id").execute()
    except Exception as e:
        print(f"save_conversation error: {e}")

def delete_conversation(user_id, conv_id):
    if not user_id or not conv_id:
        return
    try:
        (supabase.table("conversations")
        .delete()
        .eq("uid", user_id)
        .eq("id", conv_id)
        .execute())
    except Exception as e:
        print(f"delete_conversation error: {e}")

def get_history(user_id):
    conv_id = session.get("conversation_id")
    if user_id:
        return load_conversation(user_id, conv_id)
    return guest_histories.get(get_guest_key(), [])

def put_history(user_id, messages):
    conv_id =session.get("conversation_id")
    if user_id:
        save_conversation(user_id, conv_id, messages)
    else:
        guest_histories[get_guest_key()] = messages

# initializing the app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")


# defining the route or routes
@app.route('/')
def home():
    return render_template("index.html", user_name=session.get("user_name", "Guest"))

@app.route('/login', methods=['GET'])
def login():
    return render_template("login.html")

@app.route('/signup', methods=['GET'])
def signup():
    return render_template("signup.html")

#User Logout Session
@app.route('/logout', methods=['POST'])
def logout():
    #Safely clear only the Flask session cookies for the current client
    session.clear()
    return jsonify({"status": "success", "message": "Logged out successfully"}), 200
@app.route('/get-name', methods=['GET'])
def get_name():
    return jsonify({"name": session.get("user_name", "Guest")})

#Wake_Word Queuing
'''@app.route('/wake-stream')
def wake_stream():
    def event_stream():
        while True:
            wake_queue.get() # blocks until something is put in the queue
            yield "data: wake\n\n"
    return app.response_class(event_stream(), mimetype='text/event-stream')
'''
#Sending Requests to JavaScript For Token
@app.route('/verify-session', methods=['POST'])
def verify_session():
    data = request.json or {}
    token = data.get('token')

    if not token:
        session.pop('user_name', None)
        session.pop('user_id', None)
        return jsonify({"authenticated": False, "name": "Guest"})
    try:
        user = supabase.auth.get_user(token)
        display_name = user.user.user_metadata.get('display_name', 'Friend')
        user_id = getattr(user.user, 'id', getattr(user.user, 'uid', ''))

        #Remeber who logged in for this browser Session
        session['user_name'] = display_name
        session['user_id'] = user_id

        return jsonify({
            "authenticated": True,
            "name": display_name,
            "uid": user_id,
        })
    except Exception as e:
        print(f"Error in verify_session: {e}")
        session.pop('user_name', None)
        session.pop('user_id', None)
        return jsonify({"authenticated": False, "name": "Guest"})
    
#More Wake_Word Queuing
"""@app.route('/wake-detected', methods=['POST'])
def wake_detected():
    wake_queue.put('wake')
    return jsonify({"status": "ok"})
"""

# Memory wiping Route
@app.route('/wipe-memory', methods=['POST'])
def wipe_memory():
    user_id = session.get("user_id")
    memory = {"name": session.get("user_name", "Guest"), "facts": []}
    save_user_memory(user_id, memory)
    return jsonify({"status": "success", "message": "Memory wiped success",
                    "user_name": memory.get("name", "Guest")})

# The delete chat route
@app.route('/delete-chat', methods=['POST'])
def delete_chat():
    user_id = session.get('user_id')
    data = request.json or {}
    conv_id = data.get("filename")

    if not conv_id:
        return jsonify({"error": "No Conversation specified"}), 400

    delete_conversation(user_id, conv_id)

    if session.get('conversation_id') == conv_id:
        session.pop('conversation_id', None)

    return jsonify({"status": "success", "message": "Conversation deleted",})


# history click app route
@app.route('/load-chat', methods=['POST'])
def load_chat():
    user_id = session.get("user_id")
    data = request.json or {}
    conv_id = data.get("filename")

    if not conv_id:
        return jsonify({"error": "No Conversation specified"}), 400

    history = load_conversation(user_id, conv_id)
    session['conversation_id'] = conv_id

    return jsonify({"status": "success", "history": history})


@app.route('/conversations', methods=['GET'])
def get_conversations():
    user_id = session.get("user_id")
    rows = list_conversations(user_id)

    conversations = [{
        "id": row["id"],
        "filename": row["id"],
        "preview": row.get("preview") or "Untitled conversation",
    } for row in rows]

    return jsonify({"conversations": conversations})


@app.route('/new-chat', methods=['POST'])
def new_chat():
    user_id = session.get("user_id")
    session.pop('conversation_id', None)

    if not user_id:
        guest_histories.pop(get_guest_key(), None)

    return jsonify({"status": "success", "message": "New chat session started"})

@app.route('/chat', methods=['POST'])
def chat_handler():
    try:
        user_id = session.get("user_id")
        memory = load_user_memory(user_id)

        user_message = request.json.get("message")
        want_audio = request.json.get("want_audio", False)
        if not user_message:
            return jsonify({"error": "No message provided"}), 400

        if not session.get('conversation_id'):
            session['conversation_id'] = str(uuid.uuid4())

        history = get_history(user_id)
        clean_message = user_message.lower().strip()

        #NAME TRIGGER DETECTION
        for trigger in name_triggers:
            if trigger in clean_message:
                trigger_index = clean_message.find(trigger)
                extracted = clean_message[trigger_index + len(trigger):].strip()
                if is_likely_a_name(extracted):
                    memory["name"] = extracted.title()
                    save_user_memory(user_id, memory)
                    break

        #MEMORY TRIGGER DETECTION
        if any(trigger in clean_message for trigger in memory_triggers):
            for trigger in memory_triggers:
                if trigger in clean_message:
                    clean_fact = re.sub(re.escape(trigger), "", user_message, flags=re.IGNORECASE).strip()
                    memory["facts"].append(clean_fact)
                    save_user_memory(user_id, memory)
                    break

        chat = context_handler(memory, history)

        history.append({"role": "user", "parts": [{"text": user_message}]})
        response = chat.send_message(user_message)
        ai_response = response.text
        history.append({"role": "model", "parts": [{"text": ai_response}]})

        put_history(user_id, history)

        #Generate ElevenLabs Audio File
        audio_url = None
        if want_audio and ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID:
            try:
                cleanup_old_audio()
                audio_stream = eleven_client.text_to_speech.convert(
                    voice_id=ELEVENLABS_VOICE_ID,
                    text=ai_response,
                    model_id="eleven_multilingual_v2"
                )

                audio_filename = f"{uuid.uuid4()}.mp3"
                audio_filepath = os.path.join("static/audio", audio_filename)

                with open(audio_filepath, "wb") as f:
                    for chunk in audio_stream:
                        f.write(chunk)

                audio_url = f"/static/audio/{audio_filename}"
            except Exception as tts_err:
                print(f"ElevenLabs TTS Generation Error: {tts_err}")

        return jsonify({"response": ai_response, "audio_url": audio_url})
    except Exception as e:
        print(f"Error in chat_handler: {e}")
        return jsonify({"error": "An error occurred while processing"}), 500



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
