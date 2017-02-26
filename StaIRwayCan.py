import can

from Observable import Observable
from LightBarrier import LightBarrier
from config import NUM_STEPS, MAX_LEDS_PER_STEP, STEPS_PER_CONTROLLER
from config import CAN_BASE_ID, CAN_BASE_MASK, CAN_FUNCTION_MASK
from config import CAN_ID_BARRIER_STATUS, CAN_ID_SET_LED, CAN_ID_SET_ALL_LEDS, CAN_ID_UPDATE_LEDS


class StaIRwayCan:

    def __init__(self, device):
        can_filters = [{'can_id': self.make_can_id(0, CAN_ID_BARRIER_STATUS), 'can_mask': CAN_FUNCTION_MASK}]
        self.bus = can.interface.Bus(channel=device, bustype="socketcan_native", can_filters=can_filters)
        self.barriers = [LightBarrier() for _ in range(NUM_STEPS)]
        self.leds = [([0] * MAX_LEDS_PER_STEP) for _ in range(NUM_STEPS)]
        self.OnStepStatusChanged = Observable()
        self.msg_set_led = can.Message(arbitration_id=self.make_can_id_all(CAN_ID_SET_ALL_LEDS), extended_id=True, data=[0, 0, 0, 0, 0])
        self.msg_set_step = can.Message(arbitration_id=self.make_can_id_all(CAN_ID_SET_ALL_LEDS), extended_id=True, data=[0xFF, 0, 0, 0])
        self.msg_set_all = can.Message(arbitration_id=self.make_can_id_all(CAN_ID_SET_ALL_LEDS), extended_id=True, data=[0xFF, 0, 0, 0])
        self.msg_flush = can.Message(arbitration_id=self.make_can_id_all(CAN_ID_UPDATE_LEDS), extended_id=True, data=[0xFF])

    def poll(self, max_delay=0.1):
        msg = self.bus.recv(max_delay)
        while msg is not None:
            self.process_can_message(msg)
            msg = self.bus.recv(0)

    def process_can_message(self, msg):
        id = msg.arbitration_id
        if id & CAN_BASE_MASK != CAN_BASE_ID:
            return

        device_mask = (id >> 8) & 0xFF
        function_id = id & 0xFF

        if function_id == CAN_ID_BARRIER_STATUS:
            for i in range(8):
                if (device_mask & (1 << i)) != 0:
                    self.process_barrier_status(i, msg.data[0])

    def process_barrier_status(self, device_id, status_byte):
        for i in range(STEPS_PER_CONTROLLER):
            self.update_step_status(STEPS_PER_CONTROLLER * device_id + i, (status_byte & (1 << i)) != 0)

    def update_step_status(self, step_id, status):
        if (step_id < 0) or (step_id > NUM_STEPS):
            return
        has_changed = self.barriers[step_id].set_active(status)
        if has_changed:
            self.OnStepStatusChanged.fire(step=step_id, status=status)

    def get_step_status(self, step_id):
        if (step_id < 0) or (step_id > NUM_STEPS):
            return False
        return self.barriers[step_id].get_status()

    def set_led_color(self, step_id, led_id, color):
        if (step_id < 0) or (step_id >= NUM_STEPS) or (led_id < 0) or (led_id >= MAX_LEDS_PER_STEP):
            return
        if self.leds[step_id][led_id] != color:
            r, g, b = self.make_rgb(color)
            self.msg_set_led.data = [0, led_id, r, g, b]
            self.set_can_addr(self.msg_set_led, step_id, CAN_ID_SET_LED)
            self.send_can_message(self.msg_set_led)
            self.leds[step_id][led_id] = color

    def set_step_color(self, step_id, color):
        if (step_id < 0) or (step_id >= NUM_STEPS):
            return
        r, g, b = self.make_rgb(color)
        self.msg_set_step.data = [0, r, g, b]
        self.set_can_addr(self.msg_set_step, step_id, CAN_ID_SET_ALL_LEDS)
        self.send_can_message(self.msg_set_step)
        for led_id, k in enumerate(self.leds[step_id]):
            self.leds[step_id][led_id] = color

    def set_all_color(self, color):
        r, g, b = self.make_rgb(color)
        self.msg_set_all.data = [0xFF, r, g, b]
        self.send_can_message(self.msg_set_all)
        for step_id, _ in enumerate(self.leds):
            for led_id, _ in enumerate(self.leds[step_id]):
                self.leds[step_id][led_id] = color

    def update_leds(self):
        self.send_can_message(self.msg_flush)

    def send_can_message(self, msg):
        self.bus.send(msg)

    @staticmethod
    def make_can_id(step_id, function_id=0):
        device_id = int(step_id / STEPS_PER_CONTROLLER)
        return CAN_BASE_ID | ((1 << device_id) << 8) | function_id

    @staticmethod
    def make_can_id_all(function_id=0):
        return CAN_BASE_ID | 0xFF00 | function_id

    @staticmethod
    def make_step_mask(step_id) -> object:
        return 1 << (step_id % STEPS_PER_CONTROLLER)

    @staticmethod
    def set_can_addr(msg, step_id, function_id):
        msg.arbitration_id = StaIRwayCan.make_can_id(step_id, function_id)
        msg.data[0] = StaIRwayCan.make_step_mask(step_id)

    @staticmethod
    def make_rgb(color):
        r = (color >> 16) & 0xFF
        g = (color >> 8) & 0xFF
        b = color & 0xFF
        return r, g, b
