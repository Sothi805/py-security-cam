# 🚀 Quick Start Guide

Get your CCTV Streaming API up and running in minutes!

## 1. Prerequisites Check

Run the setup verification script:
```bash
python test_setup.py
```

This will check:
- Python 3.8+ installation
- FFmpeg availability
- Required dependencies
- Configuration setup

## 2. Install Dependencies

```bash
pip install -r requirements.txt
```

## 3. Configure Your Cameras

Create a `.env` file (copy from `.env.example`):
```bash
# Copy the example file
cp .env.example .env

# Edit with your camera details
# Replace the RTSP URLs with your actual camera URLs
```

### Hikvision RTSP URL Format:
```
rtsp://username:password@camera_ip:554/Streaming/Channels/101
```

Example configuration in `.env`:
```env
CAMERA_1_ID=front_door
CAMERA_1_NAME=Front Door Camera
CAMERA_1_RTSP_URL=rtsp://admin:mypassword@192.168.1.100:554/Streaming/Channels/101
CAMERA_1_ENABLED=true

CAMERA_2_ID=parking_lot
CAMERA_2_NAME=Parking Lot Camera
CAMERA_2_RTSP_URL=rtsp://admin:mypassword@192.168.1.101:554/Streaming/Channels/101
CAMERA_2_ENABLED=true
```

## 4. Start the Server

```bash
python run.py
```

The API will start on `http://localhost:8000`

## 5. Test Your Setup

### Check API Status:
```bash
curl http://localhost:8000/
```

### Check System Health:
```bash
curl http://localhost:8000/health
```

### List Cameras:
```bash
curl http://localhost:8000/cameras
```

### Access Live Stream:
Open in VLC or web browser:
```
http://localhost:8000/stream/front_door/live.m3u8
```

## 6. Flutter Integration

Add to your Flutter app:
```dart
VideoPlayerController.network(
  'http://your-server-ip:8000/stream/front_door/live.m3u8'
)
```

## 📁 Directory Structure

After starting, your files will be organized as:
```
hls/
├── front_door/
│   ├── live/
│   │   ├── segment000.ts
│   │   ├── segment001.ts
│   │   └── live.m3u8
│   └── recordings/
│       └── 2024-01-15/
│           └── 14/
│               ├── 00.ts
│               ├── 01.ts
│               └── playlist.m3u8
└── parking_lot/
    └── ... (same structure)
```

## 🔧 Common Issues

### FFmpeg Not Found
**Windows:** Download from https://ffmpeg.org and add to PATH  
**Linux:** `sudo apt install ffmpeg`  
**macOS:** `brew install ffmpeg`

### Camera Connection Failed
- Verify RTSP URL format
- Check camera IP address and credentials
- Ensure camera is accessible from server

### No Video in Flutter
- Check HLS URL accessibility
- Verify CORS headers (should work automatically)
- Test stream in VLC first

## 🐳 Docker Deployment

Quick Docker setup:
```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f cctv-api
```

## 📊 Monitoring

### API Endpoints:
- **Health:** `GET /health`
- **Cameras:** `GET /cameras`
- **Recordings:** `GET /recordings/{camera_id}`
- **Cleanup:** `GET /cleanup/preview`

### Web Interface:
Access the API documentation at:
```
http://localhost:8000/docs
```

## 🔄 Next Steps

1. **Configure retention:** Adjust `RETENTION_DAYS` in `.env`
2. **Add more cameras:** Add `CAMERA_X_*` variables
3. **Production deployment:** Use Docker or systemd
4. **SSL/HTTPS:** Add reverse proxy (nginx example included)
5. **Monitoring:** Set up alerts for health endpoints

## 💡 Tips

- Use different bitrates for mobile vs desktop
- Monitor disk usage - video files grow quickly
- Test with one camera first before adding more
- Keep camera firmware updated for best compatibility

Happy streaming! 📹✨ 