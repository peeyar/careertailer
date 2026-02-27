# CareerTailor UI - Project Status (RAG Edition)

## 🖥️ Frontend Architecture Overview
A responsive React/Vite application designed to interface with a FastAPI/LangGraph backend. Features complex state management to handle batch job scraping, Master Resume vectorization (RAG ingestion), and real-time human-in-the-loop interviews.

## 🗺️ Project Roadmap

### Phase 1: Core Interface & Foundation 🟢 Completed
* [x] Initialize React/Vite application with Tailwind CSS.
* [x] Build foundational layout (Header, split-screen UI).
* [x] Connect to Python FastAPI Backend (`axios`) and handle CORS.
* [x] Build Data Display: Show Match Score, AI Summary, Keywords.
* [x] Build History Sidebar: Fetch past analyses from Supabase and auto-refresh.

### Phase 2: RAG Setup & Batch Dashboard 🟡 Next
* [ ] **Master Resume Ingestion UI**: Add a dedicated "Upload Master Context" zone that hits the `/api/ingest` endpoint to vectorize the user's resume into Pinecone.
* [ ] **Vectorization States**: Add specific loading animations (e.g., "Chunking document...", "Embedding text...") to give the user visibility into the RAG process.
* [ ] **Multi-Submit Form**: Upgrade the job input to accept 3-5 Job URLs simultaneously.
* [ ] **Traffic Light Grid**: Replace the single score with a "Feasibility Score" grid (Green/Yellow/Red) for batched jobs.

### Phase 3: The "Bridge" Chat UI (Unified Interview) 🔴 Pending
* [ ] **Human Interview Component**: Build an interactive chat interface that prompts the user to verify skills that the Pinecone Vector Search could not find in their history.
* [ ] **Context Feedback**: Allow users to type answers that are sent back to the backend to be vectorized and added to their Pinecone index on the fly.

### Phase 4: Resume Factory & Export 🔴 Pending
* [ ] **Generation Hub**: Create a progress component that tracks the creation of the formatted `Resume-[Company]-[Role].docx` files.
* [ ] **Local Download Handler**: Implement a secure way to receive Streamed Bytes from FastAPI and trigger local downloads.

---

## 🧠 UI/UX Technical Standards
1. **Asynchronous Feedback for RAG:** Because embedding a document and parallel scraping takes time, the UI must use aggressive, descriptive loading states (e.g., "Searching your past experience vectors...") to keep user trust.
2. **State Management:** Multi-step flows (Ingestion -> Triage -> Interview -> Factory) should use isolated state stages.
3. **Ephemeral Document Communication:** The UI must clearly state that original PDF/Docx files are not saved, only their mathematical embeddings.