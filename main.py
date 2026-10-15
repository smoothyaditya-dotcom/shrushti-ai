import os, glob, json, importlib.util, io
from flask import Flask, request, jsonify, render_template_string, Response
from google import genai
from pypdf import PdfReader

# Apni key yahan daal do (chahe AIza wali ho ya AQ wali, SDK khud handle kar lega)
GEMINI_KEY = "AQ.Ab8RN6K5izNAAcoZXagQfO-7UIIaFts2uhP8Io-oZm9YjJQm_Q"

app = Flask(__name__)

# Official GenAI Client setup
client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY and "Yahan" not in GEMINI_KEY else None

ASSISTANT_CONFIG = {
    "names": ["Shrushti", "Didi", "Didu"],
    "user_name": "Chhote",
    "tone": "loving, casual, natural, and friendly big sister (Didi)",
    "preferred_language": "Auto-detect (match the user's exact language and script)"
}

# Model ladder
MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]

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
        "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}
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

def ask_gemini(user_message):
    if not client:
        return "Arey Chhote! Code mein valid GEMINI_API_KEY daalna bhool gaye ho."

    mem_text = "\n".join([f"- {m}" for m in MEMORIES]) or "No saved memories yet."
    sys_prompt = (
        f"Your name is Shrushti (Didi). You are a very close, loving, and casual big sister to the user. "
        f"Talk in a super natural, conversational everyday tone (WhatsApp style). Use casual words like 'Arey', 'Suno', emojis. "
        f"Known facts:\n{mem_text}"
    )

    last_err = ""
    for model_name in MODELS:
        try:
            # Official SDK call configuration
            response = client.models.generate_content(
                model=model_name,
                contents=user_message,
                config={
                    "system_instruction": sys_prompt,
                    "temperature": 0.7,
                }
            )
            if response and response.text:
                return response.text
        except Exception as e:
            last_err = str(e)
            continue
            
    return f"Arey, sabhi models busy the ya error aaya: {last_err}"

@app.route("/")
def index():
    return render_template_string(APP_HTML)

@app.route("/manifest.json")
def manifest():
    return Response(json.dumps({"name": "Shrushti AI", "start_url": "/", "display": "standalone"}), mimetype="application/json")

@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True)
    user_text = data.get("message", "")
    reply = ask_gemini(user_text)
    return jsonify({"reply": reply})

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
  <div id="chat">
    <div class="msg bot">Arey Chhote! Main aa gayi. Batao kya chal raha hai? 💕</div>
  </div>
  <footer>
    <button class="btn-circle" id="mic-btn" onclick="toggleMic()">🎤</button>
    <input id="inp" type="text" placeholder="Type to Didi..." onkeypress="if(event.key==='Enter')sendMsg()">
    <button class="btn-circle" id="send-btn" onclick="sendMsg()">➤</button>
  </footer>
<script>
const chat = document.getElementById('chat');
const inp = document.getElementById('inp');
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
  } catch(e) {
    const bd = document.createElement('div'); bd.className = 'msg bot'; bd.innerText = "Network error!"; chat.appendChild(bd);
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
    
