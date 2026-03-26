import logging
import math

# Motor database, contains specifications for stepper motors.

# coil_resistance: Ohms
# coil_inductance: Henries
# holding_torque: Nm (be careful about units here)
# steps_per_revolution: 200 (1.8deg) or 400 (0.9deg)
# max_current: Amps


class MotorConstants:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]
        self.coil_resistance = config.getfloat("resistance", minval=0.0)
        self.coil_inductance = config.getfloat("inductance", minval=0.0)
        self.holding_torque = config.getfloat("holding_torque", minval=0.0)
        self.steps_per_revolution = config.getint("steps_per_revolution", minval=0)
        self.max_current = config.getfloat("max_current", minval=0.0)
        self.cbemf = self.holding_torque / (2.0 * self.max_current)

    def pwmgrad(self, fclk=12.5e6, steps=0, volts=24.0):
        if steps == 0:
            steps = self.steps_per_revolution
        return int(
            math.ceil(self.cbemf * 2 * math.pi * fclk * 1.46 / (volts * 256.0 * steps))
        )

    def pwmofs(self, volts=24.0, current=0.0):
        effective_current = current if current > 0.0 else self.max_current
        return int(math.ceil(374 * self.coil_resistance * effective_current / volts))

    # Maximum revolutions per second before PWM maxes out.
    def maxpwmrps(self, fclk=12.5e6, steps=0, volts=24.0, current=0.0):
        if steps == 0:
            steps = self.steps_per_revolution
        return (255 - self.pwmofs(volts, current)) / (
            math.pi * self.pwmgrad(fclk, steps)
        )

    def hysteresis(
        self, extra=0, fclk=12.5e6, volts=24.0, current=0.0, tblank_cycles=24, toff=0
    ):
        effective_current = current if current > 0.0 else self.max_current
        logging.info("autotune_tmc setting hysteresis based on %s V", volts)
        tsd = (12.0 + 32.0 * toff) / fclk
        dcoilblank = volts * (tblank_cycles / fclk) / self.coil_inductance
        dcoilsd = (
            self.coil_resistance * effective_current * 2.0 * tsd / self.coil_inductance
        )
        logging.info("dcoilblank = %f, dcoilsd = %f", dcoilblank, dcoilsd)
        hysteresis = extra + int(
            math.ceil(
                max(
                    0.5
                    + ((dcoilblank + dcoilsd) * 2 * 248 * 32 / effective_current) / 32
                    - 8,
                    -2,
                )
            )
        )
        htotal = min(hysteresis, 14)
        hstrt = max(min(htotal, 8), 1)
        hend = min(htotal - hstrt, 12)
        logging.info(
            "hysteresis = %d, htotal = %d, hstrt = %d, hend = %d",
            hysteresis,
            htotal,
            hstrt,
            hend,
        )
        return hstrt - 1, hend + 3


class MotorAlias:
    def __init__(self, config):
        self.name: str = config.get_name().split()[-1]
        self.motor: str = config.get("motor")
        self.deprecated: bool = config.getboolean("deprecated", default=False)

    def register(self, printer) -> None:
        target_name: str = "motor_constants " + self.motor
        target = printer.lookup_object(target_name, default=None)
        if target is None:
            raise printer.config_error(
                "Motor alias '%s' references unknown motor '%s'"
                % (self.name, self.motor)
            )
        if not isinstance(target, MotorConstants):
            raise printer.config_error(
                "Motor alias '%s' targets '%s' which is not a motor definition"
                % (self.name, self.motor)
            )
        alias_key = "motor_constants " + self.name
        existing = printer.objects.get(alias_key)
        if existing is None or isinstance(existing, MotorAlias):
            printer.objects[alias_key] = target


def load_config_prefix(config):
    return MotorConstants(config)
