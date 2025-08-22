from fastapi import Depends, HTTPException, Request
from classes.settings import settings

from middleware.ip_whitelist import IPWhitelistMiddleware


def ip_whitelist_dependency():
    """Dependency для проверки IP в отдельных эндпоинтах"""

    def check_ip(request: Request):
        if not settings.ENABLE_IP_WHITELIST:
            return request.client.host

        middleware = IPWhitelistMiddleware(app=None)
        client_ip = middleware.get_real_ip(request)

        if not middleware.is_ip_allowed(client_ip):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied for IP: {client_ip}"
            )

        return client_ip

    return Depends(check_ip)
