$python = ".venv\Scripts\python.exe"

Write-Host "Starting FastAPI backend on port 8000..." -ForegroundColor Cyan
$backend = Start-Process -NoNewWindow -PassThru $python "-m", "uvicorn", "api.main:app", "--reload", "--port", "8000"

Write-Host "Starting Streamlit frontend on port 8501..." -ForegroundColor Cyan
$frontend = Start-Process -NoNewWindow -PassThru $python "-m", "streamlit", "run", "app.py", "--server.port", "8501"

Write-Host ""
Write-Host "Both servers are running." -ForegroundColor Green
Write-Host "  Backend  : http://localhost:8000"
Write-Host "  Frontend : http://localhost:8501"
Write-Host ""
Write-Host "Press Ctrl+C to stop both." -ForegroundColor Yellow

try {
    $backend.WaitForExit()
    $frontend.WaitForExit()
} finally {
    if (!$backend.HasExited) { Stop-Process -Id $backend.Id -Force }
    if (!$frontend.HasExited) { Stop-Process -Id $frontend.Id -Force }
    Write-Host "Servers stopped." -ForegroundColor Red
}
