import time
from flask import Flask
from sqlalchemy.exc import OperationalError
from config import Config
from bd_struc_flask import db
from routes.users import users_bp

def create_app(config_class=Config):
    """
    Initialize aplicatia Flask
    """
    app = Flask(__name__)
    # adaug setarile din config
    app.config.from_object(config_class)

    # initialez BD-ul, leg SQLAlchemy la Flask
    db.init_app(app)

    # adaug rutele aplicatiei
    app.register_blueprint(users_bp)


    # deoarece nu se conecteaza din prima la BD pt ca nu e gata(initializat), conexiunea esueaza
    # asa ca incerc sa ma conectez de mai multe ori pana cand reusesc (max incercari 10)
    with app.app_context():
        max_retries = 10
        for attempt in range(max_retries):
            try:
                # daca s a facut conexiunea creez tabelele
                db.create_all()
                print("Conexiunea la baza de date realizata cu succes!")
                break # iesim din bucla

            except OperationalError as e:
                if attempt == max_retries - 1:
                    print(f"Eroare nu s-a putut conecta la baza de date dupa {max_retries} incercari.")
                    raise e

                print(f"Baza de date nu este gata... -> Incercarea {attempt + 1}/{max_retries}")
                time.sleep(3)
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5000) # pornesc seviciul user pe portul 5000