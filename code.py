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


def led_fill(color):
    led_status.fill(COLORS[color])
    led_strip.fill(COLORS[color])


def led_chase(color, direction="right"):
    length = 4
    wait = 0.05

    led_status.fill(COLORS[color])

    if "right" == direction:
        for i in range(LEDS + length):
            if i < LEDS:
                led_strip[i] = COLORS[color]
            if i >= length:
                led_strip[i - length] = COLORS["off"]
            time.sleep(wait)
    elif "left" == direction :
        for i in range(LEDS - 1, -1 - length, -1):
            if i >= 0:
                led_strip[i] = COLORS[color]
            if i < LEDS - length:
                led_strip[i + length] = COLORS["off"]
            time.sleep(wait)


# b: from 0 (off) to 1 (100% brightness)
def led_bright(b):
    led_status.brightness = b
    led_strip.brightness = b


def led_pulse(color):
    wait = 0.01
    led_bright(0)
    led_fill(color)

    for i in range(1, 101):
        led_bright(i / 100)
        time.sleep(wait)

    for i in range(100, -1, -1):
        led_bright(i / 100)
        time.sleep(wait)

    led_fill("off")
    led_bright(BRIGHT)


def led_rainbow():
    for j in range(256):
        led_strip.fill(colorwheel(j % 255))
        time.sleep(0.01)

def led_reset():
    led_fill("off")
    led_bright(BRIGHT)

def led_animate():
    if not led_params:
        return

    command = led_params[0]
    # Default to "white"
    if len(led_params) == 2:
        option = led_params[1]
    else:
        option = "white"
    if option not in COLORS and command != "bright":
        option = "white"

    if "chase" == command:
        led_chase(option)
    elif "chaseleft" == command:
        led_chase(option, "left")
    elif "bounce" == command:
        led_chase(option)
        led_chase(option, "left")
    elif "fill" == command:
        led_fill(option)
    elif "pulse" == command:
        led_pulse(option)
    elif "rainbow" == command:
        led_rainbow()
    elif "bright" == command:
        try:
            bright = int(option)
            # Restrict value between 0 and 10, then convert to 0.0 - 1.0
            bright = max(0, min(10, bright)) / 10
            led_bright(bright)
        except (ValueError, TypeError):
            print("Invalid bright value, resetting to default")
            led_bright(BRIGHT)

# MQTT Functions
def connect(client, userdata, flags, rc):
    print("Connected to MQTT Broker!")
    print("Flags: {0}\n RC: {1}".format(flags, rc))


def disconnected(client, userdata, rc):
    print("Disconnected from MQTT Broker!")


def subscribe(client, userdata, topic, granted_qos):
    print("Subscribed to {0} with QOS level {1}".format(topic, granted_qos))


def publish(client, userdata, topic, pid):
    print("Published to {0} with PID {1}".format(topic, pid))


def message(client, topic, message):
    print("New message on topic {0}: {1}".format(topic, message))

    if topic == LEDS_MQTT:
        global led_params

        if message:
            led_params = message.replace('"', "").split(":")

    for i in range(len(lines)):
        if topic == lines[i]["mqtt"]:
            if "unavailable" == message:
                message = " "

            line = lines[i]

            new_label = line["fmt"].format(message)
            if line["align"] == "right":
                labels[i].x = line["pos"][0] - FONT_WIDTH * len(new_label)
            elif line["align"] == "center":
                labels[i].x = line["pos"][0] - FONT_WIDTH * math.ceil(
                    len(new_label) / 2
                )

            labels[i].text = new_label


def mqtt_subscribe(topic):
    if len(topic) > 0:
        try:
            client.subscribe(topic)
        except:
            print("MQTT Subscribe exception")


def calc_line_y(line_num):
    return line_num * (FONT_HEIGHT + LINE_MARGIN) - line_num


COLORS = {
    "amber": (255, 100, 0),
    "aqua": (50, 255, 255),
    "blue": (0, 0, 255),
    "cyan": (0, 255, 255),
    "gold": (255, 222, 30),
    "jade": (0, 255, 40),
    "green": (0, 255, 0),
    "magenta": (255, 0, 20),
    "off": (0, 0, 0),
    "orange": (255, 40, 0),
    "pink": (255, 51, 119),
    "purple": (180, 0, 255),
    "red": (255, 0, 0),
    "teal": (0, 255, 120),
    "violet": (153, 0, 255),
    "white": (255, 255, 255),
    "yellow": (255, 150, 0),
}

LEDS = 12
BRIGHT = 0.5
LEDS_MQTT = "pyportal/leds"

led_params = []
led_status = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=BRIGHT)
led_strip = neopixel.NeoPixel(board.D3, LEDS, brightness=BRIGHT)
led_fill("off")

try:
    from secrets import secrets
except ImportError:
    print("Add WiFi secrets in secrets.py!")
    raise

esp32_spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
esp32 = adafruit_esp32spi.ESP_SPIcontrol(esp32_spi, esp32_cs, esp32_ready, esp32_reset)

wifi = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp32, secrets, led_status)

# Screen setup
display = board.DISPLAY

ts = adafruit_touchscreen.Touchscreen(
    board.TOUCH_XL,
    board.TOUCH_XR,
    board.TOUCH_YD,
    board.TOUCH_YU,
    calibration=((5200, 59000), (5800, 57000)),
    size=(320, 240),
)

# Font source: https://github.com/fcambus/spleen
font = bitmap_font.load_font("/fonts/spleen-8x16.bdf")
FONT_WIDTH = 8
FONT_HEIGHT = 16

# Preload the text images
font.load_glyphs("abcdefghjiklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890 :°%µ/³")

# Display context
splash = displayio.Group()
board.DISPLAY.root_group = splash

# Background color fill
SCREEN_WIDTH = 320
SCREEN_HEIGHT = 240
color_bitmap = displayio.Bitmap(SCREEN_WIDTH, SCREEN_HEIGHT, 1)
color_palette = displayio.Palette(1)
color_palette[0] = 0x000000
splash.append(displayio.TileGrid(color_bitmap, x=0, y=0, pixel_shader=color_palette))
try:
    board.DISPLAY.auto_brightness = False
except AttributeError:
    pass
board.DISPLAY.brightness = 0.5

buttons = []
BUTTON_WIDTH = 80
BUTTON_HEIGHT = 70
BUTTON_MARGIN = 8
# Times a button must be pressed before triggering it's MQTT action
BUTTON_PRESS_TRIGGER = 2

b_info = [
    {
        "y": BUTTON_MARGIN,
        "label": "Ads",
        "fill_color": 0xDC143C,
        "mqtt": "pyportal/button_ads",
        "led_color": "red",
    },
    {
        "y": BUTTON_MARGIN * 2 + BUTTON_HEIGHT,
        "label": "Golf",
        "fill_color": 0x008000,
        "mqtt": "pyportal/button_golf",
        "led_color": "green",
    },
    {
        "y": BUTTON_MARGIN * 3 + BUTTON_HEIGHT * 2,
        "label": "Gym",
        "fill_color": 0x187BCD,
        "mqtt": "pyportal/button_gym",
        "led_color": "blue",
    },
]

for i in range(len(b_info)):
    # Initialize button presses
    b_info[i]["presses"] = 0

    b = b_info[i]
    buttons.append(
        Button(
            x=BUTTON_MARGIN,
            y=b["y"],
            width=BUTTON_WIDTH,
            height=BUTTON_HEIGHT,
            label=b["label"],
            label_font=font,
            style=Button.SHADOWROUNDRECT,
            label_color=0xFFFFFF,
            selected_label=0x000000,
            fill_color=b["fill_color"],
            selected_fill=0xFFFFFF,
            outline_color=0xCCCCCC,
            selected_outline=0x333333,
        )
    )

for b in buttons:
    splash.append(b)

# Lines for output
TEXT_X = BUTTON_WIDTH + 2 * BUTTON_MARGIN
TEXT_X_MID = math.floor((SCREEN_WIDTH - TEXT_X) / 2) + TEXT_X
LINE_MARGIN = 7
labels = []
lines = [
    {
        "label": "",
        "align": "right",
        "pos": (TEXT_X_MID - int(FONT_WIDTH / 2), calc_line_y(1)),
        "mqtt": "pyportal/out_temp",
        "fmt": "{}°",
    },
    {
        "label": "",
        "align": "left",
        "pos": (TEXT_X_MID + int(FONT_WIDTH / 2), calc_line_y(1)),
        "mqtt": "pyportal/out_humid",
        "fmt": "{}%",
    },
    {
        "label": "",
        "align": "center",
        "pos": (TEXT_X_MID, calc_line_y(2)),
        "mqtt": "pyportal/out_status",
        "fmt": "{}",
    },
    {
        "label": "",
        "align": "right",
        "pos": (TEXT_X_MID - int(FONT_WIDTH / 2), calc_line_y(4)),
        "mqtt": "pyportal/office_temp",
        "fmt": "{}°",
    },
    {
        "label": "",
        "align": "left",
        "pos": (TEXT_X_MID + int(FONT_WIDTH / 2), calc_line_y(4)),
        "mqtt": "pyportal/office_humid",
        "fmt": "{}%",
    },
    {
        "label": "CO2:",
        "align": "left",
        "pos": (TEXT_X_MID - int(FONT_WIDTH / 2) - (4 * FONT_WIDTH), calc_line_y(5)),
        "mqtt": "pyportal/office_co2",
        "fmt": "CO2: {} ppm",
    },
    {
        "label": "VOC:",
        "align": "left",
        "pos": (TEXT_X_MID - int(FONT_WIDTH / 2) - (4 * FONT_WIDTH), calc_line_y(6)),
        "mqtt": "pyportal/office_voc",
        "fmt": "VOC: {} ppb",
    },
    {
        "label": "AQI:",
        "align": "left",
        "pos": (TEXT_X_MID - int(FONT_WIDTH / 2) - (4 * FONT_WIDTH), calc_line_y(7)),
        "mqtt": "pyportal/office_aqi",
        "fmt": "AQI: {}",
    },
    {
        "label": "Particulate Matter (µg/m³)",
        "align": "left",
        "pos": (TEXT_X_MID - int(FONT_WIDTH / 2) - (13 * FONT_WIDTH), calc_line_y(8)),
        "mqtt": "",
        "fmt": "",
    },
    {
        "label": "< 1µm:",
        "align": "left",
        "pos": (TEXT_X, calc_line_y(9)),
        "mqtt": "pyportal/office_pm_1",
        "fmt": "< 1µm: {}",
    },
    {
        "label": "< 2.5µm:",
        "align": "left",
        "pos": (TEXT_X_MID - FONT_WIDTH, calc_line_y(9)),
        "mqtt": "pyportal/office_pm_2_5",
        "fmt": "< 2.5µm: {}",
    },
    {
        "label": "< 4µm:",
        "align": "left",
        "pos": (TEXT_X, calc_line_y(10)),
        "mqtt": "pyportal/office_pm_4",
        "fmt": "< 4µm: {}",
    },
    {
        "label": "< 10µm:",
        "align": "left",
        "pos": (TEXT_X_MID, calc_line_y(10)),
        "mqtt": "pyportal/office_pm_10",
        "fmt": "< 10µm: {}",
    },
]

for i in range(len(lines)):
    line = lines[i]
    label = Label(font, text=line["label"], color=0xFFFFFF)
    label.x = line["pos"][0]
    label.y = line["pos"][1]
    labels.append(label)
    splash.append(labels[i])

# WiFi
print("Connecting to WiFi...")
wifi.connect()
print("Connected to WiFi network %s" % secrets["ssid"])

# MiniMQTT Client
client = MQTT.MQTT(
    port=1883,
    broker=secrets["broker"],
    username=secrets["user"],
    password=secrets["pass"],
    socket_pool=adafruit_connection_manager.get_radio_socketpool(esp32),
    ssl_context=adafruit_connection_manager.get_radio_ssl_context(esp32),
)

# MQTT callback handlers
client.on_connect = connect
client.on_disconnect = disconnected
client.on_subscribe = subscribe
client.on_publish = publish
client.on_message = message

print("Attempting to connect to %s" % client.broker)
client.connect()
print("Subscribing to MQTT")

for i in range(len(lines)):
    mqtt_subscribe(lines[i]["mqtt"])

mqtt_subscribe(LEDS_MQTT)

while True:
    # Reset every hour
    if time.monotonic() > 3600:
        microcontroller.reset()

    # Poll MQTT message queue
    try:
        client.loop()
    except:
        print("MQTT loop exception")

    led_animate()

    # Check for button presses
    touch = ts.touch_point
    if touch:
        for i, b in enumerate(buttons):
            if b.contains(touch):
                print("%s button pressed" % b.label)

                b.selected = True

                b_info[i]["presses"] += 1
                trigger = b_info[i]["presses"] == BUTTON_PRESS_TRIGGER
                if trigger:
                    if len(b_info[i]["mqtt"]) > 0:
                        print("MQTT publish ON")
                        client.publish(b_info[i]["mqtt"], 1)

                # Debounce
                while ts.touch_point:
                    print("%s button held" % b.label)

                    led_chase(b_info[i]["led_color"])
                    time.sleep(0.5)

                print("%s button released" % b.label)

                if trigger and len(b_info[i]["mqtt"]) > 0:
                    time.sleep(2)
                    print("MQTT publish OFF")
                    client.publish(b_info[i]["mqtt"], 0)

                    b_info[i]["presses"] = 0

                    for x in range(5):
                        led_pulse(b_info[i]["led_color"])

                b.selected = False

            else:
                b_info[i]["presses"] = 0
