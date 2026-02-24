package com.quantstream.datacollector.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.socket.client.standard.StandardWebSocketClient;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;
import jakarta.annotation.PostConstruct;
import java.util.Map;

@Service
public class BinanceStreamService extends TextWebSocketHandler {
    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    @Value("${app.kafka.topic}")
    private String topicName;

    public BinanceStreamService(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    @PostConstruct
    public void connect() {
        try {
            StandardWebSocketClient client = new StandardWebSocketClient();
            String uri = "wss://stream.binance.com:443/ws/btcusdt@trade";
            client.execute(this, uri);
            System.out.println("SPRING BOOT CONNECTING TO BINANCE: " + uri);
        } catch (Exception e) {
            System.err.println("CONNECTION FATAL ERROR: " + e.getMessage());
        }
    }

    @Override
    protected void handleTextMessage(WebSocketSession session, TextMessage message) {
        try {
            JsonNode node = objectMapper.readTree(message.getPayload());
            Map<String, Object> payload = Map.of(
                "t", node.get("T").asLong(),
                "p", node.get("p").asText(),
                "q", node.get("q").asText()
            );
            
            String jsonPayload = objectMapper.writeValueAsString(payload);
            kafkaTemplate.send(topicName, jsonPayload);
            
            // Print only prices ending in '0' to avoid terminal spam, but prove data flows
            if (node.get("p").asText().endsWith("0")) {
                System.out.println("DATA SENT TO KAFKA: Price = " + node.get("p").asText());
            }
        } catch (Exception e) {
            System.err.println("DATA PARSING ERROR: " + e.getMessage());
        }
    }
}
