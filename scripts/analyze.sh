#!/usr/bin/env bash

set -e

echo "Generating pytest coverage report..."

docker compose exec -T backend pytest \
    --cov=. \
    --cov-report=xml:/app/coverage.xml

echo "Adjusting coverage report paths for SonarQube..."

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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
    "-Dsonar.working.directory=/usr/src/.scannerwork"

echo "Updating README with SonarQube metrics..."

docker compose run --rm --no-deps -e SONAR_TOKEN sonarqube-tools python scripts/update_sonar_readme.py

echo "Analysis completed and README metrics updated locally."