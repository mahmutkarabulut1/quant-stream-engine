IMAGE_NAME := mahmut/analytics-engine:v1
JAVA_IMAGE := mahmut/data-collector:v1

.PHONY: setup build deploy clean tunnel status

setup: build deploy
	@echo "INFRASTRUCTURE DEPLOYED SUCCESSFULLY."

build:
	@eval $$(minikube docker-env) && docker build -t $(JAVA_IMAGE) ./data-collector
	@eval $$(minikube docker-env) && docker build -t $(IMAGE_NAME) ./analytics-engine

deploy:
	kubectl apply -f k8s/kafka.yaml
	kubectl apply -f k8s/apps.yaml

clean:
	kubectl delete -f k8s/apps.yaml --ignore-not-found

tunnel:
	kubectl port-forward svc/dashboard-service 8501:8501

status:
	kubectl get pods -w
