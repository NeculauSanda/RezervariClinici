#!/usr/bin/env python3
import subprocess
import requests
import time
from typing import Dict, List, Tuple, Optional

colors = {'GREEN': '\033[92m', 'RED': '\033[91m', 'YELLOW': '\033[93m',
            'BLUE': '\033[94m', 'BLUE_GREEN': '\033[96m', 'RESET': '\033[0m', 'BOLD': '\033[1m'}

class TestApp:
    def __init__(self):
        #pastrez local tokenurile, si rezultatele testelor in dictionare
        self.tokens = {}
        self.test_results = []

        self.keycloak_url = "http://localhost:8080"
        self.user_service_url = "http://localhost:5001"
        self.doctor_service_url = "http://localhost:5002"
        self.realm = "medical-clinica"
        self.client_id = "medical-app"

        # am adaugat eu cate un user in realm Keycloak pentru fiecare rol pe care il am, ca sa pot sa testez
        self.users = {
            'admin': ('admin', 'admin123'),
            'doctor': ('doctor1', 'doctor123'),
            'patient': ('patient1', 'patient123'),
            'patient_nou': ('pacient_nou@test.com', 'parola_noua_123'),
        }
       

    # ---------------------------- FUNCTII AJUTATOARE -----------------------------------

    def print_T(self, text: str):
        """
        Printez colorat fiecare titlu
        """
        print(f"\n{colors['BOLD']}{colors['BLUE']}{'-'*70}\n \
              {colors['BLUE_GREEN']}{text}\n{colors['BLUE']}{'-'*70}{colors['RESET']}\n")

    def print_Sectiuni(self, text: str):
        """
        Sa mi fie mai usor sa vad unde ma aflu cu testele
        """
        print(f"\n{colors['BOLD']} ----> {text} <---- \n{'-'*70}{colors['RESET']}\n")
    
    def print_TesteRez(self, status: str, mesaj: str, detalii: str = ""):
        """
        Printez colorat rezultatul testului
        """

        if status == "OK" or status == "CORECT TEST":
            color = colors['GREEN']
        elif status == "EROARE" or status == "EROARE TEST":
            color = colors['RED']
        else:
            color = colors['BLUE']

        print(f"{color}{mesaj}{colors['RESET']}")
        if detalii:
            print(f"   {detalii}")

        # imi salvez rezultatele doar a testelor
        if status in ["CORECT TEST", "EROARE TEST"]:
            self.test_results.append({'status': status, 'mesaj': mesaj, 'detalii': detalii})

    def run_Shell(self, cmd: str, check: bool = False) -> Tuple[int, str, str]:
        """
        Executa comanda in shell
        """
        try:
            rez = subprocess.run( cmd, shell=True, capture_output=True, text=True, timeout=100)
            return rez.returncode, rez.stdout, rez.stderr

        except Exception as e:
            return 1, "", str(e)

    # ---------------------------------------------------------------


    def Initializare_DockerSwarm(self):
        """
        Pasul 1: Initializez Dockerul Imaginile
        """
        self.print_Sectiuni("Initializare Docker Swarm si construire imagini")

        comenzi = [
            ("docker swarm init && sleep 2", "Initializare docker-swarm"),
            ("docker build -t medical-user-service:latest ./user-service && sleep 10", "construire User-Service"),
            ("docker build -t medical-doctor-service:latest ./doctor-service && sleep 5", "construire Doctor-Service"),
        ]

        for cmd, descriere in comenzi:
            print(f"Se ruleaza: {descriere}")

            if descriere.startswith("construire User-Service"):
                print("!!! Dureaza cam 40-45 secunde build-ul prima data !!!")

            returncode, stdout, stderr = self.run_Shell(cmd)

            if returncode == 0:
                self.print_TesteRez("OK", f"Gata: {descriere}\n")
            else:
                self.print_TesteRez("EROARE", f"Gata: {descriere}", f"Eroare: {stderr[:100]}\n")


    def rulare_DockerApp(self):
        """
        Pasul 2: Rulare aplicatiei
        """

        self.print_Sectiuni("Rulare Aplicatie cu Docker Swarm")

        # comanda
        returncode, stdout, stderr = self.run_Shell( "docker stack deploy -c docker-compose.swarm.yml medical_app && sleep 5" )

        if returncode == 0:
            self.print_TesteRez("OK", "S-a pornit Docker Stack")

            # Trebuie asteptat putin ca sa se active toate serviciile si ca BD ul sa fie si el up
            print("\nSe pregatesc serviciile, dureaza cam 30 sec, pana cand sunt toate up + BD ul\n")
            time.sleep(30)

            # Afisare servicii
            returncode, stdout, stderr = self.run_Shell("docker service ls")
            if returncode == 0:
                self.print_TesteRez("OK", f"Servicii:\n")
                print(stdout)

        else:
            self.print_TesteRez("EROARE", "Nu s-a pornit Docker Stack", stderr[:200])

    def Get_Tokens(self):
        """
        Pasul 3: Trebuie sa obtin token-urile de la Keycloak pentru fiecare user
        ca sa pot sa fac cerreri pe urma
        """

        self.print_Sectiuni("Obtinere token-uri Keycloak pentru userii predefiniti")

        for role, (username, password) in list(self.users.items())[:-1]:
            print(f"Obtin token pentru {role}, user: {username}")

            try:
                response = requests.post(
                    f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/token",
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    data={
                        "username": username,
                        "password": password,
                        "grant_type": "password",
                        "client_id": self.client_id
                    },
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()
                    self.tokens[role] = data['access_token']
                    self.print_TesteRez("S-A OBTINUT TOKEN", f"S-A OBTINUT TOKEN-UL PENTRU {username}")
                else:
                    self.print_TesteRez("EROARE", f"Nu s-a putut obtine token pentru {username}", f"Status: {response.status_code}")

            except Exception as e:
                self.print_TesteRez("EROARE", f"Nu s-a putut obtine token pentru {username}", str(e)[:100])


    def Get_Token(self, rol: str):
        """
        Functie care i-a tokenul de la userii abia inregistrati care nu se afla in realm la inceput
        cum e patient_nou din userii pe care l-am pus mai sus
        """

        username, password = self.users[rol]
        print(f"Obtin token pentru userul '{rol}', username: {username}")

        try:
            raspuns = requests.post(f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={
                    "username": username,
                    "password": password,
                    "grant_type": "password",
                    "client_id": self.client_id
                },
                timeout=10
            )

            if raspuns.status_code == 200:
                # data = raspuns.json()
                self.tokens[rol] = raspuns.json()['access_token']
                self.print_TesteRez("OK", f"S-a obtinut TOKEN pentru userul {rol} ({username})\n")
                return True
            else:
                self.print_TesteRez("EROARE", f"Nu s-a putut obtine token pentru {rol}", f"Status: {raspuns.status_code}")
                return False

        except Exception as e:
            self.print_TesteRez("EROARE", f"Exceptie la obtinere token pentru {rol}", str(e)[:100])
            return False

    def request(self, rol: str, metoda: str, endpoint: str, data: Dict = None) -> Tuple[int, Dict]:
        """
        STRUCTURA CERERE CATRE SERVICII
        """
        if rol not in self.tokens:
            return 401, {"EROARE": "Nu exista token pentru rolul asta"}

        # IMPART URL-UL IN FUNCTIE SERVICIU CA SA STIU UNDE SA TRIMIT CEREREA
        if endpoint.startswith('/doctors') or endpoint.startswith('/specializations') or endpoint.startswith('/cabinets'):
            url = f"{self.doctor_service_url}{endpoint}"

        if endpoint.startswith('/users'):
            url = f"{self.user_service_url}{endpoint}"

        # tokenul
        headers = {
            "Authorization": f"Bearer {self.tokens[rol]}",
            "Content-Type": "application/json"
        }

        try:
            if metoda == "GET":
                raspuns = requests.get(url, headers=headers, timeout=10)
            elif metoda == "POST":
                raspuns = requests.post(url, headers=headers, json=data, timeout=10)
            elif metoda == "PUT":
                raspuns = requests.put(url, headers=headers, json=data, timeout=10)
            elif metoda == "DELETE":
                raspuns = requests.delete(url, headers=headers, timeout=10)
            else:
                return 400, {"EROARE": "Nu exista metoda asta"}

            try:
                return raspuns.status_code, raspuns.json()
            except:
                return raspuns.status_code, {"REZULTAT": raspuns.text}

        except Exception as e:
            return 0, {"EROARE": str(e)}
    
    def sincronizare_Keycloak_BD(self):
        """
        Pasul 4: Trebuie sa sincronizez useri din Keycloak, pe care i-am pus prin realm, si in BD-ul local
        Pentru admin, doctor si pacient, (patient_nou -> e un user ce o sa fie inregistrat mai incolo)
        """

        self.print_Sectiuni("Sincronizare utilizatori(de test) din realm si in BD local")

        for role in ['admin', 'doctor', 'patient']:
            status, raspuns = self.request(role, 'POST', '/users/sync-keycloak')

            print(f"{colors['BOLD']}Sincronizare userului {role} in BD-ul local{colors['RESET']}")
            if status == 200:
                self.print_TesteRez("OK", f"Sincronizare gata pentru {role}")
            else:
                self.print_TesteRez("EROARE", f"Sincronizarea pentru {role} nu s-a putut face", f"Status: {status}")

    def teste_USER_Service(self):
        """
        Pasul 5: Testare USERSERVICE
        """

        self.print_Sectiuni("Testare User-Service")

        # --------------------INREGISTRARE UNUI UTILIZATOR NOU - NU E NEVOIE DE TOKEN LA INCEPUT -------------

        print(f"{colors['BOLD']}       INREGISTRARE UNUI NOU UTILIZATOR {colors['RESET']}\n")

        date_user_nou = {
            "email": "pacient_nou@test.com",
            "password": "parola_noua_123",
            "full_name": "Pacient Nou Test",
            "phone": "0700111222",
            "role": "PATIENT"
        }

        try:
            raspuns = requests.post(f"{self.user_service_url}/users/register",
                headers={"Content-Type": "application/json"},
                json=date_user_nou, timeout=10)

            if raspuns.status_code == 201 or raspuns.status_code == 200:
                user_data = raspuns.json()
                self.print_TesteRez("CORECT TEST", "POST /users/register \nInregistrarea s-a facut cu succes",
                               f"Raspuns: {user_data.get('message', '')}, ID: {user_data.get('id', '')}\n")
            else:
                self.print_TesteRez("EROARE TEST", "Inregistrare nu a reusit", 
                               f"Status: {raspuns.status_code}, Raspuns: {raspuns.text[:100]}\n")
        except Exception as e:
            self.print_TesteRez("EROARE TEST", "Inregistrare utilizator nou nu a reusit", str(e)[:100])

        # Obtin token-ul pentru userul nou inregistrat
        self.Get_Token('patient_nou')

        # ------------------ AFIARE UTILIZATORI DOAR DE CATRE ADMIN ------------------

        print(f"{colors['BOLD']}       AFISAREA UTILIZATORILOR DOAR DE CATRE ADMIN {colors['RESET']}")
        print("->se pot aplica filtre de rol ?role=PATIENT/DOCTOR/ADMIN\n")
        print(f"{colors['BOLD']}Afisare toti utilizatorii:{colors['RESET']}\n")

        status, raspuns = self.request('admin', 'GET', '/users/')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) GET /users/\nStatus: {status}", f"Rezultat : {raspuns}")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) GET /users/\nStatus: {status}", f"Raspuns: {raspuns}\n")

        # In functie de rol

        print(f"\n{colors['BOLD']}       AFISARE DUPA FILTRUL PATIENT{colors['RESET']}\n")

        status, raspuns = self.request('admin', 'GET', f'/users/?role=PATIENT')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) GET /users/?role=PATIENT\nStatus: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) GET /users/?role=PATIENT\nStatus: {status}", f"Raspuns: {raspuns}\n")
        
        #-------------------AFISARE DUPA ID DOAR DE CATRE ADMIN ------------------

        print(f"\n{colors['BOLD']}       AFISARE UTILIZATOR DUPA ID DOAR DE CATRE ADMIN {colors['RESET']}\n")
        # CORECT
        print(f"{colors['BOLD']}->VARIANTA CORECTA\n{colors['RESET']}")
        status, raspuns = self.request('admin', 'GET', f'/users/2')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) GET /users/2\nStatus: {status}", f"Rezultat: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) GET /users/2\nStatus: {status}", f"Raspuns: {raspuns}\n")

        # GRESIT
        print(f"\n{colors['BOLD']}->VARIANTA GRESITA\n{colors['RESET']}")
        status, raspuns = self.request('patient', 'GET', f'/users/2')
        # aici v-a fi pe invers rezultatul pt ca e un test pt logica la admin
        if status != 200:
            self.print_TesteRez("CORECT TEST", f"(patient) GET /users/2 \nStatus: {status}", f"Rezultat: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(patient) GET /users/2 \nStatus: {status}", f"Raspuns: {raspuns}\n")
        
        # -------------------- AFISARE PROFIL PROPRIU NU POATE ACCESA PROFIL ALTUIA --------------------

        print(f"\n{colors['BOLD']}       AFISARE PROFILUL PROPRIU AL UTILIZATORULUI ACTUAL {colors['RESET']}\n")
        for role in ['doctor', 'patient_nou']:
            status, raspuns = self.request(role, 'GET', '/users/me')

            if status == 200:
                self.print_TesteRez("CORECT TEST", f"({role}) GET /users/me\nStatus: {status}", f"Raspuns: {raspuns}\n")
            else:
                self.print_TesteRez("EROARE TEST", f"({role}) GET /users/me\nStatus: {status}", f"Raspuns: {raspuns}\n")

        # -------------------- ACTUALIZARE DATE UTILIZATORULUI DE CATRE EL -------------------- 

        print(f"\n{colors['BOLD']}       ACTUALIZARE PROFIL PROPRIU {colors['RESET']}\n")
        print("-> Datele neactualizate a userului (patient_nou) sunt afisate la comanda anterioara de mai sus\n" \
        "!!! Toate actualizarile de date la useri sau eliminarea lor se fac si in keycloak !!!\n")
        date_input = {
            "full_name": "Popescu Ionut",
            "phone": "0700123456"
        }
        status, raspuns = self.request('patient_nou', 'PUT', '/users/me', date_input)
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(patient_nou) PUT /users/me {{date}}\nStatus: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(patient_nou) PUT /users/me {{date}}\nStatus: {status}", f"Raspuns: {raspuns}\n")
    
        # -------------------- ACTUALIZARE MAI MULTE DATE UTILIZATOR DE CATRE ADMIN --------------------

        print(f"\n{colors['BOLD']}       ACTUALIZARE DATE PROFIL DE CATRE ADMIN {colors['RESET']}\n")
        print("-> Adminul actualizeaza datele la pacient = id 3\n")
        date_input_admin = {
            "full_name": "Dr. Ionescu Andrei",
            "phone": "0710987654",
            "email": "doctor2@clinica.com"
        }
        status, raspuns = self.request('admin', 'PUT', '/users/3', date_input_admin)
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) PUT /users/3 {{date}}\nStatus: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) PUT /users/3 {{date}}\nStatus: {status}", f"Raspuns: {raspuns}\n")

        # -------------------- ACTUALIZARE ROL UTILIZATOR DE CATRE ADMIN --------------------

        print(f"\n{colors['BOLD']}       ACTUALIZARE ROL PROFIL DE CATRE ADMIN {colors['RESET']}\n")
        print("-> Adminul actualizeaza rolul la pacient = id 3 in DOCTOR\n")
        date_input = {
            "role": "DOCTOR"
        }
        status, raspuns = self.request('admin', 'PUT', '/users/3/role', date_input)
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) PUT /users/3/role {{date}}\nStatus: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) PUT /users/3/role {{date}}\nStatus: {status}", f"Raspuns: {raspuns}\n")

        # -------------------- STERGERE UTILIZATOR DE CATRE ADMIN --------------------

        print(f"\n{colors['BOLD']}       STERGERE UTILIZATOR DE CATRE ADMIN {colors['RESET']}\n")
        print("-> Adminul sterge utilizatorul nou creat = id 4\n")
        status, raspuns = self.request('admin', 'DELETE', '/users/4')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) DELETE /users/4 \nStatus: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) DELETE /users/4 \nStatus: {status}", f"Raspuns: {raspuns}\n")

        # ------------------- mai inregistrez din nou userul ca am nevoie la testele urmatoare -------------------
        print(f"{colors['BOLD']}       INREGISTREZ DIN NOU UTILIZATORUL STERS PENTRU TESTELE VIITOARE {colors['RESET']}\n")
        date_user_nou = {
            "email": "pacient_nou@test.com",
            "password": "parola_noua_123",
            "full_name": "Pacient Nou Test",
            "phone": "0700111222",
            "role": "PATIENT"
        }

        try:
            raspuns = requests.post(f"{self.user_service_url}/users/register", headers={"Content-Type": "application/json"},
                json=date_user_nou, timeout=10)
            if raspuns.status_code == 201 or raspuns.status_code == 200:
                print("Inregistrarea s-a facut cu succes\n")
            else:
                print("Inregistrare nu a reusit\n")
        except Exception as e:
            print(f"Inregistrare utilizator nou nu a reusit: {str(e)[:100]}\n")

        self.Get_Token('patient_nou')

    def test_Specializari(self):
        """
        Testare specializari
        """

        self.print_Sectiuni("Testare Specilizari")
        
        #  --------------------------- AFISARE LISTA SPECIALIZARI --------------------------

        print(f"\n{colors['BOLD']}       AFISARE LISTA SPECIALIZARI {colors['RESET']}\n")
        status, raspuns = self.request('patient_nou', 'GET', '/specializations')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(patient_nou) GET /specializations\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(patient_nou) GET /specializations\n Status: {status}", f"Raspuns: {raspuns}\n")
        
        # -------------------------- CREARE SPECIALIZARE NOUA DE CATRE ADMIN --------------------------

        print(f"\n{colors['BOLD']}       CREARE SPECIALIZARE NOUA DE CATRE ADMIN {colors['RESET']}\n")
        print("-> Se poate pune o singura data\n")
        date_input = { 
            "name": "Oftalmologie",
            "description": "Medicina oculara"
        }
        status, raspuns = self.request('admin', 'POST', '/specializations', date_input)
        if status == 201 or status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) POST /specializations '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) POST /specializations '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")

        print("-> Mai incerc inca o data sa pun aceeasi specializare\n")
        status, raspuns = self.request('admin', 'POST', '/specializations', date_input)
        if status == 201 or status == 200:
            self.print_TesteRez(f"OK", f"(admin) POST /specializations '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez(f"{colors['YELLOW']}", f"(admin) POST /specializations '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")


        # ---------------------------- ACTUALIZARE SPECIALIZARE DE CATRE ADMIN ----------------------------

        print(f"\n{colors['BOLD']}       ACTUALIZARE SPECIALIZARE DE CATRE ADMIN {colors['RESET']}\n")
        print("-> Actualizez specializarea cu id 6\n")
        date_input = {
            "name": "Oftalmologie 2",
            "description": "Medicina oculara pentru copii"
        }
        status, raspuns = self.request('admin', 'PUT', '/specializations/6', date_input)
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) PUT /specializations/6 '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) PUT /specializations/6 '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")

        # --------------------------- STERGERE SPECIALIZARE DE CATRE ADMIN ---------------------------

        print(f"\n{colors['BOLD']}       STERGERE SPECIALIZARE DE CATRE ADMIN {colors['RESET']}\n")
        print("-> Sterg specializarea cu id 6\n")

        status, raspuns = self.request('admin', 'DELETE', '/specializations/6')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) DELETE /specializations/6\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) DELETE /specializations/6\n Status: {status}", f"Raspuns: {raspuns}\n")
    
    def test_Cabinete(self):
        """
        Testare cabinete
        """

        self.print_Sectiuni("Testare Cabinete")

        # --------------------------- AFISARE LISTA CABINETE ---------------------------

        print(f"\n{colors['BOLD']}       AFISARE LISTA CABINETE {colors['RESET']}\n")
        status, raspuns = self.request('patient_nou', 'GET', '/cabinets')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(patient_nou) GET /cabinets\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(patient_nou) GET /cabinets\n Status: {status}", f"Raspuns: {raspuns}\n")
        # ------------------------- CREARE CABINET NOU DE CATRE ADMIN ----------------------------

        print(f"\n{colors['BOLD']}       CREARE CABINET NOU DE CATRE ADMIN {colors['RESET']}\n")
        print("-> Se poate pune o singura data la fel ca la specializari\n")
        date_input = { 
            "name": "Cabinet 6",
            "floor": 2, "location": 
            "Etaj 2, Usa 206" 
        }
        status, raspuns = self.request('admin', 'POST', '/cabinets', date_input)
        if status == 201 or status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) POST /cabinets '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) POST /cabinets '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")

        # ---------------------------- ACTUALIZARE CABINET DE CATRE ADMIN --------------------------
        print(f"\n{colors['BOLD']}       ACTUALIZARE CABINET DE CATRE ADMIN {colors['RESET']}\n")
        print("-> Actualizez cabinetul cu id 7\n")
        date_input = { 
            "name": "Cabinet 6",
            "floor": 2,
            "location": "Etaj 3, Usa 306" 
        }
        status, raspuns = self.request('admin', 'PUT', '/cabinets/7', date_input)
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) PUT /cabinets/7 '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) PUT /cabinets/7 '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")

        # ------------------------ STERGERE CABINET DE CATRE ADMIN ----------------------------

        print(f"\n{colors['BOLD']}       STERGERE CABINET DE CATRE ADMIN {colors['RESET']}\n")
        print("-> Sterg cabinetul cu id 7\n")
        status, raspuns = self.request('admin', 'DELETE', '/cabinets/7')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) DELETE /cabinets/7\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) DELETE /cabinets/7\n Status: {status}", f"Raspuns: {raspuns}\n")

    
    def test_Doctor_Service(self):
        """
        Pasul 6: Testare DOCTORSERVICE
        """

        self.print_Sectiuni("Testare Doctor-Service")

        print(f"{colors['BOLD']} La inceput nu se afla niciun doctor in lista pentru ca nu au profil de doctor")
        print(f"{colors['BOLD']}Trebuie facut profilul de catre admin, chiar daca au rol de DOCTOR intial{colors['RESET']}\n")
        # -------------------------- AFISARE LISTA DOCTORI LA INCEPUT ----------------------------

        print(f"\n{colors['BOLD']}       AFISARE LISTA DOCTORI LA INCEPUT {colors['RESET']}\n")
        status, raspuns = self.request('patient_nou', 'GET', '/doctors')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(patient_nou) GET /doctors\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(patient_nou) GET /doctors\n Status: {status}", f"Raspuns: {raspuns}\n")

        # --------------------------- CREARE PROFIL DOCTOR DE CATRE ADMIN ----------------------------

        print(f"\n{colors['BOLD']}       CREAREA PROFILULUI DE DOCTOR DE CATRE ADMIN {colors['RESET']}\n")
        print("-> Fac profil de doctor pentru userul cu id 2 (nu se poate pune de 2 ori)\n")
        date_input = { 
            "user_id": 2, 
            "specialization_id": 1, 
            "cabinet_id": 1, 
            "bio": "Doctor specialist", 
            "years_experience": 10 
        }
        status, raspuns = self.request('admin', 'POST', '/doctors', date_input)
        if status == 201 or status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) POST /doctors '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) POST /doctors '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")

        # ---------------------------- AFISEZ LISTA DOCTORI IARASI ---------------------------

        print(f"\n{colors['BOLD']}       AFISARE LISTA DOCTORI {colors['RESET']}\n")
        print("-> Se pot pune si filtre de specializare/cabinet")
        status, raspuns = self.request('patient_nou', 'GET', '/doctors')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(patient_nou) GET /doctors\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(patient_nou) GET /doctors\n Status: {status}", f"Raspuns: {raspuns}\n")

    
        # ---------------------------- AFISARE DOCTOR DUPA ID ----------------------------------

        print(f"\n{colors['BOLD']}       AFISARE DOCTOR DUPA ID {colors['RESET']}\n")
        status, raspuns = self.request('patient_nou', 'GET', '/doctors/1')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(patient_nou) GET /doctors/1\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(patient_nou) GET /doctors/1\n Status: {status}", f"Raspuns: {raspuns}\n")

        # ---------------------------- ACTUALIZARE PROFIL DOCTOR DE CATRE ADMIN ---------------------------

        print(f"\n{colors['BOLD']}        ACTUALIZARE PROFIL DOCTOR DE CATRE ADMIN {colors['RESET']}\n")
        print("-> Actualizez profilul doctorului cu id 1\n")
        date_input = {
            "specialization_id": 1, 
            "cabinet_id": 3,
            "bio": "Cardiolog cu vechime si premii", 
            "years_experience": 15
        }
        status, raspuns = self.request('admin', 'PUT', '/doctors/1', date_input)
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) PUT /doctors/1 '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) PUT /doctors/1 '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")

        # ------------------------------- AFISARE PROGRAM DE LUCRU DOCTOR ---------------------------

        print(f"\n{colors['BOLD']}       AFISARE PROGRAM DE LUCRU DOCTOR {colors['RESET']}\n")
        print("-> La inceput nu are program de lucru\n")
        status, raspuns = self.request('patient_nou', 'GET', '/doctors/1/schedule')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(patient_nou) GET /doctors/1/schedule\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(patient_nou) GET /doctors/1/schedule\n Status: {status}", f"Raspuns: {raspuns}\n")

        # --------------------------- ADAUGARE PROGRAM DE LUCRU DOCTORULUI DE CATRE DOCTOR INSUSI/ADMIN -----------

        print(f"\n{colors['BOLD']}       ADAUGARE PROGRAM DE LUCRU DOCTORULUI DE CATRE DOCTORUL INSUSI/ADMIN {colors['RESET']}\n")
        print("-> Adaug program de lucru pentru doctorul cu id 1 (nu se poate pune 2 ori acelasi program)\n")
        date_input = {
            "weekday": 0,
            "start_time": "09:00:00",
            "end_time": "17:00:00",
            "slot_duration_minutes": 30
        }
        status, raspuns = self.request('doctor', 'POST', '/doctors/1/schedule', date_input)
        if status == 201 or status == 200:
            self.print_TesteRez("CORECT TEST", f"(doctor) POST /doctors/1/schedule '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(doctor) POST /doctors/1/schedule '{{date}}'\n Status: {status}", f"Raspuns: {raspuns}\n")

        # ------------------- ------ AFISARE PROGRAM DE LUCRU DOCTOR ----------------------------

        print(f"\n{colors['BOLD']}       AFISARE PROGRAM DE LUCRU DOCTOR {colors['RESET']}\n")
        status, raspuns = self.request('patient_nou', 'GET', '/doctors/1/schedule')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(patient_nou) GET /doctors/1/schedule\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(patient_nou) GET /doctors/1/schedule\n Status: {status}", f"Raspuns: {raspuns}\n")

        # ------------------------- AFISARE SLOT-URI DISPONIBILE LA DOCTORUL CERUT IN FUNCTIE DE ZI --------------------------

        print(f"\n{colors['BOLD']}       AFISARE SLOT-URI DISPONIBILE LA DOCTORUL CERUT IN FUNCTIE DE ZI {colors['RESET']}\n")
        print("-> Programul setat e LUNEA trebuie pusa o data de luni, altfel nu are program\n")
        status, raspuns = self.request('patient_nou', 'GET', '/doctors/1/available-slots?date=2025-12-15')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(patient_nou) GET /doctors/1/available-slots?date=2025-12-15\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(patient_nou) GET /doctors/1/available-slots?date=2025-12-15\n Status: {status}", f"Raspuns: {raspuns}\n")

        #  ---------------------------- STERGERE PROGRAM DE LUCRU DOCTOR --------------------------

        print(f"\n{colors['BOLD']}       STERGERE PROGRAM DE LUCRU DOCTOR {colors['RESET']}\n")
        print("-> Sterg programul de lucru cu id 1 pentru doctorul cu id 1\n")
        status, raspuns = self.request('doctor', 'DELETE', '/doctors/1/schedule/1')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(doctor) DELETE /doctors/1/schedule/1\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(doctor) DELETE /doctors/1/schedule/1\n Status: {status}", f"Raspuns: {raspuns}\n")

        # --------------------------- AFISARE SLOT-URI DISPONIBILE LA DOCTORUL CERUT IN FUNCTIE DE ZI ---------------------------

        print(f"\n{colors['BOLD']}       AFISARE SLOT-URI DISPONIBILE DUPA ELIMINARE PROGRAM {colors['RESET']}\n")
        status, raspuns = self.request('patient_nou', 'GET', '/doctors/1/available-slots?date=2025-12-15')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(patient_nou) GET /doctors/1/available-slots?date=2025-12-15\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(patient_nou) GET /doctors/1/available-slots?date=2025-12-15\n Status: {status}", f"Raspuns: {raspuns}\n")

        #  --------------------------- STERGERE PROFIL DOCTOR DE CATRE ADMIN ---------------------------

        print(f"\n{colors['BOLD']}       STERGERE PROFIL DOCTOR DE CATRE ADMIN {colors['RESET']}\n")
        print("-> Sterg profilul de doctor cu id 1 -> revine la rolul de PACIENT, se schimba si in Keycloak\n")
        status, raspuns = self.request('admin', 'DELETE', '/doctors/1')
        if status == 200:
            self.print_TesteRez("CORECT TEST", f"(admin) DELETE /doctors/1\n Status: {status}", f"Raspuns: {raspuns}\n")
        else:
            self.print_TesteRez("EROARE TEST", f"(admin) DELETE /doctors/1\n Status: {status}", f"Raspuns: {raspuns}\n")

    def inchidere_DockerApp(self):
        """
        Oprire aplicatie docker
        """
        self.print_T("OPRIREA APLICATIEI DOCKER")
        comenzi = [
            ("docker stack rm medical_app && sleep 10", "Oprire stack Docker"),
            ("docker swarm leave --force", "Iesire din swarm Docker"),
            ("docker volume rm medical_app_db_data", "Curatarea volumelor ale aplicatiei"),
            ("docker rmi medical-doctor-service:latest medical-user-service:latest", "Curatarea imaginilor ale aplicatiei"),
        ]

        for cmd, description in comenzi:
            print(f"Se ruleaza: {description}")

            if description.startswith("Oprire stack Docker"):
                print("Dureaza 10 secunde pentru oprirea completa a serviciilor")

            returncode, stdout, stderr = self.run_Shell(cmd)

            if returncode == 0:
                self.print_TesteRez("OK", f"Gata: {description}\n")
            else:
                self.print_TesteRez("EROARE", f"Gata: {description}", f"Eroare: {stderr[:100]}\n")


    def rezultate(self):
        """
        Printeaza rezultatele finale ale testelor
        """
        self.print_T("REZULTATE TESTE")
        
        total = len(self.test_results)
        crt_corect = 0
        crt_gresit = 0
        for rez in self.test_results:
            if rez['status'] == 'CORECT TEST':
                crt_corect += 1
            elif rez['status'] == 'EROARE TEST':
                crt_gresit += 1
        
        print(f"\nSTATISTICI:")
        print(f"Trecute:  {crt_corect}/{total}")
        print(f"Picate:  {crt_gresit}/{total}")


    def all_tests(self):
        """
        Testele
        """
        self.print_T("REZERVARI CLINICI - TESTE")

        try:
            self.Initializare_DockerSwarm()
            self.rulare_DockerApp()
            self.Get_Tokens()
            self.sincronizare_Keycloak_BD()
            self.teste_USER_Service()
            self.test_Specializari()
            self.test_Cabinete()
            self.test_Doctor_Service()
        except Exception as e:
            print(f"\n{colors['RED']}Eroare: {str(e)}{colors['RESET']}")
        finally:
            self.rezultate()
            self.inchidere_DockerApp()


def main():
    app = TestApp()
    app.all_tests()


if __name__ == "__main__":
    main()