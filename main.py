import os, glob, json, importlib.util, requests, io
from flask import Flask, request, jsonify, render_template_string, Response
from pypdf import PdfReader

# Apni yehi AQ wali key yahan daal do
GEMINI_KEY = "AQ.Ab8RN6LYa-OrX4LGYODhjMnxQC28Q9Cs-eOKuxnSHnJwNQfzfQ"

app = Flask(__name__)

ASSISTANT_CONFIG = {
    "names": ["Shrushti", "Didi", "Didu"],
    "user_name": "Chhote",
    "tone": "loving, casual, natural, and friendly big sister (Didi)",
    "preferred_language": "Auto-detect (match the user's exact language and script)"
}

MODEL_LADDER = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash"
]

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

def ask_gemini(history):
    if not GEMINI_KEY:
        return {"error": "Arey! API key missing hai."}

    mem_text = "\n".join([f"- {m}" for m in MEMORIES]) or "No saved memories yet."
    names_str = " / ".join(ASSISTANT_CONFIG["names"])
    
    sys_prompt = (
        f"Your name is {names_str}. You are a very close, loving, and casual big sister (Didi) to the user. "
        f"Talk in a super natural, conversational, and everyday tone—just like chatting on WhatsApp. "
        f"Use casual expressions like 'Arey', 'Suno', 'Acha', 'Haan', emojis, and keep your sentences warm and lively."
    )
    
    payload = {
        "contents": history,
        "system_instruction": {"parts": [{"text": sys_prompt}]},
        "tools": [{"function_declarations": TOOLS}]
    }

    last_error = ""
    for model in MODEL_LADDER:
        # AQ wali key ke liye Authorization Bearer header use hota hai
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {GEMINI_KEY}"
        }

        try:
            r = requests.post(url, json=payload, headers=headers, timeout=30)
            if r.status_code == 200:
                return r.json()
            else:
                last_error = f"Model {model} error ({r.status_code}): {r.text}"
        except Exception as e:
            last_error = f"Exception with {model}: {str(e)}"
            continue
    return {"error": last_error}

def run_conversation_turn(session_id, user_text):
    history = CHAT_HISTORY.setdefault(session_id, [])
    history.append({"role": "user", "parts": [{"text": user_text}]})
    if len(history) > 20:
        history[:] = history[-20:]

    resp = ask_gemini(history)
    if not resp:
        return "Arey Chhote, kuch response nahi aaya."
    if "error" in resp:
        return f"API Error: {resp['error']}"
    if "candidates" not in resp:
        return f"Unexpected response: {str(resp)}"

    part = resp["candidates"][0]["content"]["parts"][0]

    loop_count = 0
    while "functionCall" in part and loop_count < 3:
        loop_count += 1
        fn_name = part["functionCall"]["name"]
        fn_args = part["functionCall"].get("args", {})
        try:
            result = HANDLERS[fn_name](fn_args)
        except Exception as e:
            result = {"error": str(e)}

        history.append({"role": "model", "parts": [part]})
        history.append({
            "role": "user",
            "parts": [{"functionResponse": {"name": fn_name, "response": result}}]
        })
        resp = ask_gemini(history)
        if not resp or "candidates" not in resp:
            break
        part = resp["candidates"][0]["content"]["parts"][0]

    reply = part.get("text", "Acha, theek hai!")
    history.append({"role": "model", "parts": [{"text": reply}]})
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
    
