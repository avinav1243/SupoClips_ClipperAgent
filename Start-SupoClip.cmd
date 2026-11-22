@echo off
setlocal
cd /d "%~dp0supoclip"
if not exist "docker-compose.yml" (
  echo SupoClip source folder is missing.
  pause
  exit /b 1
)
where docker >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is not on PATH. Open Docker Desktop, then try again.
  pause
  exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
  echo Starting Docker Desktop. Its first start may take several minutes.
  docker desktop start
  if errorlevel 1 (
    echo Docker Desktop could not start. Restart Windows after the WSL installation.
    echo If WSL still reports virtualization unavailable, check BIOS virtualization.
    pause
    exit /b 1
  )
)
docker info >nul 2>&1
if errorlevel 1 (
  echo Wait for Docker Desktop to show that its engine is running, then try again.
  pause
  exit /b 1
)
docker compose config --quiet
if errorlevel 1 (
  echo SupoClip configuration is invalid. Check supoclip\.env.
  pause
  exit /b 1
)
echo Downloading and building SupoClip. The first run may take a while.
docker compose up -d --build
if errorlevel 1 (
  echo SupoClip did not start successfully. Review the error above.
  pause
  exit /b 1
)
echo.
docker compose ps
echo.
echo Open http://localhost:3107 after the services become healthy.
echo Add your API keys in supoclip\.env before submitting videos.
echo Backend API docs: http://localhost:8000/docs
pause
