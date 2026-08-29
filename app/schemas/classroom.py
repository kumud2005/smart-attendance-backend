from pydantic import BaseModel, ConfigDict

class FacultyClassroomResponse(BaseModel):
    classroom_id: int
    building_name: str | None = None
    room_number: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geofence_radius_meters: float | None = None

    model_config = ConfigDict(from_attributes=True)