from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Meeting Management API",
    version="1.0.0",
    description="Simple CRUD API for managing meetings"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- ENUMS ---
class MeetingStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"

# --- PYDANTIC MODELS ---
class Room(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    capacity: int
    location: str
    isAvailable: bool = True

class Meeting(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    description: Optional[str] = None
    startTime: datetime
    endTime: datetime
    organizerId: UUID
    roomId: UUID
    status: MeetingStatus = MeetingStatus.SCHEDULED

# --- IN-MEMORY DATABASE ---
# Pre-populating a room so you can test meeting creation
rooms_db: List[Room] = [
    Room(
        id=UUID("123e4567-e89b-12d3-a456-426614174000"), 
        name="Boardroom A", 
        capacity=20, 
        location="Floor 1"
    )
]
meetings_db: List[Meeting] = []

# --- HELPER FUNCTION ---
def check_room_conflict(new_meeting: Meeting, exclude_meeting_id: Optional[UUID] = None):
    """Checks if a meeting overlaps with existing scheduled meetings in the same room."""
    for existing in meetings_db:
        # Skip checking against itself (useful for updates)
        if exclude_meeting_id and existing.id == exclude_meeting_id:
            continue
            
        if existing.roomId == new_meeting.roomId and existing.status != MeetingStatus.CANCELLED:
            # Overlap logic
            if (new_meeting.startTime < existing.endTime) and (new_meeting.endTime > existing.startTime):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Room conflict: Overlaps with meeting {existing.id}"
                )

# --- ROUTES ---

@app.get("/rooms", response_model=List[Room], summary="Get all rooms")
def get_rooms():
    return rooms_db

@app.get("/meetings", response_model=List[Meeting], summary="Get all meetings")
def get_meetings():
    return meetings_db

@app.post("/meetings", response_model=Meeting, status_code=status.HTTP_201_CREATED, summary="Create a new meeting")
def create_meeting(meeting: Meeting):
    if meeting.endTime <= meeting.startTime:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="endTime must be after startTime")

    if not any(r.id == meeting.roomId for r in rooms_db):
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Room not found")

    check_room_conflict(meeting)
    
    meetings_db.append(meeting)
    return meeting

@app.put("/meetings/{meeting_id}", response_model=Meeting, summary="Update an existing meeting")
def update_meeting(meeting_id: UUID, updated_meeting: Meeting):
    # 1. Find the existing meeting
    for index, existing_meeting in enumerate(meetings_db):
        if existing_meeting.id == meeting_id:
            # 2. Validate new times
            if updated_meeting.endTime <= updated_meeting.startTime:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="endTime must be after startTime")
            
            # 3. Check for conflicts (ignoring the current meeting being updated)
            check_room_conflict(updated_meeting, exclude_meeting_id=meeting_id)
            
            # 4. Enforce the ID from the path stays the same
            updated_meeting.id = meeting_id 
            
            # 5. Update and return
            meetings_db[index] = updated_meeting
            return updated_meeting
            
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

@app.delete("/meetings/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a meeting")
def delete_meeting(meeting_id: UUID):
    for index, meeting in enumerate(meetings_db):
        if meeting.id == meeting_id:
            # Remove the meeting from the list completely
            meetings_db.pop(index)
            return
            
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")