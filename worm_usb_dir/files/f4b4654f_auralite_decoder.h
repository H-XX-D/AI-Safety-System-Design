/*
 * AURALITE Decoder for ESP32
 *
 * Decodes AURALITE (lightweight) compressed messages.
 *
 * Format:
 *   Byte 0: 0x02 (method identifier)
 *   Bytes 1+: Run-length encoded data
 *
 * RLE format:
 *   < 0x80: Literal byte
 *   >= 0x80: Run-length (repeat next byte N-0x80 times)
 */

#ifndef AURALITE_DECODER_H
#define AURALITE_DECODER_H

#include <Arduino.h>

class AuraliteDecoder {
public:
    bool decompress(const uint8_t* data, size_t len, char* output, size_t out_len) {
        if(len < 2 || data[0] != 0x02) {
            Serial.println("ERROR: Not an AURALITE message");
            return false;
        }

        const uint8_t* input = data + 1;
        size_t in_len = len - 1;
        size_t out_pos = 0;

        for(size_t i = 0; i < in_len && out_pos < out_len - 1; ) {
            uint8_t byte = input[i++];

            if(byte < 0x80) {
                // Literal byte
                output[out_pos++] = byte;
            } else {
                // Run-length encoding
                uint8_t count = byte - 0x80;

                if(i >= in_len) {
                    Serial.println("ERROR: RLE missing value byte");
                    return false;
                }

                uint8_t value = input[i++];

                // Repeat value 'count' times
                for(uint8_t j = 0; j < count && out_pos < out_len - 1; j++) {
                    output[out_pos++] = value;
                }
            }
        }

        // Null-terminate
        output[out_pos] = '\0';
        return true;
    }
};

#endif
