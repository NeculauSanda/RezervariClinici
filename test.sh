#!/bin/bash

# Configurare
KEYCLOAK_URL="http://localhost:8080"
REALM="medical-clinica"
CLIENT_ID="medical-app"

# Porturi Servicii
USER_SERVICE_URL="http://localhost:5001"
DOCTOR_SERVICE_URL="http://localhost:5002" 
APPOINTMENT_SERVICE_URL="http://localhost:5003"
NOTIFICATION_SERVICE_URL="http://localhost:5004"

# Culori pentru output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 1 -> verificam argumentele
ROLE=$1
METHOD=$2
ENDPOINT=$3
DATA=$4

if [ -z "$ROLE" ] || [ -z "$METHOD" ] || [ -z "$ENDPOINT" ]; then
    echo -e "Utilizare: ${GREEN}./test.sh <ROL> <METODA> <ENDPOINT> [JSON_DATA]${NC}"
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
    USERNAME="pacient_nou@test.com"  # Keycloak foloseste username=email
    PASSWORD="parola_noua_123"
    ;;
  *)
    echo -e "${RED}Rol necunoscut! FOLOSESTE: admin, doctor, patient${NC}"
    exit 1
    ;;
esac

echo -e "Authentication as ${GREEN}$USERNAME${NC}..."

# 3 --> luam token-ul de la Keycloak (Ascuns de utilizator) - aici e grant user doar pe partea de frontend (simuleaza logarea)
TOKEN_RESPONSE=$(curl -s -X POST "$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$USERNAME" \
  -d "password=$PASSWORD" \
  -d "grant_type=password" \
  -d "client_id=$CLIENT_ID")

# extragem doar access_token
TOKEN=$(echo $TOKEN_RESPONSE | grep -o '"access_token":"[^"]*' | grep -o '[^"]*$')

if [ -z "$TOKEN" ]; then
    echo -e "${RED}Eroare la autentificare! Verifica Keycloak.${NC}"
    echo "Raspuns Keycloak: $TOKEN_RESPONSE"
    exit 1
fi

# 4 --> Alegem URL-ul serviciului (Momentan testam User Service pe 5001 si DOCTOR pe 5002)
# Daca endpoint-ul incepe cu /users, merge la 5001.
# Detectare serviciu pe baza endpoint-ului
if [[ $ENDPOINT == /doctors* ]] || [[ $ENDPOINT == /specializations* ]] || [[ $ENDPOINT == /cabinets* ]]; then
    TARGET_URL="$DOCTOR_SERVICE_URL$ENDPOINT"
    SERVICE_NAME="DOCTOR-SERVICE"
elif [[ $ENDPOINT == /appointments* ]]; then
    TARGET_URL="$APPOINTMENT_SERVICE_URL$ENDPOINT"
    SERVICE_NAME="APPOINTMENT-SERVICE"
elif [[ $ENDPOINT == /events* ]]; then
    TARGET_URL="$APPOINTMENT_SERVICE_URL$ENDPOINT"
    SERVICE_NAME="APPOINTMENT-SERVICE"
elif [[ $ENDPOINT == /notifications* ]]; then  
    TARGET_URL="$NOTIFICATION_SERVICE_URL$ENDPOINT"
    SERVICE_NAME="NOTIFICATION-SERVICE"
elif [[ $ENDPOINT == /users* ]]; then
    TARGET_URL="$USER_SERVICE_URL$ENDPOINT"
    SERVICE_NAME="USER-SERVICE"
else
    # Default
    TARGET_URL="$USER_SERVICE_URL$ENDPOINT"
    SERVICE_NAME="USER-SERVICE"
fi

echo -e "${BLUE}[$SERVICE_NAME]${NC} ${YELLOW}$METHOD${NC} ${GREEN}$TARGET_URL${NC}"

#5-> cerere finala
if [ -z "$DATA" ]; then
    # Cerere fara body (GET, DELETE)
    RESPONSE=$(curl -s -X $METHOD "$TARGET_URL" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json")
else
    # Cerere cu body (POST, PUT)
    RESPONSE=$(curl -s -X $METHOD "$TARGET_URL" \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      -d "$DATA")
fi

# Format raspuns
echo "$RESPONSE" | python -m json.tool 2>/dev/null || echo "$RESPONSE"


echo ""