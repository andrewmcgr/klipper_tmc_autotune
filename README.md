# klipper_tmc_autotune
TMC stepper driver autotuning Klipper python extra

# Installation

Preparation:
```
git clone https://github.com/andrewmcgr/klipper_tmc_autotune.git
ln -sr klipper_tmc_autotune/autotune_tmc.py $HOME/klipper/klippy/extras/
ln -sr klipper_tmc_autotune/motor_constants.py $HOME/klipper/klippy/extras/
ln -sr klipper_tmc_autotune/motor_database.cfg $HOME/printer_data/config/
```

Add the following to your printer.cfg, which assumes you have a Voron 2.4. Remove any sections for steppers you don't have (e.g. if you have less than four Z motors), add more if required. Motor names are in the `motor_database.cfg`. If a motor is not listed, add it, taking careful note of the units. PRs for more motors gratefully accepted.
```
[include motor_database.cfg]

[autotune_tmc stepper_x]
motor: ldo-42sth48-2004mah
sg4_thrs: 80
# Sensorless homing threshold, tune if using sensorless
voltage: 24.0
# Motor supply voltage for this stepper driver
[autotune_tmc stepper_y]
motor: ldo-42sth48-2004mah
sg4_thrs: 10
# Sensorless homing threshold, tune if using sensorless
voltage: 24.0
# Motor supply voltage for this stepper driver

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

This is compatible with homing overrides for sensorless homing, but take care to tune sg4_thrs through the autotune section if using 2240 or 5160 drivers, rather than by attempting to use gcode (that will not error, but won't do anything either as the autotune will override it). It should also work with any other homing overrides.
