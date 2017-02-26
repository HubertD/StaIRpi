import paho.mqtt.client as mqtt
import config
from config import MQTT_HOST, MQTT_PORT, MQTT_TOPIC_LED, MQTT_TOPIC_BARRIER, MQTT_TOPIC_COLOR, MQTT_TOPIC_STANDALONE
from StaIRwayCan import StaIRwayCan


def str2bool(v):
    return v.lower() in ("yes", "true", "1")


class StaIRpi:
    def __init__(self):
        self.mqttc = mqtt.Client()
        self.mqttc.on_message = self.on_mqtt_message
        self.swcan = StaIRwayCan(config.CAN_DEVICE)
        self.standalone_mode = True

    def run(self):
        self.mqttc.connect(MQTT_HOST, MQTT_PORT, 60)
        self.mqttc.subscribe(MQTT_TOPIC_LED + "#")
        self.mqttc.subscribe(MQTT_TOPIC_STANDALONE)
        self.mqttc.loop_start()
        self.swcan.OnStepStatusChanged.subscribe(lambda e: self.on_barrier_status_changed(e.step, e.status))
        self.swcan.set_all_color(config.COLOR_BLACK)
        self.swcan.update_leds()

        while True:
            self.swcan.poll(0.1)

    def on_barrier_status_changed(self, step_id, status):
        self.send_mqtt_barrier_status(step_id, status)
        if self.standalone_mode:
           self.update_standalone()

    def send_mqtt_barrier_status(self, step_id, status):
        self.mqttc.publish(MQTT_TOPIC_BARRIER % step_id, status)

    def on_mqtt_message(self, client, userdata, message):
        topic = message.topic

        if topic == MQTT_TOPIC_STANDALONE:
            self.process_mqtt_standalone(message.payload)
            return

        if topic.startswith(MQTT_TOPIC_LED):
            params = topic[-len(MQTT_TOPIC_LED)+1:].split('/')
            self.process_mqtt_led_command(params, message.payload)
            return

    def process_mqtt_standalone(self, payload):
        self.standalone_mode = str2bool(payload)

    def process_mqtt_led_command(self, cmd, payload):

        if cmd[-1] != MQTT_TOPIC_COLOR:
            return

        color = self.parse_color(payload)

        if len(cmd) == 1:
            self.swcan.set_all_color(color)

        if len(cmd) == 2:
            step_id = int(cmd[0])
            self.swcan.set_step_color(step_id, color)

        if len(cmd) == 3:
            step_id = int(cmd[0])
            led_id = int(cmd[1])
            self.swcan.set_led_color(step_id, led_id, color)

        self.swcan.update_leds()

    def update_standalone(self):
        self.swcan.set_all_color(config.COLOR_GREEN)
        for step_id in range(config.NUM_STEPS):
            if self.swcan.get_step_status(step_id):
                self.swcan.set_step_color(step_id - 0, config.COLOR_YELLOW)
                self.swcan.set_step_color(step_id - 1, config.COLOR_RED)
                self.swcan.set_step_color(step_id - 2, config.COLOR_YELLOW)
        self.swcan.update_leds()

    @staticmethod
    def parse_color(str):
        return int(str, 16)

StaIRpi().run()
