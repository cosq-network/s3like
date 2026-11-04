from . import create_console_app
from .config import Config
app=create_console_app()
if __name__ == '__main__': app.run(host=Config().CONSOLE_LISTEN_HOST,port=Config().CONSOLE_PORT)
