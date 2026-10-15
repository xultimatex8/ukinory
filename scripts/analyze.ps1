$ErrorActionPreference = "Stop"

Write-Host "Generating pytest coverage report..."

docker compose exec -T backend pytest `
    --cov=. `
    --cov-report=xml:/app/coverage.xml

if ($LASTEXITCODE -ne 0) {
    throw "Tests failed. Aborting analysis."
}

Write-Host "Adjusting coverage report paths for SonarQube..."

$projectRoot = Split-Path $PSScriptRoot -Parent
$coveragePath = Join-Path $projectRoot "backend/coverage.xml"

if (-not (Test-Path $coveragePath)) {
    throw "Coverage report not found at '$coveragePath'. Check the Docker volume mapping for the backend service."
}

[xml]$coverage = Get-Content $coveragePath -Raw

foreach ($source in $coverage.SelectNodes("//sources/source")) {
    if ($source.InnerText -eq "/app") {
        $source.InnerText = "/usr/src/backend"
    }
}

$coverage.Save($coveragePath)

Write-Host "Running SonarScanner..."

docker compose run --rm sonarscanner

if ($LASTEXITCODE -ne 0) {
    throw "SonarQube analysis failed."
}

Write-Host "Analysis completed."