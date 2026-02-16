# Project Variables
IMAGE_NAME := mahmut/analytics-engine:v1
K8S_FILE := k8s/apps.yaml
PORT := 8501
APP_LABEL := app=dashboard-engine
SERVICE_NAME := svc/dashboard-service

.PHONY: all setup check-network clean build deploy wait tunnel logs help

# Default target
all: help

# --- MAIN WORKFLOW ---

setup: check-network clean build deploy wait
	@echo "---------------------------------------------------"
	@echo "SYSTEM READY."
	@echo "---------------------------------------------------"
	@echo "Run 'make tunnel' to access the dashboard."

# --- INDIVIDUAL STEPS ---

# 0. Network Check (Self-Healing)
check-network:
	@echo "Checking Kubernetes cluster connectivity..."
	@kubectl get nodes > /dev/null 2>&1 || (echo "Minikube is stopped or IP changed. Restarting Minikube..." && minikube start)

# 1. Clean Resources
clean:
	@echo "Cleaning up legacy resources and processes..."
	-kubectl delete -f $(K8S_FILE) --ignore-not-found
	-sudo fuser -k $(PORT)/tcp > /dev/null 2>&1
	-pkill -f "kubectl port-forward" > /dev/null 2>&1

# 2. Build Docker Image
# Uses --no-cache to ensure code updates are reflected.
# Uses eval $(minikube docker-env) to build directly inside Minikube.
build:
	@echo "Building Docker image inside Minikube (no-cache)..."
	@eval $$(minikube docker-env) && docker build --no-cache -t $(IMAGE_NAME) ./analytics-engine

# 3. Deploy to Kubernetes
deploy:
	@echo "Deploying to Kubernetes..."
	kubectl apply -f $(K8S_FILE)

# 4. Wait for Readiness
wait:
	@echo "Waiting for pod to be ready (timeout: 120s)..."
	kubectl wait --for=condition=ready pod -l $(APP_LABEL) --timeout=120s

# 5. Port Forwarding
tunnel:
	@echo "Opening tunnel to localhost:$(PORT)..."
	@echo "Access here: http://localhost:$(PORT)"
	kubectl port-forward $(SERVICE_NAME) $(PORT):$(PORT)

# --- UTILITIES ---

logs:
	kubectl logs -l $(APP_LABEL) -f

help:
	@echo "Available commands:"
	@echo "  make setup   - Fix network, build, clean, deploy and wait."
	@echo "  make tunnel  - Start port forwarding to access the site."
	@echo "  make logs    - View real-time logs."
	@echo "  make clean   - Remove all resources."