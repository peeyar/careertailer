# CareerTailor Backend - Project Status (RAG Edition)

## 🏗️ System Architecture Overview
A FastAPI Gateway orchestrating a LangGraph AI agent. It utilizes a hybrid database approach: Supabase (Postgres) for session state/history, and Pinecone (Vector DB) for Retrieval-Augmented Generation (RAG) to dynamically match user experiences to job requirements.

## 🗺️ Project Roadmap

### Phase 1: Foundation & Core Logic 🟢 Completed
* [x] Set up Python environment (Python 3.14, Poetry).
* [x] Initialize FastAPI application & define Pydantic models.
* [x] Integrate Google Gemini API (`llm.py`).
* [x] Build Playwright Scraper (`scraper.py`) with Smart Selectors.
* [x] Implement initial LangGraph Orchestrator for workflow management.

### Phase 2: Persistence & Enterprise Reliability 🟢 Completed
* [x] Set up Supabase PostgreSQL for session history.
* [x] Build Database Service (`db.py`) to handle upserts.
* [x] Implement Unit Testing with `pytest` and `AsyncMock`.
* [x] Secure GitHub repository (Scrubbed `.env`, rotated keys).

### Phase 3: RAG Ingestion (The "Brain" Upgrade) 🟡 Next
* [ ] **Pinecone Integration**: Set up Pinecone Serverless index for vector storage.
* [ ] **Document Processing**: Implement a text splitter (e.g., `langchain` RecursiveCharacterTextSplitter) to chunk the Master Resume.
* [ ] **Embedding Pipeline**: Use an embedding model (e.g., Gemini `text-embedding-004`) to convert resume chunks into mathematical vectors.
* [ ] **Vector Upsert**: Create an API endpoint (`/api/ingest`) to save these vectors and metadata to Pinecone.

### Phase 4: RAG Retrieval & The "Bridge" 🔴 Pending
* [ ] **Parallel Triage**: Update LangGraph to spawn parallel 'Scraper Nodes' for 3-5 job URLs simultaneously.
* [ ] **Semantic Search**: Update the Analyst Node to embed missing job requirements and perform a Cosine Similarity search in Pinecone to find the user's matching past experiences.
* [ ] **Interview Agent**: Implement a LangGraph node to ask the user clarifying questions *only* if Pinecone returns no matching semantic experience.

### Phase 5: The "Factory" (Generation & Injection) 🔴 Pending
* [ ] **Contextual Generation**: Use retrieved Pinecone context to rewrite resume bullet points accurately without hallucination.
* [ ] **Docx Injector Node**: Build a Python service (`python-docx`) to read a Master Resume and inject tailored keywords into paragraph runs, preserving format.
* [ ] **File Delivery**: Stream generated `Resume-[Company].docx` bytes to the user.

### Phase 6: Observability & Deployment 🔴 Pending
* [ ] **LangSmith**: Integrate to trace LangGraph steps, RAG retrieval quality, and token costs.
* [ ] **Docker & Cloud Run**: Containerize and deploy the application.

---

## 🧠 Lessons Learned & Technical Standards
1. **Scraping Modern Web Apps**: Using `wait_until="networkidle"` is a trap. Use `domcontentloaded` combined with explicit element waits.
2. **Hybrid State Management**: We use Postgres for relational tracking (Session History, Audit Logs) and Pinecone exclusively for high-dimensional semantic search (The AI Skill Bank).
3. **Privacy-First Files**: Master resume files and generated `.docx` binaries are ephemeral (RAM only). Only vectorized, chunked text lives in Pinecone.