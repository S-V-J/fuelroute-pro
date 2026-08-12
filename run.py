#!/usr/bin/env python
"""
Dynamic Port Runner for FuelRoute Pro.
Automatically finds an available ephemeral port and boots the Django development server.
This eliminates "Port already in use" errors without requiring hardcoded port assignments.
"""
import os
import sys
import socket
import subprocess

def get_free_port():
    """
    Binds to port 0, which instructs the OS kernel to assign a random free ephemeral port.
    We immediately close the socket and return the assigned port number.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]

def main():
    port = get_free_port()
    print(f"🔍 Scanning for available ports...")
    print(f"🚀 Selected dynamic free port: {port}")
    print(f"🌐 Server will be available at: http://127.0.0.1:{port}/api/v1/health/")
    print(f"📚 API Docs available at: http://127.0.0.1:{port}/api/docs/")
    print("-" * 60)
    
    # Use sys.executable to ensure we use the current virtual environment's Python
    cmd = [sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}"]
    
    try:
        # Pass the current environment variables to the subprocess
        subprocess.run(cmd, env=os.environ)
    except KeyboardInterrupt:
        print("\n🛑 Server stopped gracefully.")

if __name__ == "__main__":
    main()