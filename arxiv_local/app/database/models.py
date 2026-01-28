from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, Float
from sqlalchemy.sql import func
from .database import Base

class Paper(Base):
    __tablename__ = "papers"

    id = Column(String, primary_key=True, index=True) # Arxiv ID
    title = Column(String, index=True)
    authors = Column(String) # Stored as comma-separated string or JSON
    abstract = Column(Text)
    published_date = Column(Date, index=True)
    updated_date = Column(Date)
    arxiv_category = Column(String, index=True)
    link = Column(String)
    
    # For recommendation sorting
    score = Column(Float, default=0.0)

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    paper_id = Column(String, index=True) # Foreign key to Paper.id logically
    is_liked = Column(Boolean, default=False)
    viewed_date = Column(DateTime, server_default=func.now())

class FetchLog(Base):
    __tablename__ = "fetch_logs"

    id = Column(Integer, primary_key=True, index=True)
    fetch_date = Column(DateTime, server_default=func.now())
    category = Column(String)
    status = Column(String)

class ViewedDate(Base):
    __tablename__ = "viewed_dates"

    date = Column(Date, primary_key=True, index=True)
    viewed_at = Column(DateTime, server_default=func.now())
