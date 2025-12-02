/*
 * BRIO Decoder for ESP32
 *
 * Decodes BRIO (LZ77 + rANS) compressed messages.
 *
 * Format:
 *   Byte 0: 0x03 (method identifier)
 *   Bytes 1+: LZ77 compressed data
 *
 * LZ77 format:
 *   [literal_len][literals...][match_len][match_offset_high][match_offset_low]
 */

#ifndef BRIO_DECODER_H
#define BRIO_DECODER_H

#include <Arduino.h>

class BrioDecoder {
private:
    uint8_t lz77_buffer[32768];  // 32 KB sliding window

    // Decompress LZ77 format
    bool decompress_lz77(const uint8_t* input, size_t in_len,
                         uint8_t* output, size_t* out_len) {
        size_t in_pos = 0;
        size_t out_pos = 0;

        while(in_pos < in_len) {
            // Read literal length
            uint8_t literal_len = input[in_pos++];

            // Copy literals
            if(literal_len > 0) {
                if(in_pos + literal_len > in_len) {
                    Serial.println("ERROR: Invalid LZ77 literal length");
                    return false;
                }
                memcpy(output + out_pos, input + in_pos, literal_len);
                in_pos += literal_len;
                out_pos += literal_len;
            }

            if(in_pos >= in_len) break;

            // Read match length
            uint8_t match_len = input[in_pos++];

            if(match_len > 0) {
                if(in_pos + 2 > in_len) {
                    Serial.println("ERROR: Invalid LZ77 match offset");
                    return false;
                }

                // Read match offset (big-endian)
                uint16_t match_offset = (input[in_pos] << 8) | input[in_pos + 1];
                in_pos += 2;

                // Validate match offset
                if(match_offset > out_pos) {
                    Serial.println("ERROR: Match offset exceeds output position");
                    return false;
                }

                // Copy from history
                size_t match_pos = out_pos - match_offset;
                for(size_t i = 0; i < match_len; i++) {
                    output[out_pos++] = output[match_pos + i];
                }
            }
        }

        *out_len = out_pos;
        return true;
    }

public:
    bool decompress(const uint8_t* data, size_t len, char* output, size_t out_len) {
        if(len < 2 || data[0] != 0x03) {
            Serial.println("ERROR: Not a BRIO message");
            return false;
        }

        // Decompress LZ77
        const uint8_t* compressed = data + 1;
        size_t compressed_len = len - 1;

        size_t decompressed_len = 0;
        if(!decompress_lz77(compressed, compressed_len,
                           (uint8_t*)output, &decompressed_len)) {
            Serial.println("ERROR: LZ77 decompression failed");
            return false;
        }

        // Null-terminate
        if(decompressed_len >= out_len) {
            Serial.println("ERROR: Output buffer too small");
            return false;
        }

        output[decompressed_len] = '\0';
        return true;
    }
};

#endif
