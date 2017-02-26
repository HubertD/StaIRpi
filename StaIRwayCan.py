from LightBarrier import LightBarrier
from Observable import Observable
from config import NUM_STEPS, MAX_LEDS_PER_STEP

import can
import copy

class StaIRwayCan:

    def __init__(self, device):
        self.bus = can.interface.Bus(channel=device, bustype="socketcan_native")
        self.barriers = [LightBarrier() for _ in range(NUM_STEPS)]
        self.leds = [([0] * MAX_LEDS_PER_STEP) for _ in range(NUM_STEPS)]
        self.leds_shadow = copy.deepcopy(self.leds)
        self.OnStepStatusChanged = Observable()
        self.flush_msg = can.Message(arbitration_id=0x1339FF05, extended_id=True, data=[0xFF])
        self.setall_msg = can.Message(arbitration_id=0x1339FF04, extended_id=True, data=[0xFF, 0, 0, 0])

    def poll(self, max_delay=0.1):
        msg = self.bus.recv(max_delay)
        while msg is not None:
            self.process_message(msg)
            msg = self.bus.recv(0)

    def process_message(self, msg):
        id = msg.arbitration_id
        if id & 0x1FFF0000 != 0x13390000:
            return

        device_mask = (id >> 8) & 0xFF
        function_id = id & 0xFF
        for i in range(8):
            if (device_mask & (1<<i)) == 0:
                continue
            if function_id == 2:
                self.process_barrier_status(i, msg.data[0])

    def process_barrier_status(self, device_id, status_byte):
        self.set_step_status(3 * device_id + 0, (status_byte & 0x01) != 0)
        self.set_step_status(3 * device_id + 1, (status_byte & 0x02) != 0)
        self.set_step_status(3 * device_id + 2, (status_byte & 0x04) != 0)

    def set_step_status(self, step_id, status):
        has_changed = self.barriers[step_id].set_active(status)
        if has_changed:
            self.OnStepStatusChanged.fire(step=step_id, status=status)

    def set_led(self, step, led, color):
        self.leds[step][led] = color

    def set_step_color(self, step, color):
        self.send_step_color(step, color)

    def set_all_color(self, color):
        self.send_all_color(color)

    def update_leds(self):
        for step_id, stepdata in enumerate(self.leds):
            for (led_id, color) in enumerate(stepdata):
                if self.leds_shadow[step_id][led_id] != color:
                    self.send_led_color(step_id, led_id, color)
        self.send_flush_leds()

    def send_led_color(self, step_id, led_id, color):
        r, g, b = self.make_rgb(color)
        msg = can.Message(arbitration_id=self.make_can_id(step_id)+3, extended_id=True, data=[self.make_step_mask(step_id), led_id, r, g, b])
        self.bus.send(msg)
        self.leds_shadow[step_id][led_id] = color

    def send_step_color(self, step_id, color):
        r, g, b = self.make_rgb(color)
        msg = can.Message(arbitration_id=self.make_can_id(step_id)+4, extended_id=True, data=[self.make_step_mask(step_id), r, g, b])
        self.bus.send(msg)
        for led_id, k in enumerate(self.leds_shadow[step_id]):
            self.leds[step_id][led_id] = color
            self.leds_shadow[step_id][led_id] = color

    def send_all_color(self, color):
        r, g, b = self.make_rgb(color)
        self.setall_msg.data[1] = r
        self.setall_msg.data[2] = g
        self.setall_msg.data[3] = b
        self.bus.send(self.setall_msg)
        print(self.setall_msg)
        for step_id, _ in enumerate(self.leds):
            for led_id, _ in enumerate(self.leds[step_id]):
                self.leds[step_id][led_id] = color
                self.leds_shadow[step_id][led_id] = color

    def make_can_id(self, step_id):
        device_id = int(step_id / 3)
        return 0x13390000 | ((1 << device_id) << 8)

    def make_step_mask(self, step_id):
        return 1 << (step_id % 3)

    def make_rgb(self, color):
        r = (color>>16) & 0xFF
        g = (color>>8) & 0xFF
        b = color & 0xFF
        return r, g, b

    def send_flush_leds(self):
        self.bus.send(self.flush_msg)
