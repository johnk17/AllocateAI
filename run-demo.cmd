@echo off
cd /d "%~dp0"
docker compose up -d --build
if errorlevel 1 exit /b 1
echo AllocateAI dashboard: http://localhost:3000
echo API documentation:   http://localhost:8800/docs
echo PostgreSQL:          localhost:55432
echo Stop with: docker compose down
