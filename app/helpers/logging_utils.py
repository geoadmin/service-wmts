import logging
import logging.config
import os
from os import path
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def get_logging_cfg():
    cfg_file = os.getenv('LOGGING_CFG', './config/logging-cfg-local.yml')
    if 'LOGS_DIR' not in os.environ:
        # Build paths inside the project like this: BASE_DIR / 'subdir'.
        logs_dir = Path(__file__).resolve(
            strict=True
        ).parent.parent.parent / 'logs'
        os.environ['LOGS_DIR'] = str(logs_dir)
    print(f"LOGS_DIR is {os.environ['LOGS_DIR']}")
    print(f"LOGGING_CFG is {cfg_file}")

    config = {}
    with open(cfg_file, 'rt') as fd:
        config = yaml.safe_load(path.expandvars(fd.read()))

    logger.debug('Load logging configuration from file %s', cfg_file)
    return config


def init_logging():
    config = get_logging_cfg()
    logging.config.dictConfig(config)
