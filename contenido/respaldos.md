# Respaldos de ejemplo

Los respaldos de Faro se realizan todos los días a las 03.00 UTC.
La retención es de siete copias diarias y cuatro semanales.
El respaldo de SQLite se realiza con la API online de la biblioteca.
La copia se comprueba con PRAGMA quick_check antes de transferirse.

## Restauración

Primero se detiene la aplicación que escribe en la base de destino.
Se guarda una copia de la base actual antes de reemplazarla.
Después se restaura en un directorio de prueba y se comprueba su integridad.
El responsable valida el resultado antes de aplicar el cambio al servicio.
La restauración no la ejecuta este MCP.
