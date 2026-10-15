from duckduckgo_search import DDGS

TOOL = {
    "name": "multi_mode_web_search",
    "description": "Search the live web for news, research, product prices, or general facts.",
    "parameters": {
        "type": "object",
        "properties": {
            "mode": {
                "type": "string",
                "enum": ["news", "research", "price", "search"],
                "description": "Type of search to run"
            },
            "query": {
                "type": "string",
                "description": "The search keywords"
            }
        },
        "required": ["mode", "query"]
    }
}

def handler(args):
    mode = args.get("mode", "search")
    query = args.get("query", "")
    ddgs = DDGS()
    try:
        if mode == "news":
            res = list(ddgs.news(query, max_results=5))
        elif mode == "price":
            res = list(ddgs.text(f"{query} price online", max_results=5))
        else:
            res = list(ddgs.text(query, max_results=5))
        return {"mode": mode, "results": res}
    except Exception as e:
        return {"error": str(e)}
      
