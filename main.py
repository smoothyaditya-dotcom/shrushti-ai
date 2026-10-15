import os, subprocess, sys

try:
    import flask, requests, duckduckgo_search
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "requests", "duckduckgo-search", "pypdf"])

import requests
import glob, json, importlib.util, io
from flask import Flask, request, jsonify, render_template_string, Response
from pypdf import PdfReader

# Apni Groq API key yahan daal do (gsk_ se shuru hoti hai)
GROQ_KEY = "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"

app = Flask(__name__)

ASSISTANT_CONFIG = {
    "names": ["Shrushti", "Didi", "Didu"],
    "user_name": "Chhote",
    "tone": "loving, casual, natural, and friendly big sister (Didi)",
    "preferred_language": "Auto-detect (match the user's exact language and script)"
}

MODEL_NAME = "llama-3.1-8b-instant"

MEMORIES = []
ACTION_LOG = []
CHAT_HISTORY = {}

def save_memory(args):
    fact = args.get("fact", "")
    MEMORIES.append(fact)
    ACTION_LOG.append({"action": "save_memory", "fact": fact})
    return {"status": "Saved to memory", "fact": fact}

def recall_memory(args):
    query = args.get("query", "").lower()
    matches = [m for m in MEMORIES if query in m.lower()]
    return {"matches": matches if matches else MEMORIES}

def undo_last_action(args):
    if not ACTION_LOG:
        return {"status": "Nothing to undo."}
    last = ACTION_LOG.pop()
    if last["action"] == "save_memory" and last["fact"] in MEMORIES:
        MEMORIES.remove(last["fact"])
        return {"status": f"Undid memory: {last['fact']}"}
    return {"status": "Undone"}

def customize_assistant(args):
    prev = dict(ASSISTANT_CONFIG)
    if "user_name" in args:
        ASSISTANT_CONFIG["user_name"] = args["user_name"]
    if "tone" in args:
        ASSISTANT_CONFIG["tone"] = args["tone"]
    if "preferred_language" in args:
        ASSISTANT_CONFIG["preferred_language"] = args["preferred_language"]
    ACTION_LOG.append({"action": "customize", "previous": prev})
    return {"status": "Updated immediately", "current_config": ASSISTANT_CONFIG}

TOOLS = [
    {
        "name": "save_memory",
        "description": "Save an important fact, preference, or goal about the user.",
        "parameters": {"type": "object", "properties": {"fact": {"type": "string"}}, "required": ["fact"]}
    },
    {
        "name": "recall_memory",
        "description": "Search saved memories on demand.",
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": {"query"}}
    },
    {
        "name": "undo_last_action",
        "description": "Undo the last memory saved or setting changed.",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "customize_assistant",
        "description": "Update user name, tone, or preferred language.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_name": {"type": "string"},
                "tone": {"type": "string"},
                "preferred_language": {"type": "string"}
            }
        }
    }
]

HANDLERS = {
    "save_memory": save_memory,
    "recall_memory": recall_memory,
    "undo_last_action": undo_last_action,
    "customize_assistant": customize_assistant
}

for path in glob.glob("plugins/*.py"):
    spec = importlib.util.spec_from_file_location("plugin", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, "TOOL") and hasattr(mod, "handler"):
        TOOLS.append(mod.TOOL)
        HANDLERS[mod.TOOL["name"]] = mod.handler

def ask_groq(history):
    if not GROQ_KEY or "gsk_Yahan" in GROQ_KEY:
        return "Arey Chhote! Code mein apni asli Groq API key (gsk_...) dalna bhool gaye ho!"

    mem_text = "\n".join([f"- {m}" for m in MEMORIES]) or "No saved memories yet."
    names_str = " / ".join(ASSISTANT_CONFIG["names"])
    
    sys_prompt = (
        f"Your name is {names_str}. You are a very close, loving, and casual big sister (Didi) to the user. "
        f"Talk in a super natural, conversational, and everyday tone—just like chatting on WhatsApp or talking face-to-face. "
        f"Use casual expressions like 'Arey', 'Suno', 'Acha', 'Haan', emojis, and keep your sentences short, lively, and warm. "
        f"Never sound like a robot, tool, or formal AI. Always act like a real family member who cares deeply. "
        f"MULTILINGUAL RULE: Reply in the exact casual language and script the user uses (Hinglish, Marathi, Hindi, English). "
        f"Current language setting: {ASSISTANT_CONFIG['preferred_language']}.\n"
        f"Known facts:\n{mem_text}"
    )

    messages = [{"role": "system", "content": sys_prompt}] + history

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "temperature": 0.7
    }

    try:
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code == 200:
            res_json = r.json()
            return res_json["choices"][0]["message"]["content"]
        else:
            return f"Groq API Error ({r.status_code}): {r.text}"
    except Exception as e:
        return f"Exception: {str(e)}"

def run_conversation_turn(session_id, user_text):
    history = CHAT_HISTORY.setdefault(session_id, [])
    history.append({"role": "user", "content": user_text})
    if len(history) > 20:
        history[:] = history[-20:]

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
<meta name="apple-mobile-web-app-capable" content="yes">
<link rel="manifest" href="/manifest.json">
<title>Shrushti AI - Your Big Sister</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  body { background: #090d16; color: #f1f5f9; display: flex; flex-direction: column; height: 100dvh; overflow: hidden; }
  header { background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(12px); padding: 12px 16px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(56, 189, 248, 0.15); flex-shrink: 0; z-index: 10; }
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
  #mem-panel { display: none; background: rgba(15, 23, 42, 0.95); backdrop-filter: blur(16px); padding: 16px; border-bottom: 1px solid rgba(56, 189, 248, 0.2); max-height: 45vh; overflow-y: auto; flex-shrink: 0; z-index: 5; }
  #mem-panel h3 { font-size: 0.95rem; color: #38bdf8; margin-bottom: 8px; }
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
    <div class="chip" onclick="sendQuick('☀️ Morning Briefing dedo didu!')">☀️ Briefing</div>
    <div class="chip" onclick="sendQuick('Aaj ka mausam kaisa hai?')">🌤️ Weather</div>
    <div class="chip" onclick="sendQuick('Kuch motivational bolo didu!')">💬 Motivation</div>
  </div>
  <div id="mem-panel"></div>
  <div id="chat">
    <div class="msg bot">Arey Chhote! Main aa gayi. Batao kya chal raha hai? 💕</div>
  </div>
  <footer>
    <button class="btn-circle" id="mic-btn" onclick="toggleMic()">🎤</button>
    <input id="inp" type="text" placeholder="Type or talk to Didi..." onkeypress="if(event.key==='Enter')sendMsg()">
    <button class="btn-circle" id="send-btn" onclick="sendMsg()">➤</button>
  </footer>
<script>
const chat = document.getElementById('chat');
const inp = document.getElementById('inp');
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
      const u = new SpeechSynthesisUtterance(data.reply);
      u.lang = 'hi-IN';
      window.speechSynthesis.speak(u);
    }
  } catch(e) {
    const bd = document.createElement('div'); bd.className = 'msg bot'; bd.innerText = "Network error!"; chat.appendChild(bd);
  }
}
function toggleMic() {
  const rec = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
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
    
