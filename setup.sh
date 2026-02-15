#!/bin/bash
echo "🧹 Cleaning up zombie processes and ports..."
# 8501 portunu kullanan her seyi (kubectl, streamlit, zombie) temizle
sudo fuser -k 8501/tcp || true
pkill -f "kubectl port-forward" || true

echo "📦 Building Docker images inside Minikube..."
eval $(minikube docker-env)
docker build -t mahmut/analytics-engine:v1 ./analytics-engine

echo "🚀 Deploying to Kubernetes..."
kubectl apply -f k8s/apps.yaml

echo "⏳ Waiting for Dashboard to be Ready..."
kubectl wait --for=condition=ready pod -l app=dashboard-engine --timeout=60s

echo "🌉 Opening the Unbreakable Tunnel..."
kubectl port-forward svc/dashboard-service 8501:8501 &

sleep 3
echo "✨ SYSTEM READY! Open: http://localhost:8501"
