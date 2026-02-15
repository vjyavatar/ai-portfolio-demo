"""
Portfolio Demo - AI Company Risk Reports
Super Simple Version - Just FastAPI + Anthropic
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import anthropic
from datetime import datetime
import hashlib

# Initialize FastAPI
app = FastAPI(
    title="AI Risk Reports - Portfolio Demo",
    description="🎓 Portfolio Project - FREE Reports",
    version="1.0-SIMPLE"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Anthropic client
client = anthropic.Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

# Models
class ReportRequest(BaseModel):
    company_name: str
    email: str

class ReportResponse(BaseModel):
    success: bool
    report: str
    company_name: str
    timestamp: str
    report_id: str
    report_number: int

# Storage
report_counter = {"count": 0}


@app.get("/")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "version": "1.0-SIMPLE",
        "portfolio_mode": True,
        "reports_generated": report_counter["count"],
        "message": "🎓 Portfolio Demo - FREE Reports"
    }


@app.post("/api/generate-report", response_model=ReportResponse)
async def generate_report(request: ReportRequest):
    """Generate FREE company risk report"""
    try:
        company = request.company_name.strip()
        
        # Create prompt for Claude
        prompt = f"""Analyze the company "{company}" and create a professional risk assessment report.

Search for information about:
- Financial health and performance
- Market position and competition
- Operational risks
- Regulatory compliance
- Strategic execution

Create a report with:
1. Executive Summary (3-4 sentences)
2. Risk Score Dashboard (rate 1-10 for: Financial, Market, Operational, Regulatory, Strategic)
3. Top 5 Material Risks (with severity indicators 🔴🟡🟢)
4. Recommendations

Make it professional but easy to understand (no jargon).
Use visual indicators (🔴 High Risk, 🟡 Moderate, 🟢 Low).

Format as markdown."""

        # Call Claude API
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Extract response
        report = message.content[0].text
        
        # Update counter
        report_counter["count"] += 1
        
        # Create report ID
        report_id = hashlib.md5(
            f"{company}{datetime.now()}".encode()
        ).hexdigest()[:12]
        
        return {
            "success": True,
            "report": report,
            "company_name": company,
            "timestamp": datetime.now().isoformat(),
            "report_id": report_id,
            "report_number": report_counter["count"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error: {str(e)}"
        )


@app.get("/api/stats")
async def stats():
    """Get statistics"""
    return {
        "total_reports": report_counter["count"],
        "portfolio_mode": True,
        "pricing": "FREE - Portfolio Demo"
    }


# Run server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
