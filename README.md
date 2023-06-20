# Klipper TMC Autotune

Klipper extension for automatic configuration and tuning of TMC drivers.

This extension calculates good values for most registers of TMC stepper motor drivers, given the motor's datasheet information.

In particular, it enables StealthChop by default on Z motors and extruders, CoolStep where possible, and correctly switches to full step operation at very high speeds. Where multiple modes are possible, it should select the lowest power and quietest modes available, subject to the constraints of sensorless homing (which does not allow certain combinations).


### Current status

- Support for TMC2209, TMC2240, and TMC5160 at least partially tested.
- Support for TMC2130, TMC2208 and TMC2660 may work, but is completely untested.
- Sensorless homing with autotuning enabled is known to work on TMC2209, TMC2240 and TMC5160, provided you home fast enough (homing_speed should be numerically greater than rotation_distance for those axes using sensorless homing). As always, be very careful when trying sensorless homing for the first time.
- StealthChop support for X/Y axes is possible, but not recommended at this time. Since Klipper doesn't provide the necessary hooks to safely switch the TMC mode, this may cause lost steps or unwanted vibrations near the switching speed.


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


## Main configuration

Add the following to your `printer.cfg` (remove or add any sections as needed) to enable the autotuning for your TMC drivers and motors and restart Klipper:
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

All `[autotune_tmc]` sections accept additional parameters to tweak the behavior of the autotune process for each motor:

| Parameter | Default value | Range | Description |
| --- | --- | --- | --- |
| motor |  | [See DB](motor_database.cfg) | This parameter is used to retrieve the physical constants of the motor connected to the TMC driver |
| stealth | False (for X/Y TMCs)<br>True (for the others) | True / False | Enable the use of StealthChop for this driver at the automatically calculated appropriate speed range |
| extra_hysteresis | 0 | 0 to 8 | Additional hysteresis to reduce motor humming and vibration at low to medium speeds and maintain proper microstep accuracy. Warning: use only as much as necessary as a too high value will result in more chopper noise and motor power dissipation (ie. more heat) |
| tbl | 2 | 0 to 3 | Comparator blank time. This time must safely cover the TMC switching events. A value of 1 or 2 (default) should be fine for most typical applications, but higher capacitive loads may require this to be set to 3. Also, lower values allow StealthChop to regulate to lower coil current values |
| toff | 0 | 0 to 15 | Sets the slow decay time (off time) of the chopper cycle. This setting also limits the maximum chopper frequency. When set to 0, the value is automatically computed by this autotuning algorithm. Highest motor velocities sometimes benefit from forcing `toff` to 1 or 2 and a setting a short `tbl` of 1 or 0 |
| sgt | 1 | -64 to 63 | Sensorless homing threshold for TMC5160, TMC2240, TMC2130, TMC2660. Set value appropriately if using sensorless homing (higher value means more sensitive detection and easier stall) |
| sg4_thrs | 10 | 0 to 255 | Sensorless homing threshold for TMC2209 and TMC2260. Set value appropriately if using sensorless homing (lower value means more sensitive detection and easier stall). This parameter is also used as the CoolStep current regulation threshold for TMC2209, TMC2240 and TMC5160. A default value of 80 is usually a good starting point for CoolStep (in the case of TMC2209, the tuned sensorless homing value will also work correctly) |
| voltage | 24 | 0.0 to 60.0 | Voltage used to power this motor and stepper driver |
| overvoltage_vth |  | 0.0 to 60.0 | Set the optional overvoltage snubber built into the TMC2240 and TMC5160. Users of the BTT SB2240 toolhead board should use it for the extruder by reading the actual toolhead voltage and adding 0.8V |

  > Note:
  >
  > This autotuning extension can be used together with homing overrides for sensorless homing. However, remember to adjust the `sg4_thrs` and/or `sgt` values specifically in the autotune sections. Attempting to make these changes via gcode will not result in an error message, but will have no effect since the autotuning algorithm will simply override them.


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


## Removing this Klipper extension

Commenting out all `[autotune_tmc xxxx]` sections from your config and restarting Klipper will completely deactivate the plugin. So you can enable/disable it as you like.

If you want to uninstall it completely, remove the moonraker update manager section from your `moonraker.conf` file, delete the `~/klipper_tmc_autotune` folder on your Pi and restart Klipper and Moonraker.
