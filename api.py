"""
B2B Research Agent API - Portfolio Demo Version
FREE AI-powered company risk reports - H1B Compliant
No payments accepted - Educational/Portfolio project only
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import os
from agent import B2BResearchAgent
import hashlib
from datetime import datetime


# Initialize FastAPI
app = FastAPI(
    title="B2B Research Agent - Portfolio Demo",
    description="🎓 AI-Powered Company Risk Analysis - FREE Demo (Portfolio Project)",
    version="1.0.0-PORTFOLIO"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Agent
agent = B2BResearchAgent(
    anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    tavily_api_key=os.getenv("TAVILY_API_KEY")
)

# Request/Response models
class ReportRequest(BaseModel):
    company_name: str = Field(..., min_length=2, max_length=200)
    email: str = Field(..., description="Email for report delivery")


class ReportResponse(BaseModel):
    success: bool
    report: str
    company_name: str
    timestamp: str
    report_id: str
    report_number: int
    note: str


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    portfolio_mode: bool
    total_reports_generated: int
    message: str


# In-memory storage
generated_reports = {}
report_counter = {"count": 0}


@app.get("/", response_model=HealthResponse)
async def health_check():
    """API health check"""
    return {
        "status": "healthy",
        "version": "1.0.0-PORTFOLIO",
        "timestamp": datetime.now().isoformat(),
        "portfolio_mode": True,
        "total_reports_generated": report_counter["count"],
        "message": "🎓 Portfolio Demo - All Reports FREE - No Payment Required"
    }


@app.post("/api/generate-report", response_model=ReportResponse)
async def generate_report(request: ReportRequest):
    """
    Generate FREE company risk report
    
    Portfolio demonstration - All reports are free and unlimited.
    This project showcases AI/ML development capabilities.
    Built by an H1B visa holder as a portfolio project (no commercial use).
    """
    try:
        company_name = request.company_name.strip()
        email = request.email.strip()
        
        # Generate report using AI agent
        print(f"Generating report for: {company_name}")
        result = agent.run(company_name)
        
        if result.get("final_report"):
            # Increment counter
            report_counter["count"] += 1
            current_count = report_counter["count"]
            
            # Generate unique report ID
            report_id = hashlib.md5(
                f"{company_name}{email}{datetime.now()}".encode()
            ).hexdigest()[:12]
            
            # Store report
            report_data = {
                "company": company_name,
                "report": result["final_report"],
                "timestamp": datetime.now().isoformat(),
                "report_id": report_id,
                "email": email,
                "report_number": current_count
            }
            
            generated_reports[report_id] = report_data
            
            print(f"✅ Report #{current_count} generated successfully")
            
            return {
                "success": True,
                "report": result["final_report"],
                "company_name": company_name,
                "timestamp": datetime.now().isoformat(),
                "report_id": report_id,
                "report_number": current_count,
                "note": f"✅ FREE Portfolio Demo Report #{current_count} | Showcasing AI Development Skills"
            }
        else:
            error_msg = result.get("error", "Unknown error occurred")
            raise HTTPException(
                status_code=500,
                detail=f"Report generation failed: {error_msg}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Report generation error: {str(e)}"
        )


@app.get("/api/report/{report_id}")
async def get_report(report_id: str):
    """Retrieve a previously generated report"""
    if report_id in generated_reports:
        return {
            "success": True,
            **generated_reports[report_id]
        }
    else:
        raise HTTPException(
            status_code=404,
            detail="Report not found"
        )


@app.get("/api/stats")
async def get_stats():
    """Get demo statistics"""
    return {
        "total_reports": report_counter["count"],
        "portfolio_mode": True,
        "pricing": "FREE - Portfolio Demo",
        "message": "This is a portfolio demonstration project",
        "h1b_compliant": True,
        "commercial_use": False
    }


# Run server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000))
    )
