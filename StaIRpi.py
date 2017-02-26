import can
from datetime import datetime
import paho.mqtt.client as mqtt


class LightBarrier:

    def __init__(self):
        self.is_active = False
        self.t_last_active = None

    def set_active(self, is_active):
        was_active = self.is_active
        self.is_active = is_active
        if is_active:
            self.t_last_active = datetime.now()
        return was_active != is_active

    def get_status(self):
        return self.is_active

    def seconds_since_last_active(self):
        if self.t_last_active is None:
            return None
        else:
            interval = datetime.now() - self.t_last_active
            return interval.total_seconds()


NUM_STAIRS = 18
bus = can.interface.Bus(channel="can0", bustype="socketcan_native")
barriers = [LightBarrier() for i in range(NUM_STAIRS)]
step_colors = [0x000000] * NUM_STAIRS
last_led_update = datetime.now()

mqttc = mqtt.Client()

def main():
    mqttc.connect("localhost", 1883, 60)
    mqttc.loop_start()

    while True:
        msg = bus.recv(0.1)
        while msg is not None:
            process_message(msg)
            msg = bus.recv(0)
        update_ledstrips()

def process_message(msg):
    id = msg.arbitration_id

    if id & 0x1FFF0000 != 0x13390000:
        return

    device_mask = (id >> 8) & 0xFF
    function_id = id & 0xFF
    for i in range(8):
        if (device_mask & (1<<i)) == 0:
            continue
        if function_id == 2:
            process_barrier_status(i, msg.data[0])

def process_barrier_status(device_id, status_byte):
    set_step_status(3 * device_id + 0, (status_byte & 0x01) != 0)
    set_step_status(3 * device_id + 1, (status_byte & 0x02) != 0)
    set_step_status(3 * device_id + 2, (status_byte & 0x04) != 0)

def set_step_status(step_id, status):
    has_changed = barriers[step_id].set_active(status)
    if has_changed:
        mqttc.publish("StaIRwaY/steps/"+str(step_id)+"/active", status)

def calc_step_colors():
    for i in range(NUM_STAIRS):
        t = barriers[i].seconds_since_last_active()
        if (t is None) or (t>0.15):
            step_colors[i] = 0x00FF00
        else:
            step_colors[i] = 0xFF0000

def update_ledstrips():
    global last_led_update

    last_led_update = datetime.now()
    calc_step_colors()

    for i in range(len(step_colors)):
        color = step_colors[i]
        send_step_color(i, (color >> 16) & 0xFF, (color >> 8) & 0xFF, (color >> 0) & 0xFF)
    send_flush_leds()

def send_all_off():
    msg = can.Message(arbitration_id=0x1339FF04, extended_id=True, data=[0xFF, 0, 0, 0])
    bus.send(msg)

def send_step_color(step_id, r, g, b):
    device_id = (int)(step_id / 3)
    device_mask = (1 << device_id)
    msg = can.Message(arbitration_id=0x13390004 | (device_mask << 8), extended_id=True, data=[1 << (step_id % 3), r, g, b])
    bus.send(msg)

def send_flush_leds():
    msg = can.Message(arbitration_id=0x1339FF05, extended_id=True, data=[0xFF])
    bus.send(msg)

main()
