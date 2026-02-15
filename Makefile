# Quant-Stream Intelligence Engine Management
# Powered by Mahmut's Nitro Laptop & Kubernetes

COLLECTOR_IMAGE=mahmut/data-collector:v1
ANALYTICS_IMAGE=mahmut/analytics-engine:v1
K8S_DIR=k8s

.PHONY: help build-all deploy restart-dashboard service logs-analytics clean

help:
	@echo "Available commands:"
	@echo "  make build-all      - Build both Java and Python Docker images"
	@echo "  make deploy         - Apply all Kubernetes manifests"
	@echo "  make restart-dashboard - Rebuild and restart the analytics dashboard"
	@echo "  make service        - Expose the dashboard via Minikube"
	@echo "  make logs-analytics - Stream logs from the analytics engine"
	@echo "  make clean          - Delete all deployments and services"

build-all:
	@echo "Building Data Collector..."
	eval $$(minikube docker-env) && cd data-collector && docker build -t $(COLLECTOR_IMAGE) .
	@echo "Building Analytics Engine..."
	eval $$(minikube docker-env) && cd analytics-engine && docker build -t $(ANALYTICS_IMAGE) .

deploy:
	@echo "Deploying to Kubernetes..."
	kubectl apply -f $(K8S_DIR)/apps.yaml

restart-dashboard:
	@echo "Hot-reloading Dashboard..."
	eval $$(minikube docker-env) && cd analytics-engine && docker build -t $(ANALYTICS_IMAGE) .
	kubectl delete pod -l app=dashboard-engine

service:
	minikube service dashboard-service

logs-analytics:
	kubectl logs -f deployment/analytics-engine

clean:
	kubectl delete -f $(K8S_DIR)/apps.yaml
