"""
Server launcher for Chemical Store Management System.
Runs Uvicorn on http://127.0.0.1:8000
"""

import uvicorn
import os
import sys

# Ensure current directory is on python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("==================================================================")
    print("STARTING CHEMICAL STORE MANAGEMENT SYSTEM SERVER")
    print("Access web interface at: http://127.0.0.1:8000")
    print("==================================================================")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False, log_level="info")
