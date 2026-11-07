# andromeda-contrato

Contrato compartido entre la app acompañante (**repo B**) y la casa (**repo A**).
No es una app, no es un servidor y no se despliega: es la dependencia de compilación
que ambos leen y ejecutan en sus tests.

## Repos

| Repo | Qué es |
|---|---|
| **A** `doha-server-motog` | La casa: residente, gateway, luces, cámara, mensajes |
| **B** `andromeda-movil` | La app del teléfono |
| **C** `andromeda-contrato` | Este repo: el idioma común |

No hay repo D. Cloudflare no se usa.

## Qué contiene

```
home-api-v1/
  openapi.json     endpoints, campos, tipos y errores
  policies.json    nombres de políticas que Python y Java deben compartir
  limits.json      límites de comandos, mensajes y cámara
  errors.json      códigos de error y su HTTP
  vectors/         ejemplos petición/respuesta que A y B ejecutan
tools/verify.py    valida todo sin dependencias externas
VERSION            versión del contrato
SHA256SUMS         huellas de los archivos, para copias vendorizadas
```

## Cómo se consume

Cada repo guarda una copia vendorizada de `home-api-v1/`, `VERSION` y `SHA256SUMS`
dentro de su carpeta `contract/`. No hay submódulo ni descarga en tiempo de ejecución.
Actualizar el contrato es un acto deliberado: se copia la nueva versión y se corre
`verify.py`. Esto mantiene los repos independientes y evita que un cambio silencioso
en un lado rompa el otro.

Los tests de A y B deben comprobar:

1. Que `VERSION` y `policies.json` coinciden con sus constantes.
2. Que los límites de `limits.json` son los que usa el código.
3. Que los vectores de `vectors/` siguen pasando.

Si Python y Java divergen, el test falla antes de llegar al teléfono.

## Reglas de compatibilidad

- `contract` es un entero mayor: `1`.
- Solo se permiten cambios aditivos dentro de la misma versión mayor.
- Un cambio incompatible obliga a `contract: 2` y a que la casa soporte ambas
  versiones mientras la app se actualiza.
- La app envía `X-Andromeda-Contract: 1`. La casa responde `426 unsupported_version`
  si no lo entiende.

## Seguridad

- Este repo no contiene tokens, claves, certificados ni datos de nadie.
- El token de dispositivo vive en el Keystore del teléfono.
- El certificado del gateway se fija por SHA-256 en la app.
- El transporte es Tailscale; no hay puerto público.
- La casa rechaza cualquier origen que no sea `100.64.0.0/10`.
- Las políticas y los límites son datos, no secretos.

## Verificar

```powershell
python tools/verify.py
```

Debe imprimir `OK: contrato 1.0.0, ...`.

## Cambiar el contrato

1. Edita los archivos de `home-api-v1/`.
2. Actualiza `VERSION` si cambia la versión mayor o menor.
3. Regenera `SHA256SUMS`.
4. Corre `python tools/verify.py`.
5. Copia `home-api-v1/`, `VERSION` y `SHA256SUMS` a `contract/` en A y B.
6. Actualiza las constantes de Python/Java/Kotlin y corre los tests de ambos repos.
