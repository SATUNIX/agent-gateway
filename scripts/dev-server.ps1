Param(
    [int]$Port = 8000
)

Write-Host "Starting Agent Gateway dev server on port $Port..."
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port $Port
