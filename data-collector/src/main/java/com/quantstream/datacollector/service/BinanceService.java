package com.quantstream.datacollector.service;

import org.json.JSONArray;
import org.json.JSONObject;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import javax.annotation.PostConstruct;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.WebSocket;
import java.util.concurrent.CompletionStage;

@Service
public class BinanceService {

    private static final String TRADE_TOPIC  = "trade-events";
    private static final String CANDLE_TOPIC = "candle-events";  // historical doğrudan buraya
    private static final String BINANCE_REST_URL = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=100";
    private static final String BINANCE_WS_URL   = "wss://stream.binance.com:9443/ws/btcusdt@trade";

    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;

    @PostConstruct
    public void init() {
        fetchHistoricalCandles();   // candle-events'e direkt
        connectToWebSocket();       // trade-events'e realtime
    }

    private void fetchHistoricalCandles() {
        System.out.println("==> Historical candles fetch başladı (100 mum, 5m)...");
        try {
            RestTemplate restTemplate = new RestTemplate();
            String response = restTemplate.getForObject(BINANCE_REST_URL, String.class);
            JSONArray klines = new JSONArray(response);

            int sent = 0;
            for (int i = 0; i < klines.length(); i++) {
                JSONArray k = klines.getJSONArray(i);

                // Binance kline: [0]=openTime [1]=open [2]=high [3]=low [4]=close [5]=volume
                JSONObject candle = new JSONObject();
                candle.put("timestamp",   k.getLong(0));
                candle.put("open",        k.getDouble(1));
                candle.put("high",        k.getDouble(2));
                candle.put("low",         k.getDouble(3));
                candle.put("close",       k.getDouble(4));
                candle.put("volume",      k.getDouble(5));
                candle.put("pv_sum",      k.getDouble(4) * k.getDouble(5));
                candle.put("trade_count", k.optInt(8, 0));

                // Doğrudan candle-events'e gönder, aggregator'ı atla
                kafkaTemplate.send(CANDLE_TOPIC, candle.toString());
                sent++;
                Thread.sleep(10);
            }
            System.out.println("==> Historical candles sent: " + sent + " -> " + CANDLE_TOPIC);

        } catch (Exception e) {
            System.err.println("Historical fetch FAILED: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private void connectToWebSocket() {
        System.out.println("==> Binance WebSocket bağlantısı kuruluyor...");
        try {
            HttpClient client = HttpClient.newHttpClient();
            WebSocket webSocket = client.newWebSocketBuilder()
                .buildAsync(URI.create(BINANCE_WS_URL), new WebSocket.Listener() {

                    @Override
                    public CompletionStage<?> onText(WebSocket ws, CharSequence data, boolean last) {
                        try {
                            JSONObject trade = new JSONObject(data.toString());
                            // Realtime trade'ler aggregator'a gider, aggregator candle üretir
                            JSONObject tradeEvent = new JSONObject();
                            tradeEvent.put("p", trade.getString("p"));
                            tradeEvent.put("t", trade.getLong("T"));
                            tradeEvent.put("q", trade.getString("q"));
                            kafkaTemplate.send(TRADE_TOPIC, tradeEvent.toString());
                        } catch (Exception e) {
                            System.err.println("WS parse error: " + e.getMessage());
                        }
                        ws.request(1);
                        return null;
                    }

                    @Override
                    public void onError(WebSocket ws, Throwable error) {
                        System.err.println("WS error: " + error.getMessage());
                        try { Thread.sleep(5000); } catch (InterruptedException ignored) {}
                        connectToWebSocket();
                    }

                    @Override
                    public CompletionStage<?> onClose(WebSocket ws, int statusCode, String reason) {
                        System.out.println("WS closed — yeniden bağlanıyor...");
                        try { Thread.sleep(3000); } catch (InterruptedException ignored) {}
                        connectToWebSocket();
                        return null;
                    }
                }).join();

            webSocket.request(1);
        } catch (Exception e) {
            System.err.println("WS bağlantı hatası: " + e.getMessage());
        }
    }
}
