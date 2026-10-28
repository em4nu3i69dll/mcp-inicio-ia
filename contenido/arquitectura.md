# Arquitectura de ejemplo

El proyecto ficticio Faro tiene tres servicios llamados portal, api y respaldos.
El portal muestra la información que recibe de la API.
La API escucha exclusivamente en loopback y conserva sus datos en SQLite.
Cloudflare Tunnel conecta el dominio público con el portal.
La consulta interna de la API requiere certificado cliente.

## Fuentes

La documentación describe decisiones y procedimientos.
Una descripción no prueba que un servicio esté disponible en este momento.
Para comprobar disponibilidad se consulta la API de estado.
