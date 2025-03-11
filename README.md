# Klipper TMC Autotune

Klipper extension for automatic configuration and tuning of TMC drivers.

This extension calculates good values for most registers of TMC stepper motor drivers, given the motor's datasheet information and user selected tuning goal.

In particular, it enables StealthChop by default on Z motors and extruders, CoolStep where possible, and correctly switches to full step operation at very high speeds. Where multiple modes are possible, it should select the lowest power and quietest modes available, subject to the constraints of sensorless homing (which does not allow certain combinations).


### Current status

- Official support for TMC2209, TMC2240, and TMC5160.
- Support for TMC2130, TMC2208 and TMC2660 may work, but is completely untested.
- Sensorless homing with autotuning enabled is known to work on TMC2209, TMC2240 and TMC5160, provided you home fast enough (homing_speed should be numerically greater than rotation_distance for those axes using sensorless homing). As always, be very careful when trying sensorless homing for the first time.
- Using autotuning for your motors can improve efficiency by allowing them to run cooler and consume less power. However, it's important to note that this process can also cause the TMC drivers to run hotter, so proper cooling measures must be implemented.


## Installation

To install this plugin, run the installation script using the following command over SSH. This script will download this GitHub repository to your RaspberryPi home directory, and symlink the files in the Klipper extra folder.

```bash
wget -O - https://raw.githubusercontent.com/andrewmcgr/klipper_tmc_autotune/main/install.sh | bash
```

Then, add the following to your `moonraker.conf` to enable automatic updates:
```ini
[update_manager klipper_tmc_autotune]
type: git_repo
channel: dev
path: ~/klipper_tmc_autotune
origin: https://github.com/andrewmcgr/klipper_tmc_autotune.git
managed_services: klipper
primary_branch: main
install_script: install.sh
```

## Adjusting existing configuration

Your driver configurations should contain:
* Pins
* Currents (run current, hold current, homing current if using a Klipper version that supports the latter)
* `interpolate: true`
* Comment out any other register settings and sensorless homing values (keep them for reference, but they will not be active)

The Klipper documentation recommends not using interpolation. However, that is most applicable if using low microstep counts, and using the default driver configuration. Autotune gives better results, both dimensionally and quality, by using interpolation and as many microsteps as feasible.

Check the pinouts of your stepper driver boards: BTT TMC 2240 boards require configuring `diag1_pin` not `diag0_pin`, but MKS TMC 2240 stepsticks require `diag0_pin` and *not* `diag1_pin`. There may be other unusual drivers.

## Sensorless homing

Autotune can be used together with homing overrides for sensorless homing. However, you must adjust the `sg4_thrs` (TMC2209, TMC2260) and/or `sgt` (TMC5160, TMC2240, TMC2130, TMC2660) values specifically in the autotune sections. Attempting to make these changes via gcode or via the tmc driver sections will not result in an error message, but will have no effect since the autotuning algorithm will simply override them.

Also note that the sensorless homing tuning will most likely change due to the other settings. In particular, autotune may require faster homing speeds to work; take the `rotation_distance` of the stepper as a minimum speed that can work, and if it is hard to tune home faster. Sensorless homing becomes much more sensitive at higher speeds.

## Autotune configuration

Add the following to your `printer.cfg` (change motor names and remove or add any sections as needed) to enable the autotuning for your TMC drivers and motors and restart Klipper:
```ini
[autotune_tmc stepper_x]
motor: ldo-42sth48-2004mah
[autotune_tmc stepper_y]
motor: ldo-42sth48-2004mah

[autotune_tmc stepper_z]
motor: ldo-42sth48-2004ac
[autotune_tmc stepper_z1]
motor: ldo-42sth48-2004ac
[autotune_tmc stepper_z2]
motor: ldo-42sth48-2004ac
[autotune_tmc stepper_z3]
motor: ldo-42sth48-2004ac

[autotune_tmc extruder]
motor: ldo-36sth20-1004ahg
```

All the `[autotune_tmc]` sections accept additional parameters to tweak the behavior of the autotune process for each motor:

| Parameter | Default value | Range | Description |
| --- | --- | --- | --- |
| motor |  | [See DB](motor_database.cfg) | This parameter is used to retrieve the physical constants of the motor connected to the TMC driver |
| tuning_goal | `auto` | `auto`, `silent`, `performance`, and `autoswitch` | Parameter to choose how to fine-tune the TMC driver using StealthChop and tailored parameters. By opting for `auto`, it will automatically apply `performance` for the X and Y axes and `silent` for the Z axis and extruder unless the motor is very small. `autoswitch` is an highly experimental choice that enables dynamic switching between `silent` and `performance` modes in real-time when needed. However, at the moment, this transition can potentially be troublesome, resulting in unwanted behavior, noise disturbances and lost steps. Hence, it is recommended to avoid using 'autoswitch' until its identified issues are fully addressed |
| extra_hysteresis | 0 | 0 to 8 | Additional hysteresis to reduce motor humming and vibration at low to medium speeds and maintain proper microstep accuracy. Warning: use only as much as necessary as a too high value will result in more chopper noise and motor power dissipation (ie. more heat) |
| tbl | 2 | 0 to 3 | Comparator blank time. This time must safely cover the TMC switching events. A value of 1 or 2 (default) should be fine for most typical applications, but higher capacitive loads may require this to be set to 3. Also, lower values allow StealthChop to regulate to lower coil current values |
| toff | 0 | 0 to 15 | Sets the slow decay time (off time) of the chopper cycle. This setting also limits the maximum chopper frequency. When set to 0, the value is automatically computed by this autotuning algorithm. Highest motor velocities sometimes benefit from forcing `toff` to 1 or 2 and a setting a short `tbl` of 1 or 0 |
| sgt | 1 | -64 to 63 | Sensorless homing threshold for TMC5160, TMC2240, TMC2130, TMC2660. Set value appropriately if using sensorless homing (lower value means more sensitive detection and easier stall) |
| sg4_thrs | 10 | 0 to 255 | Sensorless homing threshold for TMC2209 and TMC2260. Set value appropriately if using sensorless homing (higher value means more sensitive detection and easier stall). This parameter is also used as the CoolStep current regulation threshold for TMC2209, TMC2240 and TMC5160. A default value of 80 is usually a good starting point for CoolStep (in the case of TMC2209, the tuned sensorless homing value will also work correctly) |
| pwm_freq_target | 55e3 | 10e3 to 60e3 | Switching frequency target, in Hz. The code selects the highest available PWM switching frequency less than or equal to this. The default usually results in 48 kHz switching. |
| voltage | 24 | 0.0 to 60.0 | Voltage used to power this motor and stepper driver |
| overvoltage_vth |  | 0.0 to 60.0 | Set the optional overvoltage snubber built into the TMC2240 and TMC5160. Users of the BTT SB2240 toolhead board should use it for the extruder by reading the actual toolhead voltage and adding 0.8V |

Also if needed, you can adjust everything on the go when the printer is running by using the `AUTOTUNE_TMC` macro in the Klipper console. All previous parameters are available:
```
AUTOTUNE_TMC STEPPER=<name> [PARAMETER=<value>]
```


## User-defined motors

The motor names and their physical constants are in the [motor_database.cfg file](motor_database.cfg), which is automatically loaded by the script. If a motor is not listed, feel free to add its proper definition in your own `printer.cfg` configuration file by adding this section (PRs for other motors are also welcome). You can usually find this information in their datasheets but pay very special attention to the units!
```ini
[motor_constants my_custom_motor]
# Coil resistance, Ohms
resistance: 0.00
# Coil inductance, Henries
inductance: 0.00
# Holding torque, Nm
holding_torque: 0.00
# Nominal rated current, Amps
max_current: 0.00
# Steps per revolution (1.8deg motors use 200, 0.9deg motors use 400)
steps_per_revolution: 200
```

Note that lead screw motors very often do not have a published torque. Use an online calculator to estimate the torque from the lead screw thrust, for example https://www.dingsmotionusa.com/torque-calculator.


## Removing this Klipper extension

Commenting out all `[autotune_tmc xxxx]` sections from your config and restarting Klipper will completely deactivate the plugin. So you can enable/disable it as you like.

If you want to uninstall it completely, remove the moonraker update manager section from your `moonraker.conf` file, delete the `~/klipper_tmc_autotune` folder on your Pi and restart Klipper and Moonraker.
