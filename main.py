from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime
from typing import List, Dict

from config import settings, camera_configs
from models import (
    CameraInfo, StreamInfo, HealthMetrics, SystemStatus, 
    APIResponse, ErrorResponse, RecordingInfo
)
from ffmpeg_manager import ffmpeg_manager
from health_monitor import health_monitor
from cleanup_manager import cleanup_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Starting CCTV Streaming API...")
    
    # Create HLS directories
    hls_path = Path(settings.hls_base_path)
    hls_path.mkdir(exist_ok=True)
    
    # Start cleanup scheduler
    await cleanup_manager.start_cleanup_scheduler()
    
    # Start camera streams
    for camera_config in camera_configs.values():
        if camera_config.enabled:
            logger.info(f"Starting stream for camera {camera_config.camera_id}")
            await ffmpeg_manager.start_camera_stream(camera_config)
    
    logger.info("CCTV Streaming API started successfully!")
    yield
    
    # Cleanup on shutdown
    logger.info("Shutting down CCTV Streaming API...")
    await cleanup_manager.stop_cleanup_scheduler()
    await ffmpeg_manager.stop_all_streams()
    logger.info("CCTV Streaming API shutdown complete.")

# Create FastAPI app
app = FastAPI(
    title="CCTV Streaming API",
    description="Real-time CCTV streaming and recording API with HLS support",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for HLS segments
app.mount("/hls", StaticFiles(directory=settings.hls_base_path), name="hls")

# Root endpoint
@app.get("/")
async def root():
    return APIResponse(
        success=True,
        message="CCTV Streaming API is running",
        data={
            "version": "1.0.0",
            "active_cameras": len(camera_configs),
            "hls_base_path": settings.hls_base_path
        }
    )

# Health monitoring endpoints
@app.get("/health", response_model=SystemStatus)
async def get_system_health():
    """Get comprehensive system health status"""
    try:
        return await health_monitor.check_system_health()
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health/metrics", response_model=HealthMetrics)
async def get_health_metrics():
    """Get current system metrics"""
    try:
        return await health_monitor.get_system_metrics()
    except Exception as e:
        logger.error(f"Error getting health metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health/processes")
async def get_process_info():
    """Get detailed FFmpeg process information"""
    try:
        return await health_monitor.get_detailed_process_info()
    except Exception as e:
        logger.error(f"Error getting process info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health/storage")
async def get_storage_info():
    """Get detailed storage information"""
    try:
        return await health_monitor.get_storage_details()
    except Exception as e:
        logger.error(f"Error getting storage info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Camera management endpoints
@app.get("/cameras", response_model=List[CameraInfo])
async def list_cameras():
    """List all configured cameras"""
    cameras = []
    for camera_id, config in camera_configs.items():
        status = ffmpeg_manager.get_process_status(camera_id)
        cameras.append(CameraInfo(
            camera_id=camera_id,
            name=config.name,
            enabled=config.enabled,
            status="online" if status["status"] == "running" else "offline",
            last_activity=status.get("start_time")
        ))
    return cameras

@app.get("/cameras/{camera_id}", response_model=CameraInfo)
async def get_camera_info(camera_id: str):
    """Get information about a specific camera"""
    if camera_id not in camera_configs:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    config = camera_configs[camera_id]
    status = ffmpeg_manager.get_process_status(camera_id)
    
    return CameraInfo(
        camera_id=camera_id,
        name=config.name,
        enabled=config.enabled,
        status="online" if status["status"] == "running" else "offline",
        last_activity=status.get("start_time")
    )

# Streaming endpoints
@app.get("/stream/{camera_id}/live.m3u8")
async def get_live_stream(camera_id: str):
    """Get HLS playlist for live streaming"""
    if camera_id not in camera_configs:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    playlist_path = Path(settings.hls_base_path) / camera_id / "live" / "live.m3u8"
    
    if not playlist_path.exists():
        raise HTTPException(status_code=404, detail="Live stream not available")
    
    return FileResponse(
        playlist_path,
        media_type="application/vnd.apple.mpegurl",
        headers={"Cache-Control": "no-cache"}
    )

@app.get("/stream/{camera_id}/info", response_model=StreamInfo)
async def get_stream_info(camera_id: str):
    """Get streaming information for a camera"""
    if camera_id not in camera_configs:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    config = camera_configs[camera_id]
    status = ffmpeg_manager.get_process_status(camera_id)
    
    return StreamInfo(
        camera_id=camera_id,
        stream_url=f"/stream/{camera_id}/live.m3u8",
        playlist_url=f"/hls/{camera_id}/live/live.m3u8",
        status="running" if status["status"] == "running" else "stopped",
        resolution="Native",
        bitrate=settings.video_bitrate
    )

# Camera control endpoints
@app.post("/cameras/{camera_id}/start")
async def start_camera_stream(camera_id: str):
    """Start streaming for a camera"""
    if camera_id not in camera_configs:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    try:
        config = camera_configs[camera_id]
        await ffmpeg_manager.start_camera_stream(config)
        return APIResponse(
            success=True,
            message=f"Started streaming for camera {camera_id}"
        )
    except Exception as e:
        logger.error(f"Error starting camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cameras/{camera_id}/stop")
async def stop_camera_stream(camera_id: str):
    """Stop streaming for a camera"""
    if camera_id not in camera_configs:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    try:
        await ffmpeg_manager.stop_camera_stream(camera_id)
        return APIResponse(
            success=True,
            message=f"Stopped streaming for camera {camera_id}"
        )
    except Exception as e:
        logger.error(f"Error stopping camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cameras/{camera_id}/restart")
async def restart_camera_stream(camera_id: str):
    """Restart streaming for a camera"""
    if camera_id not in camera_configs:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    try:
        await ffmpeg_manager.restart_camera_stream(camera_id)
        return APIResponse(
            success=True,
            message=f"Restarted streaming for camera {camera_id}"
        )
    except Exception as e:
        logger.error(f"Error restarting camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Recording endpoints
@app.get("/recordings/{camera_id}")
async def list_recordings(camera_id: str):
    """List available recordings for a camera"""
    if camera_id not in camera_configs:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    recordings_path = Path(settings.hls_base_path) / camera_id / "recordings"
    
    if not recordings_path.exists():
        return []
    
    recordings = []
    for date_dir in sorted(recordings_path.iterdir(), reverse=True):
        if date_dir.is_dir():
            for hour_dir in sorted(date_dir.iterdir(), reverse=True):
                if hour_dir.is_dir():
                    segments = [f.name for f in hour_dir.glob("*.ts")]
                    playlist_path = hour_dir / "playlist.m3u8"
                    
                    if segments and playlist_path.exists():
                        total_size = sum(f.stat().st_size for f in hour_dir.glob("*.ts"))
                        recordings.append(RecordingInfo(
                            camera_id=camera_id,
                            date=date_dir.name,
                            hour=int(hour_dir.name),
                            segments=segments,
                            playlist_url=f"/hls/{camera_id}/recordings/{date_dir.name}/{hour_dir.name}/playlist.m3u8",
                            total_size=total_size
                        ))
    
    return recordings

@app.get("/recordings/{camera_id}/{date}/{hour}/playlist.m3u8")
async def get_recording_playlist(camera_id: str, date: str, hour: str):
    """Get HLS playlist for recorded footage"""
    if camera_id not in camera_configs:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    playlist_path = Path(settings.hls_base_path) / camera_id / "recordings" / date / hour / "playlist.m3u8"
    
    if not playlist_path.exists():
        raise HTTPException(status_code=404, detail="Recording not found")
    
    return FileResponse(
        playlist_path,
        media_type="application/vnd.apple.mpegurl"
    )

# Cleanup endpoints
@app.get("/cleanup/preview")
async def preview_cleanup():
    """Preview what would be cleaned up"""
    try:
        return await cleanup_manager.get_cleanup_preview()
    except Exception as e:
        logger.error(f"Error getting cleanup preview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cleanup/run")
async def run_cleanup(background_tasks: BackgroundTasks):
    """Manually trigger cleanup process"""
    try:
        background_tasks.add_task(cleanup_manager.cleanup_old_recordings)
        return APIResponse(
            success=True,
            message="Cleanup process started in background"
        )
    except Exception as e:
        logger.error(f"Error starting cleanup: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cleanup/camera/{camera_id}")
async def cleanup_camera(camera_id: str, days_to_keep: int = None):
    """Clean up recordings for a specific camera"""
    if camera_id not in camera_configs:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    try:
        result = await cleanup_manager.cleanup_specific_camera(camera_id, days_to_keep)
        return APIResponse(
            success=True,
            message=f"Cleanup completed for camera {camera_id}",
            data=result
        )
    except Exception as e:
        logger.error(f"Error cleaning up camera {camera_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=True
    ) 