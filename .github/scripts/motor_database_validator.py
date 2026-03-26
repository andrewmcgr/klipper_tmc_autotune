#!/usr/bin/env python3

import argparse
import logging
import sys
from collections import defaultdict
from configparser import ConfigParser, Error
from enum import IntEnum
from pathlib import Path

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

ALIAS_REQUIRED_PARAMS: set[str] = {"motor"}
ALIAS_OPTIONAL_PARAMS: set[str] = {"deprecated"}
ALIAS_ALL_PARAMS: set[str] = ALIAS_REQUIRED_PARAMS | ALIAS_OPTIONAL_PARAMS


def load_database(path: Path) -> ConfigParser:
    if not path.exists():
        logger.error("Motor constants database %s not found!", path)
        sys.exit(1)

    config = ConfigParser()
    try:
        config.read(path)
    except Error as e:
        logger.error("%s", str(e))
        sys.exit(1)

    return config


def validate_motors(config: ConfigParser, motor_sections: list[str]) -> bool:
    valid = True
    required_params = set(MOTOR_PARAMS.keys())

    for motor_name in motor_sections:
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
            if param not in motor_params:
                continue
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
    return valid


def validate_aliases(
    config: ConfigParser,
    motor_sections: list[str],
    alias_sections: list[str],
) -> bool:
    valid = True
    motor_names = {s.split()[-1] for s in motor_sections}
    alias_names: set[str] = set()

    for alias_section in alias_sections:
        _, name, *_ = alias_section.split()
        logger.info("Verifying alias %s", name)
        alias_params = set(config.options(alias_section))

        if missing := ALIAS_REQUIRED_PARAMS - alias_params:
            valid = False
            for param in sorted(missing):
                logger.error(
                    "Required parameter %s is missing from alias %s",
                    param,
                    name,
                )

        if unexpected := alias_params - ALIAS_ALL_PARAMS:
            valid = False
            for param in sorted(unexpected):
                logger.error(
                    "Unexpected parameter %s in alias %s",
                    param,
                    name,
                )

        if name in motor_names:
            logger.error(
                "Alias %s conflicts with an existing motor_constants definition",
                name,
            )
            valid = False

        if name in alias_names:
            logger.error("Duplicate alias definition for %s", name)
            valid = False
        alias_names.add(name)

        if "motor" in alias_params:
            target = config.get(alias_section, "motor")
            if target not in motor_names:
                if target in alias_names or any(
                    s.split()[-1] == target for s in alias_sections
                ):
                    logger.error(
                        "Alias %s targets another alias '%s', alias chains are not allowed",
                        name,
                        target,
                    )
                else:
                    logger.error(
                        "Alias %s references unknown motor '%s'",
                        name,
                        target,
                    )
                valid = False

        if "deprecated" in alias_params:
            value = config.get(alias_section, "deprecated").lower()
            if value not in ("true", "false", "yes", "no", "1", "0"):
                logger.error(
                    "Invalid boolean value '%s' for deprecated in alias %s",
                    value,
                    name,
                )
                valid = False

    return valid


def check_duplicates(config: ConfigParser, motor_sections: list[str]) -> None:
    specs: dict[tuple, list[str]] = defaultdict(list)
    spec_keys = (
        "resistance",
        "inductance",
        "holding_torque",
        "max_current",
        "steps_per_revolution",
    )

    for motor_name in motor_sections:
        name = motor_name.split()[-1]
        try:
            values = tuple(float(config.get(motor_name, k)) for k in spec_keys)
        except (ValueError, Exception):
            continue
        specs[values].append(name)

    found = False
    for values, names in sorted(specs.items()):
        if len(names) > 1:
            found = True
            spec_str = ", ".join("%s=%s" % (k, v) for k, v in zip(spec_keys, values))
            logger.warning(
                "Duplicate motor specs found: [%s] share identical values (%s)",
                ", ".join(sorted(names)),
                spec_str,
            )

    if not found:
        logger.info("No duplicate motor specifications found")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="Verbose output", action="store_true")
    parser.add_argument(
        "--check-duplicates",
        help="Check for duplicate motor specs (advisory, does not block)",
        action="store_true",
    )
    parser.add_argument("database", help="Path to the motor constants database")
    args = parser.parse_args()

    level: int = logging.WARNING
    if args.verbose:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )

    config = load_database(Path(args.database))

    motor_sections = [s for s in config.sections() if s.startswith("motor_constants ")]
    alias_sections = [s for s in config.sections() if s.startswith("motor_alias ")]

    if args.check_duplicates:
        check_duplicates(config, motor_sections)
    else:
        valid = validate_motors(config, motor_sections)
        valid = validate_aliases(config, motor_sections, alias_sections) and valid
        if not valid:
            logger.error(
                "Encountered validation errors in database file %s",
                args.database,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
