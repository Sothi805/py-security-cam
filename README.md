# CCTV Streaming API

A high-performance FastAPI backend for 24/7 CCTV streaming and recording with FFmpeg integration, designed for Hikvision HVR/DVR systems and Flutter mobile applications.

## Features

- **Real-time HLS Streaming**: Live camera feeds via HTTP Live Streaming (HLS)
- **Automatic Recording**: 24/7 recording with hourly segments
- **Health Monitoring**: System resource monitoring and alerts
- **Auto Cleanup**: Configurable retention period (default 30 days)
- **Multi-Camera Support**: Environment variable-based camera configuration
- **Flutter Compatible**: Optimized for Flutter's video_player package
- **RESTful API**: Comprehensive REST endpoints for management
- **Process Management**: Automatic FFmpeg process monitoring and restart

## Directory Structure

```
hls/{camera_id}/
     ├── live/
     │     ├── segment0.ts
     │     ├── segment1.ts
     │     └── live.m3u8
     └── recordings/
           └── YYYY-MM-DD/
                 └── HH/
                       ├── 00.ts
                       ├── 01.ts
                       ├── ...
                       ├── 59.ts
                       └── playlist.m3u8
```

## Prerequisites

- Python 3.8+
- FFmpeg (must be installed and available in PATH)
- Windows/Linux/macOS support

### Installing FFmpeg

**Windows:**
1. Download from https://ffmpeg.org/download.html
2. Extract and add to PATH
3. Verify: `ffmpeg -version`

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**CentOS/RHEL:**
```bash
sudo yum install epel-release
sudo yum install ffmpeg
```

**macOS:**
```bash
brew install ffmpeg
```

## Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd fastapi_cctv
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create environment configuration:**
   ```bash
   cp config.py.example .env
   ```

4. **Configure your cameras in `.env`:**
   ```env
   # Camera 1
   CAMERA_1_ID=camera_01
   CAMERA_1_NAME=Front Entrance
   CAMERA_1_RTSP_URL=rtsp://admin:password@192.168.1.100:554/Streaming/Channels/101
   CAMERA_1_ENABLED=true

   # Camera 2
   CAMERA_2_ID=camera_02
   CAMERA_2_NAME=Parking Lot
   CAMERA_2_RTSP_URL=rtsp://admin:password@192.168.1.101:554/Streaming/Channels/101
   CAMERA_2_ENABLED=true
   ```

5. **Start the server:**
   ```bash
   python run.py
   ```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SERVER_HOST` | `0.0.0.0` | Server bind address |
| `SERVER_PORT` | `8000` | Server port |
| `HLS_BASE_PATH` | `./hls` | HLS files storage path |
| `RETENTION_DAYS` | `30` | Recording retention period |
| `FFMPEG_THREAD_COUNT` | `2` | FFmpeg thread count |
| `HLS_SEGMENT_DURATION` | `10` | HLS segment duration (seconds) |
| `VIDEO_BITRATE` | `2000k` | Video bitrate |
| `AUDIO_BITRATE` | `128k` | Audio bitrate |

### Camera Configuration

Each camera requires these environment variables:
- `CAMERA_X_ID`: Unique camera identifier
- `CAMERA_X_NAME`: Human-readable name
- `CAMERA_X_RTSP_URL`: RTSP stream URL
- `CAMERA_X_ENABLED`: Enable/disable camera (true/false)

## API Endpoints

### Health Monitoring

- `GET /health` - Complete system health status
- `GET /health/metrics` - Current system metrics
- `GET /health/processes` - FFmpeg process information
- `GET /health/storage` - Storage usage details

### Camera Management

- `GET /cameras` - List all cameras
- `GET /cameras/{camera_id}` - Get camera information
- `POST /cameras/{camera_id}/start` - Start camera stream
- `POST /cameras/{camera_id}/stop` - Stop camera stream
- `POST /cameras/{camera_id}/restart` - Restart camera stream

### Streaming

- `GET /stream/{camera_id}/live.m3u8` - Live HLS playlist
- `GET /stream/{camera_id}/info` - Stream information

### Recordings

- `GET /recordings/{camera_id}` - List recordings
- `GET /recordings/{camera_id}/{date}/{hour}/playlist.m3u8` - Recording playlist

### Cleanup

- `GET /cleanup/preview` - Preview cleanup operations
- `POST /cleanup/run` - Manual cleanup trigger
- `POST /cleanup/camera/{camera_id}` - Camera-specific cleanup

## Flutter Integration

### Using with video_player package

```dart
import 'package:video_player/video_player.dart';

class CCTVPlayer extends StatefulWidget {
  final String cameraId;
  
  @override
  _CCTVPlayerState createState() => _CCTVPlayerState();
}

class _CCTVPlayerState extends State<CCTVPlayer> {
  VideoPlayerController? _controller;
  
  @override
  void initState() {
    super.initState();
    _initializePlayer();
  }
  
  void _initializePlayer() {
    final hlsUrl = 'http://your-server:8000/stream/${widget.cameraId}/live.m3u8';
    _controller = VideoPlayerController.network(hlsUrl);
    _controller!.initialize().then((_) {
      setState(() {});
      _controller!.play();
    });
  }
  
  @override
  Widget build(BuildContext context) {
    return _controller?.value.isInitialized ?? false
        ? AspectRatio(
            aspectRatio: _controller!.value.aspectRatio,
            child: VideoPlayer(_controller!),
          )
        : CircularProgressIndicator();
  }
}
```

### Health Monitoring

```dart
class HealthService {
  static const String baseUrl = 'http://your-server:8000';
  
  static Future<Map<String, dynamic>> getSystemHealth() async {
    final response = await http.get(Uri.parse('$baseUrl/health'));
    return json.decode(response.body);
  }
  
  static Future<List<dynamic>> getCameras() async {
    final response = await http.get(Uri.parse('$baseUrl/cameras'));
    return json.decode(response.body);
  }
}
```

## Production Deployment

### Using Docker

```dockerfile
FROM python:3.9-slim

# Install FFmpeg
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "run.py"]
```

### Using systemd (Linux)

```ini
[Unit]
Description=CCTV Streaming API
After=network.target

[Service]
Type=simple
User=cctv
WorkingDirectory=/opt/cctv-api
ExecStart=/opt/cctv-api/venv/bin/python run.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /hls/ {
        add_header Cache-Control no-cache;
        add_header Access-Control-Allow-Origin *;
    }
}
```

## Troubleshooting

### Common Issues

1. **FFmpeg not found**: Ensure FFmpeg is installed and in PATH
2. **Camera connection failed**: Verify RTSP URLs and credentials
3. **HLS segments not generated**: Check FFmpeg logs and permissions
4. **High CPU usage**: Reduce video bitrate or thread count

### Logs

Application logs include:
- FFmpeg process management
- Camera connection status
- System health alerts
- Cleanup operations

### Performance Tuning

- Adjust `FFMPEG_THREAD_COUNT` based on CPU cores
- Lower `VIDEO_BITRATE` for bandwidth-limited scenarios
- Increase `HLS_SEGMENT_DURATION` for better efficiency
- Monitor disk usage and adjust `RETENTION_DAYS`

## License

This project is licensed under the MIT License.

## Support

For issues and feature requests, please create an issue in the repository. 