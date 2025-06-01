import asyncio
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
from config import settings

logger = logging.getLogger(__name__)


class CleanupManager:
    def __init__(self):
        self.is_running = False
        self.cleanup_task = None
        
    async def start_cleanup_scheduler(self):
        """Start the automatic cleanup scheduler"""
        if self.is_running:
            return
            
        self.is_running = True
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Cleanup scheduler started")
        
    async def stop_cleanup_scheduler(self):
        """Stop the automatic cleanup scheduler"""
        self.is_running = False
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        logger.info("Cleanup scheduler stopped")
        
    async def _cleanup_loop(self):
        """Main cleanup loop that runs periodically"""
        while self.is_running:
            try:
                await self.cleanup_old_recordings()
                # Run cleanup every hour
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes before retrying
                
    async def cleanup_old_recordings(self) -> dict:
        """Clean up recordings older than retention period"""
        cleanup_stats = {
            "deleted_files": 0,
            "deleted_folders": 0,
            "freed_space": 0,
            "errors": []
        }
        
        try:
            hls_path = Path(settings.hls_base_path)
            if not hls_path.exists():
                return cleanup_stats
                
            cutoff_date = datetime.now() - timedelta(days=settings.retention_days)
            logger.info(f"Starting cleanup of recordings older than {cutoff_date.strftime('%Y-%m-%d')}")
            
            # Process each camera directory
            for camera_dir in hls_path.iterdir():
                if not camera_dir.is_dir():
                    continue
                    
                recordings_dir = camera_dir / "recordings"
                if not recordings_dir.exists():
                    continue
                
                camera_stats = await self._cleanup_camera_recordings(
                    recordings_dir, cutoff_date
                )
                
                cleanup_stats["deleted_files"] += camera_stats["deleted_files"]
                cleanup_stats["deleted_folders"] += camera_stats["deleted_folders"]
                cleanup_stats["freed_space"] += camera_stats["freed_space"]
                cleanup_stats["errors"].extend(camera_stats["errors"])
                
            logger.info(
                f"Cleanup completed: {cleanup_stats['deleted_files']} files, "
                f"{cleanup_stats['deleted_folders']} folders, "
                f"{cleanup_stats['freed_space'] / 1024 / 1024:.2f} MB freed"
            )
            
        except Exception as e:
            error_msg = f"Error during cleanup: {e}"
            logger.error(error_msg)
            cleanup_stats["errors"].append(error_msg)
            
        return cleanup_stats
        
    async def _cleanup_camera_recordings(self, recordings_dir: Path, cutoff_date: datetime) -> dict:
        """Clean up recordings for a specific camera"""
        stats = {
            "deleted_files": 0,
            "deleted_folders": 0,
            "freed_space": 0,
            "errors": []
        }
        
        try:
            # Process each date directory
            for date_dir in recordings_dir.iterdir():
                if not date_dir.is_dir():
                    continue
                    
                try:
                    # Parse date from directory name (YYYY-MM-DD)
                    dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                    
                    if dir_date < cutoff_date:
                        # Calculate size before deletion
                        dir_size = await self._get_directory_size(date_dir)
                        
                        # Delete the entire date directory
                        shutil.rmtree(date_dir)
                        
                        stats["deleted_folders"] += 1
                        stats["freed_space"] += dir_size
                        
                        # Count files that were deleted
                        stats["deleted_files"] += await self._count_files_in_directory(date_dir)
                        
                        logger.debug(f"Deleted directory: {date_dir}")
                        
                except ValueError:
                    # Invalid date format, skip
                    logger.warning(f"Skipping directory with invalid date format: {date_dir}")
                    continue
                except Exception as e:
                    error_msg = f"Error deleting directory {date_dir}: {e}"
                    logger.error(error_msg)
                    stats["errors"].append(error_msg)
                    
        except Exception as e:
            error_msg = f"Error processing recordings directory {recordings_dir}: {e}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)
            
        return stats
        
    async def _get_directory_size(self, directory: Path) -> int:
        """Calculate total size of a directory"""
        total_size = 0
        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
        except Exception as e:
            logger.error(f"Error calculating directory size for {directory}: {e}")
        return total_size
        
    async def _count_files_in_directory(self, directory: Path) -> int:
        """Count total number of files in a directory"""
        count = 0
        try:
            for file_path in directory.rglob("*"):
                if file_path.is_file():
                    count += 1
        except Exception as e:
            logger.error(f"Error counting files in directory {directory}: {e}")
        return count
        
    async def get_cleanup_preview(self) -> dict:
        """Preview what would be cleaned up without actually deleting"""
        preview = {
            "files_to_delete": 0,
            "folders_to_delete": 0,
            "space_to_free": 0,
            "affected_cameras": [],
            "cutoff_date": None
        }
        
        try:
            hls_path = Path(settings.hls_base_path)
            if not hls_path.exists():
                return preview
                
            cutoff_date = datetime.now() - timedelta(days=settings.retention_days)
            preview["cutoff_date"] = cutoff_date.strftime("%Y-%m-%d")
            
            # Process each camera directory
            for camera_dir in hls_path.iterdir():
                if not camera_dir.is_dir():
                    continue
                    
                recordings_dir = camera_dir / "recordings"
                if not recordings_dir.exists():
                    continue
                
                camera_preview = await self._preview_camera_cleanup(
                    recordings_dir, cutoff_date
                )
                
                if camera_preview["folders_to_delete"] > 0:
                    preview["files_to_delete"] += camera_preview["files_to_delete"]
                    preview["folders_to_delete"] += camera_preview["folders_to_delete"]
                    preview["space_to_free"] += camera_preview["space_to_free"]
                    preview["affected_cameras"].append({
                        "camera_id": camera_dir.name,
                        "folders_to_delete": camera_preview["folders_to_delete"],
                        "files_to_delete": camera_preview["files_to_delete"],
                        "space_to_free": camera_preview["space_to_free"]
                    })
                    
        except Exception as e:
            logger.error(f"Error generating cleanup preview: {e}")
            
        return preview
        
    async def _preview_camera_cleanup(self, recordings_dir: Path, cutoff_date: datetime) -> dict:
        """Preview cleanup for a specific camera"""
        preview = {
            "files_to_delete": 0,
            "folders_to_delete": 0,
            "space_to_free": 0
        }
        
        try:
            # Process each date directory
            for date_dir in recordings_dir.iterdir():
                if not date_dir.is_dir():
                    continue
                    
                try:
                    # Parse date from directory name (YYYY-MM-DD)
                    dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                    
                    if dir_date < cutoff_date:
                        # Calculate size and file count
                        dir_size = await self._get_directory_size(date_dir)
                        file_count = await self._count_files_in_directory(date_dir)
                        
                        preview["folders_to_delete"] += 1
                        preview["files_to_delete"] += file_count
                        preview["space_to_free"] += dir_size
                        
                except ValueError:
                    # Invalid date format, skip
                    continue
                except Exception as e:
                    logger.error(f"Error previewing directory {date_dir}: {e}")
                    
        except Exception as e:
            logger.error(f"Error previewing camera recordings {recordings_dir}: {e}")
            
        return preview
        
    async def cleanup_specific_camera(self, camera_id: str, days_to_keep: int = None) -> dict:
        """Clean up recordings for a specific camera"""
        cleanup_stats = {
            "deleted_files": 0,
            "deleted_folders": 0,
            "freed_space": 0,
            "errors": []
        }
        
        try:
            hls_path = Path(settings.hls_base_path)
            camera_dir = hls_path / camera_id
            recordings_dir = camera_dir / "recordings"
            
            if not recordings_dir.exists():
                cleanup_stats["errors"].append(f"Recordings directory not found for camera {camera_id}")
                return cleanup_stats
                
            days = days_to_keep if days_to_keep is not None else settings.retention_days
            cutoff_date = datetime.now() - timedelta(days=days)
            
            camera_stats = await self._cleanup_camera_recordings(
                recordings_dir, cutoff_date
            )
            
            cleanup_stats.update(camera_stats)
            
            logger.info(f"Cleanup completed for camera {camera_id}: {cleanup_stats}")
            
        except Exception as e:
            error_msg = f"Error during cleanup for camera {camera_id}: {e}"
            logger.error(error_msg)
            cleanup_stats["errors"].append(error_msg)
            
        return cleanup_stats


# Global cleanup manager instance
cleanup_manager = CleanupManager() 