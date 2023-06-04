import math
# Motor database, contains specifications for stepper motors.

# R is coil resistance, Ohms
# L is coil inductance, Henries
# T is holding torque, Nm (be careful about units here)
# I is nominal rated current, Amps

# [gcode_macro _motor_data]
#  variable_motors: {
#                    "ldo-42sth48-2804ah": {"R": 0.7, "L": 0.0006, "T": 0.42, "I": 2.8, "S": 200},
#                    "ldo-42sth48-2504ac": {"R": 1.2, "L": 0.0015, "T": 0.55, "I": 2.5, "S": 200},
#                    "ldo-42sth48-2004mah": {"R": 1.4, "L": 0.003, "T": 0.44, "I": 2.0, "S": 400},
#                    "ldo-42sth48-2004ac": {"R": 1.6, "L": 0.003, "T": 0.59, "I": 2.0, "S": 200},
#                    "ldo-36sth20-1004ahg": {"R": 2.1, "L": 0.0016, "T": 0.1, "I": 1.0, "S": 400},
#                    "17HM19-2004S": {"R": 1.45, "L": 0.004, "T": 0.46, "I": 2.0, "S": 400}
#                    }
#  gcode:
#

class MotorConstants:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]
        self.R = config.getfloat('resistance', minval=0.)
        self.L = config.getfloat('inductance', minval=0.)
        self.T = config.getfloat('holding_torque', minval=0.)
        self.S = config.getint('steps_per_revolution', minval=0)
        self.I = config.getfloat('max_current', minval=0.)
        self.cbemf = self.T / (2.0 * self.I)
    def pwmgrad(self, fclk=12.5e6, steps=0):
        if steps==0:
            steps=self.S
        return int(self.cbemf * 2 * math.pi * fclk  * 1.46 / (24 * 256 * steps))
    def pwmofs(self, volts=24.0):
        return int(374 * self.R * self.L / volts)
    # Maximum revolutions per second before PWM maxes out.
    def maxpwmrps(self, fclk=12.5e6, steps=0, volts=24.0):
        if steps==0:
            steps=self.S
        return (255 - self.pwmofs(volts)) / ( math.pi * self.pwmgrad(fclk, steps))
    def hysteresis(self, fclk=12.5e6, volts=24.0, current=0.0, tbl=1, toff=3):
        I = current if current > 0.0 else self.I
        tblank = 16.0 * (1.5 ** tbl) / fclk
        tsd = (12.0 + 32.0 * toff) / fclk
        dcoilblank = volts * tblank / self.L
        dcoilsd = self.R * I * 2.0 * tsd / self.L
        hstartmin = 0.5 + ((dcoilblank + dcoilsd) * 2 * 248 * 32 / I) / 32 - 8
        hstrt = min(int(max(hstartmin + 0.5, -2.0)), 8)
        hend = min(int(hstartmin + 0.5) - hstrt, 12)
        return hstrt - 1, hend + 3


def load_config_prefix(config):
    return MotorConstants(config)

