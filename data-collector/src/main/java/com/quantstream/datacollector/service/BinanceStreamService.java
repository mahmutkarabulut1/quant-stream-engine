package com.quantstream.datacollector.service;

import org.springframework.stereotype.Service;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.web.socket.client.WebSocketClient;
import org.springframework.web.socket.client.standard.StandardWebSocketClient;
import org.springframework.web.socket.WebSocketHandler;
import org.springframework.web.socket.WebSocketSession;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.handler.TextWebSocketHandler;
import jakarta.annotation.PostConstruct;
import java.util.concurrent.ExecutionException;

@Service
public class BinanceStreamService {

    private static final String BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@trade";
    private static final String KAFKA_TOPIC = "trade-events";

    private final KafkaTemplate<String, String> kafkaTemplate;

    // Constructor Injection ile KafkaTemplate'i aliyoruz
    public BinanceStreamService(KafkaTemplate<String, String> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    @PostConstruct
    public void connectToStream() {
        System.out.println(">>> 🚀 Binance WebSocket Baglantisi Baslatiliyor...");
        
        WebSocketClient client = new StandardWebSocketClient();
        
        WebSocketHandler handler = new TextWebSocketHandler() {
            @Override
            public void afterConnectionEstablished(WebSocketSession session) {
                System.out.println(">>> ✅ BAGLANTI BASARILI! Veriler Kafka'ya (" + KAFKA_TOPIC + ") akiyor...");
            }

            @Override
            protected void handleTextMessage(WebSocketSession session, TextMessage message) {
                // Gelen JSON verisini direkt Kafka'ya basiyoruz
                kafkaTemplate.send(KAFKA_TOPIC, message.getPayload());
                
                // Terminali kitlememek icin sadece nokta basalim
                System.out.print("."); 
            }
        };

        try {
            client.doHandshake(handler, BINANCE_WS_URL).get();
        } catch (InterruptedException | ExecutionException e) {
            System.err.println(">>> ❌ Baglanti Hatasi: " + e.getMessage());
        }
    }
}
