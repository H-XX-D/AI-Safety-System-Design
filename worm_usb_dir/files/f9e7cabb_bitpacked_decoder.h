/*
 * BitPacked Decoder for ESP32
 *
 * Decodes 4-byte and 6-byte ultra-compressed messages.
 *
 * Standard format (4 bytes):
 *   Byte 0: 0x06 (method identifier)
 *   Byte 1: Control byte [MsgType:3][Action:2][Confidence:2][Risk:1]
 *   Byte 2: Proposal ID (0-255)
 *   Byte 3: System IDs [FromSystem:4][ToSystem:4]
 *
 * Secure format (6 bytes):
 *   Bytes 0-3: Same as standard
 *   Byte 4: Sequence number (0-255)
 *   Byte 5: CRC-8 checksum
 */

#ifndef BITPACKED_DECODER_H
#define BITPACKED_DECODER_H

#include <Arduino.h>

// Enums matching Python implementation
enum BitPackedMessageType {
    APPROVAL = 0b001,
    REJECTION = 0b010,
    REVIEW = 0b011,
    VOTE = 0b100,
    ALERT = 0b101,
    STATUS = 0b110
};

enum BitPackedAction {
    APPROVE = 0b00,
    REJECT = 0b01,
    ABSTAIN = 0b10,
    ESCALATE = 0b11
};

enum BitPackedConfidence {
    LOW = 0b00,      // < 50%
    MEDIUM = 0b01,   // 50-75%
    HIGH = 0b10,     // 75-95%
    MAXIMUM = 0b11   // 95%+
};

enum BitPackedRisk {
    NO_RISK = 0b0,
    HAS_RISK = 0b1
};

class BitPackedDecoder {
private:
    static const uint8_t METHOD_BYTE = 0x06;
    static const uint8_t SECURE_METHOD_BYTE = 0x16;
    int last_sequence_by_sender[16]; // -1 means unseen

    // CRC-8 computation (polynomial 0xD5)
    static uint8_t crc8(const uint8_t* data, size_t len) {
        uint8_t crc = 0;
        for(size_t i = 0; i < len; i++) {
            crc ^= data[i];
            for(int j = 0; j < 8; j++) {
                if(crc & 0x80) {
                    crc = ((crc << 1) ^ 0xD5) & 0xFF;
                } else {
                    crc = (crc << 1) & 0xFF;
                }
            }
        }
        return crc;
    }

    // Decode message type to string
    const char* decode_message_type(uint8_t msg_type) {
        switch(msg_type) {
            case APPROVAL: return "approval";
            case REJECTION: return "rejection";
            case REVIEW: return "review";
            case VOTE: return "vote";
            case ALERT: return "alert";
            case STATUS: return "status";
            default: return "unknown";
        }
    }

    // Decode action to string (considers message type)
    const char* decode_action(uint8_t action, uint8_t msg_type) {
        // For reviews, use "reviews" instead of "approves"
        if(msg_type == REVIEW) {
            return "reviews";
        }

        switch(action) {
            case APPROVE: return "approves";
            case REJECT: return "rejects";
            case ABSTAIN: return "abstains on";
            case ESCALATE: return "escalates";
            default: return "unknown";
        }
    }

    // Decode confidence to string
    const char* decode_confidence(uint8_t confidence) {
        switch(confidence) {
            case LOW: return "low";
            case MEDIUM: return "medium";
            case HIGH: return "high";
            case MAXIMUM: return "maximum";
            default: return "unknown";
        }
    }

    // Decode risk to string
    const char* decode_risk(uint8_t risk) {
        return (risk == HAS_RISK) ? "has risk" : "no risk";
    }

public:
    BitPackedDecoder() {
        for (int i = 0; i < 16; i++) {
            last_sequence_by_sender[i] = -1;
        }
    }
    // Decompress standard 4-byte format
    bool decompress(const uint8_t* data, size_t len, char* output, size_t out_len) {
        if(len < 4 || data[0] != METHOD_BYTE) {
            return false;
        }

        uint8_t control_byte = data[1];
        uint8_t proposal_id = data[2];
        uint8_t system_ids = data[3];

        // Extract bit fields
        uint8_t msg_type = (control_byte >> 5) & 0b111;
        uint8_t action = (control_byte >> 3) & 0b11;
        uint8_t confidence = (control_byte >> 1) & 0b11;
        uint8_t risk = control_byte & 0b1;
        uint8_t from_sys = (system_ids >> 4) & 0xF;
        uint8_t to_sys = system_ids & 0xF;

        // Build message
        int pos = snprintf(output, out_len, "System %d %s proposal %03d",
                          from_sys,
                          decode_action(action, msg_type),
                          proposal_id);

        // Add confidence if not medium
        if(confidence != MEDIUM) {
            pos += snprintf(output + pos, out_len - pos, " with %s confidence",
                           decode_confidence(confidence));
        }

        // Add risk indicator
        if(risk == HAS_RISK) {
            pos += snprintf(output + pos, out_len - pos, " (has risk)");
        }

        return true;
    }

    // Decompress secure 6-byte format (with CRC verification)
    bool decompress_secure(const uint8_t* data, size_t len, char* output, size_t out_len) {
        if(len != 6 || data[0] != SECURE_METHOD_BYTE) {
            return false;
        }

        // Verify CRC
        uint8_t crc_expected = data[5];
        uint8_t crc_actual = crc8(data, 5);

        if(crc_actual != crc_expected) {
            Serial.printf("CRC mismatch: expected 0x%02X, got 0x%02X\n", crc_expected, crc_actual);
            return false;
        }

        // Decode same as standard (bytes 0-3)
        uint8_t control_byte = data[1];
        uint8_t proposal_id = data[2];
        uint8_t system_ids = data[3];
    uint8_t sequence = data[4];

        // Extract bit fields
        uint8_t msg_type = (control_byte >> 5) & 0b111;
        uint8_t action = (control_byte >> 3) & 0b11;
        uint8_t confidence = (control_byte >> 1) & 0b11;
        uint8_t risk = control_byte & 0b1;
        uint8_t from_sys = (system_ids >> 4) & 0xF;
        uint8_t to_sys = system_ids & 0xF;

        // Sequence tracking (replay / ordering warnings)
        int last = last_sequence_by_sender[from_sys & 0xF];
        bool replay = (last >= 0 && ((uint8_t)last) == sequence);
        bool seq_ok = (last < 0) || ((((uint8_t)last) + 1) == sequence);
        last_sequence_by_sender[from_sys & 0xF] = (int)sequence;
        if (replay) {
            Serial.println("WARN: Replay detected (same sequence as last)");
        } else if (!seq_ok) {
            Serial.println("WARN: Non-monotonic sequence (possible drop or reordering)");
        }

        // Build message
        int pos = snprintf(output, out_len, "System %d %s proposal %03d",
                          from_sys,
                          decode_action(action, msg_type),
                          proposal_id);

        if(confidence != MEDIUM) {
            pos += snprintf(output + pos, out_len - pos, " with %s confidence",
                           decode_confidence(confidence));
        }

        if(risk == HAS_RISK) {
            pos += snprintf(output + pos, out_len - pos, " (has risk)");
        }

        return true;
    }

    // Verify CRC of secure message
    bool verify_crc(const uint8_t* data, size_t len) {
        if(len != 6 || data[0] != SECURE_METHOD_BYTE) {
            return false;
        }

        uint8_t crc_expected = data[5];
        uint8_t crc_actual = crc8(data, 5);

        return (crc_actual == crc_expected);
    }
};

#endif
