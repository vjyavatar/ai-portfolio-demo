"""
Portfolio Demo - AI Company Risk Reports
ULTRA MINIMAL - No Pydantic models, just plain dicts
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import anthropic
from datetime import datetime
import hashlib

# Initialize
app = FastAPI(title="AI Risk Reports - Portfolio Demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
report_counter = {"count": 0}


@app.get("/")
async def health():
    return {
        "status": "healthy",
        "portfolio_mode": True,
        "reports_generated": report_counter["count"],
        "message": "🎓 Portfolio Demo - FREE Reports"
    }


@app.post("/api/generate-report")
async def generate_report(request: Request):
    try:
        data = await request.json()
        company = data.get("company_name", "").strip()
        email = data.get("email", "").strip()
        
        if not company or not email:
            raise HTTPException(400, "company_name and email required")
        
        # Create prompt
        prompt = f"""Analyze "{company}" and create a professional risk assessment report.

Include:
1. Executive Summary (3-4 sentences)
2. Risk Score Dashboard (rate 1-10 for: Financial, Market, Operational, Regulatory, Strategic)
3. Top 5 Risks (with 🔴🟡🟢 severity)
4. Recommendations

Make it professional but clear. Use markdown formatting."""

        # Call Claude
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        
        report = message.content[0].text
        report_counter["count"] += 1
        
        report_id = hashlib.md5(f"{company}{datetime.now()}".encode()).hexdigest()[:12]
        
        return {
            "success": True,
            "report": report,
            "company_name": company,
            "timestamp": datetime.now().isoformat(),
            "report_id": report_id,
            "report_number": report_counter["count"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error: {str(e)}")


@app.get("/api/stats")
async def stats():
    return {
        "total_reports": report_counter["count"],
        "portfolio_mode": True,
        "pricing": "FREE"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
