#!/bin/bash

REPORT_FILE="quantstream_mega_report.txt"

echo "==================================================" > $REPORT_FILE
echo "       QUANTSTREAM MEGA REPORT FOR ANALYSIS       " >> $REPORT_FILE
echo "==================================================" >> $REPORT_FILE
echo "Date: $(date)" >> $REPORT_FILE
echo "" >> $REPORT_FILE

echo "--- 1. PROJECT STRUCTURE ---" >> $REPORT_FILE
if command -v tree >/dev/null 2>&1; then
    tree -I "venv|__pycache__|target|.git|.idea|*.pyc|*.class|bin|obj" >> $REPORT_FILE
else
    find . -maxdepth 4 -not -path '*/.*' >> $REPORT_FILE
fi
echo "" >> $REPORT_FILE

echo "--- 2. MAKEFILE AND SCRIPTS ---" >> $REPORT_FILE
find . -name "Makefile" -o -name "*.sh" | grep -v "venv" | while read -r file; do
    echo "--------------------------------------------------" >> $REPORT_FILE
    echo "FILE: $file" >> $REPORT_FILE
    echo "--------------------------------------------------" >> $REPORT_FILE
    cat "$file" >> $REPORT_FILE
    echo -e "\n" >> $REPORT_FILE
done

echo "--- 3. KUBERNETES CONFIGS ---" >> $REPORT_FILE
find . -name "*.yaml" -o -name "*.yml" | grep -v "venv" | while read -r file; do
    echo "--------------------------------------------------" >> $REPORT_FILE
    echo "FILE: $file" >> $REPORT_FILE
    echo "--------------------------------------------------" >> $REPORT_FILE
    cat "$file" >> $REPORT_FILE
    echo -e "\n" >> $REPORT_FILE
done

echo "--- 4. PYTHON SOURCE CODE ---" >> $REPORT_FILE
find ./analytics-engine -name "*.py" | grep -v "venv" | while read -r file; do
    echo "--------------------------------------------------" >> $REPORT_FILE
    echo "FILE: $file" >> $REPORT_FILE
    echo "--------------------------------------------------" >> $REPORT_FILE
    cat "$file" >> $REPORT_FILE
    echo -e "\n" >> $REPORT_FILE
done

echo "--- 5. JAVA SOURCE CODE ---" >> $REPORT_FILE
find ./data-collector -name "*.java" -o -name "pom.xml" | grep -v "target" | grep -v "venv" | while read -r file; do
    echo "--------------------------------------------------" >> $REPORT_FILE
    echo "FILE: $file" >> $REPORT_FILE
    echo "--------------------------------------------------" >> $REPORT_FILE
    cat "$file" >> $REPORT_FILE
    echo -e "\n" >> $REPORT_FILE
done

echo "--- 6. DOCKERFILES ---" >> $REPORT_FILE
find . -name "Dockerfile" | while read -r file; do
    echo "--------------------------------------------------" >> $REPORT_FILE
    echo "FILE: $file" >> $REPORT_FILE
    echo "--------------------------------------------------" >> $REPORT_FILE
    cat "$file" >> $REPORT_FILE
    echo -e "\n" >> $REPORT_FILE
done

echo "Report generated: $REPORT_FILE"
