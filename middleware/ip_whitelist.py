# middleware/ip_whitelist.py
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import ipaddress
from classes.settings import settings


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Если IP-фильтрация отключена, пропускаем проверку
        if not settings.ENABLE_IP_WHITELIST:
            return await call_next(request)

        # Получаем реальный IP клиента
        client_ip = self.get_real_ip(request)

        # Проверяем доступ
        if not self.is_ip_allowed(client_ip):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": f"Access denied for IP: {client_ip}",
                    "allowed_ips": settings.ALLOWED_IPS
                }
            )

        # Добавляем IP в запрос для дальнейшего использования
        request.state.client_ip = client_ip
        return await call_next(request)

    def get_real_ip(self, request: Request) -> str:
        """Получает реальный IP клиента с учетом прокси"""
        client_ip = request.client.host

        # Если есть доверенные прокси, проверяем заголовки
        if settings.trusted_proxies_list:
            for header in ["X-Real-IP", "X-Forwarded-For"]:
                if header in request.headers:
                    ips = [ip.strip() for ip in request.headers[header].split(",")]
                    # Ищем первый непроксированный IP
                    for ip in reversed(ips):
                        if ip and not self.is_trusted_proxy(ip):
                            return ip
                        client_ip = ip  # fallback to last proxy

        return client_ip

    def is_trusted_proxy(self, ip: str) -> bool:
        """Проверяет, является ли IP доверенным прокси"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            for proxy in settings.trusted_proxies_list:
                if (isinstance(proxy, (ipaddress.IPv4Network, ipaddress.IPv6Network)) and ip_obj in proxy) or \
                        (isinstance(proxy, (ipaddress.IPv4Address, ipaddress.IPv6Address)) and ip_obj == proxy) or \
                        (isinstance(proxy, str) and proxy == ip):
                    return True
        except ValueError:
            pass
        return False

    def is_ip_allowed(self, ip: str) -> bool:
        """Проверяет, разрешен ли IP"""
        try:
            ip_obj = ipaddress.ip_address(ip)
            for net in settings.allowed_networks:
                if (isinstance(net, (ipaddress.IPv4Network, ipaddress.IPv6Network)) and ip_obj in net) or \
                        (isinstance(net, (ipaddress.IPv4Address, ipaddress.IPv6Address)) and ip_obj == net) or \
                        (isinstance(net, str) and net == ip):
                    return True
        except ValueError:
            # Если IP невалидный, проверяем как строку (для hostnames)
            for net in settings.allowed_networks:
                if isinstance(net, str) and net == ip:
                    return True
        return False
