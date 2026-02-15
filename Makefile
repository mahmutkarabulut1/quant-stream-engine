IMAGE_NAME := mahmut/analytics-engine:v1
K8S_FILE := k8s/apps.yaml
PORT := 8501
APP_LABEL := app=dashboard-engine
SERVICE_NAME := svc/dashboard-service

.PHONY: all setup build deploy clean tunnel logs wait help

all: help

setup: clean build deploy wait
	@echo "Setup complete. Run 'make tunnel' to access the dashboard."

build:
	@echo "Building Docker image..."
	@eval $$(minikube docker-env) && docker build -t $(IMAGE_NAME) ./analytics-engine

clean:
	@echo "Cleaning up legacy resources..."
	-kubectl delete -f $(K8S_FILE) --ignore-not-found
	-sudo fuser -k $(PORT)/tcp > /dev/null 2>&1
	-pkill -f "kubectl port-forward" > /dev/null 2>&1

deploy:
	@echo "Deploying to Kubernetes..."
	kubectl apply -f $(K8S_FILE)

wait:
	@echo "Waiting for pod to be ready..."
	kubectl wait --for=condition=ready pod -l $(APP_LABEL) --timeout=120s

tunnel:
	@echo "Opening tunnel to localhost:$(PORT)..."
	@echo "Access here: http://localhost:$(PORT)"
	kubectl port-forward $(SERVICE_NAME) $(PORT):$(PORT)

logs:
	kubectl logs -l $(APP_LABEL) -f

help:
	@echo "Available commands:"
	@echo "  make setup   - Clean, Build, Deploy, and Wait"
	@echo "  make tunnel  - Start the connection"
	@echo "  make logs    - View real-time logs"
	@echo "  make clean   - Remove all resources"
