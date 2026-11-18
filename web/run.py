from config.config import Config
from web.app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(host=Config.API_HOST, port=Config.API_PORT, debug=False)
