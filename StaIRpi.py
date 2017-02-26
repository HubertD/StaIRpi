import re
import paho.mqtt.client as mqtt
from StaIRwayCan import StaIRwayCan
from config import NUM_STEPS, MAX_LEDS_PER_STEP

class StaIRpi:
    def __init__(self):
        self.mqttc = mqtt.Client()
        self.mqttc.on_message = self.on_mqtt_message
        self.swcan = StaIRwayCan("can0")

        self.re_setled = re.compile(r'StaIRwaY\/led\/(\d+)\/(\d+)\/color')
        self.re_setledstep = re.compile(r'StaIRwaY\/led\/(\d+)\/color')

    def run(self):
        self.mqttc.connect("localhost", 1883, 60)
        self.mqttc.subscribe("StaIRwaY/led/#")
        self.mqttc.subscribe("StaIRwaY/auto")
        self.mqttc.loop_start()
        self.swcan.OnStepStatusChanged.subscribe(lambda e: self.send_mqtt_barrier_status(e.step, e.status))

        while True:
            self.swcan.poll(0)
            """
            for step_id in range(NUM_STEPS):
                r = range(MAX_LEDS_PER_STEP)
                if (step_id%2)==1:
                    r = reversed(r)
                for led_id in r:
                    self.swcan.set_led(step_id, led_id, 0xFF0000)
                    self.swcan.update_leds()
                    self.swcan.poll(0.01)
                    self.swcan.set_led(step_id, led_id, 0x000000)
            """

    def send_mqtt_barrier_status(self, step_id, status):
        self.mqttc.publish("StaIRwaY/barrier/" + str(step_id) + "/active", status)

    def on_mqtt_message(self, client, userdata, message):

        if message.topic == "StaIRwaY/led/color":
            self.swcan.set_all_color(self.parse_color(message.payload))
            self.swcan.update_leds()
            return

        obj = re.match(self.re_setled, message.topic)
        if obj:
            self.swcan.set_led(int(obj.group(1)), int(obj.group(2)), self.parse_color(message.payload))
            self.swcan.update_leds()
            return

        obj = re.match(self.re_setledstep, message.topic)
        if obj:
            self.swcan.set_step_color(int(obj.group(1)), self.parse_color(message.payload))
            self.swcan.update_leds()
            return

    def parse_color(self, str):
        return int(str, 16)

StaIRpi().run()
