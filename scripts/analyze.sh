#!/usr/bin/env bash

set -e

echo "Generating pytest coverage report..."

docker compose exec -T backend pytest \
    --cov=. \
    --cov-report=xml:/app/coverage.xml

echo "Generating frontend coverage report..."

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

(
    cd "$PROJECT_ROOT/frontend"
    npm run test:run -- --coverage
)

FRONTEND_COVERAGE_PATH="$PROJECT_ROOT/frontend/coverage/lcov.info"

if [ ! -f "$FRONTEND_COVERAGE_PATH" ]; then
    echo "Frontend coverage report not found at '$FRONTEND_COVERAGE_PATH'."
    exit 1
fi

echo "Adjusting coverage report paths for SonarQube..."

COVERAGE_PATH="$PROJECT_ROOT/backend/coverage.xml"

if [ ! -f "$COVERAGE_PATH" ]; then
    echo "Coverage report not found at '$COVERAGE_PATH'. Check the Docker volume mapping for the backend service."
    exit 1
fi

python3 - "$COVERAGE_PATH" <<'PYTHON'
import sys
import xml.etree.ElementTree as ET

coverage_path = sys.argv[1]
tree = ET.parse(coverage_path)
root = tree.getroot()

for source in root.findall(".//sources/source"):
    if source.text == "/app":
        source.text = "/usr/src/backend"

tree.write(coverage_path, encoding="utf-8", xml_declaration=True)
PYTHON

echo "Running SonarScanner..."

docker compose run --rm sonarscanner \
    "-Dsonar.working.directory=/usr/src/.scannerwork" \
    "-Dsonar.javascript.lcov.reportPaths=frontend/coverage/lcov.info"

echo "Updating README with SonarQube metrics..."

docker compose run --rm --no-deps -e SONAR_TOKEN sonarqube-tools python scripts/update_sonar_readme.py

echo "Analysis completed and README metrics updated locally."