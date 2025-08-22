import uvicorn.logging as u_logging
import logging

FORMAT: str = "%(levelprefix)s %(asctime)s [%(threadName)s]  [%(name)s]  %(message)s"

logger = logging.getLogger("logger")
logger.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = u_logging.DefaultFormatter(FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


class Logger:
    @staticmethod
    def info(msg: str):
        logger.info(msg)

    @staticmethod
    def warn(msg: str):
        logger.warning(msg)

    @staticmethod
    def err(msg: str | Exception):
        logger.error(msg)

    @staticmethod
    def debug(msg: str):
        logger.debug(msg)
