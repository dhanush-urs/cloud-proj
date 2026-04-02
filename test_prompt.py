import sys
import os
import json
sys.path.append("/app")
from app.llm.provider import get_chat_provider
from app.llm.prompt_builder import build_system_prompt, build_line_impact_prompt

p = get_chat_provider()
sp = build_system_prompt()
up = build_line_impact_prompt("what'll happen if I delete import java.util.Random;", [], {"found": False, "file_hint": "", "lookup_completed": True}, "line_impact")

print("MODEL USED:", p.model_name)
try:
    ans = p.answer(sp, up)
    print("SUCCESS")
except Exception as e:
    print(repr(e))
    # if it's ClientError, try to print its details
    if hasattr(e, 'message'): print("Message:", e.message)
    if hasattr(e, 'response'): print("Response:", e.response.text)
