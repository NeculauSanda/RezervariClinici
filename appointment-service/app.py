import time
from flask import Flask
from sqlalchemy.exc import OperationalError
from config import Config
from bd_struc_flask import db
from routes.appointments import appointments_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.json.sort_keys = False
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = True
    
    db.init_app(app)
    app.register_blueprint(appointments_bp)

    with app.app_context():
        max_retries = 10
        for attempt in range(max_retries):
            try:
                db.engine.connect()
                print("S-a realizat conexiunea la BD")
                break
            except OperationalError:
                if attempt == max_retries - 1: exit(1)
                print(f"Eroare BD nu e up inca")
                time.sleep(3)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)