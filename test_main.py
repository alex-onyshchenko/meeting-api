import pytest
from fastapi.testclient import TestClient
from main import app, meetings_db  # Import your app and the in-memory DB
import uuid

client = TestClient(app)

# The hardcoded room ID from main.py
ROOM_ID = "123e4567-e89b-12d3-a456-426614174000"

@pytest.fixture(autouse=True)
def reset_db():
    """This fixture runs before every test to clear the in-memory database."""
    meetings_db.clear()
    yield

def test_create_and_read_meeting():
    """Test POST (Create) and GET (Read)."""
    organizer_id = str(uuid.uuid4())
    meeting_data = {
        "title": "Initial Planning",
        "startTime": "2026-03-10T10:00:00Z",
        "endTime": "2026-03-10T11:00:00Z",
        "organizerId": organizer_id,
        "roomId": ROOM_ID,
        "status": "SCHEDULED"
    }
    
    # 1. CREATE
    post_res = client.post("/meetings", json=meeting_data)
    assert post_res.status_code == 201
    created_id = post_res.json()["id"]

    # 2. READ
    get_res = client.get("/meetings")
    assert get_res.status_code == 200
    all_meetings = get_res.json()
    
    assert len(all_meetings) == 1
    assert all_meetings[0]["id"] == created_id
    assert all_meetings[0]["title"] == "Initial Planning"

def test_room_conflict_on_create():
    """Test 409 Conflict when creating overlapping meetings."""
    organizer_id = str(uuid.uuid4())
    
    # Create the first meeting (10:00 to 11:00)
    client.post("/meetings", json={
        "title": "Meeting 1",
        "startTime": "2026-03-10T10:00:00Z",
        "endTime": "2026-03-10T11:00:00Z",
        "organizerId": organizer_id,
        "roomId": ROOM_ID
    })

    # Try to create an overlapping meeting (10:30 to 11:30)
    conflict_res = client.post("/meetings", json={
        "title": "Meeting 2",
        "startTime": "2026-03-10T10:30:00Z",
        "endTime": "2026-03-10T11:30:00Z",
        "organizerId": organizer_id,
        "roomId": ROOM_ID
    })
    
    assert conflict_res.status_code == 409
    assert "Room conflict" in conflict_res.json()["detail"]

def test_update_meeting():
    """Test PUT (Update) modifying an existing meeting without conflicting with itself."""
    organizer_id = str(uuid.uuid4())
    
    # 1. Create a meeting
    post_res = client.post("/meetings", json={
        "title": "Old Title",
        "startTime": "2026-03-10T13:00:00Z",
        "endTime": "2026-03-10T14:00:00Z",
        "organizerId": organizer_id,
        "roomId": ROOM_ID
    })
    meeting_id = post_res.json()["id"]

    # 2. Update the meeting (changing title and extending time)
    update_data = post_res.json()
    update_data["title"] = "New Title"
    update_data["endTime"] = "2026-03-10T14:30:00Z"

    put_res = client.put(f"/meetings/{meeting_id}", json=update_data)
    
    assert put_res.status_code == 200
    assert put_res.json()["title"] == "New Title"
    assert put_res.json()["endTime"] == "2026-03-10T14:30:00Z"

def test_room_conflict_on_update():
    """Test 409 Conflict when updating a meeting to overlap with ANOTHER meeting."""
    organizer_id = str(uuid.uuid4())
    
    # Meeting A: 09:00 - 10:00
    client.post("/meetings", json={
        "title": "Meeting A",
        "startTime": "2026-03-10T09:00:00Z",
        "endTime": "2026-03-10T10:00:00Z",
        "organizerId": organizer_id,
        "roomId": ROOM_ID
    })

    # Meeting B: 11:00 - 12:00
    post_res_b = client.post("/meetings", json={
        "title": "Meeting B",
        "startTime": "2026-03-10T11:00:00Z",
        "endTime": "2026-03-10T12:00:00Z",
        "organizerId": organizer_id,
        "roomId": ROOM_ID
    })
    meeting_b = post_res_b.json()

    # Try to update Meeting B to 09:30 - 10:30 (overlaps with Meeting A)
    meeting_b["startTime"] = "2026-03-10T09:30:00Z"
    meeting_b["endTime"] = "2026-03-10T10:30:00Z"
    
    put_res = client.put(f"/meetings/{meeting_b['id']}", json=meeting_b)
    assert put_res.status_code == 409

def test_delete_meeting():
    """Test DELETE successfully removes a meeting."""
    organizer_id = str(uuid.uuid4())
    
    # 1. Create meeting
    post_res = client.post("/meetings", json={
        "title": "To Be Deleted",
        "startTime": "2026-03-10T15:00:00Z",
        "endTime": "2026-03-10T16:00:00Z",
        "organizerId": organizer_id,
        "roomId": ROOM_ID
    })
    meeting_id = post_res.json()["id"]

    # 2. Delete it
    del_res = client.delete(f"/meetings/{meeting_id}")
    assert del_res.status_code == 204  # 204 No Content

    # 3. Verify it's gone
    get_res = client.get("/meetings")
    assert len(get_res.json()) == 0

    # 4. Try deleting it again (should 404)
    del_res_again = client.delete(f"/meetings/{meeting_id}")
    assert del_res_again.status_code == 404