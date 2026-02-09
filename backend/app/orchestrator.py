from typing import TypedDict, Optional, Any
from langgraph.graph import StateGraph, END
from app.core.interfaces import IJobScraper, ICareerAI
# 👇 THIS IMPORT IS CRITICAL FOR THE TEST TO PASS
from app.services.db import DatabaseService  

# State Definition
class GraphState(TypedDict):
    job_url: str
    resume_text: str
    job_text: str
    analysis: Optional[Any]
    error: Optional[str]

class CareerOrchestrator:
    def __init__(self, scraper_service: IJobScraper, ai_service: ICareerAI):
        self.scraper = scraper_service
        self.ai = ai_service
        # 👇 THIS INITIALIZATION IS CRITICAL
        self.db = DatabaseService()  
        self._workflow = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(GraphState)
        workflow.add_node("scraper", self._scrape_job_node)
        workflow.add_node("analyst", self._analyze_match_node)
        workflow.set_entry_point("scraper")
        workflow.add_edge("scraper", "analyst")
        workflow.add_edge("analyst", END)
        return workflow.compile()

    # --- Node Implementations ---

    async def _scrape_job_node(self, state: GraphState):
        try:
            text = await self.scraper.scrape(state['job_url'])
            
            # Save to DB
            await self.db.save_scrape(state['job_url'], text)
            
            return {"job_text": text}
        except Exception as e:
            return {"error": f"Scraping Error: {str(e)}"}

    async def _analyze_match_node(self, state: GraphState):
        if state.get("error"):
            return {"analysis": None}

        try:
            result = await self.ai.analyze_match(
                state['resume_text'], 
                state['job_text']
            )
            
            # Save to DB
            await self.db.save_analysis(state['job_url'], result)
            
            return {"analysis": result}
        except Exception as e:
            return {"error": f"AI Error: {str(e)}"}

    async def run(self, job_url: str, resume_text: str) -> Any:
        initial_state = {
            "job_url": job_url,
            "resume_text": resume_text,
            "job_text": "",
            "analysis": None,
            "error": None
        }
        final_state = await self._workflow.ainvoke(initial_state)
        
        if final_state.get("error"):
            raise Exception(final_state["error"])
            
        return final_state["analysis"]