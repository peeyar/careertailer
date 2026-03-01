from typing import TypedDict, Optional, Any, List
from langgraph.graph import StateGraph, END
from app.core.interfaces import IJobScraper, ICareerAI, IEmbeddingService
from app.services.db import DatabaseService


# ── State Definition ──────────────────────────────────────────────────────────

class GraphState(TypedDict):
    job_url:          str
    user_id:          str
    resume_text:      str        # set when user uploads a custom resume
    use_rag:          bool       # False = user uploaded a file, skip RAG
    job_text:         str
    retrieved_chunks: List[str]
    analysis:         Optional[Any]
    error:            Optional[str]


# ── Orchestrator ──────────────────────────────────────────────────────────────

class CareerOrchestrator:
    def __init__(
        self,
        scraper_service:   IJobScraper,
        ai_service:        ICareerAI,
        embedding_service: IEmbeddingService,
    ):
        self.scraper   = scraper_service
        self.ai        = ai_service
        self.embedding = embedding_service
        self.db        = DatabaseService()
        self._workflow = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(GraphState)

        workflow.add_node("scraper",   self._scrape_job_node)
        workflow.add_node("retriever", self._retrieve_chunks_node)
        workflow.add_node("analyst",   self._analyze_match_node)

        workflow.set_entry_point("scraper")
        workflow.add_edge("scraper",   "retriever")
        workflow.add_edge("retriever", "analyst")
        workflow.add_edge("analyst",   END)

        return workflow.compile()

    # ── Node 1: Scrape ────────────────────────────────────────────────────────

    async def _scrape_job_node(self, state: GraphState):
        try:
            text = await self.scraper.scrape(state["job_url"])
            await self.db.save_scrape(state["job_url"], text)
            return {"job_text": text}
        except Exception as e:
            return {"error": f"Scraping Error: {str(e)}"}

    # ── Node 2: RAG Retrieval ─────────────────────────────────────────────────

    async def _retrieve_chunks_node(self, state: GraphState):
        """
        Skipped entirely if user uploaded a custom resume (use_rag=False).
        In that case the uploaded resume_text is used directly by the analyst.
        """
        if state.get("error"):
            return {"retrieved_chunks": []}

        # User uploaded a specific resume — respect that choice, skip RAG
        if not state.get("use_rag", True):
            print("📄 Retriever: Custom resume uploaded — skipping RAG, using uploaded text")
            return {"retrieved_chunks": []}

        try:
            print(f"🔍 Retriever: Embedding job text for similarity search...")
            query_embedding = await self.embedding.embed_query(state["job_text"][:3000])

            print(f"🔍 Retriever: Searching resume chunks for user '{state['user_id']}'...")
            matches = await self.db.search_similar_chunks(
                user_id=state["user_id"],
                query_embedding=query_embedding,
                match_threshold=0.4,
                match_count=8,
            )

            if not matches:
                print("⚠️  Retriever: No chunks found — falling back to uploaded resume text")
                return {"retrieved_chunks": []}

            chunks = [m["chunk_text"] for m in matches]
            scores = [round(m["similarity"], 3) for m in matches]
            print(f"✅ Retriever: Found {len(chunks)} relevant chunks (scores: {scores})")
            return {"retrieved_chunks": chunks}

        except Exception as e:
            print(f"⚠️  Retriever Error (non-fatal, falling back): {str(e)}")
            return {"retrieved_chunks": []}

    # ── Node 3: Analyze ───────────────────────────────────────────────────────

    async def _analyze_match_node(self, state: GraphState):
        if state.get("error"):
            return {"analysis": None}

        try:
            retrieved = state.get("retrieved_chunks", [])

            if retrieved:
                resume_context = "\n\n---\n\n".join(retrieved)
                print(f"🧠 Analyst: Using {len(retrieved)} RAG chunks (master resume)")
            else:
                resume_context = state["resume_text"]
                if state.get("use_rag", True):
                    print("🧠 Analyst: Using full resume text (no RAG chunks found)")
                else:
                    print("🧠 Analyst: Using uploaded custom resume text")

            result = await self.ai.analyze_match(
                resume_text=resume_context,
                job_text=state["job_text"],
            )

            await self.db.save_analysis(state["job_url"], result)
            return {"analysis": result}

        except Exception as e:
            return {"error": f"AI Error: {str(e)}"}

    # ── Run ───────────────────────────────────────────────────────────────────

    async def run(
        self,
        job_url:     str,
        resume_text: str  = "",
        user_id:     str  = "default_user",
        use_rag:     bool = True,   # False when user uploads a custom resume
    ) -> Any:
        initial_state = {
            "job_url":          job_url,
            "user_id":          user_id,
            "resume_text":      resume_text,
            "use_rag":          use_rag,
            "job_text":         "",
            "retrieved_chunks": [],
            "analysis":         None,
            "error":            None,
        }
        final_state = await self._workflow.ainvoke(initial_state)

        if final_state.get("error"):
            raise Exception(final_state["error"])

        return final_state["analysis"]
    