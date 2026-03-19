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
#
# # 1. Получаем логгер библиотеки
# whisper_logger = logging.getLogger("faster_whisper")
#
# # 2. Запрещаем ему отправлять логи выше (в root логгер), чтобы не было дублей
# whisper_logger.propagate = False
#
# # 3. Добавляем ему ваш готовый console_handler с uvicorn-форматированием
# whisper_logger.addHandler(console_handler)
#
# # 4. Устанавливаем нужный уровень (например, INFO, чтобы не спамить DEBUG-ом из недр CTranslate2)
# whisper_logger.setLevel(logging.INFO)


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
