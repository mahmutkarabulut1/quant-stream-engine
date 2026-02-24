#!/bin/bash

# ANSI Color Codes for a professional look
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

while true; do
    clear
    echo -e "${YELLOW}==================================================${NC}"
    echo -e "${YELLOW}       QUANTSTREAM SYSTEM OBSERVABILITY           ${NC}"
    echo -e "${YELLOW}==================================================${NC}"
    echo -e "System Time: $(date)"
    echo ""
    
    echo "--- 1. KUBERNETES POD STATUS ---"
    # Filter out only active pods and hide the old/failed ones for the video
    kubectl get pods | grep -E "aggregator|predictor|dashboard|kafka|zookeeper|data-collector-engine|evaluator|streamer"
    echo ""
    
    echo "--- 2. AGGREGATOR ENGINE (Data Pipeline) ---"
    # Look for real exceptions while ignoring startup/kafka waits
    AGG_ERRORS=$(kubectl logs --tail=50 -l app=aggregator-engine 2>&1 | grep -iE "exception|fatal|error" | grep -v "wait-for-kafka")
    if [ -z "$AGG_ERRORS" ]; then
        echo -e "Status: ${GREEN}HEALTHY${NC}"
        echo "Latest Flow:"
        kubectl logs --tail=10 -l app=aggregator-engine 2>&1 | grep "Candle Created" | tail -n 2
    else
        echo -e "Status: ${RED}ATTENTION REQUIRED${NC}"
        echo "$AGG_ERRORS" | tail -n 2
    fi
    echo ""
    
    echo "--- 3. PREDICTOR ENGINE (AI Analysis) ---"
    # Filter out ALL TensorFlow/CUDA/oneDNN non-critical messages
    PRED_ERRORS=$(kubectl logs --tail=50 -l app=predictor-engine 2>&1 | grep -i "error" | grep -vE "oneDNN|floating-point|cuDNN|cuFFT|cuBLAS|TensorRT|cuda|GPU|binary is optimized")
    if [ -z "$PRED_ERRORS" ]; then
        echo -e "Status: ${GREEN}HEALTHY${NC}"
        echo "Latest AI Prediction:"
        # Shows actual AI results instead of log spam
        kubectl logs --tail=30 -l app=predictor-engine 2>&1 | grep -E "Prediction|Signal|Active" | tail -n 2
    else
        echo -e "Status: ${RED}CRITICAL ERROR${NC}"
        echo "$PRED_ERRORS" | tail -n 2
    fi
    echo ""
    
    echo "--- 4. DASHBOARD ENGINE (Web UI) ---"
    DASH_ERRORS=$(kubectl logs --tail=30 -l app=dashboard-engine 2>&1 | grep -iE "error|exception|fail")
    if [ -z "$DASH_ERRORS" ]; then
        echo -e "Status: ${GREEN}ONLINE${NC}"
    else
        echo -e "Status: ${RED}UI DISRUPTION${NC}"
        echo "$DASH_ERRORS" | tail -n 1
    fi
    echo ""
    
    echo -e "${YELLOW}Monitoring Active... Press Ctrl+C to exit${NC}"
    sleep 10
done
