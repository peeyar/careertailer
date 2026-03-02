from typing import TypedDict, Optional, Any, List
from langgraph.graph import StateGraph, END
from app.core.interfaces import IJobScraper, ICareerAI, IEmbeddingService
from app.services.db import DatabaseService
from app.services.resume_writer import ResumeWriter
from app.services.style_extractor import ResumeStyle


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
    job_id:           str        # used as docx filename
    docx_path:        Optional[str]  # set by writer node, None if generation failed
    full_resume_text: str        # all chunks joined in order — used by writer (not analyst)
    resume_style:     Optional[dict]  # extracted style from original file
    changes_summary:  List[str]       # list of changes from Gemini


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
        self.writer    = ResumeWriter()
        self._workflow = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(GraphState)

        workflow.add_node("scraper",   self._scrape_job_node)
        workflow.add_node("retriever", self._retrieve_chunks_node)
        workflow.add_node("analyst",   self._analyze_match_node)
        workflow.add_node("writer",    self._write_resume_node)

        workflow.set_entry_point("scraper")
        workflow.add_edge("scraper",   "retriever")
        workflow.add_edge("retriever", "analyst")
        workflow.add_edge("analyst",   "writer")
        workflow.add_edge("writer",    END)

        return workflow.compile()

    # ── Node 1: Scrape ────────────────────────────────────────────────────────

    # Phrases that indicate a job posting is closed or expired
    _CLOSED_JOB_SIGNALS = [
        "no longer accepting applications",
        "not accepting applications",
        "position has been filled",
        "job is no longer available",
        "this position has been closed",
        "application period has closed",
        "posting has expired",
        "job posting is closed",
        "this job is closed",
    ]

    async def _scrape_job_node(self, state: GraphState):
        try:
            text = await self.scraper.scrape(state["job_url"])

            # Detect closed/expired job postings before wasting an AI call
            text_lower = text.lower()
            for signal in self._CLOSED_JOB_SIGNALS:
                if signal in text_lower:
                    return {"error": "This job posting is no longer accepting applications. Please try a different job URL."}

            if len(text) < 300:
                return {"error": "The scraped page doesn't contain enough content to analyze. The job posting may be behind a login wall or no longer available."}

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
            return {"retrieved_chunks": [], "full_resume_text": ""}

        try:
            print(f"🔍 Retriever: Embedding job text for similarity search...")
            query_embedding = await self.embedding.embed_query(state["job_text"][:3000])

            # Fetch top-k chunks for analyst (focused, high-signal context)
            print(f"🔍 Retriever: Searching resume chunks for user '{state['user_id']}'...")
            matches = await self.db.search_similar_chunks(
                user_id=state["user_id"],
                query_embedding=query_embedding,
                match_threshold=0.4,
                match_count=8,
            )

            # Fetch ALL chunks for writer (complete resume, preserves nothing)
            all_chunks = await self.db.get_all_resume_chunks(state["user_id"])
            full_resume_text = "\n\n".join(all_chunks)
            print(f"📄 Retriever: Loaded {len(all_chunks)} total chunks for writer")

            # Fetch stored style for this user
            style = await self.db.get_resume_style(state["user_id"])

            if not matches:
                print("⚠️  Retriever: No similarity matches — analyst will use full resume text")
                return {"retrieved_chunks": [], "full_resume_text": full_resume_text, "resume_style": style}

            chunks = [m["chunk_text"] for m in matches]
            scores = [round(m["similarity"], 3) for m in matches]
            print(f"✅ Retriever: Found {len(chunks)} relevant chunks for analyst (scores: {scores})")
            return {"retrieved_chunks": chunks, "full_resume_text": full_resume_text, "resume_style": style}

        except Exception as e:
            print(f"⚠️  Retriever Error (non-fatal, falling back): {str(e)}")
            return {"retrieved_chunks": [], "full_resume_text": ""}

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

    # ── Node 4: Write Resume ──────────────────────────────────────────────────

    async def _write_resume_node(self, state: GraphState):
        if state.get("error") or not state.get("analysis"):
            return {"docx_path": None, "changes_summary": []}
        try:
            resume_context = state.get("full_resume_text") or state["resume_text"]
            tailored_text, changes_summary = await self.ai.generate_resume(
                resume_text=resume_context,
                job_text=state["job_text"],
                analysis=state["analysis"],
            )
            if not tailored_text:
                return {"docx_path": None, "changes_summary": []}

            style_dict = state.get("resume_style")
            style = ResumeStyle(**style_dict) if style_dict else None

            docx_bytes   = self.writer.create_docx(tailored_text, style=style)
            storage_path = await self.db.upload_resume(state["user_id"], state["job_id"], docx_bytes)
            if not storage_path:
                print("⚠️  Writer: Storage upload failed — resume not saved")
                return {"docx_path": None, "changes_summary": changes_summary}

            print(f"☁️  Writer: Resume stored at {storage_path}")
            return {"docx_path": storage_path, "changes_summary": changes_summary}
        except Exception as e:
            print(f"⚠️  Writer node failed (non-fatal): {str(e)}")
            return {"docx_path": None, "changes_summary": []}

    # ── Run ───────────────────────────────────────────────────────────────────

    async def run(
        self,
        job_url:      str,
        resume_text:  str  = "",
        user_id:      str  = "default_user",
        use_rag:      bool = True,   # False when user uploads a custom resume
        job_id:       str  = "",
        resume_style: Optional[dict] = None,
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
            "job_id":           job_id,
            "docx_path":        None,
            "full_resume_text": "",
            "resume_style":     resume_style,
            "changes_summary":  [],
        }
        final_state = await self._workflow.ainvoke(initial_state)

        if final_state.get("error"):
            raise Exception(final_state["error"])

        return (
            final_state["analysis"],
            final_state.get("docx_path"),
            final_state.get("changes_summary", []),
        )
