"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


class Announcement(BaseModel):
    """Announcement model"""
    message: str = Field(..., min_length=1, max_length=500)
    start_date: Optional[str] = None
    expiration_date: str


class AnnouncementUpdate(BaseModel):
    """Announcement update model"""
    message: Optional[str] = Field(None, min_length=1, max_length=500)
    start_date: Optional[str] = None
    expiration_date: Optional[str] = None


def verify_teacher(username: str) -> Dict[str, Any]:
    """Verify that a teacher exists and return their data"""
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return teacher


@router.get("/active")
def get_active_announcements() -> List[Dict[str, Any]]:
    """Get all active announcements (current date is between start and expiration dates)"""
    now = datetime.now().isoformat()
    
    # Find announcements where:
    # - expiration_date is in the future
    # - start_date is None OR start_date is in the past
    announcements = list(announcements_collection.find({
        "expiration_date": {"$gte": now}
    }))
    
    # Filter by start_date in Python (easier than complex MongoDB query)
    active_announcements = []
    for announcement in announcements:
        if announcement.get("start_date") is None or announcement["start_date"] <= now:
            # Convert ObjectId to string for JSON serialization
            announcement["_id"] = str(announcement["_id"])
            active_announcements.append(announcement)
    
    return active_announcements


@router.get("/all")
def get_all_announcements(username: str) -> List[Dict[str, Any]]:
    """Get all announcements (requires authentication)"""
    verify_teacher(username)
    
    announcements = list(announcements_collection.find({}))
    
    # Convert ObjectId to string for JSON serialization
    for announcement in announcements:
        announcement["_id"] = str(announcement["_id"])
    
    return announcements


@router.post("/")
def create_announcement(announcement: Announcement, username: str) -> Dict[str, Any]:
    """Create a new announcement (requires authentication)"""
    verify_teacher(username)
    
    # Validate dates
    try:
        expiration_date = datetime.fromisoformat(announcement.expiration_date.replace('Z', '+00:00'))
        if announcement.start_date:
            start_date = datetime.fromisoformat(announcement.start_date.replace('Z', '+00:00'))
            if start_date >= expiration_date:
                raise HTTPException(
                    status_code=400, 
                    detail="Start date must be before expiration date"
                )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    # Create announcement document
    announcement_doc = {
        "message": announcement.message,
        "start_date": announcement.start_date,
        "expiration_date": announcement.expiration_date
    }
    
    result = announcements_collection.insert_one(announcement_doc)
    announcement_doc["_id"] = str(result.inserted_id)
    
    return announcement_doc


@router.put("/{announcement_id}")
def update_announcement(
    announcement_id: str, 
    announcement: AnnouncementUpdate, 
    username: str
) -> Dict[str, Any]:
    """Update an existing announcement (requires authentication)"""
    verify_teacher(username)
    
    from bson import ObjectId
    
    # Check if announcement exists
    try:
        existing = announcements_collection.find_one({"_id": ObjectId(announcement_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    if not existing:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    # Build update document (only include fields that are provided)
    update_doc = {}
    if announcement.message is not None:
        update_doc["message"] = announcement.message
    if announcement.start_date is not None:
        update_doc["start_date"] = announcement.start_date
    if announcement.expiration_date is not None:
        update_doc["expiration_date"] = announcement.expiration_date
    
    # Validate dates if both are provided or if one is being updated
    try:
        exp_date = update_doc.get("expiration_date", existing.get("expiration_date"))
        start_date = update_doc.get("start_date", existing.get("start_date"))
        
        if exp_date:
            expiration_date = datetime.fromisoformat(exp_date.replace('Z', '+00:00'))
        if start_date:
            start_date_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            if exp_date and start_date_dt >= expiration_date:
                raise HTTPException(
                    status_code=400, 
                    detail="Start date must be before expiration date"
                )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    if not update_doc:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    # Update the announcement
    announcements_collection.update_one(
        {"_id": ObjectId(announcement_id)},
        {"$set": update_doc}
    )
    
    # Return updated announcement
    updated = announcements_collection.find_one({"_id": ObjectId(announcement_id)})
    updated["_id"] = str(updated["_id"])
    
    return updated


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, username: str) -> Dict[str, str]:
    """Delete an announcement (requires authentication)"""
    verify_teacher(username)
    
    from bson import ObjectId
    
    try:
        result = announcements_collection.delete_one({"_id": ObjectId(announcement_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement ID")
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    
    return {"message": "Announcement deleted successfully"}
