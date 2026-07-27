# importing the Flask from the flask module
from flask import Flask, render_template, request, jsonify
import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types
from datetime import datetime

# Check if conversation directory exists before saving files into it
os.makedirs("conversations", exist_ok=True)

# Global Variables Scope
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client()

filename = "History.json"
memory_name = "memory.json"

# The history handler
history = []
try:
    with open("History.json", "r") as file:
        saved = json.load(file)
        history = saved.get("messages", [])
        current_conversation_file = saved.get("current_file", None)
except (FileNotFoundError, json.decoder.JSONDecodeError):
    history = []
    current_conversation_file = None



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
                 "this is",
                 "i am",
                 "i'm",
                 "name's",
                 "name is", ]


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


# The user memory handler
try:
    with open(memory_name, "r") as file:
        memory = json.load(file)
except(FileNotFoundError, json.decoder.JSONDecodeError):
    # The fallback if no known memories of the user.
    memory = {"name": "Guest", "facts": []}
    with open(memory_name, "w") as file:
        json.dump(memory, file, indent=4)

# Ensure "facts" key always exists defensively using .get() fallback pattern
if "facts" not in memory:
    memory["facts"] = []

current_user = memory.get("name", "Guest")
saved_facts = " ".join(memory.get("facts", []))
memory_context = f"The user's verified name is {current_user}. Known profile facts: {saved_facts}"

system_prompt = ("You are an AI."
                 "Your name is Maximus."
                 "You were created by MxDudeTesters"
                 "And you Run on a Testing Model for MxDudeTesters"
                 "The Ceo of MxDudeTesters is Kazibwe Augustine Maxwell from Uganda"
                 "The Ceo has a networth of 1 Billion Dollars as of 2026"
                 "Do not use markdown formatting in your responses. No asterisks, no bold text, no bullet points, no headers. Respond in plain conversational text only."
                 f"Use this background identity context to customize your dialogue. {memory_context}"
                 )

chat = client.chats.create(model="gemini-3.1-flash-lite",
                           config=types.GenerateContentConfig(
                               system_instruction=system_prompt),
                           history=history
                           )

# initializing the app
app = Flask(__name__)


# defining the route or routes
@app.route('/')
def home():
    return render_template("index.html", user_name=memory.get("name", "Guest"))

@app.route('/get-name', methods=['GET'])
def get_name():
    return jsonify({"name": memory.get("name", "Guest")})

# Memory wiping Route
@app.route('/wipe-memory', methods=['POST'])
def wipe_memory():
    global memory, chat

    # Reset memory structure in RAM
    memory = {"name": "Guest", "facts": []}

    # Persist the reset state back to disk
    with open(memory_name, "w") as file:
        json.dump(memory, file, indent=4)

    # 3. Re-bake system prompt without old user facts or custom name
    current_user = memory.get("name", "Guest")
    saved_facts = " ".join(memory.get("facts", []))
    memory_context = f"The user's verified name is {current_user}. Known profile facts: {saved_facts}"

    system_prompt = (
        "You are an AI."
        "Your name is Maximus."
        "You were created by MxDudeTesters"
        "And you Run on a Testing Model for MxDudeTesters"
        "The Ceo of MxDudeTesters is Kazibwe Augustine Maxwell from Uganda"
        "The Ceo has a networth of 1 Billion Dollars as of 2026"
        "Do not use markdown formatting in your responses. No asterisks, no bold text, no bullet points, no headers. Respond in plain conversational text only."
        f"Use this background identity context to customize your dialogue. {memory_context}"
    )

    # 4. Re-instantiate the global Gemini chat session with updated system prompt
    chat = client.chats.create(
        model="gemini-3.1-flash-lite",
        config=types.GenerateContentConfig(system_instruction=system_prompt),
        history=history
    )

    return jsonify({"status": "success", "message": "Memory wiped successfully", "user_name": current_user})


# The delete chat route
@app.route('/delete-chat', methods=['POST'])
def delete_chat():
    global history, chat, current_conversation_file

    # Extract filename from incoming JSON payload
    data = request.json or {}
    filename_to_delete = data.get("filename")

    if not filename_to_delete:
        return jsonify({"error": "No filename provided"}), 400

    safe_filename = os.path.basename(filename_to_delete)
    filepath = os.path.join("conversations", safe_filename)

    # check if file exists on disk
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404

    # Remove file from disk
    try:
        os.remove(filepath)
    except OSError:
        return jsonify({"error": "Failed to delete file"}), 500

    # Handle Active State Reset(If the deleted file is currently open)
    if current_conversation_file == filepath:
        history = []
        current_conversation_file = None

        # Reset main History.json file
        with open(filename, "w") as file:
            json.dump({"current_file": current_conversation_file,
                       "messages": history
                       }, file, indent=4)

        # Re-bake Gemini prompt with a clean chat session
        all_facts = " ".join(memory.get("facts", []))
        updated_context = f"The user's verified name is {memory.get('name', 'Guest')}. Known profile facts: {all_facts}"

        updated_prompt = (
            "You are an AI."
            "Your name is Maximus."
            "You were created by MxDudeTesters"
            "And you Run on a Testing Model for MxDudeTesters"
            "The Ceo of MxDudeTesters is Kazibwe Augustine Maxwell from Uganda"
            "The Ceo has a networth of 1 Billion Dollars as of 2026"
            "Do not use markdown formatting in your responses. No asterisks, no bold text, no bullet points, no headers. Respond in plain conversational text only."
            f"Use this background identity context to customize your dialogue. {updated_context}"
        )

        chat = client.chats.create(
            model="gemini-3.1-flash-lite",
            config=types.GenerateContentConfig(system_instruction=updated_prompt),
            history=history,
        )

    # 6. Return success JSON response
    return jsonify({"status": "success", "message": f"Deleted {safe_filename}"})


# history click app route
@app.route('/load-chat', methods=['POST'])
def load_chat():
    global history, chat, current_conversation_file

    # Extract filename from incoming JSON payload
    data = request.json or {}
    filename_to_load = data.get("filename")

    if not filename_to_load:
        return jsonify({"error": "No filename provided"}), 400

    # Defensive path construction & validation
    # Guard against directory traversal attacks by taking only the basename
    safe_filename = os.path.basename(filename_to_load)
    filepath = os.path.join("conversations", safe_filename)

    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404

    # Read saved history from disk
    try:
        with open(filepath, "r") as file:
            loaded_history = json.load(file)
    except (json.JSONDecodeError, OSError):
        return jsonify({"error": "Failed to read conversation file"}), 500

    # Mutate server state(RAM)
    history = loaded_history
    current_conversation_file = filepath
    # Also sync the active History.json on disk to reflect this restored session
    with open(filename, "w") as file:
        json.dump({"current_file": current_conversation_file,
                   "messages": history
                   }, file, indent=4)

    # Re-bake Gemini prompt & re-create chat instance with restored history
    all_facts = " ".join(memory.get("facts", []))
    updated_context = f"The user's verified name is {memory.get('name', 'Guest')}. Known profile facts: {all_facts}"
    updated_prompt = (
        "You are an AI."
        "Your name is Maximus."
        "You were created by MxDudeTesters"
        "And you Run on a Testing Model for MxDudeTesters"
        "The Ceo of MxDudeTesters is Kazibwe Augustine Maxwell from Uganda"
        "The Ceo has a networth of 1 Billion Dollars as of 2026"
        "Do not use markdown formatting in your responses. No asterisks, no bold text, no bullet points, no headers. Respond in plain conversational text only."
        f"Use this background identity context to customize your dialogue. {updated_context}"
    )

    chat = client.chats.create(
        model="gemini-3.1-flash-lite",
        config=types.GenerateContentConfig(system_instruction=updated_prompt),
        history=history,
    )

    # 6. Return loaded messages back to frontend UI
    return jsonify({"status": "success", "history": history})


@app.route('/conversations', methods=['GET'])
def get_conversations():
    conversations_dir = "conversations"
    saved_chats = []

    if os.path.exists(conversations_dir):
        for file_name in os.listdir(conversations_dir):
            if file_name.endswith(".json"):
                file_path = os.path.join(conversations_dir, file_name)
                try:
                    with open(file_path, "r") as file:
                        chat_data = json.load(file)

                        preview = "Empty Conversation"
                        if chat_data:
                            first_msg = chat_data[0].get("parts", [{}])[0].get("text", "")
                            preview = first_msg[:30] + "..." if len(first_msg) > 30 else first_msg

                        mod_time = os.path.getmtime(file_path)

                        saved_chats.append({
                            "id": file_name,
                            "filename": file_name,
                            "preview": preview,
                            "timestamp": mod_time
                        })
                except(json.JSONDecodeError, OSError):
                    continue

    saved_chats.sort(key=lambda x: x["timestamp"], reverse=True)
    return jsonify({"conversations": saved_chats})


@app.route('/new-chat', methods=['POST'])
def new_chat():
    global history, chat, current_conversation_file

    # Save current history if there are messages to save
    if history:
        save_path = current_conversation_file or os.path.join("conversations",
                                                              f"chat_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.json")
        with open(save_path, "w") as file:
            json.dump(history, file, indent=4)
    # Clear history in RAM and reset main History.json
    history = []

    current_conversation_file = None
    with open(filename, "w") as file:
        json.dump({"current_file": current_conversation_file,
                   "messages": history
                   }, file, indent=4)

    # Recreating the chat session with clean history
    all_facts = " ".join(memory.get("facts", []))
    updated_context = f"The user's verified name is {memory.get('name', 'Guest')}. Known profile facts: {all_facts}"

    updated_prompt = (
        "You are an AI."
        "Your name is Maximus."
        "You were created by MxDudeTesters"
        "And you Run on a Testing Model for MxDudeTesters"
        "The Ceo of MxDudeTesters is Kazibwe Augustine Maxwell from Uganda"
        "The Ceo has a networth of 1 Billion Dollars as of 2026"
        "Do not use markdown formatting in your responses. No asterisks, no bold text, no bullet points, no headers. Respond in plain conversational text only."
        f"Use this background identity context to customize your dialogue. {updated_context}"
    )

    chat = client.chats.create(
        model="gemini-3.1-flash-lite",
        config=types.GenerateContentConfig(system_instruction=updated_prompt),
        history=history,
    )

    # 4. Return success JSON response
    return jsonify({"status": "success", "message": "New chat session started"})


@app.route('/chat', methods=['POST'])
def chat_handler():
    global chat, memory, history, current_conversation_file

    user_message = request.json.get("message")
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    if not current_conversation_file:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        current_conversation_file = os.path.join("conversations", f"chat_{timestamp}.json")

    clean_message = user_message.lower().strip()

    # ----NAME TRIGGER DETECTION ----
    for trigger in name_triggers:
        if trigger in clean_message:
            # extract the text after the trigger
            trigger_index = clean_message.find(trigger)
            extracted = clean_message[trigger_index + len(trigger):].strip()
            # check if it looks like a name
            if is_likely_a_name(extracted):
                # Update memory dictionary in RAM
                memory["name"] = extracted.title()

                # Save updated memory to memory.json
                with open(memory_name, "w") as file:
                    json.dump(memory, file, indent=4)

                # Re-bake system prompt & chat instance with  new name
                all_facts = " ".join(memory.get("facts", []))
                updated_context = f"The user's verified name is {memory['name']}. Known profile facts: {all_facts}"

                updated_prompt = (
                    "You are an AI."
                    "Your name is Maximus."
                    "You were created by MxDudeTesters"
                    "And you Run on a Testing Model for MxDudeTesters"
                    "The Ceo of MxDudeTesters is Kazibwe Augustine Maxwell from Uganda"
                    "The Ceo has a networth of 1 Billion Dollars as of 2026"
                    "Do not use markdown formatting in your responses. No asterisks, no bold text, no bullet points, no headers. Respond in plain conversational text only."
                    f"Use this background identity context to customize your dialogue. {updated_context}"
                )

                chat = client.chats.create(
                    model="gemini-3.1-flash-lite",
                    config=types.GenerateContentConfig(system_instruction=updated_prompt),
                    history=history,
                )
                break
    # ---- MEMORY TRIGGER DETECTION ----
    if any(trigger in clean_message for trigger in memory_triggers):
        # loop through to pinpoint exactly which trigger phrase was hit
        for trigger in memory_triggers:
            if trigger in clean_message:
                # Extract the fact by stripping the trigger string out
                clean_fact = user_message.replace(trigger, " ").replace(trigger.capitalize(), "").strip()

                # Update RAM
                memory["facts"].append(clean_fact)

                # Save data in memory.json
                with open(memory_name, "w") as file:
                    json.dump(memory, file, indent=4)

                # Rebuild and re-bake prompt configuration parameters
                all_facts = " ".join(memory.get("facts", []))
                updated_context = f"The user's verified name is {memory.get('name', 'Guest')}. Known profile facts: {all_facts}"

                updated_prompt = ("You are an AI."
                                  "Your name is Maximus."
                                  "You were created by MxDudeTesters"
                                  "And you Run on a Testing Model for MxDudeTesters"
                                  "The Ceo of MxDudeTesters is Kazibwe Augustine Maxwell from Uganda"
                                  "The Ceo has a networth of 1 Billion Dollars as of 2026"
                                  "Do not use markdown formatting in your responses. No asterisks, no bold text, no bullet points, no headers. Respond in plain conversational text only."
                                  f"Use this background identity context to customize your dialogue. {updated_context}"
                                  )

                chat = client.chats.create(model="gemini-3.1-flash-lite",
                                           config=types.GenerateContentConfig(
                                               system_instruction=updated_prompt),
                                           history=history
                                           )
                break  # The trigger has been found and cleaned up. Break the inner lookup loop.

    history.append({"role": "user", "parts": [{"text": user_message}]})
    response = chat.send_message(user_message)
    ai_response = response.text
    history.append({"role": "model", "parts": [{"text": ai_response}]})

    with open(filename, "w") as file:
        json.dump({"current_file": current_conversation_file,
                   "messages": history
                   }, file, indent=4)

    if current_conversation_file:
        with open(current_conversation_file, "w") as file:
            json.dump(history, file, indent=4)

    return jsonify({"response": ai_response})


if __name__ == '__main__':
    app.run(debug=True)
