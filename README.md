# Maximus - Personal AI Assistant

Maximus is a web-based AI chatbot I built in 2026. You can chat with it as a guest or sign in, and it remembers your name and facts you tell it across conversations. It can also answer out loud with a generated voice.

**Live_demo:** https://maximus-bot-xnz9.onrender.com/
*(Hosted on a free plan: the first load can take up to a minute while the server wakes up.)*

## Features

- **Chat with Gemini:** Conversations run on Google's Gemini model, with a custom system prompt that gives Maximus its personality.
- **Accounts:** Sign up and log in with email or Google (via Supabase Auth), or chat as a guest without an account.
- **Saved conversations:** Start new chats, reopen old ones from the sidebar, or delete them. Conversations are stored per user in Supabase.
- **Memory:** Say "my name is …" or "remember that …" and Maximus saves it to your profile and uses it in later chats. A "Wipe Memory" option clears it again.
- **Voice replies:** Optional spoken answers generated with the ElevenLabs text-to-speech API.
- **Wake word (experimental, local only):** `wake_word.py` listens for "Hey Jarvis" with openWakeWord and signals the Flask app.

## How it's built

| Part | Technology |
|------|------------|
| Backend | Python, Flask, Gunicorn |
| AI model | Google Gemini (`google-genai`) |
| Database & login | Supabase (Auth + Postgres) |
| Voice | ElevenLabs API |
| Frontend | HTML, CSS, JavaScript |
| Hosting | Render |

I wrote the Python backend myself: the Flask routes, the per-user memory and conversation logic, the name and memory trigger detection, and the Gemini, Supabase and ElevenLabs integrations. The frontend (HTML, CSS and JavaScript) was built with help from AI coding tools. This is why GitHub lists HTML as the main language, since the page templates are much longer than the backend code.

`main.py` is the first version of Maximus: a command-line chatbot that saves its history to a JSON file. `app.py` is the web version that grew out of it.

## Running it locally

1. Clone the repository and install the dependencies:
   ```bash
   git clone https://github.com/TownMax/Maximus_Bot.git
   cd Maximus_Bot
   pip install -r requirements.txt
   ```
2. Create a `.env` file in the project folder:
   ```
   GEMINI_API_KEY=your_gemini_key
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   ELEVENLABS_API_KEY=your_elevenlabs_key      # optional, for voice
   ELEVENLABS_VOICE_ID=your_voice_id           # optional, for voice
   FLASK_SECRET_KEY=any_long_random_string
   ```
3. Your Supabase project needs two tables, `memories` and `conversations`.
4. Start the app:
   ```bash
   python app.py
   ```
   Then open http://127.0.0.1:5000 in your browser.

## What I learned

- Building a Flask backend with several API routes and connecting it to a frontend
- Working with external APIs (Gemini, Supabase, ElevenLabs) and keeping API keys out of the code with environment variables
- Storing data per user and handling guests and logged-in users differently
- Deploying a Python web app to the cloud

## Ideas for next steps

- Let the AI decide what is worth remembering, instead of fixed trigger phrases
- Stream replies word by word in the web version, like the command-line version does
- Bring the wake word feature to the browser
