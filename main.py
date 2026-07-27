import random as rd
import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client()

filename = "History.json"
memory_name = "memory.json"

try:
    with open(filename, "r") as file:
        history = json.load(file)
except (FileNotFoundError, json.decoder.JSONDecodeError):
    history = []

try:
    with open(memory_name, "r") as file:
        memory = json.load(file)
except (FileNotFoundError, json.decoder.JSONDecodeError):
    memory = {"name": "Guest"}
    with open(memory_name, "w") as file:
        json.dump(memory, file, indent=4)

starters = ["Hey! How's your day going?",
            "Hello! ready to jazz",
            "Whatsup with you today?"]

system_prompt = ("You are an AI."
                 "Your name is Maximus."
                 "You were created by MxDudeTesters"
                 "And you Run on a Testing Model for MxDudeTesters"
                 "The Ceo of MxDudeTesters is Kazibwe Augustine Maxwell from Uganda"
                 "The Ceo has a networth of 1 Billion Dollars as of 2026"
                 )


chat = client.chats.create(model = "gemini-3.1-flash-lite",
                           config=types.GenerateContentConfig(
                               system_instruction=system_prompt),
                           history=history
                           )

#printing the starter from list.

print(f"Maximus:{rd.choice(starters)}")

while True:
    #Taking User Input
    user_input = input("Reply: ").strip().lower()
    #Checking for goodbye
    if any(word in user_input for word in ["bye", "quit", "exit", "goodbye"]):
        goodbye_statements = ["Goodbye! Talk soon",
                              "Take Care!",
                              "See you later!",
                              "See you next time!",]

        print(f"maximus:{rd.choice(goodbye_statements)}")

        # This is giving the chat history to GEMINI_
        with open("History.json", "w") as file:
            json.dump(history, file, indent=4)
        break
    #sending....to..gemini
    response = chat.send_message_stream(user_input)
    full_response_text = ""
    #Append user message to history
    history.append({"role": "user", "parts":[{"text": user_input}]})
    #Prints Maximus AI label first before printing the text
    print("Maximus: ", end="", flush=True)
    #The streaming loop logic
    for chunk in response:
        chunk_text = chunk.text
        print( chunk_text, end="", flush = True)
        full_response_text += chunk_text
    #Add a new line after the response is done
    print()
    #Store history for the AI
    history.append({"role": "model", "parts":[{"text": full_response_text.strip()}]})


