@echo off
REM Matrix Chat Backend Starter Script for Windows

cls
echo.
echo ╔════════════════════════════════════════╗
echo ║  🟢 MATRIX CHAT - Backend Starter      ║
echo ╚════════════════════════════════════════╝
echo.

REM Navigate to backend directory
cd backend || (
    echo ❌ Error: backend directory not found
    echo Please run this script from the project root
    pause
    exit /b 1
)

REM Check if Python is installed
python --version >nul 2>&1 || (
    echo ❌ Error: Python not found
    echo Please install Python 3.8 or higher
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo 📦 Creating Python virtual environment...
    python -m venv venv
    echo ✓ Virtual environment created
) else (
    echo ✓ Virtual environment already exists
)

REM Activate virtual environment
echo 🔌 Activating virtual environment...
call venv\Scripts\activate.bat || (
    echo ❌ Error: Could not activate virtual environment
    pause
    exit /b 1
)

REM Install requirements
echo 📥 Installing dependencies...
pip install -q -r requirements.txt || (
    echo ❌ Error: Failed to install dependencies
    pause
    exit /b 1
)
echo ✓ Dependencies installed

REM Create .env if it doesn't exist
if not exist ".env" (
    echo ⚙️  Creating .env file from template...
    copy .env.example .env >nul
    echo ✓ .env file created (using defaults)
)

REM Check Ollama connection
echo.
echo 🔍 Checking Ollama connection...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Ollama is running at http://localhost:11434
) else (
    echo ⚠️  WARNING: Could not reach Ollama at http://localhost:11434
    echo    Make sure Docker Ollama container is running:
    echo    docker run -d -p 11434:11434 ollama/ollama
    echo.
)

REM Start the server in the same window
echo.
echo 🚀 Starting FastAPI server...
echo 📍 Server will be available at http://localhost:8000
echo 🏥 Health check: http://localhost:8000/health
echo.
echo ⚡ This window will show server logs
echo 💡 Press Ctrl+C to stop the server
echo.
echo ════════════════════════════════════════════════════════════════════
echo.

REM Run the server directly (this will keep the window open)
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

REM If we get here, the server was stopped
echo.
echo ════════════════════════════════════════════════════════════════════
echo 🛑 Server stopped
echo.
echo Press any key to close this window...
pause >nul