/*
 * BitPacked decoder adapted for ESP-IDF (C++ header)
 * Source: adapted from worm_usb_dir files
 */

#ifndef BITPACKED_DECODER_H
#define BITPACKED_DECODER_H

#include <stdio.h>
#include <stdint.h>
#include <string.h>

enum BitPackedMessageType {
    BP_APPROVAL = 0b001,
    BP_REJECTION = 0b010,
    BP_REVIEW = 0b011,
    BP_VOTE = 0b100,
    BP_ALERT = 0b101,
    BP_STATUS = 0b110
};

enum BitPackedAction { BP_APPROVE = 0b00, BP_REJECT = 0b01, BP_ABSTAIN = 0b10, BP_ESCALATE = 0b11 };
enum BitPackedConfidence { BP_LOW = 0b00, BP_MEDIUM = 0b01, BP_HIGH = 0b10, BP_MAXIMUM = 0b11 };
enum BitPackedRisk { BP_NO_RISK = 0, BP_HAS_RISK = 1 };

class BitPackedDecoder {
public:
    static const uint8_t METHOD_BYTE = 0x06;
    static const uint8_t SECURE_METHOD_BYTE = 0x16;

    static uint8_t crc8(const uint8_t* data, size_t len) {
        uint8_t crc = 0;
        for(size_t i = 0; i < len; ++i) {
            crc ^= data[i];
            for(int j = 0; j < 8; ++j) {
                if(crc & 0x80) crc = ((crc << 1) ^ 0xD5) & 0xFF;
                else crc = (crc << 1) & 0xFF;
            }
        }
        return crc;
    }

    const char* decode_action(uint8_t action, uint8_t msg_type) {
        if(msg_type == BP_REVIEW) return "reviews";
        switch(action) {
            case BP_APPROVE: return "approves";
            case BP_REJECT: return "rejects";
            case BP_ABSTAIN: return "abstains on";
            case BP_ESCALATE: return "escalates";
            default: return "unknown";
        }
    }

    const char* decode_confidence(uint8_t confidence) {
        switch(confidence) {
            case BP_LOW: return "low";
            case BP_MEDIUM: return "medium";
            case BP_HIGH: return "high";
            case BP_MAXIMUM: return "maximum";
            default: return "unknown";
        }
    }

    bool decompress(const uint8_t* data, size_t len, char* output, size_t out_len) {
        if(len < 4 || data[0] != METHOD_BYTE) return false;
        uint8_t control_byte = data[1];
        uint8_t proposal_id = data[2];
        uint8_t system_ids = data[3];
        uint8_t msg_type = (control_byte >> 5) & 0b111;
        uint8_t action = (control_byte >> 3) & 0b11;
        uint8_t confidence = (control_byte >> 1) & 0b11;
        uint8_t risk = control_byte & 0b1;
        uint8_t from_sys = (system_ids >> 4) & 0xF;
        int pos = snprintf(output, out_len, "System %d %s proposal %03d",
                          from_sys, decode_action(action, msg_type), proposal_id);
        if(confidence != BP_MEDIUM) {
            pos += snprintf(output + pos, out_len - pos, " with %s confidence", decode_confidence(confidence));
        }
        if(risk == BP_HAS_RISK) {
            pos += snprintf(output + pos, out_len - pos, " (has risk)");
        }
        return true;
    }

    bool decompress_secure(const uint8_t* data, size_t len, char* output, size_t out_len) {
        if(len != 6 || data[0] != SECURE_METHOD_BYTE) return false;
        uint8_t crc_expected = data[5];
        uint8_t crc_actual = crc8(data, 5);
        if(crc_actual != crc_expected) {
            printf("CRC mismatch: expected 0x%02X, got 0x%02X\n", crc_expected, crc_actual);
            return false;
        }
        uint8_t control_byte = data[1];
        uint8_t proposal_id = data[2];
        uint8_t system_ids = data[3];
        uint8_t sequence = data[4]; (void)sequence;
        uint8_t msg_type = (control_byte >> 5) & 0b111;
        uint8_t action = (control_byte >> 3) & 0b11;
        uint8_t confidence = (control_byte >> 1) & 0b11;
        uint8_t risk = control_byte & 0b1;
        uint8_t from_sys = (system_ids >> 4) & 0xF;
        int pos = snprintf(output, out_len, "System %d %s proposal %03d",
                          from_sys, decode_action(action, msg_type), proposal_id);
        if(confidence != BP_MEDIUM) {
            pos += snprintf(output + pos, out_len - pos, " with %s confidence", decode_confidence(confidence));
        }
        if(risk == BP_HAS_RISK) {
            pos += snprintf(output + pos, out_len - pos, " (has risk)");
        }
        return true;
    }

    bool verify_crc(const uint8_t* data, size_t len) {
        if(len != 6 || data[0] != SECURE_METHOD_BYTE) return false;
        uint8_t crc_expect = data[5];
        uint8_t crc_act = crc8(data, 5);
        return crc_expect == crc_act;
    }
};

#endif

