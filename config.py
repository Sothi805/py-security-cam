import os
from typing import Dict, List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Server Configuration
    server_host: str = Field(default="0.0.0.0", env="SERVER_HOST")
    server_port: int = Field(default=8000, env="SERVER_PORT")
    api_version: str = Field(default="v1", env="API_VERSION")
    
    # Storage Configuration
    hls_base_path: str = Field(default="./hls", env="HLS_BASE_PATH")
    retention_days: int = Field(default=30, env="RETENTION_DAYS")
    
    # FFmpeg Configuration
    ffmpeg_thread_count: int = Field(default=2, env="FFMPEG_THREAD_COUNT")
    hls_segment_duration: int = Field(default=10, env="HLS_SEGMENT_DURATION")
    hls_list_size: int = Field(default=6, env="HLS_LIST_SIZE")
    video_bitrate: str = Field(default="2000k", env="VIDEO_BITRATE")
    audio_bitrate: str = Field(default="128k", env="AUDIO_BITRATE")
    
    # Health Monitoring
    health_check_interval: int = Field(default=30, env="HEALTH_CHECK_INTERVAL")
    cpu_threshold: int = Field(default=80, env="CPU_THRESHOLD")
    memory_threshold: int = Field(default=80, env="MEMORY_THRESHOLD")
    disk_threshold: int = Field(default=90, env="DISK_THRESHOLD")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


class CameraConfig:
    def __init__(self, camera_id: str, name: str, rtsp_url: str, enabled: bool = True):
        self.camera_id = camera_id
        self.name = name
        self.rtsp_url = rtsp_url
        self.enabled = enabled


def load_camera_configs() -> Dict[str, CameraConfig]:
    """Load camera configurations from environment variables"""
    cameras = {}
    
    # Look for camera configurations in environment variables
    i = 1
    while True:
        camera_id = os.getenv(f"CAMERA_{i}_ID")
        if not camera_id:
            break
            
        camera_name = os.getenv(f"CAMERA_{i}_NAME", f"Camera {i}")
        rtsp_url = os.getenv(f"CAMERA_{i}_RTSP_URL")
        enabled = os.getenv(f"CAMERA_{i}_ENABLED", "true").lower() == "true"
        
        if rtsp_url and enabled:
            cameras[camera_id] = CameraConfig(
                camera_id=camera_id,
                name=camera_name,
                rtsp_url=rtsp_url,
                enabled=enabled
            )
        
        i += 1
    
    return cameras


# Global settings instance
settings = Settings()
camera_configs = load_camera_configs() 