import asyncio
import subprocess
import os
import signal
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from pathlib import Path
from config import settings, CameraConfig

logger = logging.getLogger(__name__)


class FFmpegProcess:
    def __init__(self, camera_config: CameraConfig):
        self.camera_config = camera_config
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self.start_time: Optional[datetime] = None
        self.restart_count = 0
        
    async def start(self):
        """Start FFmpeg process for the camera"""
        if self.is_running:
            return
            
        try:
            # Create directories
            await self._create_directories()
            
            # Build FFmpeg command
            cmd = self._build_ffmpeg_command()
            
            logger.info(f"Starting FFmpeg for camera {self.camera_config.camera_id}")
            logger.debug(f"FFmpeg command: {' '.join(cmd)}")
            
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )
            
            self.is_running = True
            self.start_time = datetime.now()
            
            # Monitor process in background
            asyncio.create_task(self._monitor_process())
            
        except Exception as e:
            logger.error(f"Failed to start FFmpeg for camera {self.camera_config.camera_id}: {e}")
            self.is_running = False
            
    async def stop(self):
        """Stop FFmpeg process"""
        if not self.is_running or not self.process:
            return
            
        try:
            logger.info(f"Stopping FFmpeg for camera {self.camera_config.camera_id}")
            
            if os.name == 'nt':  # Windows
                self.process.terminate()
            else:  # Unix-like
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                
            # Wait for process to terminate
            try:
                await asyncio.wait_for(
                    asyncio.create_task(self._wait_for_process()),
                    timeout=10.0
                )
            except asyncio.TimeoutError:
                logger.warning(f"FFmpeg process for camera {self.camera_config.camera_id} did not terminate gracefully, killing...")
                if os.name == 'nt':
                    self.process.kill()
                else:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                    
        except Exception as e:
            logger.error(f"Error stopping FFmpeg for camera {self.camera_config.camera_id}: {e}")
        finally:
            self.is_running = False
            self.process = None
            
    async def restart(self):
        """Restart FFmpeg process"""
        await self.stop()
        await asyncio.sleep(2)  # Brief pause before restart
        await self.start()
        self.restart_count += 1
        
    async def _create_directories(self):
        """Create necessary directories for HLS output"""
        camera_path = Path(settings.hls_base_path) / self.camera_config.camera_id
        
        # Create live stream directory
        live_path = camera_path / "live"
        live_path.mkdir(parents=True, exist_ok=True)
        
        # Create recordings directory structure
        recordings_path = camera_path / "recordings"
        
        # Create today's recording directory
        today = datetime.now()
        date_path = recordings_path / today.strftime("%Y-%m-%d")
        hour_path = date_path / f"{today.hour:02d}"
        hour_path.mkdir(parents=True, exist_ok=True)
        
    def _build_ffmpeg_command(self) -> List[str]:
        """Build FFmpeg command for HLS streaming and recording"""
        camera_path = Path(settings.hls_base_path) / self.camera_config.camera_id
        live_path = camera_path / "live"
        
        # Current hour recording path
        today = datetime.now()
        recordings_path = camera_path / "recordings" / today.strftime("%Y-%m-%d") / f"{today.hour:02d}"
        
        cmd = [
            "ffmpeg",
            "-i", self.camera_config.rtsp_url,
            "-c:v", "libx264",
            "-c:a", "aac",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-threads", str(settings.ffmpeg_thread_count),
            "-b:v", settings.video_bitrate,
            "-b:a", settings.audio_bitrate,
            "-f", "hls",
            "-hls_time", str(settings.hls_segment_duration),
            "-hls_list_size", str(settings.hls_list_size),
            "-hls_flags", "delete_segments+append_list",
            "-hls_segment_filename", str(live_path / "segment%03d.ts"),
            str(live_path / "live.m3u8"),
            # Recording output
            "-c:v", "copy",
            "-c:a", "copy",
            "-f", "segment",
            "-segment_time", "60",  # 1-minute segments
            "-segment_format", "mpegts",
            "-segment_list", str(recordings_path / "playlist.m3u8"),
            "-segment_list_flags", "live",
            "-strftime", "1",
            str(recordings_path / "%M.ts"),
            "-y"  # Overwrite output files
        ]
        
        return cmd
        
    async def _monitor_process(self):
        """Monitor FFmpeg process and restart if needed"""
        while self.is_running and self.process:
            try:
                # Check if process is still running
                retcode = self.process.poll()
                if retcode is not None:
                    logger.error(f"FFmpeg process for camera {self.camera_config.camera_id} exited with code {retcode}")
                    
                    # Read stderr for error details
                    stderr = self.process.stderr.read().decode('utf-8', errors='ignore')
                    if stderr:
                        logger.error(f"FFmpeg stderr: {stderr}")
                    
                    self.is_running = False
                    
                    # Auto-restart if not too many restarts
                    if self.restart_count < 5:
                        logger.info(f"Auto-restarting FFmpeg for camera {self.camera_config.camera_id}")
                        await asyncio.sleep(5)
                        await self.restart()
                    else:
                        logger.error(f"Too many restarts for camera {self.camera_config.camera_id}, stopping auto-restart")
                        break
                        
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring FFmpeg process for camera {self.camera_config.camera_id}: {e}")
                break
                
    async def _wait_for_process(self):
        """Wait for process to terminate"""
        while self.process and self.process.poll() is None:
            await asyncio.sleep(0.1)


class FFmpegManager:
    def __init__(self):
        self.processes: Dict[str, FFmpegProcess] = {}
        
    async def start_camera_stream(self, camera_config: CameraConfig):
        """Start streaming for a camera"""
        if camera_config.camera_id in self.processes:
            await self.stop_camera_stream(camera_config.camera_id)
            
        process = FFmpegProcess(camera_config)
        self.processes[camera_config.camera_id] = process
        await process.start()
        
    async def stop_camera_stream(self, camera_id: str):
        """Stop streaming for a camera"""
        if camera_id in self.processes:
            await self.processes[camera_id].stop()
            del self.processes[camera_id]
            
    async def restart_camera_stream(self, camera_id: str):
        """Restart streaming for a camera"""
        if camera_id in self.processes:
            await self.processes[camera_id].restart()
            
    async def stop_all_streams(self):
        """Stop all camera streams"""
        tasks = []
        for camera_id in list(self.processes.keys()):
            tasks.append(self.stop_camera_stream(camera_id))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    def get_process_status(self, camera_id: str) -> Dict:
        """Get status of a camera's FFmpeg process"""
        if camera_id not in self.processes:
            return {"status": "stopped", "message": "Process not found"}
            
        process = self.processes[camera_id]
        return {
            "status": "running" if process.is_running else "stopped",
            "start_time": process.start_time,
            "restart_count": process.restart_count,
            "pid": process.process.pid if process.process else None
        }
        
    def list_active_processes(self) -> List[str]:
        """List all active camera processes"""
        return [
            camera_id for camera_id, process in self.processes.items()
            if process.is_running
        ]


# Global FFmpeg manager instance
ffmpeg_manager = FFmpegManager() 