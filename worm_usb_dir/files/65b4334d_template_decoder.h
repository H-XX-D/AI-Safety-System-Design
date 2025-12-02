/*
 * Template Decoder for ESP32
 *
 * Decodes BINARY_SEMANTIC (template-based) AURA messages.
 *
 * Format:
 *   Byte 0: 0x01 (method identifier)
 *   Bytes 1-2: Template ID (uint16, big-endian)
 *   Bytes 3+: Slot values (null-terminated strings)
 *
 * Requires template library file on SPIFFS: /templates_ai_safety.bin
 */

#ifndef TEMPLATE_DECODER_H
#define TEMPLATE_DECODER_H

#include <Arduino.h>
#include <FS.h>
#include <SPIFFS.h>

// Template structure (matches Python export format)
struct Template {
    uint16_t id;
    char format[128];  // e.g. "System {0} approves proposal {1}"
};

class TemplateDecoder {
private:
    Template* templates;
    uint16_t template_count;

    // Find template by ID
    Template* findTemplate(uint16_t id) {
        for(uint16_t i = 0; i < template_count; i++) {
            if(templates[i].id == id) {
                return &templates[i];
            }
        }
        return nullptr;
    }

    // Fill template with slot values
    void fillTemplate(const char* format, char slot_values[][64], int slot_count,
                      char* output, size_t out_len) {
        size_t out_pos = 0;

        for(size_t i = 0; format[i] != '\0' && out_pos < out_len - 1; i++) {
            // Check for slot placeholder {N}
            if(format[i] == '{' && i + 2 < strlen(format) && format[i+2] == '}') {
                // Extract slot number
                int slot_num = format[i+1] - '0';

                if(slot_num >= 0 && slot_num < slot_count) {
                    // Insert slot value
                    size_t slot_len = strlen(slot_values[slot_num]);
                    if(out_pos + slot_len < out_len - 1) {
                        strcpy(output + out_pos, slot_values[slot_num]);
                        out_pos += slot_len;
                    }
                    i += 2;  // Skip {X}
                    continue;
                }
            }

            // Copy literal character
            output[out_pos++] = format[i];
        }

        output[out_pos] = '\0';
    }

public:
    TemplateDecoder() : templates(nullptr), template_count(0) {}

    ~TemplateDecoder() {
        if(templates) {
            delete[] templates;
        }
    }

    // Load AI Safety templates (128-2127) from SPIFFS
    bool loadAISafetyTemplates() {
        File file = SPIFFS.open("/templates_ai_safety.bin", "r");
        if(!file) {
            Serial.println("ERROR: Cannot open /templates_ai_safety.bin");
            Serial.println("Make sure template library is uploaded to SPIFFS");
            return false;
        }

        // Read template count
        file.read((uint8_t*)&template_count, sizeof(uint16_t));
        Serial.printf("Loading %d templates...\n", template_count);

        // Allocate memory
        templates = new Template[template_count];
        if(!templates) {
            Serial.println("ERROR: Cannot allocate template memory");
            file.close();
            return false;
        }

        // Read templates
        for(uint16_t i = 0; i < template_count; i++) {
            file.read((uint8_t*)&templates[i], sizeof(Template));
        }

        file.close();
        Serial.printf("✓ Loaded %d AI Safety templates\n", template_count);
        return true;
    }

    // Decompress BINARY_SEMANTIC message
    bool decompress(const uint8_t* data, size_t len, char* output, size_t out_len) {
        if(len < 3) {
            Serial.println("ERROR: BINARY_SEMANTIC message too short");
            return false;
        }

        if(data[0] != 0x01) {
            Serial.println("ERROR: Not a BINARY_SEMANTIC message");
            return false;
        }

        // Extract template ID (big-endian)
        uint16_t template_id = (data[1] << 8) | data[2];

        // Find template
        Template* tmpl = findTemplate(template_id);
        if(!tmpl) {
            Serial.printf("ERROR: Template %d not found\n", template_id);
            return false;
        }

        // Extract slot values (null-terminated strings)
        const uint8_t* slot_data = data + 3;
        size_t slot_len = len - 3;

        char slot_values[4][64];  // Support up to 4 slots
        int slot_count = 0;

        size_t offset = 0;
        while(offset < slot_len && slot_count < 4) {
            size_t str_len = strlen((char*)(slot_data + offset));
            if(str_len == 0) break;

            strncpy(slot_values[slot_count], (char*)(slot_data + offset), 63);
            slot_values[slot_count][63] = '\0';

            offset += str_len + 1;  // Skip null terminator
            slot_count++;
        }

        // Fill template
        fillTemplate(tmpl->format, slot_values, slot_count, output, out_len);
        return true;
    }

    // Get number of loaded templates
    uint16_t getTemplateCount() const {
        return template_count;
    }
};

#endif
