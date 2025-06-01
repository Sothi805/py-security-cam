#!/usr/bin/env python3
"""
CCTV Streaming API Server
Run script for the FastAPI application
"""

import uvicorn
import os
from config import settings, camera_configs

if __name__ == "__main__":
    # Set environment variables if .env file exists
    if os.path.exists(".env"):
        from dotenv import load_dotenv
        load_dotenv()
    
    print(f"Starting CCTV Streaming API on {settings.server_host}:{settings.server_port}")
    print(f"HLS files will be stored in: {settings.hls_base_path}")
    print(f"Configured cameras: {len(camera_configs)}")
    
    for camera_id, config in camera_configs.items():
        status = "enabled" if config.enabled else "disabled"
        print(f"  - {camera_id}: {config.name} ({status})")
    
    uvicorn.run(
        "main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        access_log=True,
        log_level="info"
    ) 