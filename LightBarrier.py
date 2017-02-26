from datetime import datetime


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