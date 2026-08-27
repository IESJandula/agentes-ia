#!/bin/bash
# Crea (idempotente) el cliente público PKCE `agentes` en el realm del centro,
# para que el frontal del agente autentique con Keycloak.
#
# Es el gemelo de configure-accesos-client.sh y configure-guardias-client.sh del
# repo vegaies: MISMO realm, mismos roles (`profesor`, `directiva`, `admin`) y
# mismo reparto desde el Directorio. Aquí no se crea ningún rol nuevo: si hubiera
# uno propio del agente, habría que asignarlo a mano usuario por usuario y se
# quedaría puesto para siempre.
#
#   KEYCLOAK_URL=https://sso.tucentro.es \
#   KC_ADMIN_USER=admin KC_ADMIN_PASSWORD=… \
#   AGENTES_ORIGIN=https://agente.tucentro.es \
#   bash infra/keycloak/configure-agentes-client.sh
#
# Orígenes por defecto: dev en http://localhost:8010 (el puerto del contenedor).
set -euo pipefail

KC_URL="${KEYCLOAK_URL:-http://localhost:8080}"
ADMIN_REALM="${KEYCLOAK_ADMIN_REALM:-master}"
ADMIN_USER="${KC_ADMIN_USER:-admin}"
ADMIN_PASS="${KC_ADMIN_PASSWORD:-admin}"
REALM="${KEYCLOAK_REALM:-vegaies}"
CLIENT_ID="${AGENTES_CLIENT_ID:-agentes}"
ORIGIN="${AGENTES_ORIGIN:-http://localhost:8010}"

jsonget() { node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{const d=JSON.parse(s);process.stdout.write(String(eval('d'+process.argv[1])))})" "$1"; }

echo "→ Token admin de Keycloak…"
TOKEN=$(curl -s -X POST "$KC_URL/realms/$ADMIN_REALM/protocol/openid-connect/token" \
  -d "client_id=admin-cli" -d "username=$ADMIN_USER" -d "password=$ADMIN_PASS" \
  -d "grant_type=password" | jsonget ".access_token")
AUTH=(-H "Authorization: Bearer $TOKEN")

read -r -d '' BODY <<JSON || true
{
  "clientId": "$CLIENT_ID",
  "name": "Agentes IA (front)",
  "enabled": true,
  "protocol": "openid-connect",
  "publicClient": true,
  "standardFlowEnabled": true,
  "directAccessGrantsEnabled": false,
  "redirectUris": ["$ORIGIN/*"],
  "webOrigins": ["$ORIGIN"],
  "attributes": {
    "pkce.code.challenge.method": "S256",
    "post.logout.redirect.uris": "$ORIGIN/*"
  }
}
JSON

CID=$(curl -s "${AUTH[@]}" "$KC_URL/admin/realms/$REALM/clients?clientId=$CLIENT_ID" \
  | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{const a=JSON.parse(s);process.stdout.write(a.length?a[0].id:'')})")

if [ -z "$CID" ]; then
  echo "→ Creando cliente $CLIENT_ID (origen $ORIGIN)…"
  curl -s -X POST "${AUTH[@]}" -H "Content-Type: application/json" \
    "$KC_URL/admin/realms/$REALM/clients" -d "$BODY" -w "  POST -> %{http_code}\n"
else
  echo "→ Actualizando cliente $CLIENT_ID ($CID)…"
  curl -s -X PUT "${AUTH[@]}" -H "Content-Type: application/json" \
    "$KC_URL/admin/realms/$REALM/clients/$CID" -d "$BODY" -w "  PUT -> %{http_code}\n"
fi

echo "✔ Cliente $CLIENT_ID listo (público, PKCE S256, origen $ORIGIN)."
echo "  El front del agente usará: realm=$REALM, clientId=$CLIENT_ID."
echo ""
echo "  Los roles ('profesor' para consultar, 'directiva' para administrar) los"
echo "  reparte el sync desde el Directorio: no hay que asignar nada a mano."
