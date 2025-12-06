#!/bin/bash

# Configurare
KEYCLOAK_URL="http://localhost:8080"
REALM="medical-clinica"
CLIENT_ID="medical-app"

# Porturi Servicii
USER_SERVICE_URL="http://localhost:5001"
# DOCTOR_SERVICE_URL="http://localhost:5002" 
# APPOINTMENT_SERVICE_URL="http://localhost:5003"

# Culori pentru output
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1 -> verificam argumentele
ROLE=$1
METHOD=$2
ENDPOINT=$3
DATA=$4

if [ -z "$ROLE" ] || [ -z "$METHOD" ] || [ -z "$ENDPOINT" ]; then
    echo "Utilizare: ./test.sh <ROL> <METODA> <ENDPOINT> [JSON_DATA]"
    echo "Exemplu:   ./test.sh admin GET /users"
    echo "Exemplu:   ./test.sh patient POST /users/sync-keycloak"
    echo "Roluri disponibile: admin, doctor, patient"
    exit 1
fi

# 2 --> pentru usurinta am setat deja useri pe care i am predefinit in realm la export
# Deci doar alegem userul si parola in functie de rolul dat ca argument si am mai adaugat
# eu unu cand inregistrez unu nou
case $ROLE in
  admin)
    USERNAME="admin"
    PASSWORD="admin123"
    ;;
  doctor)
    USERNAME="doctor1"
    PASSWORD="doctor123"
    ;;
  patient)
    USERNAME="patient1"
    PASSWORD="patient123"
    ;;
  nou)
    USERNAME="pacient_nou@test.com"  # Atentie: Keycloak foloseste username=email
    USERNAME="pacient_nou@test.com"
    PASSWORD="parola_noua_123"
    ;;
  *)
    echo -e "${RED}Rol necunoscut! Folosește: admin, doctor, patient${NC}"
    exit 1
    ;;
esac

echo -e "Authentication as ${GREEN}$USERNAME${NC}..."

# 3 --> luam token-ul de la Keycloak (Ascuns de utilizator)
TOKEN_RESPONSE=$(curl -s -X POST "$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$USERNAME" \
  -d "password=$PASSWORD" \
  -d "grant_type=password" \
  -d "client_id=$CLIENT_ID")

# extragem doar access_token (folosind grep/sed pentru a nu depinde de jq)
TOKEN=$(echo $TOKEN_RESPONSE | grep -o '"access_token":"[^"]*' | grep -o '[^"]*$')

if [ -z "$TOKEN" ]; then
    echo -e "${RED}Eroare la autentificare! Verifica Keycloak.${NC}"
    echo "Raspuns Keycloak: $TOKEN_RESPONSE"
    exit 1
fi

# 4 --> Alegem URL-ul serviciului (Momentan testam User Service pe 5001)
# Daca endpoint-ul începe cu /users, merge la 5001.
TARGET_URL="$USER_SERVICE_URL$ENDPOINT"

echo -e "Calling: ${GREEN}$METHOD $TARGET_URL${NC}"

# 5 --> Facem cererea finala cu tokenul
if [ -z "$DATA" ]; then
    # Cerere fara body (GET, DELETE)
    curl -s -X $METHOD "$TARGET_URL" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json"
else
    # Cerere cu body (POST, PUT)
    curl -s -X $METHOD "$TARGET_URL" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "$DATA"
fi

echo ""