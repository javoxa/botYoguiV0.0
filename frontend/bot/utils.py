import re
import time
from collections import defaultdict

def anonymize_message(msg: str) -> str:
    """Anonimiza mensajes para logging respetando privacidad"""
    # Eliminar información sensible (emails, teléfonos)
    msg = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', msg)
    msg = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[TELÉFONO]', msg)

    # Solo registrar primeros 50 caracteres
    return msg[:50] + ("..." if len(msg) > 50 else "")

class RateLimiter:
    """Limitador de solicitudes por usuario"""
    def __init__(self, window_seconds: int = 60, max_requests: int = 15):
        self.requests = defaultdict(list)  # {user_id: [timestamps]}
        self.window_seconds = window_seconds
        self.max_requests = max_requests

    def is_allowed(self, user_id: int) -> bool:
        now = time.time()
        user_requests = self.requests[user_id]

        # Eliminar solicitudes antiguas
        user_requests = [ts for ts in user_requests if now - ts < self.window_seconds]
        self.requests[user_id] = user_requests

        if len(user_requests) >= self.max_requests:
            return False

        user_requests.append(now)
        return True

def escape_md(text: str) -> str:
    """Escapa caracteres especiales de Markdown para Telegram"""
    escape_chars = r'([_*[\]()~`>#+\-=|{}.!])'
    return re.sub(escape_chars, r'\\\1', text)
