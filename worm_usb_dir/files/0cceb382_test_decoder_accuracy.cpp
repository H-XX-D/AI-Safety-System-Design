/*
 * ESP32 AURA Decoder Accuracy Test
 *
 * Verifies that ESP32 C++ decoder produces IDENTICAL output to Python AURA.
 *
 * Compile: g++ -std=c++11 test_decoder_accuracy.cpp -o test_decoder_accuracy
 * Run: ./test_decoder_accuracy
 */

#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cstdarg>

// CRC-8 computation (matches Python implementation)
uint8_t crc8(const uint8_t* data, size_t len) {
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

// Bit-packed decoder (standalone, no Arduino deps)
class BitPackedDecoder {
private:
    // Decode action to string
    const char* decode_action(uint8_t action, uint8_t msg_type) {
        // For reviews (msg_type=3), use "reviews"
        if(msg_type == 3) {  // REVIEW = 0b011
            return "reviews";
        }

        switch(action) {
            case 0: return "approves";  // APPROVE
            case 1: return "rejects";   // REJECT
            case 2: return "abstains on";  // ABSTAIN
            case 3: return "escalates";  // ESCALATE
            default: return "unknown";
        }
    }

    const char* decode_confidence(uint8_t confidence) {
        switch(confidence) {
            case 0: return "low";
            case 1: return "medium";
            case 2: return "high";
            case 3: return "maximum";
            default: return "unknown";
        }
    }

public:
    bool decompress(const uint8_t* data, size_t len, char* output, size_t out_len) {
        if(len < 4 || data[0] != 0x06) {
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
        if(confidence != 1) {  // MEDIUM = 0b01
            pos += snprintf(output + pos, out_len - pos, " with %s confidence",
                           decode_confidence(confidence));
        }

        // Add risk indicator
        if(risk == 1) {  // HAS_RISK = 0b1
            pos += snprintf(output + pos, out_len - pos, " (has risk)");
        }

        return true;
    }

    bool decompress_secure(const uint8_t* data, size_t len, char* output, size_t out_len) {
        if(len != 6 || data[0] != 0x16) {
            return false;
        }

        // Verify CRC
        uint8_t crc_expected = data[5];
        uint8_t crc_actual = crc8(data, 5);

        if(crc_actual != crc_expected) {
            printf("  CRC mismatch: expected 0x%02X, got 0x%02X\n", crc_expected, crc_actual);
            return false;
        }

        // Decode same as standard (bytes 0-3)
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

        if(confidence != 1) {
            pos += snprintf(output + pos, out_len - pos, " with %s confidence",
                           decode_confidence(confidence));
        }

        if(risk == 1) {
            pos += snprintf(output + pos, out_len - pos, " (has risk)");
        }

        return true;
    }
};

// Test cases from Python AURA
struct TestCase {
    const char* name;
    const uint8_t* data;
    size_t len;
    const char* expected;
};

// Test data (from Python AURA output)
const uint8_t test1[] = {0x06, 0x22, 0x2A, 0x16};
const uint8_t test2[] = {0x06, 0x4A, 0x2B, 0x26};
const uint8_t test3[] = {0x06, 0x64, 0x01, 0x36};
const uint8_t test4[] = {0x16, 0x22, 0x2A, 0x16, 0x00, 0x73};
const uint8_t test5[] = {0x16, 0x4A, 0x2B, 0x26, 0x00, 0xEC};

TestCase test_cases[] = {
    {
        "BITPACKED: System 1 approves proposal 042",
        test1, sizeof(test1),
        "System 1 approves proposal 042"
    },
    {
        "BITPACKED: System 2 rejects proposal 043",
        test2, sizeof(test2),
        "System 2 rejects proposal 043"
    },
    {
        "BITPACKED: System 3 reviews proposal 001 with high confidence",
        test3, sizeof(test3),
        "System 3 reviews proposal 001 with high confidence"
    },
    {
        "BITPACKED_SECURE: System 1 approves proposal 042",
        test4, sizeof(test4),
        "System 1 approves proposal 042"
    },
    {
        "BITPACKED_SECURE: System 2 rejects proposal 043",
        test5, sizeof(test5),
        "System 2 rejects proposal 043"
    },
};

int main() {
    printf("================================================================================\n");
    printf("ESP32 AURA Decoder Accuracy Test\n");
    printf("Verifying C++ decoder matches Python AURA exactly\n");
    printf("================================================================================\n\n");

    BitPackedDecoder decoder;
    int passed = 0;
    int failed = 0;

    for(size_t i = 0; i < sizeof(test_cases) / sizeof(TestCase); i++) {
        TestCase& tc = test_cases[i];

        printf("Test %zu: %s\n", i + 1, tc.name);
        printf("  Input hex: ");
        for(size_t j = 0; j < tc.len; j++) {
            printf("%02X ", tc.data[j]);
        }
        printf("\n");

        char output[256];
        bool result;

        // Choose decoder based on method byte
        if(tc.data[0] == 0x06) {
            result = decoder.decompress(tc.data, tc.len, output, sizeof(output));
        } else if(tc.data[0] == 0x16) {
            result = decoder.decompress_secure(tc.data, tc.len, output, sizeof(output));
        } else {
            printf("  ERROR: Unknown method byte 0x%02X\n", tc.data[0]);
            failed++;
            continue;
        }

        if(!result) {
            printf("  ERROR: Decompression failed\n");
            failed++;
            continue;
        }

        printf("  Decoded: %s\n", output);
        printf("  Expected: %s\n", tc.expected);

        bool match = strcmp(output, tc.expected) == 0;
        printf("  Result: %s\n", match ? "✓ PASS" : "✗ FAIL");

        if(match) {
            passed++;
        } else {
            failed++;
            printf("  ERROR: Output mismatch!\n");
        }

        printf("\n");
    }

    printf("================================================================================\n");
    printf("Test Results:\n");
    printf("  Passed: %d\n", passed);
    printf("  Failed: %d\n", failed);
    printf("  Total: %zu\n", sizeof(test_cases) / sizeof(TestCase));
    printf("================================================================================\n");

    if(failed == 0) {
        printf("\n✓ ALL TESTS PASSED - ESP32 decoder is ACCURATE\n\n");
        return 0;
    } else {
        printf("\n✗ SOME TESTS FAILED - Decoder needs fixes\n\n");
        return 1;
    }
}
