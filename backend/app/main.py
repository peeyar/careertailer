from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from app.services.db import DatabaseService # Put this at the top with other imports if it isn't there
from fastapi.middleware.cors import CORSMiddleware
from app.dependencies import get_orchestrator
from app.orchestrator import CareerOrchestrator
from app.services.parser import ResumeParser
from app.core.interfaces import AnalysisResult

# Initialize the App
app = FastAPI(title="CareerTailor Enterprise API")

# --- CORS MIDDLEWARE (Required for Frontend Connection) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace "*" with specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# --------------------------------------------------------

@app.get("/")
async def root():
    return {"message": "CareerTailor Enterprise API is online 🚀"}

@app.get("/api/history")
async def get_analysis_history():
    """Endpoint to retrieve past job matches."""
    try:
        db = DatabaseService()
        history_data = await db.get_history()
        return {"status": "success", "data": history_data}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/analyze", response_model=AnalysisResult)
async def analyze_match(
    resume: UploadFile = File(...),
    job_url: str = Form(...),
    # INJECTION: We ask FastAPI for the Orchestrator
    orchestrator: CareerOrchestrator = Depends(get_orchestrator) 
):
    """
    Controller endpoint. 
    Delegates all logic to the Orchestrator (Business Layer).
    """
    
    # 1. Validation (Presentation Layer)
    filename = resume.filename.lower()
    if not filename.endswith(('.pdf', '.docx', '.txt')):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF, DOCX, and TXT are supported.")

    # 2. Parsing (Utility)
    try:
        content = await resume.read()
        
        # Simple parsing logic (can be moved to a service if it grows)
        if filename.endswith('.pdf'):
            resume_text = ResumeParser.parse_pdf(content)
        elif filename.endswith('.docx'):
            resume_text = ResumeParser.parse_docx(content)
        else:
            resume_text = content.decode("utf-8")
            
        if len(resume_text) < 50:
             raise HTTPException(status_code=400, detail="Resume text is too short or unreadable.")

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Resume parse failed: {str(e)}")

    # 3. Execution (Business Logic Layer)
    try:
        # The Orchestrator handles the scraping, AI analysis, and error handling flow
        print(f"🚀 Controller: Triggering Orchestrator for {job_url}")
        result = await orchestrator.run(job_url, resume_text)
        return result
        
    except Exception as e:
        print(f"❌ Controller Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)