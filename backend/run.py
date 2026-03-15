from app import create_app
from app.socketio_instance import socketio

app = create_app()

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5001, allow_unsafe_werkzeug=True)
