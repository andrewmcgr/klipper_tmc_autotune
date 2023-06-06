import re, logging
import configfile
import stepper
from . import tmc

TRINAMIC_DRIVERS = ["tmc2130", "tmc2208", "tmc2209", "tmc2240", "tmc2660",
    "tmc5160"]

class AutotuneTMC:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.name = config.get_name().split()[-1]
        if not config.has_section(self.name):
            raise config.error(
                "Could not find config section '[%s]' required by tmc autotuning"
                % (self.name,))
        for driver in TRINAMIC_DRIVERS:
            driver_name = "%s %s" % (driver, self.name)
            if config.has_section(driver_name):
                self.tmc_section = config.getsection(driver_name)
                self.driver_name = driver_name
                break
        if self.tmc_section is None:
            raise config.error(
                "Could not find TMC driver required by tmc autotuning for %s"
                % (self.name,))
        self.tmc_object=None # look this up at connect time
        self.tmc_cmdhelper=None # Ditto
        self.tmc_init_registers=None # Ditto
        self.motor = config.get('motor')
        self.motor_object = None
        self.motor_name = "motor_constants " + self.motor
        if not config.has_section(self.motor_name):
            raise config.error(
                "Could not find config section '[%s]' required by tmc autotuning"
                % (self.motor_name))
        self.extrahyst = config.getint('extra_hysteresis', default=0, minval=0, maxval=8)
        self.tbl = config.getint('tbl', default=1, minval=0, maxval=3)
        self.toff = config.getint('toff', default=3, minval=1, maxval=15)
        self.sgt = config.getint('sgt', default=1, minval=-64, maxval=63)
        self.sg4_thrs = config.getint('sg4_thrs', default=10, minval=0, maxval=255)
        self.voltage = config.getfloat('voltage', default=24.0, minval=0.0, maxval=60.0)
        self.overvoltage_vth = config.getfloat('overvoltage_vth', default=None,
                                              minval=0.0, maxval=60.0)
        self.printer.register_event_handler("klippy:connect",
                                            self.handle_connect)
        self.printer.register_event_handler("klippy:ready",
                                            self.handle_ready)
        # Register command
        gcode = self.printer.lookup_object("gcode")
        gcode.register_mux_command("AUTOTUNE_TMC", "STEPPER", self.name,
                                   self.cmd_AUTOTUNE_TMC,
                                   desc=self.cmd_AUTOTUNE_TMC_help)
    def handle_connect(self):
        self.tmc_object = self.printer.lookup_object(self.driver_name)
        # The cmdhelper itself isn't a member... but we can still get to it.
        self.tmc_cmdhelper = self.tmc_object.get_status.__self__
        self.motor_object = self.printer.lookup_object(self.motor_name)
        #self.tune_driver()
    cmd_AUTOTUNE_TMC_help = "Apply autotuning configuration to TMC stepper driver"
    def cmd_AUTOTUNE_TMC(self, gcmd):
        logging.info("AUTOTUNE_TMC %s", self.name)
        self.tune_driver()
    def handle_ready(self):
        self.tune_driver()
        pass
    def _set_driver_field(self, field, arg):
        tmco = self.tmc_object
        register = tmco.fields.lookup_register(field, None)
        # Just bail if the field doesn't exist.
        if register is None:
            return
        logging.info("autotune_tmc set %s %s=%s", self.name, field, repr(arg))
        val = tmco.fields.set_field(field, arg)
        tmco.mcu_tmc.set_register(register, val, None)
    def _set_driver_velocity_field(self, field, velocity):
        tmco = self.tmc_object
        register = tmco.fields.lookup_register(field, None)
        # Just bail if the field doesn't exist.
        if register is None:
            return
        fclk = tmco.mcu_tmc.get_tmc_frequency()
        if fclk is None:
            fclk = 12.5e6
        step_dist = self.tmc_cmdhelper.stepper.get_step_dist()
        mres = tmco.fields.get_field("mres")
        arg = tmc.TMCtstepHelper(step_dist, mres, fclk, velocity)
        logging.info("autotune_tmc set %s %s=%s(%s)",
                     self.name, field, repr(arg), repr(velocity))
        val = tmco.fields.set_field(field, arg)
    def tune_driver(self, print_time=None):
        if self.tmc_init_registers is not None:
            self.tmc_init_registers(print_time=print_time)
        tmco = self.tmc_object
        motor = self.motor_object
        setfield = self._set_driver_field
        setvel = self._set_driver_velocity_field
        run_current, _, _, _ = self.tmc_cmdhelper.current_helper.get_current()
        pwmgrad = motor.pwmgrad(volts=self.voltage)
        pwmofs = motor.pwmofs(volts=self.voltage)
        maxpwmrps = motor.maxpwmrps(volts=self.voltage)
        hstrt, hend = motor.hysteresis(volts=self.voltage,
                                       current=run_current,
                                       tbl=self.tbl,
                                       toff=self.toff)
        rdist, _ = self.tmc_cmdhelper.stepper.get_rotation_distance()
        velref = maxpwmrps * rdist
        logging.info("autotune_tmc using max PWM speed %f", velref)
        if self.overvoltage_vth is not None:
            vth = int((self.overvoltage_vth / 0.009732))
            setfield('overvoltage_vth', vth)
        setfield('en_pwm_mode', True)
        setvel('tpwmthrs', velref / 8)
        # setfield('tpwmthrs', 0xfffff)
        setvel('tcoolthrs', 1.25 * (velref / 8))
        setvel('thigh', 0.5 * velref)
        setfield('tpfd', 1)
        setfield('tbl', self.tbl)
        setfield('toff', self.toff)
        setfield('sgt', self.sgt)
        setfield('sg4_thrs', self.sg4_thrs)
        setfield('pwm_autoscale', True)
        setfield('pwm_autograd', True)
        setfield('pwm_grad', pwmgrad)
        setfield('pwm_ofs', pwmofs)
        setfield('pwm_reg', 15)
        setfield('pwm_lim', 12)
        setfield('semin', 2)
        setfield('semax', 8)
        setfield('seup', 3)
        setfield('iholddelay', 12)
        setfield('irundelay', 2)
        setfield('hstrt', hstrt)
        setfield('hend', hend)

def load_config_prefix(config):
    return AutotuneTMC(config)
