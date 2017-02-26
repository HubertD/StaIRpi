import paho.mqtt.client as mqtt
from config import MQTT_TOPIC_LED, MQTT_TOPIC_BARRIER, MQTT_TOPIC_COLOR, MQTT_TOPIC_STANDALONE, MQTT_HOST, MQTT_PORT
from config import CAN_DEVICE
from config import COLOR_BLACK
from StaIRwayCan import StaIRwayCan


def str2bool(v):
    return v.lower() in ("yes", "true", "1")


class StaIRpi:
    def __init__(self):
        self.mqttc = mqtt.Client()
        self.mqttc.on_message = self.on_mqtt_message
        self.swcan = StaIRwayCan(CAN_DEVICE)
        self.standalone_mode = True

    def run(self):
        self.mqttc.connect(MQTT_HOST, MQTT_PORT, 60)
        self.mqttc.subscribe(MQTT_TOPIC_LED + "#")
        self.mqttc.subscribe(MQTT_TOPIC_STANDALONE)
        self.mqttc.loop_start()
        self.swcan.OnStepStatusChanged.subscribe(lambda e: self.send_mqtt_barrier_status(e.step, e.status))
        self.swcan.set_all_color(COLOR_BLACK)
        self.swcan.update_leds()

        while True:
            self.swcan.poll(0.1)

    def send_mqtt_barrier_status(self, step_id, status):
        self.mqttc.publish(MQTT_TOPIC_BARRIER % step_id, status)

    def on_mqtt_message(self, client, userdata, message):
        topic = message.topic

        if topic == MQTT_TOPIC_STANDALONE:
            self.process_mqtt_standalone(message.payload)
            return

        if topic.startswith(MQTT_TOPIC_LED):
            self.process_mqtt_led_command(message.topic.split('/')[2:], message.payload)
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

    @staticmethod
    def parse_color(str):
        return int(str, 16)


StaIRpi().run()
