# ═════════════════════════════════════════════════════════════════════════
# CELESYS AI Q&A — Backend Reference Implementation
# Drop into api.py to wire up the /api/celesys-ai-qa endpoint that the
# frontend chat widget calls (added in r63.78.0).
#
# Recommended: Anthropic Claude Haiku
#   - ~$0.001 per question (very cheap, scales easily)
#   - ~3-second response time
#   - Excellent at financial analysis with structured context
#
# Alternative: OpenAI gpt-4o-mini (similar price, similar quality)
# Alternative: Cohere command-r (cheaper, slightly weaker)
# Alternative: Self-hosted Ollama (free, requires GPU)
# ═════════════════════════════════════════════════════════════════════════

import os
import json
from fastapi import HTTPException
from pydantic import BaseModel
import anthropic  # pip install anthropic

# ─── 1. Initialize the client ───
# Set ANTHROPIC_API_KEY in Render env vars (Settings → Environment)
_anthropic_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# ─── 2. Request/response models ───
class CelesysAIRequest(BaseModel):
    symbol: str
    region: str = "US"
    question: str
    context: str = "{}"  # JSON string from window._celesysAIBuildContext

class CelesysAIResponse(BaseModel):
    success: bool
    answer: str = ""
    error: str = ""
    tokens_used: int = 0

# ─── 3. System prompt — institutional analyst persona ───
CELESYS_AI_SYSTEM_PROMPT = """You are Celesys AI, an institutional stock research assistant embedded in the Celesys platform (celesys.ai). The user is viewing a comprehensive research report on a specific stock. Your job: answer questions about that stock based on the report data, with the rigor of a buy-side analyst.

RULES:
1. Cite specific numbers from the report (P/E, score, upside %, F-Score, etc.). Never make up data.
2. If the report doesn't contain what's needed, say so explicitly: "The current report doesn't include [X] — you'd need to check [where]."
3. Be direct. Take a position. No "this may or may not be a good investment" hedging.
4. For "bear case" / "bull case": numbered list of 3-5 strongest points with the specific metric supporting each.
5. For "what if" scenarios: reason through the chain (input change → factor impact → stock impact). Show the work.
6. For peer comparisons: name 2-3 specific tickers if known.
7. Default length: 2-4 short paragraphs OR a bulleted list. Concise > comprehensive.
8. NO legal/financial-advice disclaimers — the UI already shows one. Stay focused on analysis.
9. Use **markdown bold** for emphasis on key numbers/conclusions. Use - for bullets, line breaks for separation.

CALIBRATION:
- F-Score 7+ = strong fundamentals. 4-6 = mixed. <4 = weak.
- Upside >20% = significant. -5% to +5% = fairly valued. <-10% = overvalued.
- Moat 70+ = wide moat. 40-70 = narrow. <40 = no moat.
- Beta >1.5 = high volatility. 0.8-1.5 = normal. <0.8 = defensive.
- RSI >70 = overbought. 30-70 = neutral. <30 = oversold.
"""

# ─── 4. The endpoint handler ───
@app.post("/api/celesys-ai-qa")
async def celesys_ai_qa(req: CelesysAIRequest):
    """Conversational Q&A endpoint for the Celesys AI chat widget."""
    try:
        # Validate inputs
        if not req.question or len(req.question.strip()) < 3:
            return CelesysAIResponse(success=False, error="Question too short")
        if len(req.question) > 500:
            return CelesysAIResponse(success=False, error="Question too long (500 char max)")

        # Build the user message — combines context + question
        user_message = f"""Report context for {req.symbol} ({req.region}):
```json
{req.context}
```

User question: {req.question}"""

        # Call Anthropic Claude Haiku
        # Haiku 3.5 = best price/quality for this use case
        message = _anthropic_client.messages.create(
            model="claude-3-5-haiku-20241022",  # Or "claude-3-5-sonnet-20241022" for higher quality (~10x cost)
            max_tokens=800,  # Keep responses concise
            system=CELESYS_AI_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message}
            ],
        )

        answer = message.content[0].text if message.content else ""
        tokens = message.usage.input_tokens + message.usage.output_tokens

        return CelesysAIResponse(
            success=True,
            answer=answer,
            tokens_used=tokens,
        )

    except anthropic.APIError as e:
        return CelesysAIResponse(success=False, error=f"AI service error: {str(e)}")
    except Exception as e:
        return CelesysAIResponse(success=False, error=f"Server error: {str(e)}")


# ═════════════════════════════════════════════════════════════════════════
# ALTERNATIVE: OpenAI implementation (if you prefer GPT)
# ═════════════════════════════════════════════════════════════════════════
"""
import openai

_openai_client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.post("/api/celesys-ai-qa")
async def celesys_ai_qa_openai(req: CelesysAIRequest):
    try:
        completion = _openai_client.chat.completions.create(
            model="gpt-4o-mini",  # ~$0.001 per question, similar to Haiku
            messages=[
                {"role": "system", "content": CELESYS_AI_SYSTEM_PROMPT},
                {"role": "user", "content": f"Context: {req.context}\\n\\nQuestion: {req.question}"}
            ],
            max_tokens=800,
            temperature=0.3,
        )
        answer = completion.choices[0].message.content
        tokens = completion.usage.total_tokens
        return CelesysAIResponse(success=True, answer=answer, tokens_used=tokens)
    except Exception as e:
        return CelesysAIResponse(success=False, error=str(e))
"""

# ═════════════════════════════════════════════════════════════════════════
# DEPLOYMENT CHECKLIST
# ═════════════════════════════════════════════════════════════════════════
# 1. pip install anthropic (or openai if using that path)
#    Add to requirements.txt: anthropic==0.40.0
#
# 2. Get API key from https://console.anthropic.com/settings/keys
#    (Or https://platform.openai.com/api-keys)
#
# 3. In Render dashboard:
#    Settings → Environment → Add Environment Variable:
#    Key: ANTHROPIC_API_KEY
#    Value: sk-ant-api03-...
#
# 4. Add the endpoint above to api.py
#
# 5. Set monthly spend limit on the Anthropic console as a safety net
#    (Settings → Limits — start at $50/month while testing)
#
# 6. Optional: Add rate limiting per user to prevent abuse
#    (e.g., 30 questions per user per hour)
#
# 7. Optional: Cache common Q&A responses (Redis) — same question on
#    same symbol within 1hr = served from cache, zero API cost
#
# COST ESTIMATES (Anthropic Haiku 3.5):
# - Input: ~2000 tokens × $0.0008/1k = $0.0016
# - Output: ~500 tokens × $0.004/1k = $0.0020
# - Per question: ~$0.0036
# - 1000 questions/day = $3.60/day = ~$108/month
# - 100 questions/day = $0.36/day = ~$11/month
