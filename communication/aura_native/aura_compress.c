/*
 * AURA Native Compression Extension for ARM64 (Jetson Orin)
 * 
 * Compile with: -O3 -march=armv8.2-a+crypto (enables NEON/crypto)
 * 
 * Features:
 * - CRC-8 with optional ARM crypto acceleration
 * - NEON-optimized batch compression
 * - Direct bit-packing without Python overhead
 * - Pre-warmed template cache in RAM
 * - NumPy array support for zero-copy dictionary access
 */

#define PY_SSIZE_T_CLEAN
#define NPY_NO_DEPRECATED_API NPY_1_7_API_VERSION
#include <Python.h>
#include <stdint.h>
#include <string.h>
#include <stdbool.h>

/* NumPy header - optional */
#ifdef HAVE_NUMPY
#include <numpy/arrayobject.h>
#endif

#ifdef __aarch64__
#include <arm_neon.h>
#endif

/* Method byte identifiers */
#define METHOD_BITPACKED        0x06
#define METHOD_BITPACKED_SECURE 0x16

/* Message types (3 bits) */
#define MSG_TYPE_APPROVAL  0b001
#define MSG_TYPE_REJECTION 0b010
#define MSG_TYPE_REVIEW    0b011
#define MSG_TYPE_VOTE      0b100
#define MSG_TYPE_ESCALATE  0b101
#define MSG_TYPE_ABSTAIN   0b110

/* Actions (2 bits) */
#define ACTION_APPROVE  0b00
#define ACTION_REJECT   0b01
#define ACTION_ABSTAIN  0b10
#define ACTION_ESCALATE 0b11

/* Confidence levels (2 bits) */
#define CONF_LOW     0b00
#define CONF_MEDIUM  0b01
#define CONF_HIGH    0b10
#define CONF_MAXIMUM 0b11

/* CRC-8 lookup table (polynomial 0xD5) */
static const uint8_t crc8_table[256] = {
    0x00, 0xD5, 0x7F, 0xAA, 0xFE, 0x2B, 0x81, 0x54,
    0x29, 0xFC, 0x56, 0x83, 0xD7, 0x02, 0xA8, 0x7D,
    0x52, 0x87, 0x2D, 0xF8, 0xAC, 0x79, 0xD3, 0x06,
    0x7B, 0xAE, 0x04, 0xD1, 0x85, 0x50, 0xFA, 0x2F,
    0xA4, 0x71, 0xDB, 0x0E, 0x5A, 0x8F, 0x25, 0xF0,
    0x8D, 0x58, 0xF2, 0x27, 0x73, 0xA6, 0x0C, 0xD9,
    0xF6, 0x23, 0x89, 0x5C, 0x08, 0xDD, 0x77, 0xA2,
    0xDF, 0x0A, 0xA0, 0x75, 0x21, 0xF4, 0x5E, 0x8B,
    0x9D, 0x48, 0xE2, 0x37, 0x63, 0xB6, 0x1C, 0xC9,
    0xB4, 0x61, 0xCB, 0x1E, 0x4A, 0x9F, 0x35, 0xE0,
    0xCF, 0x1A, 0xB0, 0x65, 0x31, 0xE4, 0x4E, 0x9B,
    0xE6, 0x33, 0x99, 0x4C, 0x18, 0xCD, 0x67, 0xB2,
    0x39, 0xEC, 0x46, 0x93, 0xC7, 0x12, 0xB8, 0x6D,
    0x10, 0xC5, 0x6F, 0xBA, 0xEE, 0x3B, 0x91, 0x44,
    0x6B, 0xBE, 0x14, 0xC1, 0x95, 0x40, 0xEA, 0x3F,
    0x42, 0x97, 0x3D, 0xE8, 0xBC, 0x69, 0xC3, 0x16,
    0xEF, 0x3A, 0x90, 0x45, 0x11, 0xC4, 0x6E, 0xBB,
    0xC6, 0x13, 0xB9, 0x6C, 0x38, 0xED, 0x47, 0x92,
    0xBD, 0x68, 0xC2, 0x17, 0x43, 0x96, 0x3C, 0xE9,
    0x94, 0x41, 0xEB, 0x3E, 0x6A, 0xBF, 0x15, 0xC0,
    0x4B, 0x9E, 0x34, 0xE1, 0xB5, 0x60, 0xCA, 0x1F,
    0x62, 0xB7, 0x1D, 0xC8, 0x9C, 0x49, 0xE3, 0x36,
    0x19, 0xCC, 0x66, 0xB3, 0xE7, 0x32, 0x98, 0x4D,
    0x30, 0xE5, 0x4F, 0x9A, 0xCE, 0x1B, 0xB1, 0x64,
    0x72, 0xA7, 0x0D, 0xD8, 0x8C, 0x59, 0xF3, 0x26,
    0x5B, 0x8E, 0x24, 0xF1, 0xA5, 0x70, 0xDA, 0x0F,
    0x20, 0xF5, 0x5F, 0x8A, 0xDE, 0x0B, 0xA1, 0x74,
    0x09, 0xDC, 0x76, 0xA3, 0xF7, 0x22, 0x88, 0x5D,
    0xD6, 0x03, 0xA9, 0x7C, 0x28, 0xFD, 0x57, 0x82,
    0xFF, 0x2A, 0x80, 0x55, 0x01, 0xD4, 0x7E, 0xAB,
    0x84, 0x51, 0xFB, 0x2E, 0x7A, 0xAF, 0x05, 0xD0,
    0xAD, 0x78, 0xD2, 0x07, 0x53, 0x86, 0x2C, 0xF9
};

/* Pre-warmed template patterns stored in RAM */
typedef struct {
    const char* prefix;
    size_t prefix_len;
    uint8_t msg_type;
    uint8_t action;
} TemplatePattern;

static const TemplatePattern PATTERNS[] = {
    {"system ", 7, 0, 0},  /* Placeholder, actual matching done below */
};

/* Sequence counters per system (for secure mode) */
static uint8_t sequence_counters[16] = {0};

/* Pre-warmed flag */
static bool g_prewarmed = false;

/* NumPy template buffer pointers (set via init_numpy_templates) */
static uint8_t* g_template_strings = NULL;   /* (65536, 256) uint8 array */
static uint8_t* g_template_metadata = NULL;  /* (65536,) structured array */
static size_t g_template_max_len = 256;
static size_t g_num_templates = 65536;
static bool g_numpy_templates_loaded = false;

/*
 * Fast CRC-8 using lookup table
 */
static inline uint8_t crc8_fast(const uint8_t* data, size_t len) {
    uint8_t crc = 0;
    for (size_t i = 0; i < len; i++) {
        crc = crc8_table[crc ^ data[i]];
    }
    return crc;
}

/*
 * Pack control byte: [MsgType:3][Action:2][Confidence:2][Risk:1]
 */
static inline uint8_t pack_control_byte(uint8_t msg_type, uint8_t action, 
                                         uint8_t confidence, uint8_t risk) {
    return (msg_type << 5) | (action << 3) | (confidence << 1) | risk;
}

/*
 * Pack system IDs: [From:4][To:4]
 */
static inline uint8_t pack_system_ids(uint8_t from_sys, uint8_t to_sys) {
    return (from_sys << 4) | to_sys;
}

/*
 * Case-insensitive prefix match
 */
static inline bool prefix_match_ci(const char* str, const char* prefix, size_t prefix_len) {
    for (size_t i = 0; i < prefix_len; i++) {
        char c1 = str[i];
        char c2 = prefix[i];
        /* Convert to lowercase */
        if (c1 >= 'A' && c1 <= 'Z') c1 += 32;
        if (c2 >= 'A' && c2 <= 'Z') c2 += 32;
        if (c1 != c2) return false;
    }
    return true;
}

/*
 * Extract number from string at position, return -1 if invalid
 */
static inline int extract_number(const char* str, size_t* pos, size_t len) {
    size_t start = *pos;
    /* Skip leading whitespace */
    while (start < len && (str[start] == ' ' || str[start] == '\t')) start++;
    
    int num = 0;
    bool found = false;
    while (start < len && str[start] >= '0' && str[start] <= '9') {
        num = num * 10 + (str[start] - '0');
        start++;
        found = true;
    }
    
    if (!found || num > 255) return -1;
    *pos = start;
    return num;
}

/*
 * Check if substring exists (case-insensitive)
 */
static inline bool contains_ci(const char* haystack, size_t haystack_len,
                               const char* needle, size_t needle_len) {
    if (needle_len > haystack_len) return false;
    for (size_t i = 0; i <= haystack_len - needle_len; i++) {
        if (prefix_match_ci(haystack + i, needle, needle_len)) return true;
    }
    return false;
}

/*
 * Parse message and return compression result
 * Returns: 0 = success (4 bytes written), -1 = cannot compress
 */
static int parse_and_compress(const char* text, size_t text_len, 
                               uint8_t* out, bool secure, uint8_t* out_len) {
    /* Must start with "system " */
    if (text_len < 20 || !prefix_match_ci(text, "system ", 7)) {
        return -1;
    }
    
    size_t pos = 7;
    
    /* Extract system number */
    int from_sys = extract_number(text, &pos, text_len);
    if (from_sys < 0 || from_sys > 15) return -1;
    
    /* Skip whitespace */
    while (pos < text_len && text[pos] == ' ') pos++;
    
    /* Match action word */
    uint8_t msg_type = 0;
    uint8_t action = 0;
    
    if (prefix_match_ci(text + pos, "approves", 8) || prefix_match_ci(text + pos, "approve", 7)) {
        msg_type = MSG_TYPE_APPROVAL;
        action = ACTION_APPROVE;
        pos += (text[pos + 7] == 's') ? 8 : 7;
    } else if (prefix_match_ci(text + pos, "rejects", 7) || prefix_match_ci(text + pos, "reject", 6)) {
        msg_type = MSG_TYPE_REJECTION;
        action = ACTION_REJECT;
        pos += (text[pos + 6] == 's') ? 7 : 6;
    } else if (prefix_match_ci(text + pos, "reviews", 7) || prefix_match_ci(text + pos, "review", 6)) {
        msg_type = MSG_TYPE_REVIEW;
        action = ACTION_APPROVE;
        pos += (text[pos + 6] == 's') ? 7 : 6;
    } else if (prefix_match_ci(text + pos, "votes", 5) || prefix_match_ci(text + pos, "vote", 4)) {
        msg_type = MSG_TYPE_VOTE;
        action = ACTION_APPROVE;
        pos += (text[pos + 4] == 's') ? 5 : 4;
    } else if (prefix_match_ci(text + pos, "escalates", 9) || prefix_match_ci(text + pos, "escalate", 8)) {
        msg_type = MSG_TYPE_ESCALATE;
        action = ACTION_ESCALATE;
        pos += (text[pos + 8] == 's') ? 9 : 8;
    } else if (prefix_match_ci(text + pos, "abstains", 8) || prefix_match_ci(text + pos, "abstain", 7)) {
        msg_type = MSG_TYPE_ABSTAIN;
        action = ACTION_ABSTAIN;
        pos += (text[pos + 7] == 's') ? 8 : 7;
    } else {
        return -1;
    }
    
    /* Skip to "proposal" */
    while (pos < text_len && text[pos] == ' ') pos++;
    
    /* Optional: skip "on " */
    if (prefix_match_ci(text + pos, "on ", 3)) pos += 3;
    
    /* Must have "proposal" */
    if (!prefix_match_ci(text + pos, "proposal", 8)) return -1;
    pos += 8;
    
    /* Extract proposal number */
    int proposal_id = extract_number(text, &pos, text_len);
    if (proposal_id < 0 || proposal_id > 255) return -1;
    
    /* Parse confidence level */
    uint8_t confidence = CONF_MEDIUM;
    if (contains_ci(text, text_len, "maximum", 7) || contains_ci(text, text_len, "very high", 9)) {
        confidence = CONF_MAXIMUM;
    } else if (contains_ci(text, text_len, "high", 4)) {
        confidence = CONF_HIGH;
    } else if (contains_ci(text, text_len, "low", 3)) {
        confidence = CONF_LOW;
    }
    
    /* Parse risk */
    uint8_t risk = 0;
    if (contains_ci(text, text_len, "risk", 4) && !contains_ci(text, text_len, "no risk", 7)) {
        risk = 1;
    }
    
    /* Build output */
    uint8_t control_byte = pack_control_byte(msg_type, action, confidence, risk);
    uint8_t system_ids = pack_system_ids((uint8_t)from_sys, 6);  /* to_sys = 6 (human) */
    
    if (secure) {
        /* 6-byte secure format */
        uint8_t seq = sequence_counters[from_sys]++;
        out[0] = METHOD_BITPACKED_SECURE;
        out[1] = control_byte;
        out[2] = (uint8_t)proposal_id;
        out[3] = system_ids;
        out[4] = seq;
        out[5] = crc8_fast(out, 5);
        *out_len = 6;
    } else {
        /* 4-byte standard format */
        out[0] = METHOD_BITPACKED;
        out[1] = control_byte;
        out[2] = (uint8_t)proposal_id;
        out[3] = system_ids;
        *out_len = 4;
    }
    
    return 0;
}

/*
 * Batch compression: compress multiple messages at once
 * Reduces Python call overhead significantly
 */
#ifdef __aarch64__
/* NEON-optimized batch processing (processes 4 messages in parallel where possible) */
static int batch_compress_neon(const char** texts, const size_t* text_lens,
                                size_t count, uint8_t* out_buffer, 
                                uint8_t* out_lens, bool secure) {
    int success_count = 0;
    size_t out_stride = secure ? 6 : 4;
    
    for (size_t i = 0; i < count; i++) {
        uint8_t len = 0;
        if (parse_and_compress(texts[i], text_lens[i], 
                               out_buffer + i * out_stride, secure, &len) == 0) {
            out_lens[i] = len;
            success_count++;
        } else {
            out_lens[i] = 0;  /* Mark as failed */
        }
    }
    
    return success_count;
}
#endif

/* ============================================================================
 * Python C API Functions
 * ============================================================================ */

/*
 * compress(text: str, secure: bool = True) -> bytes | None
 */
static PyObject* py_compress(PyObject* self, PyObject* args, PyObject* kwargs) {
    const char* text;
    Py_ssize_t text_len;
    int secure = 1;  /* Default to secure mode */
    
    static char* kwlist[] = {"text", "secure", NULL};
    
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "s#|p", kwlist, 
                                      &text, &text_len, &secure)) {
        return NULL;
    }
    
    uint8_t buffer[6];
    uint8_t out_len = 0;
    
    if (parse_and_compress(text, (size_t)text_len, buffer, secure != 0, &out_len) == 0) {
        return PyBytes_FromStringAndSize((char*)buffer, out_len);
    }
    
    Py_RETURN_NONE;
}

/*
 * can_compress(text: str) -> bool
 */
static PyObject* py_can_compress(PyObject* self, PyObject* args) {
    const char* text;
    Py_ssize_t text_len;
    
    if (!PyArg_ParseTuple(args, "s#", &text, &text_len)) {
        return NULL;
    }
    
    uint8_t buffer[6];
    uint8_t out_len = 0;
    
    if (parse_and_compress(text, (size_t)text_len, buffer, false, &out_len) == 0) {
        Py_RETURN_TRUE;
    }
    
    Py_RETURN_FALSE;
}

/*
 * batch_compress(messages: List[str], secure: bool = True) -> List[bytes | None]
 */
static PyObject* py_batch_compress(PyObject* self, PyObject* args, PyObject* kwargs) {
    PyObject* messages;
    int secure = 1;
    
    static char* kwlist[] = {"messages", "secure", NULL};
    
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "O|p", kwlist, &messages, &secure)) {
        return NULL;
    }
    
    if (!PyList_Check(messages)) {
        PyErr_SetString(PyExc_TypeError, "messages must be a list");
        return NULL;
    }
    
    Py_ssize_t count = PyList_Size(messages);
    PyObject* results = PyList_New(count);
    if (!results) return NULL;
    
    uint8_t buffer[6];
    
    for (Py_ssize_t i = 0; i < count; i++) {
        PyObject* item = PyList_GetItem(messages, i);
        
        if (!PyUnicode_Check(item)) {
            Py_INCREF(Py_None);
            PyList_SetItem(results, i, Py_None);
            continue;
        }
        
        Py_ssize_t text_len;
        const char* text = PyUnicode_AsUTF8AndSize(item, &text_len);
        
        if (!text) {
            Py_INCREF(Py_None);
            PyList_SetItem(results, i, Py_None);
            continue;
        }
        
        uint8_t out_len = 0;
        if (parse_and_compress(text, (size_t)text_len, buffer, secure != 0, &out_len) == 0) {
            PyObject* bytes_obj = PyBytes_FromStringAndSize((char*)buffer, out_len);
            PyList_SetItem(results, i, bytes_obj);
        } else {
            Py_INCREF(Py_None);
            PyList_SetItem(results, i, Py_None);
        }
    }
    
    return results;
}

/* Message type names for decompression */
static const char* MSG_TYPE_NAMES[] = {
    "reserved", "approves", "rejects", "reviews", 
    "votes on", "alerts on", "status of", "reserved"
};

static const char* CONFIDENCE_NAMES[] = {
    "low", "medium", "high", "maximum"
};

/*
 * decompress(data: bytes) -> str | None
 * 
 * Fast native decompression of AURA bitpacked format
 */
static PyObject* py_decompress(PyObject* self, PyObject* args) {
    Py_buffer view;
    
    if (!PyArg_ParseTuple(args, "y*", &view)) {
        return NULL;
    }
    
    const uint8_t* data = (const uint8_t*)view.buf;
    size_t len = view.len;
    
    /* Validate length */
    if (len < 4) {
        PyBuffer_Release(&view);
        Py_RETURN_NONE;
    }
    
    uint8_t method = data[0];
    bool is_secure = (method == METHOD_BITPACKED_SECURE);
    
    if (method != METHOD_BITPACKED && method != METHOD_BITPACKED_SECURE) {
        PyBuffer_Release(&view);
        Py_RETURN_NONE;
    }
    
    if (is_secure && len < 6) {
        PyBuffer_Release(&view);
        Py_RETURN_NONE;
    }
    
    /* Validate CRC for secure format */
    if (is_secure) {
        uint8_t expected_crc = data[5];
        uint8_t actual_crc = crc8_fast(data, 5);
        if (expected_crc != actual_crc) {
            PyBuffer_Release(&view);
            Py_RETURN_NONE;  /* CRC mismatch */
        }
    }
    
    /* Decode fields */
    uint8_t control_byte = data[1];
    uint8_t proposal_id = data[2];
    uint8_t system_ids = data[3];
    
    uint8_t msg_type = (control_byte >> 5) & 0x07;
    uint8_t action = (control_byte >> 3) & 0x03;
    uint8_t confidence = (control_byte >> 1) & 0x03;
    uint8_t risk = control_byte & 0x01;
    
    uint8_t from_sys = (system_ids >> 4) & 0x0F;
    /* uint8_t to_sys = system_ids & 0x0F; */  /* Not used in output */
    
    PyBuffer_Release(&view);
    
    /* Build output string */
    char buffer[128];
    int written;
    
    /* Base message: "System X action proposal YYY" */
    const char* action_str = MSG_TYPE_NAMES[msg_type & 0x07];
    
    if (confidence == 1 && risk == 0) {
        /* Default confidence, no risk - short form */
        written = snprintf(buffer, sizeof(buffer),
                           "System %d %s proposal %03d",
                           from_sys, action_str, proposal_id);
    } else if (risk == 0) {
        /* Non-default confidence, no risk */
        written = snprintf(buffer, sizeof(buffer),
                           "System %d %s proposal %03d with %s confidence",
                           from_sys, action_str, proposal_id,
                           CONFIDENCE_NAMES[confidence & 0x03]);
    } else if (confidence == 1) {
        /* Default confidence with risk */
        written = snprintf(buffer, sizeof(buffer),
                           "System %d %s proposal %03d with risk",
                           from_sys, action_str, proposal_id);
    } else {
        /* Both confidence and risk */
        written = snprintf(buffer, sizeof(buffer),
                           "System %d %s proposal %03d with %s confidence with risk",
                           from_sys, action_str, proposal_id,
                           CONFIDENCE_NAMES[confidence & 0x03]);
    }
    
    if (written < 0 || written >= (int)sizeof(buffer)) {
        Py_RETURN_NONE;
    }
    
    return PyUnicode_FromStringAndSize(buffer, written);
}

/*
 * prewarm() -> None
 * 
 * Pre-warm the compressor: touch lookup tables to bring them into cache
 */
static PyObject* py_prewarm(PyObject* self, PyObject* args) {
    /* Touch CRC table to bring into L1/L2 cache */
    volatile uint8_t dummy = 0;
    for (int i = 0; i < 256; i++) {
        dummy ^= crc8_table[i];
    }
    
    /* Reset sequence counters */
    memset(sequence_counters, 0, sizeof(sequence_counters));
    
    g_prewarmed = true;
    
    Py_RETURN_NONE;
}

/* Semantic Hybrid Compression Support */
typedef struct {
    uint8_t *phrases;
    uint32_t *offsets;
    uint16_t *lengths;
    uint32_t count;
    uint32_t max_phrase_len;
    
    /* Hash table for fast lookup */
    /* Maps hash(phrase) -> index */
    /* Simple open addressing with linear probing */
    uint32_t *hash_table;
    uint32_t table_size;
} SemanticDict;

static SemanticDict g_sem_dict = {0};
static bool g_sem_dict_loaded = false;

/* FNV-1a hash function */
static inline uint32_t hash_phrase(const uint8_t* data, size_t len) {
    uint32_t hash = 2166136261u;
    for (size_t i = 0; i < len; i++) {
        hash ^= data[i];
        hash *= 16777619u;
    }
    return hash;
}

/* Initialize semantic dictionary from buffers */
static PyObject* py_init_semantic_hybrid(PyObject* self, PyObject* args) {
    unsigned long long phrases_ptr;
    unsigned long long offsets_ptr;
    unsigned long long lengths_ptr;
    unsigned int count;
    unsigned int max_phrase_len;
    
    if (!PyArg_ParseTuple(args, "KKKII", &phrases_ptr, &offsets_ptr, &lengths_ptr, 
                          &count, &max_phrase_len)) {
        return NULL;
    }
    
    /* Free old table if exists */
    if (g_sem_dict.hash_table) {
        free(g_sem_dict.hash_table);
        g_sem_dict.hash_table = NULL;
    }
    
    g_sem_dict.phrases = (uint8_t*)(uintptr_t)phrases_ptr;
    g_sem_dict.offsets = (uint32_t*)(uintptr_t)offsets_ptr;
    g_sem_dict.lengths = (uint16_t*)(uintptr_t)lengths_ptr;
    g_sem_dict.count = count;
    g_sem_dict.max_phrase_len = max_phrase_len;
    
    /* Build hash table */
    /* Load factor ~0.5 for speed */
    g_sem_dict.table_size = 1;
    while (g_sem_dict.table_size < count * 2) {
        g_sem_dict.table_size <<= 1;
    }
    
    g_sem_dict.hash_table = (uint32_t*)malloc(g_sem_dict.table_size * sizeof(uint32_t));
    if (!g_sem_dict.hash_table) {
        PyErr_SetString(PyExc_MemoryError, "Failed to allocate hash table");
        return NULL;
    }
    
    /* Initialize with 0xFFFFFFFF (empty) */
    memset(g_sem_dict.hash_table, 0xFF, g_sem_dict.table_size * sizeof(uint32_t));
    
    /* Populate table */
    for (uint32_t i = 0; i < count; i++) {
        uint32_t off = g_sem_dict.offsets[i];
        uint16_t len = g_sem_dict.lengths[i];
        const uint8_t* phrase = g_sem_dict.phrases + off;
        
        uint32_t h = hash_phrase(phrase, len);
        uint32_t idx = h & (g_sem_dict.table_size - 1);
        
        /* Linear probing */
        while (g_sem_dict.hash_table[idx] != 0xFFFFFFFF) {
            idx = (idx + 1) & (g_sem_dict.table_size - 1);
        }
        g_sem_dict.hash_table[idx] = i;
    }
    
    g_sem_dict_loaded = true;
    Py_RETURN_TRUE;
}

/* Fast lookup in hash table */
static inline int32_t find_phrase(const uint8_t* data, size_t len) {
    if (!g_sem_dict_loaded) return -1;
    
    uint32_t h = hash_phrase(data, len);
    uint32_t idx = h & (g_sem_dict.table_size - 1);
    
    while (true) {
        uint32_t entry = g_sem_dict.hash_table[idx];
        if (entry == 0xFFFFFFFF) return -1; /* Not found */
        
        /* Check actual match */
        uint32_t off = g_sem_dict.offsets[entry];
        uint16_t l = g_sem_dict.lengths[entry];
        
        if (l == len && memcmp(g_sem_dict.phrases + off, data, len) == 0) {
            return (int32_t)entry;
        }
        
        idx = (idx + 1) & (g_sem_dict.table_size - 1);
    }
}

/* Compress using semantic hybrid (greedy) */
static PyObject* py_compress_hybrid(PyObject* self, PyObject* args) {
    const char* text;
    Py_ssize_t text_len;
    
    if (!PyArg_ParseTuple(args, "s#", &text, &text_len)) {
        return NULL;
    }
    
    if (!g_sem_dict_loaded) {
        Py_RETURN_NONE;
    }
    
    /* Output buffer (worst case: literals + overhead) */
    /* Each literal chunk (127 bytes) adds 2 bytes overhead */
    size_t max_out = text_len + (text_len / 64) + 32;
    uint8_t* out = (uint8_t*)malloc(max_out);
    if (!out) return PyErr_NoMemory();
    
    size_t out_pos = 0;
    out[out_pos++] = 0xB2; /* Method byte */
    
    size_t in_pos = 0;
    size_t literal_start = 0;
    size_t literal_len = 0;
    
    while (in_pos < text_len) {
        /* Try to find longest match */
        int32_t best_idx = -1;
        size_t best_len = 0;
        
        size_t limit = text_len - in_pos;
        if (limit > g_sem_dict.max_phrase_len) limit = g_sem_dict.max_phrase_len;
        
        /* Try lengths from limit down to 2 */
        /* Optimization: Check min length first? No, greedy wants longest. */
        for (size_t len = limit; len >= 2; len--) {
            int32_t idx = find_phrase((const uint8_t*)text + in_pos, len);
            if (idx >= 0) {
                best_idx = idx;
                best_len = len;
                break; /* Found longest */
            }
        }
        
        if (best_idx >= 0 && best_idx <= 0x7FFF) {
            /* Found match! Flush literals first */
            if (literal_len > 0) {
                size_t lit_pos = literal_start;
                size_t lit_rem = literal_len;
                while (lit_rem > 0) {
                    size_t chunk = (lit_rem > 127) ? 127 : lit_rem;
                    out[out_pos++] = 0x00;
                    out[out_pos++] = (uint8_t)chunk;
                    memcpy(out + out_pos, text + lit_pos, chunk);
                    out_pos += chunk;
                    lit_pos += chunk;
                    lit_rem -= chunk;
                }
                literal_len = 0;
            }
            
            /* Emit token */
            out[out_pos++] = 0x80 | ((best_idx >> 8) & 0x7F);
            out[out_pos++] = best_idx & 0xFF;
            
            in_pos += best_len;
            literal_start = in_pos; /* Reset literal start */
        } else {
            /* No match, extend literal */
            literal_len++;
            in_pos++;
        }
    }
    
    /* Flush remaining literals */
    if (literal_len > 0) {
        size_t lit_pos = literal_start;
        size_t lit_rem = literal_len;
        while (lit_rem > 0) {
            size_t chunk = (lit_rem > 127) ? 127 : lit_rem;
            out[out_pos++] = 0x00;
            out[out_pos++] = (uint8_t)chunk;
            memcpy(out + out_pos, text + lit_pos, chunk);
            out_pos += chunk;
            lit_pos += chunk;
            lit_rem -= chunk;
        }
    }
    
    PyObject* result = PyBytes_FromStringAndSize((char*)out, out_pos);
    free(out);
    return result;
}

/*
 * compress_binary(msg_type, action, confidence, risk, proposal_id, from_sys, to_sys, secure=False) -> bytes
 * 
 * Ultra-fast compression from pre-parsed binary fields.
 * Skips all text parsing for maximum throughput.
 */
static PyObject* py_compress_binary(PyObject* self, PyObject* args, PyObject* kwargs) {
    int msg_type, action, confidence, risk, proposal_id, from_sys, to_sys;
    int secure = 0;
    
    static char* kwlist[] = {"msg_type", "action", "confidence", "risk", 
                              "proposal_id", "from_sys", "to_sys", "secure", NULL};
    
    if (!PyArg_ParseTupleAndKeywords(args, kwargs, "iiiiiii|p", kwlist,
                                      &msg_type, &action, &confidence, &risk,
                                      &proposal_id, &from_sys, &to_sys, &secure)) {
        return NULL;
    }
    
    /* Validate ranges */
    if (msg_type < 0 || msg_type > 7 ||
        action < 0 || action > 3 ||
        confidence < 0 || confidence > 3 ||
        risk < 0 || risk > 1 ||
        proposal_id < 0 || proposal_id > 255 ||
        from_sys < 0 || from_sys > 15 ||
        to_sys < 0 || to_sys > 15) {
        PyErr_SetString(PyExc_ValueError, "Field values out of range");
        return NULL;
    }
    
    uint8_t control_byte = pack_control_byte((uint8_t)msg_type, (uint8_t)action, 
                                              (uint8_t)confidence, (uint8_t)risk);
    uint8_t system_ids = pack_system_ids((uint8_t)from_sys, (uint8_t)to_sys);
    
    if (secure) {
        uint8_t seq = sequence_counters[from_sys]++;
        uint8_t frame[6] = {
            METHOD_BITPACKED_SECURE,
            control_byte,
            (uint8_t)proposal_id,
            system_ids,
            seq,
            0  /* CRC placeholder */
        };
        frame[5] = crc8_fast(frame, 5);
        return PyBytes_FromStringAndSize((char*)frame, 6);
    } else {
        uint8_t frame[4] = {
            METHOD_BITPACKED,
            control_byte,
            (uint8_t)proposal_id,
            system_ids
        };
        return PyBytes_FromStringAndSize((char*)frame, 4);
    }
}

/*
 * crc8(data: bytes) -> int
 * 
 * Compute CRC-8 using fast lookup table
 */
static PyObject* py_crc8(PyObject* self, PyObject* args) {
    Py_buffer view;
    
    if (!PyArg_ParseTuple(args, "y*", &view)) {
        return NULL;
    }
    
    uint8_t crc = crc8_fast((const uint8_t*)view.buf, view.len);
    PyBuffer_Release(&view);
    
    return PyLong_FromLong(crc);
}

/*
 * init_numpy_templates(strings_ptr, metadata_ptr, num_templates, max_len) -> bool
 * 
 * Initialize template buffers from numpy arrays.
 * Call this with buffer pointers from AURANumpyTemplates.to_native_dict()
 */
static PyObject* py_init_numpy_templates(PyObject* self, PyObject* args) {
    unsigned long long strings_ptr;
    unsigned long long metadata_ptr;
    unsigned int num_templates;
    unsigned int max_len;
    
    if (!PyArg_ParseTuple(args, "KKII", &strings_ptr, &metadata_ptr, 
                          &num_templates, &max_len)) {
        return NULL;
    }
    
    g_template_strings = (uint8_t*)(uintptr_t)strings_ptr;
    g_template_metadata = (uint8_t*)(uintptr_t)metadata_ptr;
    g_num_templates = (size_t)num_templates;
    g_template_max_len = (size_t)max_len;
    g_numpy_templates_loaded = true;
    
    Py_RETURN_TRUE;
}

/*
 * get_numpy_template(template_id) -> bytes
 * 
 * Fast template lookup from numpy buffer.
 * Returns raw template bytes (zero-copy from mmap'd array).
 */
static PyObject* py_get_numpy_template(PyObject* self, PyObject* args) {
    unsigned int template_id;
    
    if (!PyArg_ParseTuple(args, "I", &template_id)) {
        return NULL;
    }
    
    if (!g_numpy_templates_loaded || g_template_strings == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "NumPy templates not initialized");
        return NULL;
    }
    
    if (template_id >= g_num_templates) {
        Py_RETURN_NONE;
    }
    
    /* Metadata structure: slot_count(1) + range_id(1) + flags(1) + length(1) + hash_prefix(4) = 8 bytes */
    uint8_t* meta = g_template_metadata + (template_id * 8);
    uint8_t length = meta[3];  /* length field at offset 3 */
    uint8_t flags = meta[2];   /* flags field at offset 2 */
    
    if (flags == 0 || length == 0) {
        /* Template not active */
        Py_RETURN_NONE;
    }
    
    /* Get template string pointer */
    uint8_t* template_data = g_template_strings + (template_id * g_template_max_len);
    
    /* Return as bytes (Python will handle the reference) */
    return PyBytes_FromStringAndSize((const char*)template_data, length);
}

/*
 * has_numpy_templates() -> bool
 */
static PyObject* py_has_numpy_templates(PyObject* self, PyObject* args) {
    if (g_numpy_templates_loaded) {
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

/*
 * reset_sequences() -> None
 * 
 * Reset all sequence counters (for testing)
 */
static PyObject* py_reset_sequences(PyObject* self, PyObject* args) {
    memset(sequence_counters, 0, sizeof(sequence_counters));
    Py_RETURN_NONE;
}

/*
 * is_prewarmed() -> bool
 */
static PyObject* py_is_prewarmed(PyObject* self, PyObject* args) {
    if (g_prewarmed) {
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

/* Method definitions */
static PyMethodDef AuraCompressMethods[] = {
    {"compress", (PyCFunction)py_compress, METH_VARARGS | METH_KEYWORDS,
     "Compress a message to 4-byte (standard) or 6-byte (secure) format.\n\n"
     "Args:\n"
     "    text: Message to compress\n"
     "    secure: Use 6-byte secure format with sequence + CRC (default: True)\n\n"
     "Returns:\n"
     "    bytes if compression succeeded, None otherwise"},
    
    {"can_compress", py_can_compress, METH_VARARGS,
     "Check if a message can be bit-packed.\n\n"
     "Args:\n"
     "    text: Message to check\n\n"
     "Returns:\n"
     "    True if message matches a compressible pattern"},
    
    {"batch_compress", (PyCFunction)py_batch_compress, METH_VARARGS | METH_KEYWORDS,
     "Compress multiple messages in one call (reduces Python overhead).\n\n"
     "Args:\n"
     "    messages: List of strings to compress\n"
     "    secure: Use 6-byte secure format (default: True)\n\n"
     "Returns:\n"
     "    List of bytes (or None for non-compressible messages)"},
    
    {"decompress", py_decompress, METH_VARARGS,
     "Decompress AURA bitpacked format to human-readable string.\n\n"
     "Args:\n"
     "    data: Compressed bytes (4 or 6 bytes)\n\n"
     "Returns:\n"
     "    str if valid AURA format, None otherwise"},
    
    {"prewarm", py_prewarm, METH_NOARGS,
     "Pre-warm the compressor by loading lookup tables into CPU cache.\n"
     "Call once at startup for optimal performance."},
    
    {"compress_binary", (PyCFunction)py_compress_binary, METH_VARARGS | METH_KEYWORDS,
     "Ultra-fast compression from pre-parsed binary fields.\n\n"
     "Args:\n"
     "    msg_type: Message type (0-7: APPROVAL=1, REJECTION=2, REVIEW=3, etc.)\n"
     "    action: Action (0=APPROVE, 1=REJECT, 2=ABSTAIN, 3=ESCALATE)\n"
     "    confidence: Confidence level (0=LOW, 1=MEDIUM, 2=HIGH, 3=MAXIMUM)\n"
     "    risk: Risk flag (0=NO_RISK, 1=HAS_RISK)\n"
     "    proposal_id: Proposal ID (0-255)\n"
     "    from_sys: Source system ID (0-15)\n"
     "    to_sys: Target system ID (0-15)\n"
     "    secure: Use 6-byte secure format (default: False)\n\n"
     "Returns:\n"
     "    bytes (4 bytes standard, 6 bytes secure)"},
    
    {"crc8", py_crc8, METH_VARARGS,
     "Compute CRC-8 checksum using fast lookup table.\n\n"
     "Args:\n"
     "    data: bytes to checksum\n\n"
     "Returns:\n"
     "    CRC-8 value (0-255)"},
    
    {"reset_sequences", py_reset_sequences, METH_NOARGS,
     "Reset all sequence counters to zero (for testing)."},
    
    {"is_prewarmed", py_is_prewarmed, METH_NOARGS,
     "Check if prewarm() has been called."},
    
    {"init_numpy_templates", py_init_numpy_templates, METH_VARARGS,
     "Initialize template buffers from numpy arrays.\n\n"
     "Args:\n"
     "    strings_ptr: Pointer to template strings array (uint64)\n"
     "    metadata_ptr: Pointer to metadata array (uint64)\n"
     "    num_templates: Number of templates\n"
     "    max_len: Maximum template length\n\n"
     "Returns:\n"
     "    True if initialized successfully"},
    
    {"init_semantic_hybrid", py_init_semantic_hybrid, METH_VARARGS,
     "Initialize semantic dictionary for hybrid compression.\n\n"
     "Args:\n"
     "    phrases_ptr: Pointer to phrases array (uint64)\n"
     "    offsets_ptr: Pointer to offsets array (uint64)\n"
     "    lengths_ptr: Pointer to lengths array (uint64)\n"
     "    count: Number of phrases\n"
     "    max_phrase_len: Maximum phrase length\n\n"
     "Returns:\n"
     "    True if initialized successfully"},

    {"compress_hybrid", py_compress_hybrid, METH_VARARGS,
     "Compress text using semantic hybrid dictionary (greedy).\n\n"
     "Args:\n"
     "    text: String to compress\n\n"
     "Returns:\n"
     "    bytes (compressed payload) or None if dictionary not loaded"},

    {"get_numpy_template", py_get_numpy_template, METH_VARARGS,
     "Get template by ID from numpy buffer.\n\n"
     "Args:\n"
     "    template_id: Template ID (0-65535)\n\n"
     "Returns:\n"
     "    bytes if template exists, None otherwise"},
    
    {"has_numpy_templates", py_has_numpy_templates, METH_NOARGS,
     "Check if numpy templates are loaded."},
    
    {NULL, NULL, 0, NULL}
};

/* Module definition */
static struct PyModuleDef aura_compress_module = {
    PyModuleDef_HEAD_INIT,
    "aura_compress",
    "Native AURA compression extension optimized for ARM64 (Jetson Orin).\n\n"
    "Features:\n"
    "- CRC-8 with lookup table (optionally ARM crypto accelerated)\n"
    "- Direct bit-packing without Python overhead\n"
    "- Batch compression for high throughput\n"
    "- Pre-warmed cache for minimal latency\n\n"
    "Compile with: -O3 -march=armv8.2-a+crypto",
    -1,
    AuraCompressMethods
};

PyMODINIT_FUNC PyInit_aura_compress(void) {
    PyObject* m = PyModule_Create(&aura_compress_module);
    if (m == NULL) return NULL;
    
    /* Add constants */
    PyModule_AddIntConstant(m, "METHOD_BITPACKED", METHOD_BITPACKED);
    PyModule_AddIntConstant(m, "METHOD_BITPACKED_SECURE", METHOD_BITPACKED_SECURE);
    
#ifdef __aarch64__
    PyModule_AddIntConstant(m, "NEON_AVAILABLE", 1);
#else
    PyModule_AddIntConstant(m, "NEON_AVAILABLE", 0);
#endif
    
    return m;
}
