from .xml import error
from app.storage import StorageError

def handle_error(e): return error(e.code, e.message, e.status)
