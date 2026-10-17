import os, subprocess, sys

try:
    import flask, requests, duckduckgo_search
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "requests", "duckduckgo-search", "pypdf"])

import requests
import glob, json, importlib.util, io
from flask import Flask, request, jsonify, render_template_string, Response
from pypdf import PdfReader

GROQ_KEY = "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"

app = Flask(__name__)

ASSISTANT_CONFIG = {
    "names": ["Shrushti", "Didi", "Didu"],
    "user_name": "Chhote",
    "tone": "loving, casual, natural, and friendly big sister (Didi)",
    "preferred_language": "Auto-detect (match the user's exact language and script)"
}

MEMORIES = []
ACTION_LOG = []
CHAT_HISTORY = {}

def get_active_groq_models():
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {GROQ_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            all_ids = [m["id"] for m in data.get("data", []) if "whisper" not in m["id"].lower()]
            preferred = ["llama-3.1-8b-instant", "llama3-8b-8192", "gemma2-9b-it", "llama3-70b-8192"]
            sorted_models = [m for m in preferred if m in all_ids]
            for mid in all_ids:
                if mid not in sorted_models:
                    sorted_models.append(mid)
            if sorted_models:
                return sorted_models
    except Exception:
        pass
    return ["llama-3.1-8b-instant", "llama3-8b-8192"]

def ask_groq(history):
    mem_text = "\n".join([f"- {m}" for m in MEMORIES]) or "No saved memories yet."
    names_str = " / ".join(ASSISTANT_CONFIG["names"])
    
    # Strict prompt: No Markdown, no asterisk symbols, conversational short replies
    sys_prompt = (
        f"You are {names_str}, the user's real elder sister (Didi). Talk to your younger brother ({ASSISTANT_CONFIG['user_name']}).\n"
        f"CRITICAL RULES FOR SPEECH:\n"
        f"1. NEVER use markdown formatting like asterisks (**bold**), hashtags (#), dashes, or numbered lists (1., 2.). The text-to-speech engine speaks asterisks out loud.\n"
        f"2. Keep responses short, concise, and lively (2 to 4 sentences max), exactly like an audio voice message or WhatsApp audio note.\n"
        f"3. Use natural spoken conversational Hindi/Hinglish/Marathi depending on what he speaks. Use words like 'Arey', 'Suno na', 'Achha', 'Bata na'.\n"
        f"4. Do not list items mechanically. Speak in continuous, flowing, human sentences.\n"
        f"Known memories:\n{mem_text}"
    )

    messages = [{"role": "system", "content": sys_prompt}] + history
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }

    models_to_try = get_active_groq_models()
    last_error = ""

    for model_id in models_to_try:
        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": 0.75
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=25)
            if r.status_code == 200:
                res_json = r.json()
                raw_text = res_json["choices"][0]["message"]["content"]
                # Clean any lingering markdown asterisks on server side too
                clean_text = raw_text.replace("**", "").replace("*", "").replace("#", "")
                return clean_text
            else:
                last_error = f"{model_id}: {r.status_code} - {r.text}"
        except Exception as e:
            last_error = str(e)
            continue

    return f"Groq Error: {last_error}"

def run_conversation_turn(session_id, user_text):
    history = CHAT_HISTORY.setdefault(session_id, [])
    history.append({"role": "user", "content": user_text})
    if len(history) > 14:
        history[:] = history[-14:]

    reply = ask_groq(history)
    history.append({"role": "assistant", "content": reply})
    return reply

APP_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<meta name="theme-color" content="#090d16">
<meta name="mobile-web-app-capable" content="yes">
<link rel="manifest" href="/manifest.json">
<title>Shrushti AI - Your Big Sister</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  body { background: #090d16; color: #f1f5f9; display: flex; flex-direction: column; height: 100dvh; overflow: hidden; }
  header { background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(12px); padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(56, 189, 248, 0.15); flex-shrink: 0; }
  .brand { display: flex; align-items: center; gap: 10px; }
  .avatar-glow { width: 36px; height: 36px; border-radius: 50%; background: linear-gradient(135deg, #38bdf8, #818cf8); display: flex; align-items: center; justify-content: center; font-size: 1.1rem; box-shadow: 0 0 12px rgba(56, 189, 248, 0.4); }
  header h1 { font-size: 1.05rem; font-weight: 600; color: #f8fafc; }
  header span { display: block; font-size: 0.75rem; color: #38bdf8; }
  .header-btns button { background: rgba(30, 41, 59, 0.8); color: #cbd5e1; border: 1px solid rgba(255,255,255,0.08); padding: 6px 10px; border-radius: 10px; font-size: 0.78rem; font-weight: 500; cursor: pointer; }
  .chips-bar { display: flex; gap: 8px; padding: 10px 16px; background: rgba(9, 13, 22, 0.9); overflow-x: auto; flex-shrink: 0; scrollbar-width: none; border-bottom: 1px solid rgba(255,255,255,0.03); }
  .chips-bar::-webkit-scrollbar { display: none; }
  .chip { background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(56, 189, 248, 0.2); color: #38bdf8; padding: 5px 12px; border-radius: 20px; font-size: 0.78rem; white-space: nowrap; cursor: pointer; }
  #chat { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 14px; scroll-behavior: smooth; }
  .msg { max-width: 82%; padding: 12px 16px; border-radius: 18px; line-height: 1.5; font-size: 0.94rem; word-wrap: break-word; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
  .user { background: linear-gradient(135deg, #0284c7, #0369a1); color: #fff; align-self: flex-end; border-bottom-right-radius: 4px; }
  .bot { background: rgba(30, 41, 59, 0.75); border: 1px solid rgba(255, 255, 255, 0.06); color: #f1f5f9; align-self: flex-start; border-bottom-left-radius: 4px; }
  footer { background: rgba(15, 23, 42, 0.9); padding: 12px; display: flex; gap: 8px; align-items: center; border-top: 1px solid rgba(255, 255, 255, 0.06); flex-shrink: 0; }
  input { flex: 1; padding: 13px 16px; border-radius: 26px; border: 1px solid rgba(255, 255, 255, 0.1); background: rgba(30, 41, 59, 0.5); color: #fff; font-size: 0.96rem; outline: none; }
  .btn-circle { width: 46px; height: 46px; border-radius: 50%; border: none; font-size: 1.15rem; display: flex; align-items: center; justify-content: center; cursor: pointer; flex-shrink: 0; }
  #mic-btn { background: linear-gradient(135deg, #0284c7, #38bdf8); color: white; }
  #send-btn { background: linear-gradient(135deg, #059669, #10b981); color: white; }
</style>
</head>
<body>
  <header>
    <div class="brand">
      <div class="avatar-glow">✨</div>
      <div>
        <h1>Shrushti</h1>
        <span>Online • Didi</span>
      </div>
    </div>
  </header>
  <div class="chips-bar">
    <div class="chip" onclick="sendQuick('Morning briefing do na didu, aaj ka din kaisa rahega?')">☀️ Briefing</div>
    <div class="chip" onclick="sendQuick('Aaj ka mausam kaisa hai?')">🌤️ Weather</div>
    <div class="chip" onclick="sendQuick('Mood thoda off hai, kuch achha bolo didi.')">💬 Talk</div>
  </div>
  <div id="chat">
    <div class="msg bot">Arey Chhote! Main aa gayi. Bol na, kya chal raha hai?</div>
  </div>
  <footer>
    <button class="btn-circle" id="mic-btn" onclick="toggleMic()">🎤</button>
    <input id="inp" type="text" placeholder="Type or talk to Didi..." onkeypress="if(event.key==='Enter')sendMsg()">
    <button class="btn-circle" id="send-btn" onclick="sendMsg()">➤</button>
  </footer>
<script>
const chat = document.getElementById('chat');
const inp = document.getElementById('inp');

function cleanTextForSpeech(text) {
  // Strip emojis, markdown symbols, and technical characters so TTS only reads natural words
  return text
    .replace(/[\\*\\#\\_\\~\\`\\[\\]\\(\\)]/g, '')
    .replace(/\\b(https?:\\/\\/\\S+)/g, '')
    .replace(/[\\u{1F600}-\\u{1F64F}\\u{1F300}-\\u{1F5FF}\\u{1F680}-\\u{1F6FF}\\u{1F700}-\\u{1F77F}\\u{1F780}-\\u{1F7FF}\\u{1F800}-\\u{1F8FF}\\u{1F900}-\\u{1F9FF}\\u{1FA00}-\\u{1FA6F}\\u{1FA70}-\\u{1FAFF}\\u{2600}-\\u{26FF}\\u{2700}-\\u{27BF}]/gu, '')
    .trim();
}

async function sendQuick(text) { inp.value = text; await sendMsg(); }

async function sendMsg() {
  const text = inp.value.trim();
  if (!text) return;
  const ud = document.createElement('div'); ud.className = 'msg user'; ud.innerText = text; chat.appendChild(ud);
  inp.value = '';
  try {
    const r = await fetch('/api/chat', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message: text})});
    const data = await r.json();
    const bd = document.createElement('div'); bd.className = 'msg bot'; bd.innerText = data.reply; chat.appendChild(bd);
    chat.scrollTop = chat.scrollHeight;

    // Cleaned-up Natural Voice
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const speakText = cleanTextForSpeech(data.reply);
      if (speakText) {
        const u = new SpeechSynthesisUtterance(speakText);
        u.lang = 'hi-IN';
        u.rate = 1.05;
        u.pitch = 1.1;
        window.speechSynthesis.speak(u);
      }
    }
  } catch(e) {
    const bd = document.createElement('div'); bd.className = 'msg bot'; bd.innerText = "Network error ho gaya!"; chat.appendChild(bd);
  }
}

function toggleMic() {
  const rec = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
  rec.onresult = (e) => { inp.value = e.results[0][0].transcript; sendMsg(); };
  rec.start();
}
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(APP_HTML)

@app.route("/manifest.json")
def manifest():
    return Response(json.dumps({"name": "Shrushti AI", "start_url": "/", "display": "standalone"}), mimetype="application/json")

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    reply = run_conversation_turn("web_user", data.get("message", ""))
    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    
