#!/bin/bash

REPORT_FILE="quantstream_full_report.txt"

echo "==================================================" > $REPORT_FILE
echo "       QUANTSTREAM DEEP DIAGNOSTIC REPORT         " >> $REPORT_FILE
echo "==================================================" >> $REPORT_FILE
echo "Generated on: $(date)" >> $REPORT_FILE
echo "" >> $REPORT_FILE

echo "--- 1. PROJECT STRUCTURE ---" >> $REPORT_FILE
if command -v tree >/dev/null 2>&1; then
    tree -I "venv|__pycache__|target|.git|.idea|*.pyc|*.class|bin|obj" >> $REPORT_FILE
else
    find . -maxdepth 4 -not -path '*/.*' >> $REPORT_FILE
fi
echo "" >> $REPORT_FILE

echo "--- 2. KUBERNETES RUNTIME STATE ---" >> $REPORT_FILE
echo ">> All Resources:" >> $REPORT_FILE
kubectl get all -o wide >> $REPORT_FILE
echo -e "\n>> Predictor Engine Description (Events & Env Vars):" >> $REPORT_FILE
kubectl describe pod -l app=predictor-engine >> $REPORT_FILE
echo -e "\n>> Recent Logs (Last 100 lines):" >> $REPORT_FILE
kubectl logs -l app=predictor-engine --tail=100 >> $REPORT_FILE
echo "" >> $REPORT_FILE

echo "--- 3. KAFKA STATE (OFFSETS & GROUPS) ---" >> $REPORT_FILE
# Kafka pod ismini bulup grup bilgisini çekmeye çalışır
KAFKA_POD=$(kubectl get pods -l app=kafka -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
if [ ! -z "$KAFKA_POD" ]; then
    echo ">> Kafka Groups:" >> $REPORT_FILE
    kubectl exec $KAFKA_POD -- kafka-consumer-groups --bootstrap-server localhost:9092 --list >> $REPORT_FILE 2>&1
    echo -e "\n>> Trade-Events Topic Offset Status:" >> $REPORT_FILE
    kubectl exec $KAFKA_POD -- kafka-run-class kafka.tools.GetOffsetShell --broker-list localhost:9092 --topic trade-events --time -1 >> $REPORT_FILE 2>&1
fi
echo "" >> $REPORT_FILE

echo "--- 4. FUNCTIONAL CODE AND CONFIGURATION ---" >> $REPORT_FILE
FILE_PATTERNS=("*.py" "*.java" "*.yaml" "*.yml" "pom.xml" "*.sh" "Dockerfile")

for pattern in "${FILE_PATTERNS[@]}"; do
    find . -name "$pattern" -not -path "*/.*" -not -path "*/target/*" -not -path "*/venv/*" | while read -r file; do
        echo "--------------------------------------------------" >> $REPORT_FILE
        echo "FILE: $file" >> $REPORT_FILE
        echo "--------------------------------------------------" >> $REPORT_FILE
        cat "$file" >> $REPORT_FILE
        echo -e "\n" >> $REPORT_FILE
    done
done

echo "==================================================" >> $REPORT_FILE
echo "REPORT COMPLETE" >> $REPORT_FILE
echo "==================================================" >> $REPORT_FILE

echo "Report generation complete: $REPORT_FILE"
