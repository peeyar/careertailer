from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

Base = declarative_base()

class UserSkillBank(Base):
   """
   The  smart memory. Stores verified skills so we dont ask again.
   """    
   
   __tablename__ = "user_skill_bank"
   
   id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
   # In production, this links to Clerk/Auth0 ID. For now, it's a string.
   user_id = Column(String, index=True, nullable=False)
   
   skill_name = Column(String, nullable=False) # e.g. "python" (normalized)
   proficiency = Column(String, default="verified") # claimed, verified, expert
   source_job_url = Column(String , nullable=True) # Where did we prove this?
   
   created_at = Column(DateTime, default=datetime.now)
   last_verified_at = Column(DateTime, default=datetime.now)
  
class ResumeCache(Base):
    """
    The 'fingerprint' cache. 
    If a user uploads the exact same file twice, we skip the expensive OCR/Parsing.
    """           
    
    __tablename__ = "resume_cache"
    file_hash = Column(String(64), primary_key=True) # SHA-256 hash
    extracted_text = Column(Text, nullable=False)  # the expensive raw text
    parsed_metadata = Column(JSON , nullable=True) # {"skills" :["a", "b"]}
    
    created_at = Column(DateTime , default=datetime.now)
   
