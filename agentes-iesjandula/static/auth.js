/**
 * auth.js — sesión de Keycloak para el frontal del agente.
 *
 * Equivalente de `apps/accesos-web/src/keycloak.ts` + `stores/auth.js` de
 * vegaies, escrito como módulo ES suelto porque aquí no hay build: el HTML se
 * sirve tal cual desde FastAPI.
 *
 * Uso:
 *   import { iniciarSesion, sesion, apiFetch, cerrarSesion } from '/static/auth.js';
 *   await iniciarSesion();            // redirige al login si no hay sesión
 *   sesion.esAdmin                    // ¿puede gestionar la base de conocimiento?
 *   await apiFetch('/api/rag/kb')     // fetch con el Bearer puesto y renovado
 */
import Keycloak from '/static/vendor/keycloak.js';

/** Identidad del usuario en curso. Se rellena al iniciar sesión. */
export const sesion = {
  autenticado: false,
  email: null,
  nombre: null,
  roles: [],
  esAdmin: false,
};

let keycloak = null;

/** Mismos roles que el backend (`app/auth/roles.py`). Si cambian, cambian ahí primero. */
const ROLES_ADMIN = ['directiva', 'admin'];

/**
 * Arranca la sesión. Si no hay ninguna, redirige a Keycloak.
 *
 * `check-sso` con iframe oculto primero: si el usuario ya entró en Guardias o
 * en Accesos, aquí entra directo y sin ver ninguna pantalla de login. Solo si
 * no hay sesión en ningún sitio se hace la redirección visible.
 */
export async function iniciarSesion() {
  if (keycloak) return sesion;

  const cfg = await fetch('/api/config').then((r) => r.json());
  const { url, realm, clientId } = cfg.keycloak;

  keycloak = new Keycloak({ url, realm, clientId });

  let autenticado = await keycloak.init({
    onLoad: 'check-sso',
    silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
    pkceMethod: 'S256', // Authorization Code Flow con PKCE (sin secreto en el front)
    checkLoginIframe: false,
  });

  if (!autenticado) {
    // `idpHint: 'google'` salta la pantalla propia de Keycloak y va directo a
    // Google, igual que en vegaies: un solo login visible, no dos.
    await keycloak.login({ idpHint: 'google' });
    return sesion; // la línea anterior navega fuera; esto no llega a ejecutarse
  }

  const t = keycloak.tokenParsed ?? {};
  const roles = t.realm_access?.roles ?? [];

  sesion.autenticado = true;
  sesion.email = t.email ?? null;
  sesion.nombre = t.name ?? t.preferred_username ?? null;
  sesion.roles = roles;
  sesion.esAdmin = roles.some((r) => ROLES_ADMIN.includes(r));

  return sesion;
}

export function cerrarSesion() {
  return keycloak?.logout({ redirectUri: window.location.origin });
}

/**
 * `fetch` con el token puesto.
 *
 * Renueva el token si le quedan menos de 30 segundos: una respuesta del agente
 * puede tardar bastante, y sin esto un token que caduca a mitad de conversación
 * convierte la siguiente pregunta en un 401 sin explicación.
 */
export async function apiFetch(url, opciones = {}) {
  if (keycloak) {
    try {
      await keycloak.updateToken(30);
    } catch {
      // El refresh ha caducado: no queda sesión que renovar.
      await keycloak.login({ idpHint: 'google' });
      return new Promise(() => {}); // navegando fuera; no resolvemos
    }
  }

  const cabeceras = new Headers(opciones.headers || {});
  if (keycloak?.token) cabeceras.set('Authorization', `Bearer ${keycloak.token}`);

  const res = await fetch(url, { ...opciones, headers: cabeceras });

  if (res.status === 401) {
    await keycloak?.login({ idpHint: 'google' });
    return new Promise(() => {});
  }
  return res;
}

/** Token en crudo, para los sitios donde no se puede usar `apiFetch`. */
export async function token() {
  if (!keycloak) return null;
  try {
    await keycloak.updateToken(30);
  } catch {
    return null;
  }
  return keycloak.token ?? null;
}
