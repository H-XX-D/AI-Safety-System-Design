// Dashboard GUI helpers for ESP32 RGB panel
#ifndef AURA_TRANSLATOR_GUI_H
#define AURA_TRANSLATOR_GUI_H

#include <stddef.h>
#include <stdint.h>

#include "esp_lcd_panel_ops.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct gui_dashboard_data {
	const char* status_text;
	const char* mode_text;
	const char* connection_text;
	const char* action_text;
	uint32_t uptime_seconds;
	size_t heap_free_bytes;
	size_t heap_total_bytes;
	size_t psram_free_bytes;
	size_t psram_total_bytes;
} gui_dashboard_data_t;

typedef struct gui_decoded_message {
	char text[256];
	char timestamp[32];
	uint8_t confidence;
	uint8_t risk_flag;
	uint8_t message_type;
	uint32_t sequence;
	char file_path[128];
} gui_decoded_message_t;

typedef struct gui_translator_state {
	const char* connection_status;
	uint32_t message_count;
	uint32_t error_count;
	uint32_t uptime_seconds;
	const gui_decoded_message_t* messages;
	size_t num_messages;
	// Optional escalations/quarantine list (separate from inbox)
	const gui_decoded_message_t* escalations;
	size_t num_escalations;
} gui_translator_state_t;

typedef enum gui_tab {
	GUI_TAB_INBOX = 0,
	GUI_TAB_ESCALATIONS = 1,
	GUI_TAB_SETTINGS = 2,
} gui_tab_t;

typedef struct gui_ui_state {
	gui_tab_t active_tab;
	size_t selected_index; // Index into message list
	size_t detail_scroll_lines; // Vertical scroll position for detail view
	size_t list_scroll_index; // For scrolling the inbox message list
} gui_ui_state_t;

// Glyph rotation modes for display orientation handling. These are used by the
// GUI renderer to rotate glyphs and map input coordinates to the UI coordinate
// system. Use gui_set_rotation() to change at runtime.
typedef enum GlyphRotationMode {
	ROTATE_0 = 0,
	ROTATE_90 = 1,
	ROTATE_180 = 2,
	ROTATE_270 = 3,
} GlyphRotationMode;

// Screen resolution constants; mirror those used by the GUI module.
#define GUI_LCD_H_RES 800
#define GUI_LCD_V_RES 480

// Initialize the RGB panel and return the handle (NULL on failure)
esp_lcd_panel_handle_t gui_init(void);

// Render the dashboard using the provided metrics
void gui_render_dashboard(const gui_dashboard_data_t* data);

// Render the translator UI with message log and UI state (tabs, selection)
void gui_render_ui(const gui_translator_state_t* state, const gui_ui_state_t* ui);

// Draw a solid color-bar pattern to validate LCD output
void gui_render_test_pattern(void);

// Touch coordinate callback registration. If the platform can provide true touch
// coordinates (e.g., FT5x06, GT911), register a handler to forward taps.
typedef void (*gui_touch_handler_t)(int x, int y, bool pressed);
void gui_register_touch_handler(gui_touch_handler_t handler);

// Forward coordinate-based touch events into the GUI rendering/handler.
void gui_fire_touch_coords(int x, int y, bool pressed);

// Map raw hardware touch coordinates to GUI coordinates, applying scale and rotation.
// raw_max_x/raw_max_y represent the coordinate range of the input (e.g., 4095 for a 12-bit controller).
void gui_map_coords_raw_to_ui(int raw_x, int raw_y, int raw_max_x, int raw_max_y, int* out_x, int* out_y);

// Runtime glyph rotation handlers (allow changing rotation without recompiling)
void gui_set_rotation(GlyphRotationMode rotation);
GlyphRotationMode gui_get_rotation(void);
// Optional axis inversion for panels that are mirrored or use swapped coordinates.
void gui_set_swapxy(bool swap_xy);
bool gui_get_swapxy(void);
void gui_set_flipx(bool flip_x);
bool gui_get_flipx(void);
void gui_set_flipy(bool flip_y);
bool gui_get_flipy(void);

#ifdef __cplusplus
}
#endif

#endif // AURA_TRANSLATOR_GUI_H
