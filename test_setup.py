#!/usr/bin/env python3
"""
Test setup script for CCTV Streaming API
Verifies that all dependencies are properly installed and configured
"""

import sys
import subprocess
import importlib
import os
from pathlib import Path

def check_python_version():
    """Check Python version"""
    print("Checking Python version...")
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 3.8+ required, got {version.major}.{version.minor}")
        return False
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")
    return True

def check_ffmpeg():
    """Check if FFmpeg is available"""
    print("Checking FFmpeg installation...")
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"✅ {version_line}")
            return True
        else:
            print("❌ FFmpeg not found or not working")
            return False
    except FileNotFoundError:
        print("❌ FFmpeg not found in PATH")
        return False
    except Exception as e:
        print(f"❌ Error checking FFmpeg: {e}")
        return False

def check_dependencies():
    """Check Python dependencies"""
    print("Checking Python dependencies...")
    required_packages = [
        'fastapi',
        'uvicorn',
        'psutil',
        'aiofiles',
        'pydantic',
        'pydantic_settings'
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            importlib.import_module(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package} not found")
            missing_packages.append(package)
    
    return len(missing_packages) == 0, missing_packages

def check_config():
    """Check configuration"""
    print("Checking configuration...")
    
    # Check if .env file exists
    env_file = Path(".env")
    if not env_file.exists():
        print("⚠️  No .env file found. You can copy .env.example to .env")
        print("   The API will use default settings")
    else:
        print("✅ .env file found")
    
    # Check if config.py can be loaded
    try:
        from config import settings, camera_configs
        print(f"✅ Configuration loaded")
        print(f"   Server: {settings.server_host}:{settings.server_port}")
        print(f"   HLS Path: {settings.hls_base_path}")
        print(f"   Cameras configured: {len(camera_configs)}")
        
        for camera_id, config in camera_configs.items():
            status = "enabled" if config.enabled else "disabled"
            print(f"   - {camera_id}: {config.name} ({status})")
        
        return True
    except Exception as e:
        print(f"❌ Error loading configuration: {e}")
        return False

def create_directories():
    """Create necessary directories"""
    print("Creating directories...")
    try:
        from config import settings
        hls_path = Path(settings.hls_base_path)
        hls_path.mkdir(exist_ok=True)
        print(f"✅ Created HLS directory: {hls_path}")
        return True
    except Exception as e:
        print(f"❌ Error creating directories: {e}")
        return False

def test_api_import():
    """Test if main API can be imported"""
    print("Testing API import...")
    try:
        import main
        print("✅ Main API module imported successfully")
        return True
    except Exception as e:
        print(f"❌ Error importing main API: {e}")
        return False

def main():
    """Run all tests"""
    print("🔍 CCTV Streaming API - Setup Verification")
    print("=" * 50)
    
    tests = [
        ("Python Version", check_python_version),
        ("FFmpeg", check_ffmpeg),
        ("Python Dependencies", lambda: check_dependencies()[0]),
        ("Configuration", check_config),
        ("Directories", create_directories),
        ("API Import", test_api_import)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📋 Summary:")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name}: {status}")
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! You can now run the API with:")
        print("   python run.py")
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above before running the API.")
        
        # Check for missing dependencies
        deps_ok, missing = check_dependencies()
        if not deps_ok:
            print(f"\n💡 To install missing dependencies:")
            print("   pip install -r requirements.txt")
        
        # Check for FFmpeg
        if not check_ffmpeg():
            print(f"\n💡 To install FFmpeg:")
            print("   - Windows: Download from https://ffmpeg.org/download.html")
            print("   - Ubuntu/Debian: sudo apt install ffmpeg")
            print("   - macOS: brew install ffmpeg")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1) 