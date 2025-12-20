import time
from flask import Flask, jsonify, current_app
from sqlalchemy.exc import OperationalError
from config import Config
from bd_struc_flask import db
from routes.doctors import doctors_bp, aux_bp
from routes.schedules import schedules_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.json.sort_keys = False 
    # initializare BD
    db.init_app(app)

    # rutele
    app.register_blueprint(aux_bp)  # specializari, cabinete
    app.register_blueprint(doctors_bp)
    app.register_blueprint(schedules_bp)
    
    # la fel ca la user-service, asteptam pana se poate conecta la BD
    with app.app_context():
        max_retries = 10
        for attempt in range(max_retries):
            try:
                # nu mai cream BD doar testam conexiunea
                db.engine.connect()
                print("doctor-service: Conexiune reusita la BD")
                break
            except OperationalError:
                if attempt == max_retries - 1:
                    print("doctor-service: Eroare fatala la conexiunea cu BD")
                    exit(1)
                print(f"BD nu este gata... (Incercarea {attempt+1})")
                time.sleep(3)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000)