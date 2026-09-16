#!/usr/bin/env python3
"""Safe LLM provider diagnostics — never prints API key."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import get_settings
get_settings.cache_clear()
s = get_settings()

print(f"Provider: NVIDIA")
print(f"Endpoint: {s.LLM_BASE_URL}")
print(f"Model: {s.MODEL_NAME}")
# Test reachability without exposing key
import httpx, asyncio
async def check():
    # 1. models endpoint reachable?
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(s.LLM_BASE_URL.rstrip("/") + "/models", headers={"Authorization": f"Bearer {s.LLM_API_KEY}"})
            print(f"Reachable: {'YES' if r.status_code==200 else 'NO'} (models {r.status_code})")
    except Exception as e:
        print(f"Reachable: NO ({type(e).__name__})")
    # 2. chat completion smoke
    from app.services.llm.factory import get_llm_provider
    try:
        llm = get_llm_provider()
        resp = await llm.complete(system="You are a test assistant.", user="Reply with exactly: RESEARCHFORGE_NVIDIA_OK", max_tokens=20, temperature=0.0)
        ok = "RESEARCHFORGE_NVIDIA_OK" in resp.text
        print(f"Chat completion: {'PASS' if ok and resp.text else 'FAIL'}")
        print(f"Response schema: {'PASS' if resp.text and resp.model else 'FAIL'}")
        # Do not print full headers or key; only safe excerpt
        print(f"Response excerpt: {resp.text[:80]!r}")
        print(f"Tokens: prompt={resp.prompt_tokens} completion={resp.completion_tokens}")
    except httpx.HTTPStatusError as e:
        print(f"Chat completion: FAIL ({e.response.status_code})")
        # Safe error excerpt, no key
        try:
            body = e.response.text[:500]
            print(f"Error body excerpt: {body[:300]!r}")
        except Exception:
            pass
        print(f"Response schema: FAIL")
    except Exception as e:
        print(f"Chat completion: FAIL ({type(e).__name__}: {str(e)[:200]})")
        print(f"Response schema: FAIL")

asyncio.run(check())
