import httpx
import json
import logging

logger = logging.getLogger(__name__)

_telegraph_token = None
_telegraph_cache = {}

def get_telegraph_link_for_plan(plan_name: str, channels: list) -> str:
    global _telegraph_token
    
    if not channels:
        return ""
        
    # Cache key based on channel ids and titles
    chan_hash = hash(str([(c['channel_id'], c['title']) for c in channels]))
    cache_key = f"{plan_name}_{chan_hash}"
    
    if cache_key in _telegraph_cache:
        return _telegraph_cache[cache_key]
        
    try:
        if not _telegraph_token:
            resp = httpx.get("https://api.telegra.ph/createAccount?short_name=SubBot&author_name=SubscriptionBot", timeout=5.0)
            _telegraph_token = resp.json().get("result", {}).get("access_token")
            
        if not _telegraph_token:
            return ""
            
        content = []
        content.append({"tag": "h3", "children": [f"Premium Channels for {plan_name}"]})
        ul_children = []
        for c in channels:
            ul_children.append({"tag": "li", "children": [c['title']]})
        content.append({"tag": "ul", "children": ul_children})
        
        resp2 = httpx.post("https://api.telegra.ph/createPage", data={
            "access_token": _telegraph_token,
            "title": f"Channels: {plan_name[:30]}",
            "content": json.dumps(content),
            "return_content": "false"
        }, timeout=5.0)
        
        url = resp2.json().get("result", {}).get("url", "")
        if url:
            _telegraph_cache[cache_key] = url
        return url
    except Exception as e:
        logger.warning(f"Failed to create Telegraph page: {e}")
        return ""
