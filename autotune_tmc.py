import math, re, logging, os
import configfile
import stepper
from . import tmc

TRINAMIC_DRIVERS = ["tmc2130", "tmc2208", "tmc2209", "tmc2240", "tmc2660",
    "tmc5160"]

class AutotuneTMC:
    def __init__(self, config):
        self.printer = config.get_printer()
        # Load motor databse
        pconfig = self.printer.lookup_object('configfile')
        dir_name = os.path.dirname(os.path.realpath(__file__))
        filename = os.path.join(dir_name, 'motor_database.cfg')
        try:
            dconfig = pconfig.read_config(filename)
        except Exception:
            raise config.error("Cannot load config '%s'" % (filename,))
        for c in dconfig.get_prefix_sections(''):
            self.printer.load_object(dconfig, c.get_name())
        # Now find our stepper and driver
        # Using positional arguments for maxsplit works with both py2 and py3
        self.name = config.get_name().split(None, 1)[-1]
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
        stealth = not self.name in {'stepper_x', 'stepper_y', 'stepper_x1', 'stepper_y1'}
        self.stealth_and_spread = config.getboolean('stealth_and_spread', default=False)
        self.stealth = config.getboolean('stealth', default=stealth)
        self.tmc_object=None # look this up at connect time
        self.tmc_cmdhelper=None # Ditto
        self.tmc_init_registers=None # Ditto
        self.fclk = None
        self.motor = config.get('motor')
        self.motor_object = None
        self.motor_name = "motor_constants " + self.motor
        if not self.printer.lookup_object(self.motor_name):
            raise config.error(
                "Could not find config section '[%s]' required by tmc autotuning"
                % (self.motor_name))
        self.extra_hysteresis = config.getint('extra_hysteresis', default=0, minval=0, maxval=8)
        self.tbl = config.getint('tbl', default=2, minval=0, maxval=3)
        self.toff = config.getint('toff', default=0, minval=1, maxval=15)
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
        if self.tmc_init_registers is not None:
            self.tmc_init_registers(print_time=print_time)
        self.fclk = self.tmc_object.mcu_tmc.get_tmc_frequency()
        if self.fclk is None:
            self.fclk = 12.5e6
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
        step_dist = self.tmc_cmdhelper.stepper.get_step_dist()
        mres = tmco.fields.get_field("mres")
        arg = tmc.TMCtstepHelper(step_dist, mres, self.fclk, velocity)
        logging.info("autotune_tmc set %s %s=%s(%s)",
                     self.name, field, repr(arg), repr(velocity))
        val = tmco.fields.set_field(field, arg)
    def _set_pwmfreq(self):
        # calculate the highest pwm_freq that gives less than 50 kHz chopping
        pwm_freq = next((i
                         for i in [(3, 2./410),
                                   (2, 2./512),
                                   (1, 2./683),
                                   (0, 2./1024),
                                   (0, 0.) # Default case, just do the best we can.
                                   ]
                         if self.fclk*i[1] < 55e3))[0]
        self._set_driver_field('pwm_freq', pwm_freq)
    def _set_hysteresis(self, run_current):
        hstrt, hend = self.motor_object.hysteresis(
            volts=self.voltage,
            current=run_current,
            tbl=self.tbl,
            toff=self.toff,
            fclk=self.fclk,
            extra=self.extra_hysteresis)
        self._set_driver_field('hstrt', hstrt)
        self._set_driver_field('hend', hend)
    def _set_sg4thrs(self):
        if self.tmc_object.fields.lookup_register("sg4_thrs", None) is not None:
            # we have SG4
            self._set_driver_field('sg4_thrs', self.sg4_thrs)
            self._set_driver_field('sg4_filt_en', True)
        elif self.tmc_object.fields.lookup_register("sgthrs", None) is not None:
            # With SG4 on 2209, pwmthrs should be greater than coolthrs
            self._set_driver_field('sgthrs', self.sg4_thrs)
        else:
            # We do not have SG4
            pass
    def _pwmthrs(self, vmaxpwm, coolthrs):
        if self.tmc_object.fields.lookup_register("sg4_thrs", None) is not None:
            # we have SG4
            # 2240 doesn't care about pwmthrs vs coolthrs ordering, but this is desirable
            return max(0.2 * vmaxpwm, 1.125*coolthrs)
        elif self.tmc_object.fields.lookup_register("sgthrs", None) is not None:
            # With SG4 on 2209, pwmthrs should be greater than coolthrs
            return max(0.2 * vmaxpwm, 1.125*coolthrs)
        else:
            # We do not have SG4, so this makes the world safe for
            # sensorless homing in the presence of CoolStep
            return 0.5*coolthrs
    def _setup_pwm(self, pwm_mode, pwmthrs):
        # Setup pwm autoscale even if we won't use PWM, because it
        # gives more data about the motor and is needed for CoolStep.
        motor = self.motor_object
        pwmgrad = motor.pwmgrad(volts=self.voltage, fclk=self.fclk)
        pwmofs = motor.pwmofs(volts=self.voltage)
        self._set_driver_field('pwm_autoscale', True)
        self._set_driver_field('pwm_autograd', True)
        self._set_driver_field('pwm_grad', pwmgrad)
        self._set_driver_field('pwm_ofs', pwmofs)
        self._set_driver_field('pwm_reg', 8)
        self._set_driver_field('pwm_lim', 4)
        self._set_driver_field('en_pwm_mode', pwm_mode)
        if self.stealth_and_spread:
            self._set_driver_field('tpwmthrs', )
        if self.stealth:
            self._set_driver_field('tpwmthrs', 0xfffff)
        else:
            self._set_driver_field('tpwmthrs', 0)
    def _setup_spreadcycle(self):
        self._set_driver_field('tpfd', 3)
        self._set_driver_field('tbl', self.tbl)
        self._set_driver_field('toff', self.toff if self.toff > 0 else int(math.ceil((0.75e-5 * self.fclk - 12)/32)))
    def _setup_coolstep(self, coolthrs):
        self._set_driver_velocity_field('tcoolthrs', coolthrs)
        self._set_driver_field('sfilt', 1)
        self._set_driver_field('sgt', self.sgt)
        self._set_driver_field('fast_standstill', True)
        self._set_driver_field('small_hysteresis', False)
        self._set_driver_field('semin', 4)
        self._set_driver_field('semax', 2)
        self._set_driver_field('seup', 1)
        self._set_driver_field('sedn', 0)
        self._set_driver_field('seimin', 0)
        self._set_driver_field('iholddelay', 12)
        self._set_driver_field('irundelay', 0)
    def _setup_highspeed(self, vhigh):
        self._set_driver_velocity_field('thigh', vhigh)
        self._set_driver_field('vhighfs', True)
        self._set_driver_field('vhighchm', True)
    def tune_driver(self, print_time=None):
        tmco = self.tmc_object
        run_current, _, _, _ = self.tmc_cmdhelper.current_helper.get_current()
        self._set_hysteresis(run_current)
        self._set_pwmfreq()
        self._set_sg4thrs()
        motor = self.motor_object
        maxpwmrps = motor.maxpwmrps(volts=self.voltage)
        rdist, _ = self.tmc_cmdhelper.stepper.get_rotation_distance()
        # Speed at which we run out of PWM control and should switch to fullstep
        vmaxpwm = maxpwmrps * rdist
        logging.info("autotune_tmc using max PWM speed %f", vmaxpwm)
        if self.overvoltage_vth is not None:
            vth = int((self.overvoltage_vth / 0.009732))
            self._set_driver_field('overvoltage_vth', vth)
        coolthrs = 0.8 * rdist
        self._setup_pwm(self.stealth or self.stealth_and_spread,
                        self._pwmthrs(vmaxpwm, coolthrs))
        self._setup_spreadcycle()
        # One revolution every two seconds is about as slow as coolstep can go
        self._setup_coolstep(coolthrs)
        self._setup_highspeed(0.45 * vmaxpwm)
        self._set_driver_field('multistep_filt', True)

def load_config_prefix(config):
    return AutotuneTMC(config)
