.PHONY: setup build deploy restart clean logs

setup: build deploy restart

build:
	@echo "Building Docker images with no-cache..."
	eval $$(minikube docker-env) && docker build --no-cache -t quantstream/data-collector:latest ./data-collector
	eval $$(minikube docker-env) && docker build --no-cache -t quantstream/analytics-engine:latest ./analytics-engine

deploy:
	@echo "Applying infrastructure definitions..."
	kubectl apply -f k8s/infrastructure.yaml
	@echo "Waiting for Kafka to be ready..."
	kubectl wait --for=condition=ready pod -l app=kafka --timeout=120s || true
	@echo "Applying application definitions..."
	kubectl apply -f k8s/apps.yaml

restart:
	@echo "Forcing Kubernetes to pull latest images and restart pods..."
	kubectl rollout restart deployment data-collector-engine
	kubectl rollout restart deployment aggregator-engine
	kubectl rollout restart deployment predictor-engine
	kubectl rollout restart deployment dashboard-engine

clean:
	@echo "Cleaning up Kubernetes resources..."
	kubectl delete -f k8s/apps.yaml --ignore-not-found=true
	kubectl delete -f k8s/infrastructure.yaml --ignore-not-found=true

logs:
	@echo "Fetching dashboard logs..."
	kubectl logs -f -l app=dashboard-engine
