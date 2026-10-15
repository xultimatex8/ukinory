
#!/usr/bin/env bash

set -e

echo "Generating pytest coverage report..."

docker compose exec -T backend pytest \
    --cov=. \
    --cov-report=xml:coverage.xml

echo "Adjusting coverage report paths for SonarQube..."

COVERAGE_PATH="backend/coverage.xml"

if [ ! -f "$COVERAGE_PATH" ]; then
    echo "Coverage report not found: $COVERAGE_PATH"
    exit 1
fi

python3 - "$COVERAGE_PATH" <<'PYTHON'
import sys
import xml.etree.ElementTree as ET

coverage_path = sys.argv[1]
tree = ET.parse(coverage_path)
root = tree.getroot()

for source in root.findall("./sources/source"):
    if source.text == "/app":
        source.text = "/usr/src/backend"

tree.write(coverage_path, encoding="utf-8", xml_declaration=True)
PYTHON

echo "Running SonarScanner..."

docker compose run --rm sonarscanner

echo "Analysis completed."
