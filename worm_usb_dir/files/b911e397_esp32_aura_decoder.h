/*
 * ESP32 Full AURA Decoder
 *
 * Complete AURA decoder for ESP32 to verify any message in the AI Safety System.
 *
 * Memory Requirements:
 *   Flash: ~180 KB
 *   RAM: ~150 KB
 *
 * Supports all AURA compression methods:
 *   - BITPACKED (0x06) - 4-byte ultra-compressed
 *   - BITPACKED_SECURE (0x16) - 6-byte with CRC-8
 *   - BINARY_SEMANTIC (0x01) - Template-based
 *   - BRIO (0x03) - LZ77 + rANS
 *   - AURALITE (0x02) - Lightweight
 *   - UNCOMPRESSED (0xFF) - Passthrough
 */

#ifndef ESP32_AURA_DECODER_H
#define ESP32_AURA_DECODER_H

#include <Arduino.h>
#include "bitpacked_decoder.h"
#include "template_decoder.h"
#include "brio_decoder.h"
#include "auralite_decoder.h"

class ESP32AuraDecoder {
private:
    BitPackedDecoder bitpacked;
    TemplateDecoder templates;
    BrioDecoder brio;
    AuraliteDecoder auralite;

    static uint16_t crc16_ccitt_false(const uint8_t* data, size_t len) {
        uint16_t crc = 0xFFFF;
        for (size_t i = 0; i < len; i++) {
            crc ^= (uint16_t)data[i] << 8;
            for (int j = 0; j < 8; j++) {
                if (crc & 0x8000) {
                    crc = (crc << 1) ^ 0x1021;
                } else {
                    crc <<= 1;
                }
            }
        }
        return crc;
    }

public:
    ESP32AuraDecoder() {}

    // Initialize decoder (loads template library from SPIFFS)
    bool begin() {
        Serial.println("Initializing ESP32 AURA Decoder...");

        // Load AI Safety templates (128-2127) from filesystem
        if(!templates.loadAISafetyTemplates()) {
            Serial.println("ERROR: Failed to load template library");
            return false;
        }

        Serial.printf("✓ Loaded %d AI Safety templates\n", templates.getTemplateCount());
        Serial.println("✓ AURA Decoder ready");
        return true;
    }

    // Decode any AURA message to human-readable text
    bool decode(const uint8_t* data, size_t len, char* output, size_t out_len) {
        if(len < 1) {
            Serial.println("ERROR: Empty message");
            return false;
        }

        uint8_t method_byte = data[0];

        // Envelope with CRC16 (CCITT-FALSE): [0xE0][inner_method][payload...][CRC16_be]
        if (method_byte == 0xE0) {
            if (len < 4) {
                Serial.println("ERROR: Envelope too short");
                return false;
            }
            uint16_t expected = (uint16_t)(data[len-2] << 8) | (uint16_t)(data[len-1]);
            uint16_t actual = crc16_ccitt_false(data + 1, len - 3);
            if (expected != actual) {
                Serial.println("ERROR: Envelope CRC16 mismatch");
                return false;
            }
            uint8_t inner_method = data[1];
            size_t inner_len = len - 3; // includes inner_method + payload
            if (inner_len > 1024) {
                Serial.println("ERROR: Envelope inner frame too large (>1024)");
                return false;
            }
            uint8_t frame[1024];
            frame[0] = inner_method;
            memcpy(frame + 1, data + 2, inner_len - 1);
            // Route as if it were a normal frame
            switch(inner_method) {
                case 0x06:  // BITPACKED
                    Serial.println("Decoder: ENVELOPE→BITPACKED");
                    return bitpacked.decompress(frame, inner_len, output, out_len);
                case 0x16:  // BITPACKED_SECURE
                    Serial.println("Decoder: ENVELOPE→BITPACKED_SECURE");
                    return bitpacked.decompress_secure(frame, inner_len, output, out_len);
                case 0x01:  // BINARY_SEMANTIC
                    Serial.println("Decoder: ENVELOPE→BINARY_SEMANTIC");
                    return templates.decompress(frame, inner_len, output, out_len);
                case 0x03:  // BRIO
                    Serial.println("Decoder: ENVELOPE→BRIO");
                    return brio.decompress(frame, inner_len, output, out_len);
                case 0x02:  // AURALITE
                    Serial.println("Decoder: ENVELOPE→AURALITE");
                    return auralite.decompress(frame, inner_len, output, out_len);
                case 0xFF:  // UNCOMPRESSED
                    Serial.println("Decoder: ENVELOPE→UNCOMPRESSED");
                    if(inner_len - 1 >= out_len) { Serial.println("ERROR: Output buffer too small"); return false; }
                    memcpy(output, frame + 1, inner_len - 1);
                    output[inner_len - 1] = '\0';
                    return true;
                default:
                    Serial.printf("ERROR: Envelope inner method unknown: 0x%02X\n", inner_method);
                    return false;
            }
        }

        // Route to appropriate decoder based on method byte
        switch(method_byte) {
            case 0x06:  // BITPACKED (4 bytes)
                Serial.println("Decoder: BITPACKED (4 bytes)");
                return bitpacked.decompress(data, len, output, out_len);

            case 0x16:  // BITPACKED_SECURE (6 bytes with CRC-8)
                Serial.println("Decoder: BITPACKED_SECURE (6 bytes)");
                return bitpacked.decompress_secure(data, len, output, out_len);

            case 0x01:  // BINARY_SEMANTIC (template-based)
                Serial.println("Decoder: BINARY_SEMANTIC (templates)");
                return templates.decompress(data, len, output, out_len);

            case 0x03:  // BRIO (LZ77 + rANS)
                Serial.println("Decoder: BRIO (LZ77)");
                return brio.decompress(data, len, output, out_len);

            case 0x02:  // AURALITE (lightweight)
                Serial.println("Decoder: AURALITE");
                return auralite.decompress(data, len, output, out_len);

            case 0xFF:  // UNCOMPRESSED
                Serial.println("Decoder: UNCOMPRESSED");
                if(len - 1 >= out_len) {
                    Serial.println("ERROR: Output buffer too small");
                    return false;
                }
                memcpy(output, data + 1, len - 1);
                output[len - 1] = '\0';
                return true;

            default:
                Serial.printf("ERROR: Unknown method byte: 0x%02X\n", method_byte);
                return false;
        }
    }

    // Verify message integrity (CRC/checksum if present)
    bool verify(const uint8_t* data, size_t len) {
        if(len < 1) return false;

        uint8_t method_byte = data[0];

        // Envelope integrity check
        if (method_byte == 0xE0) {
            if (len < 4) return false;
            uint16_t expected = (uint16_t)(data[len-2] << 8) | (uint16_t)(data[len-1]);
            uint16_t actual = crc16_ccitt_false(data + 1, len - 3);
            if (expected != actual) return false;
            // Optionally chain to inner verify when inner is secure bitpacked
            uint8_t inner_method = data[1];
            if (inner_method == 0x16) {
                size_t inner_len = len - 3;
                if (inner_len > 1024) return false;
                uint8_t frame[1024];
                frame[0] = inner_method;
                memcpy(frame + 1, data + 2, inner_len - 1);
                return bitpacked.verify_crc(frame, inner_len);
            }
            return true;
        }

        // Only BITPACKED_SECURE has built-in integrity check
        if(method_byte == 0x16) {
            return bitpacked.verify_crc(data, len);
        }

        // Other methods: assume valid (rely on transport layer or external verification)
        return true;
    }

    // Get decoder statistics
    void getStats(char* output, size_t out_len) {
        snprintf(output, out_len,
            "ESP32 AURA Decoder v1.0\n"
            "Flash used: ~180 KB\n"
            "RAM used: ~150 KB\n"
            "Templates loaded: %d\n"
            "Methods supported: 7\n"
            "  - BITPACKED (0x06)\n"
            "  - BITPACKED_SECURE (0x16)\n"
            "  - BINARY_SEMANTIC (0x01)\n"
            "  - BRIO (0x03)\n"
            "  - AURALITE (0x02)\n"
            "  - UNCOMPRESSED (0xFF)\n"
            "  - ENVELOPE_CRC16 (0xE0)\n",
            templates.getTemplateCount()
        );
    }

    // Decode and display message (for debugging)
    void decodeAndDisplay(const uint8_t* data, size_t len) {
        char decoded[512];

        Serial.println("================================================================================");
        Serial.println("AURA MESSAGE DECODE");
        Serial.println("================================================================================");
        Serial.printf("Compressed size: %zu bytes\n", len);
        Serial.printf("Method byte: 0x%02X\n", data[0]);
        Serial.println();

        // Verify integrity
        bool integrity_ok = verify(data, len);
        Serial.printf("Integrity check: %s\n", integrity_ok ? "✓ PASS" : "✗ FAIL");

        if(!integrity_ok) {
            Serial.println("ERROR: Integrity check failed - message may be corrupted");
            Serial.println("================================================================================");
            return;
        }

        // Decode message
        if(decode(data, len, decoded, sizeof(decoded))) {
            Serial.println();
            Serial.println("Decoded message:");
            Serial.println(decoded);
            Serial.println();
            Serial.println("✓ Decode successful");
        } else {
            Serial.println();
            Serial.println("✗ Decode failed");
        }

        Serial.println("================================================================================");
    }
};

#endif
