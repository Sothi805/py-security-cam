import psutil
import asyncio
import logging
from typing import Dict, List
from datetime import datetime
from pathlib import Path
from models import HealthMetrics, SystemStatus
from config import settings
from ffmpeg_manager import ffmpeg_manager

logger = logging.getLogger(__name__)


class HealthMonitor:
    def __init__(self):
        self.last_metrics: HealthMetrics = None
        self.alerts: List[str] = []
        
    async def get_system_metrics(self) -> HealthMetrics:
        """Collect current system metrics"""
        try:
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            
            # Disk usage
            disk_usage = {}
            for partition in psutil.disk_partitions():
                try:
                    partition_usage = psutil.disk_usage(partition.mountpoint)
                    disk_usage[partition.mountpoint] = {
                        "total": partition_usage.total,
                        "used": partition_usage.used,
                        "free": partition_usage.free,
                        "percent": (partition_usage.used / partition_usage.total) * 100
                    }
                except PermissionError:
                    continue
            
            # Network statistics
            network = psutil.net_io_counters()
            network_stats = {
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv
            }
            
            # Active streams and FFmpeg processes
            active_streams = len(ffmpeg_manager.list_active_processes())
            ffmpeg_processes = len([
                p for p in psutil.process_iter(['name'])
                if p.info['name'] and 'ffmpeg' in p.info['name'].lower()
            ])
            
            metrics = HealthMetrics(
                timestamp=datetime.now(),
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                disk_usage=disk_usage,
                network_stats=network_stats,
                active_streams=active_streams,
                ffmpeg_processes=ffmpeg_processes
            )
            
            self.last_metrics = metrics
            return metrics
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            raise
            
    async def check_system_health(self) -> SystemStatus:
        """Check system health and generate alerts"""
        metrics = await self.get_system_metrics()
        alerts = []
        status = "healthy"
        
        # Check CPU usage
        if metrics.cpu_usage > settings.cpu_threshold:
            alerts.append(f"High CPU usage: {metrics.cpu_usage:.1f}%")
            status = "warning" if status == "healthy" else status
            
        # Check memory usage
        if metrics.memory_usage > settings.memory_threshold:
            alerts.append(f"High memory usage: {metrics.memory_usage:.1f}%")
            status = "warning" if status == "healthy" else status
            
        # Check disk usage
        for mountpoint, usage in metrics.disk_usage.items():
            if usage["percent"] > settings.disk_threshold:
                alerts.append(f"High disk usage on {mountpoint}: {usage['percent']:.1f}%")
                if usage["percent"] > 95:
                    status = "critical"
                elif status == "healthy":
                    status = "warning"
        
        # Check HLS storage specifically
        try:
            hls_path = Path(settings.hls_base_path)
            if hls_path.exists():
                hls_usage = psutil.disk_usage(str(hls_path))
                hls_percent = (hls_usage.used / hls_usage.total) * 100
                if hls_percent > settings.disk_threshold:
                    alerts.append(f"High HLS storage usage: {hls_percent:.1f}%")
        except Exception:
            pass
            
        # Check FFmpeg processes
        if metrics.ffmpeg_processes != metrics.active_streams:
            alerts.append(f"FFmpeg process mismatch: {metrics.ffmpeg_processes} processes for {metrics.active_streams} streams")
            status = "warning" if status == "healthy" else status
            
        # Check for dead processes
        dead_cameras = []
        for camera_id in ffmpeg_manager.processes:
            process_status = ffmpeg_manager.get_process_status(camera_id)
            if process_status["status"] == "stopped":
                dead_cameras.append(camera_id)
                
        if dead_cameras:
            alerts.append(f"Inactive cameras: {', '.join(dead_cameras)}")
            status = "warning" if status == "healthy" else status
        
        # Determine overall message
        if status == "healthy":
            message = "All systems operating normally"
        elif status == "warning":
            message = f"System has {len(alerts)} warning(s)"
        else:
            message = f"System has critical issues: {len(alerts)} alert(s)"
            
        self.alerts = alerts
        
        return SystemStatus(
            status=status,
            message=message,
            metrics=metrics,
            alerts=alerts
        )
        
    async def get_detailed_process_info(self) -> Dict:
        """Get detailed information about running processes"""
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'cmdline']):
            try:
                if proc.info['name'] and 'ffmpeg' in proc.info['name'].lower():
                    # Extract camera ID from command line if possible
                    camera_id = "unknown"
                    cmdline = proc.info.get('cmdline', [])
                    for i, arg in enumerate(cmdline):
                        if 'camera_' in arg or 'cam_' in arg:
                            camera_id = arg.split('/')[-2] if '/' in arg else arg
                            break
                    
                    processes.append({
                        "pid": proc.info['pid'],
                        "camera_id": camera_id,
                        "cpu_percent": proc.info['cpu_percent'],
                        "memory_percent": proc.info['memory_percent'],
                        "cmdline": ' '.join(cmdline[:5]) + "..." if len(cmdline) > 5 else ' '.join(cmdline)
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        return {
            "ffmpeg_processes": processes,
            "total_count": len(processes),
            "managed_streams": len(ffmpeg_manager.processes)
        }
        
    async def get_storage_details(self) -> Dict:
        """Get detailed storage information"""
        try:
            hls_path = Path(settings.hls_base_path)
            storage_info = {
                "hls_path": str(hls_path),
                "cameras": {}
            }
            
            if hls_path.exists():
                total_size = 0
                
                for camera_dir in hls_path.iterdir():
                    if camera_dir.is_dir():
                        camera_size = 0
                        live_size = 0
                        recordings_size = 0
                        
                        # Calculate live stream size
                        live_path = camera_dir / "live"
                        if live_path.exists():
                            for file in live_path.glob("*"):
                                if file.is_file():
                                    size = file.stat().st_size
                                    live_size += size
                                    camera_size += size
                        
                        # Calculate recordings size
                        recordings_path = camera_dir / "recordings"
                        if recordings_path.exists():
                            for file in recordings_path.rglob("*"):
                                if file.is_file():
                                    size = file.stat().st_size
                                    recordings_size += size
                                    camera_size += size
                        
                        storage_info["cameras"][camera_dir.name] = {
                            "total_size": camera_size,
                            "live_size": live_size,
                            "recordings_size": recordings_size,
                            "live_size_mb": round(live_size / 1024 / 1024, 2),
                            "recordings_size_mb": round(recordings_size / 1024 / 1024, 2),
                            "total_size_mb": round(camera_size / 1024 / 1024, 2)
                        }
                        
                        total_size += camera_size
                
                storage_info["total_size"] = total_size
                storage_info["total_size_mb"] = round(total_size / 1024 / 1024, 2)
                storage_info["total_size_gb"] = round(total_size / 1024 / 1024 / 1024, 2)
            
            return storage_info
            
        except Exception as e:
            logger.error(f"Error getting storage details: {e}")
            return {"error": str(e)}


# Global health monitor instance
health_monitor = HealthMonitor() 