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
    "preferred_language": "Auto-detect"
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
    
    # Pronunciation and Script instruction
    sys_prompt = (
        f"You are {names_str}, the user's real elder sister (Didi). Talk to your brother ({ASSISTANT_CONFIG['user_name']}).\n"
        f"RULES FOR NATURAL SPEECH:\n"
        f"1. Never use markdown like asterisks (**), hashtags (#), or lists. Keep it short (2-3 sentences).\n"
        f"2. IMPORTANT FOR MARATHI/HINDI: Whenever speaking in Marathi or Hindi, write directly in Devanagari script (मराठी किंवा हिंदी लिपीमध्ये लिहा) like 'आणि', 'काय चाललंय', 'बरं'. Do NOT write Marathi in English/Roman script because the text-to-speech mispronounces words like 'ani' as 'एनाय'.\n"
        f"3. Speak with warmth, affection, and everyday casual tone.\n"
        f"Memories:\n{mem_text}"
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
            "temperature": 0.7
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=25)
            if r.status_code == 200:
                res_json = r.json()
                clean_text = res_json["choices"][0]["message"]["content"]
                return clean_text.replace("**", "").replace("*", "").replace("#", "")
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
<html lang="mr">
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
  #mem-panel { display: none; background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(16px); padding: 16px; border-bottom: 1px solid rgba(56, 189, 248, 0.2); max-height: 45vh; overflow-y: auto; flex-shrink: 0; }
  .mem-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 0.88rem; color: #cbd5e1; }
  .mem-item button { background: rgba(239, 68, 68,.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4); padding: 3px 10px; border-radius: 6px; font-size: 0.78rem; cursor: pointer; }
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
    <div class="header-btns">
      <button onclick="toggleMemories()">🧠 Memories</button>
    </div>
  </header>
  <div class="chips-bar">
    <div class="chip" onclick="sendQuick('Morning briefing de na didu!')">☀️ Briefing</div>
    <div class="chip" onclick="sendQuick('आज हवामान कसं आहे?')">🌤️ Weather</div>
    <div class="chip" onclick="sendQuick('काय चाललंय दीदी?')">💬 Talk</div>
  </div>
  <div id="mem-panel"></div>
  <div id="chat">
    <div class="msg bot">अरे छोट्या! मी आले. बोल ना, काय चाललंय? 💕</div>
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
  let cleaned = text
    .replace(/[\\*\\#\\_\\~\\`\\[\\]\\(\\)]/g, '')
    .replace(/\\b(https?:\\/\\/\\S+)/g, '')
    .replace(/[\\u{1F600}-\\u{1F64F}\\u{1F300}-\\u{1F5FF}\\u{1F680}-\\u{1F6FF}\\u{1F700}-\\u{1F77F}\\u{1F780}-\\u{1F7FF}\\u{1F800}-\\u{1F8FF}\\u{1F900}-\\u{1F9FF}\\u{1FA00}-\\u{1FA6F}\\u{1FA70}-\\u{1FAFF}\\u{2600}-\\u{26FF}\\u{2700}-\\u{27BF}]/gu, '');

  // Roman-to-Devanagari phonetic fix for speech engine
  cleaned = cleaned.replace(/\\bani\\b/gi, 'आणि');
  cleaned = cleaned.replace(/\\baani\\b/gi, 'आणि');
  cleaned = cleaned.replace(/\\bkay\\b/gi, 'काय');
  cleaned = cleaned.replace(/\\bpan\\b/gi, 'पण');

  return cleaned.trim();
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

    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const speakText = cleanTextForSpeech(data.reply);
      if (speakText) {
        const u = new SpeechSynthesisUtterance(speakText);
        // Marathi check
        const isMarathi = /[\\u0900-\\u097F]/.test(speakText);
        u.lang = isMarathi ? 'mr-IN' : 'hi-IN';
        u.rate = 1.0;
        u.pitch = 1.05;
        window.speechSynthesis.speak(u);
      }
    }
  } catch(e) {
    const bd = document.createElement('div'); bd.className = 'msg bot'; bd.innerText = "Network error!"; chat.appendChild(bd);
  }
}

function toggleMic() {
  const rec = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
  rec.lang = 'mr-IN';
  rec.onresult = (e) => { inp.value = e.results[0][0].transcript; sendMsg(); };
  rec.start();
}

async function toggleMemories() {
  const panel = document.getElementById('mem-panel');
  if (panel.style.display === 'block') { panel.style.display = 'none'; return; }
  const r = await fetch('/api/memories');
  const data = await r.json();
  panel.innerHTML = '<h3>🧠 Saved Memories:</h3>' + (data.memories.length ? data.memories.map((m, i) =>
    `<div class="mem-item"><span>${m}</span><button onclick="delMem(${i})">Delete</button></div>`
  ).join('') : '<p style="color:#94a3b8; font-size:0.85rem;">No memories saved yet.</p>');
  panel.style.display = 'block';
}

async function delMem(idx) {
  await fetch('/api/memories/' + idx, {method: 'DELETE'});
  toggleMemories();
  toggleMemories();
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

@app.route("/api/memories", methods=["GET"])
def api_get_memories():
    return jsonify({"memories": MEMORIES})

@app.route("/api/memories/<int:idx>", methods=["DELETE"])
def api_del_memory(idx):
    if 0 <= idx < len(MEMORIES):
        MEMORIES.pop(idx)
    return jsonify({"status": "deleted"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    
