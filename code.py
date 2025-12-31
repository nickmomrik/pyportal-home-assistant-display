# PyPortal MQTT Control Pad - Non-Blocking Version
# Inspiration:
#  SPDX-FileCopyrightText: 2020 Anne Barela for Adafruit Industries
#  SPDX-License-Identifier: MIT
#  https://learn.adafruit.com/pyportal-mqtt-sensor-node-control-pad-home-assistant/
#
# By Nick Momrik

import math
import time
import board
import microcontroller
import displayio
import busio
from digitalio import DigitalInOut
import neopixel
from rainbowio import colorwheel
import adafruit_connection_manager
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi import adafruit_esp32spi_wifimanager
from adafruit_bitmap_font import bitmap_font
from adafruit_display_text.label import Label
from adafruit_button import Button
import adafruit_touchscreen
import adafruit_minimqtt.adafruit_minimqtt as MQTT

# --- Configuration ---
LEDS = 24
BRIGHT = 0.5
LEDS_MQTT = "pyportal/leds"

COLORS = {
    "amber": (255, 100, 0), "aqua": (50, 255, 255), "blue": (0, 0, 255),
    "cyan": (0, 255, 255), "gold": (255, 222, 30), "jade": (0, 255, 40),
    "green": (0, 255, 0), "magenta": (255, 0, 20), "off": (0, 0, 0),
    "orange": (255, 40, 0), "pink": (255, 51, 119), "purple": (180, 0, 255),
    "red": (255, 0, 0), "teal": (0, 255, 120), "violet": (153, 0, 255),
    "white": (255, 255, 255), "yellow": (255, 150, 0),
}

# --- Animation State Globals ---
anim_type = None
anim_step = 0
anim_color = COLORS["white"]
anim_direction = 1
last_led_update = 0

# --- Hardware Setup ---
led_status = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=BRIGHT)
led_strip = neopixel.NeoPixel(board.D3, LEDS, brightness=BRIGHT, auto_write=True)

def start_animation(atype, color_name="white", direction="right"):
    global anim_type, anim_step, anim_color, anim_direction
    print(f"Animation: {atype} | Color: {color_name}")
    anim_type = atype
    anim_step = 0
    anim_direction = 1 if direction == "right" else -1
    anim_color = COLORS.get(color_name.lower(), COLORS["white"])
    if atype != "pulse":
        led_strip.brightness = BRIGHT

def update_leds():
    global last_led_update, anim_step, anim_type
    now = time.monotonic()
    if now - last_led_update < 0.04: # ~25 FPS
        return
    last_led_update = now

    if anim_type == "fill":
        led_strip.fill(anim_color)
        led_status.fill(anim_color)
        anim_type = None

    elif anim_type in ["chase", "bounce"]:
        led_strip.fill((0, 0, 0))
        if anim_type == "bounce":
            double_leds = (LEDS - 1) * 2
            temp_step = anim_step % double_leds
            pos = temp_step if temp_step < LEDS else double_leds - temp_step
        else:
            pos = (anim_step % LEDS) if anim_direction == 1 else (LEDS - 1) - (anim_step % LEDS)
        led_strip[pos] = anim_color
        anim_step += 1

    elif anim_type == "pulse":
        level = (anim_step / 50) if anim_step <= 50 else (100 - anim_step) / 50
        led_strip.brightness = max(0, min(level * BRIGHT, 1.0))
        led_strip.fill(anim_color)
        anim_step = (anim_step + 2) if anim_step < 100 else 0

    elif anim_type == "rainbow":
        led_strip.fill(colorwheel(anim_step % 255))
        anim_step += 2

    elif anim_type == "off":
        led_strip.fill((0, 0, 0))
        led_status.fill((0, 0, 0))
        anim_type = None

# --- MQTT Callbacks ---
def message(client, topic, message):
    print(f"MQTT {topic}: {message}")

    if topic == LEDS_MQTT:
        raw = message.replace('"', "").strip().lower()
        if not raw: return
        params = raw.split(":")
        cmd = params[0]
        opt = params[1] if len(params) > 1 else "white"

        if cmd == "chase": start_animation("chase", opt, "right")
        elif cmd == "chaseleft": start_animation("chase", opt, "left")
        elif cmd == "bounce": start_animation("bounce", opt)
        elif cmd == "pulse": start_animation("pulse", opt)
        elif cmd == "rainbow": start_animation("rainbow")
        elif cmd == "fill": start_animation("fill", opt)
        elif cmd == "off": start_animation("off")
        elif cmd == "bright":
            try:
                v = float(opt)
                led_strip.brightness = v if v <= 1 else v/10
            except: pass

    for i, line in enumerate(lines):
        if topic == line["mqtt"]:
            msg = " " if message == "unavailable" else message
            new_text = line["fmt"].format(msg)
            labels[i].text = new_text
            if line["align"] == "right":
                labels[i].x = line["pos"][0] - FONT_WIDTH * len(new_text)
            elif line["align"] == "center":
                labels[i].x = line["pos"][0] - FONT_WIDTH * math.ceil(len(new_text) / 2)

# --- WiFi & MQTT Setup ---
try:
    from secrets import secrets
except ImportError:
    print("Secrets file missing!")
    raise

esp32_spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp32_cs, esp32_ready, esp32_reset = DigitalInOut(board.ESP_CS), DigitalInOut(board.ESP_BUSY), DigitalInOut(board.ESP_RESET)
esp32 = adafruit_esp32spi.ESP_SPIcontrol(esp32_spi, esp32_cs, esp32_ready, esp32_reset)
wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp32, secrets, led_status)

# --- Display Setup ---
display = board.DISPLAY
ts = adafruit_touchscreen.Touchscreen(board.TOUCH_XL, board.TOUCH_XR, board.TOUCH_YD, board.TOUCH_YU,
                                      calibration=((5200, 59000), (5800, 57000)), size=(320, 240))
font = bitmap_font.load_font("/fonts/spleen-8x16.bdf")
FONT_WIDTH, FONT_HEIGHT = 8, 16
splash = displayio.Group()
display.root_group = splash

# Background
bg_bmp = displayio.Bitmap(320, 240, 1)
bg_pal = displayio.Palette(1)
bg_pal[0] = 0x000000
splash.append(displayio.TileGrid(bg_bmp, x=0, y=0, pixel_shader=bg_pal))

# Buttons
buttons = []
b_info = [
    {"y": 8, "label": "Ads", "color": 0xDC143C, "mqtt": "pyportal/button_ads", "led": "red"},
    {"y": 86, "label": "Golf", "color": 0x008000, "mqtt": "pyportal/button_golf", "led": "green"},
    {"y": 164, "label": "Gym", "color": 0x187BCD, "mqtt": "pyportal/button_gym", "led": "blue"},
]

for info in b_info:
    info["presses"] = 0
    btn = Button(x=8, y=info["y"], width=80, height=70, label=info["label"], label_font=font,
                 fill_color=info["color"], label_color=0xFFFFFF, style=Button.SHADOWROUNDRECT)
    buttons.append(btn)
    splash.append(btn)

# Labels
def calc_y(n): return n * (FONT_HEIGHT + 7) - n
TEXT_X = 96
TEXT_MID = math.floor((320 - TEXT_X) / 2) + TEXT_X

lines = [
    {"mqtt": "pyportal/out_temp", "fmt": "{}°", "align": "right", "pos": (TEXT_MID - 4, calc_y(1))},
    {"mqtt": "pyportal/out_humid", "fmt": "{}%", "align": "left", "pos": (TEXT_MID + 4, calc_y(1))},
    {"mqtt": "pyportal/out_status", "fmt": "{}", "align": "center", "pos": (TEXT_MID, calc_y(2))},
    {"mqtt": "pyportal/office_temp", "fmt": "{}°", "align": "right", "pos": (TEXT_MID - 4, calc_y(4))},
    {"mqtt": "pyportal/office_humid", "fmt": "{}%", "align": "left", "pos": (TEXT_MID + 4, calc_y(4))},
    {"mqtt": "pyportal/office_co2", "fmt": "CO2: {} ppm", "align": "left", "pos": (TEXT_MID - 36, calc_y(5))},
    {"mqtt": "pyportal/office_voc", "fmt": "VOC: {} ppb", "align": "left", "pos": (TEXT_MID - 36, calc_y(6))},
    {"mqtt": "pyportal/office_aqi", "fmt": "AQI: {}", "align": "left", "pos": (TEXT_MID - 36, calc_y(7))},
]

labels = []
for line in lines:
    lbl = Label(font, text="", color=0xFFFFFF, x=line["pos"][0], y=line["pos"][1])
    labels.append(lbl)
    splash.append(lbl)

# --- Connect & Run ---
print("Connecting...")
wifi.connect()
client = MQTT.MQTT(broker=secrets["broker"], username=secrets["user"], password=secrets["pass"],
                   socket_pool=adafruit_connection_manager.get_radio_socketpool(esp32),
                   ssl_context=adafruit_connection_manager.get_radio_ssl_context(esp32))
client.on_message = message
client.connect()
client.subscribe(LEDS_MQTT)
for l in lines: client.subscribe(l["mqtt"])

while True:
    if time.monotonic() > 3600: microcontroller.reset()
    try:
        client.loop(timeout=0.01)
    except:
        print("MQTT Error")
    
    update_leds()

    touch = ts.touch_point
    if touch:
        for i, b in enumerate(buttons):
            if b.contains(touch):
                b.selected = True
                b_info[i]["presses"] += 1
                start_animation("chase", b_info[i]["led"])
                if b_info[i]["presses"] >= 2:
                    client.publish(b_info[i]["mqtt"], 1)
                    b_info[i]["presses"] = 0
                while ts.touch_point: update_leds() # Keep anim moving
                b.selected = False
            else: b_info[i]["presses"] = 0
