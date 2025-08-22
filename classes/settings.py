import ipaddress
from typing import List
from urllib.parse import quote_plus

from pydantic import PostgresDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Настройки БД с дефолтными значениями (для разработки)
    APP_MODE: str = "development"
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "postgres"
    DB_SERVER: str = "localhost"
    DB_PORT: int = 5432
    DB_DB: str = "speech-analyzer"
    API_ROOT: str = "/api"

    # Настройки IP-фильтрации
    ALLOWED_IPS: str = "127.0.0.1,::1,localhost"
    TRUSTED_PROXIES: str = ""
    ENABLE_IP_WHITELIST: bool = False

    # Преобразуем строки в списки IP/сетей
    @property
    def allowed_networks(self) -> List:
        """Возвращает список разрешенных IP-адресов и сетей"""
        return self._parse_ip_list(self.ALLOWED_IPS)

    @property
    def trusted_proxies_list(self) -> List:
        """Возвращает список доверенных прокси"""
        return self._parse_ip_list(self.TRUSTED_PROXIES)

    def _parse_ip_list(self, ip_list: str) -> List:
        """Парсит строку с IP-адресами в список объектов"""
        networks = []
        for ip in ip_list.split(","):
            ip = ip.strip()
            if not ip:
                continue
            try:
                if '/' in ip:
                    networks.append(ipaddress.ip_network(ip, strict=False))
                else:
                    networks.append(ipaddress.ip_address(ip))
            except ValueError:
                networks.append(ip)  # для hostnames like localhost
        return networks

    # Автоматически создаем DSN строку
    @property
    def database_url(self) -> PostgresDsn:
        encoded_password = quote_plus(self.DB_PASSWORD)
        return PostgresDsn.build(
            scheme="postgresql",
            username=self.DB_USER,
            password=encoded_password,
            host=self.DB_SERVER,
            port=self.DB_PORT,
            path=self.DB_DB,
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Создаем экземпляр настроек
settings = Settings()
