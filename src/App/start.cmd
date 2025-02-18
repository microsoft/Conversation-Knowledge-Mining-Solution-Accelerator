@echo off
echo Restoring backend python packages...
call python -m pip install -r requirements.txt
if "%errorlevel%" neq "0" (
    echo Failed to restore backend python packages
    exit /B %errorlevel%
)

echo Restoring frontend npm packages...
cd frontend
call npm install
if "%errorlevel%" neq "0" (
    echo Failed to restore frontend npm packages
    exit /B %errorlevel%
)

echo Building frontend...
call npm run build
if "%errorlevel%" neq "0" (
    echo Failed to build frontend
    exit /B %errorlevel%
)

echo Starting backend...
cd ..
start http://127.0.0.1:5000
call python -m uvicorn app:app --port 5000 --reload
if "%errorlevel%" neq "0" (
    echo Failed to start backend
    exit /B %errorlevel%
)
