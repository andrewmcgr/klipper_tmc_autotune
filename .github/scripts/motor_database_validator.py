#!/usr/bin/env python3

import argparse
from configparser import ConfigParser, Error
import logging
import sys
from pathlib import Path
from enum import IntEnum

logger = logging.getLogger(__name__)


class ValueType(IntEnum):
    INTEGER = 0
    FLOAT = 1
    CUSTOM = 2


MOTOR_PARAMS: dict[str, ValueType] = {
    "holding_torque": ValueType.FLOAT,
    "inductance": ValueType.FLOAT,
    "max_current": ValueType.FLOAT,
    "resistance": ValueType.FLOAT,
    "steps_per_revolution": ValueType.CUSTOM,
}


def validate():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="Verbose output", action="store_true")
    parser.add_argument(
        "database", help="Path to the motor constants database to validate"
    )
    args = parser.parse_args()

    level: int = logging.WARNING
    if args.verbose:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )

    database = Path(args.database)
    if not database.exists():
        logger.error("Motor constants database %s not found!", args.database)
        sys.exit(1)

    config = ConfigParser()
    try:
        config.read(database)
    except Error as e:
        logger.error("%s", str(e))
        sys.exit(1)

    valid = True
    required_params = set(MOTOR_PARAMS.keys())

    for motor_name in config.sections():
        _, name, *_ = motor_name.split()
        logger.info("Verifying motor %s", name)
        motor_params = set(config.options(motor_name))
        if missing := required_params - motor_params:
            valid = False
            for param in sorted(missing):
                logger.error(
                    "Configuration parameter %s is missing from motor definition %s",
                    param,
                    name,
                )

        for param, kind in MOTOR_PARAMS.items():
            match kind:
                case ValueType.FLOAT:
                    try:
                        value = config.getfloat(motor_name, param)
                    except ValueError:
                        logging.error(
                            "Invalid value %s for parameter %s in motor definition %s",
                            config.get(motor_name, param),
                            param,
                            name,
                        )
                        valid = False
                        continue

                    if value <= 0:
                        logger.error(
                            "Configuration paramater %s for motor definition %s can not be less than or equal to 0",
                            param,
                            name,
                        )
                        valid = False
                case ValueType.INTEGER:
                    try:
                        value = config.getint(motor_name, param)
                    except ValueError:
                        logging.error(
                            "Invalid value %s for parameter %s in motor definition %s",
                            config.get(motor_name, param),
                            param,
                            name,
                        )
                        valid = False
                        continue

                    if value <= 0:
                        logger.error(
                            "Configuration paramater %s for motor definition %s can not be less than or equal to 0",
                            param,
                            name,
                        )
                        valid = False
                case ValueType.CUSTOM:
                    match param:
                        case "steps_per_revolution":
                            value = config.getint(motor_name, param)
                            if value not in [200, 400]:
                                logger.error(
                                    "Found invalid steps per revolution for motor %s, expected 200 or 400, found %d",
                                    name,
                                    value,
                                )
                                valid = False
                        case _:
                            raise RuntimeError(
                                f"No custom validation rule defined form parameter {param}"
                            )
    if not valid:
        logger.error("Encountered validation errors in database file %s", database)
        sys.exit(1)


if __name__ == "__main__":
    validate()
