from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class CameraInfo(BaseModel):
    camera_id: str
    name: str
    enabled: bool
    status: str  # "online", "offline", "error"
    last_activity: Optional[datetime] = None


class StreamInfo(BaseModel):
    camera_id: str
    stream_url: str
    playlist_url: str
    status: str
    resolution: Optional[str] = None
    bitrate: Optional[str] = None


class HealthMetrics(BaseModel):
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: Dict[str, Any]  # Changed to Any to handle nested dictionaries
    network_stats: Dict[str, float]  # {"bytes_sent": 1000, "bytes_recv": 2000}
    active_streams: int
    ffmpeg_processes: int


class SystemStatus(BaseModel):
    status: str  # "healthy", "warning", "critical"
    message: str
    metrics: HealthMetrics
    alerts: List[str] = []


class RecordingInfo(BaseModel):
    camera_id: str
    date: str
    hour: int
    segments: List[str]
    playlist_url: str
    total_size: int  # in bytes


class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    timestamp: datetime = datetime.now()


class ErrorResponse(BaseModel):
    success: bool = False
    error: str
    details: Optional[str] = None
    timestamp: datetime = datetime.now() 