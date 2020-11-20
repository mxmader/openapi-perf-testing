from itertools import chain, combinations
import logging
import sys


def get_logger(level=logging.INFO, logger_name='api_perf_logger'):
    logger = logging.getLogger(logger_name)

    # only override the logger-scoped level if we're making it more granular with this particular invocation
    if not logger.level or level < logger.level:
        logger.setLevel(level)

    # if we already have a handler, we're likely calling get_logger for the Nth time within a given process.
    if not logger.handlers:
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def get_power_set(iterable):
    """Get the power set (all combinations with and without any value) of an iterable.

    For example:
    get_power_set([1,2,3]) --> () (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)
    """
    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(len(s)+1))


def get_zfill_hex_uuid(base_uuid, number):
    """Get a UUID with a zero-padded number"""

    if len(base_uuid) != 20:
        raise RuntimeError('Wrong base_uuid length')

    return '{}{}'.format(base_uuid, str(number).zfill(12))


def get_zfill_hyphenated_uuid(base_uuid, number):
    """Get a UUID with a zero-padded number"""

    if len(base_uuid) != 23:
        raise RuntimeError('Wrong base_uuid length')

    return '{}-{}'.format(base_uuid, str(number).zfill(12))
