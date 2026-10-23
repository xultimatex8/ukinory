$ErrorActionPreference = "Stop"

Write-Host "Generating pytest coverage report..."

docker compose exec -T backend pytest `
    --cov=. `
    --cov-report=xml:/app/coverage.xml `
    --junitxml=/app/junit.xml

if ($LASTEXITCODE -ne 0) {
    throw "Tests failed. Aborting analysis."
}

$projectRoot = Split-Path $PSScriptRoot -Parent

Write-Host "Generating frontend coverage report..."

Push-Location (Join-Path $projectRoot "frontend")
try {
    npm run test:run -- --coverage `
        --reporter=default --reporter=junit --outputFile.junit=junit.xml

    if ($LASTEXITCODE -ne 0) {
        throw "Frontend tests failed. Aborting analysis."
    }
}
finally {
    Pop-Location
}

$frontendCoveragePath = Join-Path $projectRoot "frontend/coverage/lcov.info"

if (-not (Test-Path $frontendCoveragePath)) {
    throw "Frontend coverage report not found at '$frontendCoveragePath'."
}

Write-Host "Adjusting coverage report paths for SonarQube..."

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

docker compose run --rm sonarscanner `
    "-Dsonar.working.directory=/usr/src/.scannerwork" `
    "-Dsonar.javascript.lcov.reportPaths=frontend/coverage/lcov.info"

if ($LASTEXITCODE -ne 0) {
    throw "SonarQube analysis failed."
}

Write-Host "Updating README with SonarQube metrics..."

docker compose run --rm --no-deps -e SONAR_TOKEN sonarqube-tools python scripts/update_sonar_readme.py

if ($LASTEXITCODE -ne 0) {
    throw "Failed to update README with SonarQube metrics."
}

Write-Host "Analysis completed and README metrics updated locally."