# # Verify Ollama GPU + pull SQL model (run from repo root after docker compose up)
# $ErrorActionPreference = "Stop"

# Write-Host "Checking Ollama container..."
# docker exec matrix-ollama ollama list

# Write-Host "`nPulling SQL model (one-time, ~4GB)..."
# docker exec matrix-ollama ollama pull qwen2.5-coder:7b-instruct-q4_K_M

# Write-Host "`nRunning a tiny GPU warmup query..."
# docker exec matrix-ollama ollama run qwen2.5-coder:7b-instruct-q4_K_M "Reply with exactly: SELECT 1;" --verbose 2>&1 | Select-Object -First 30

# Write-Host "`nLoaded models (look for processor=gpu):"
# docker exec matrix-ollama ollama ps

# Write-Host "`nBackend health (ollama section should show processor gpu after a query):"
# try {
#   Invoke-RestMethod -Uri "http://localhost:8000/health" | ConvertTo-Json -Depth 6
# } catch {
#   Write-Warning "Backend not reachable on :8000 yet."
# }
