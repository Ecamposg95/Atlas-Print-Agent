# Contexto técnico: Configuración de impresoras térmicas en Linux para POS

## 1. Objetivo

Documentar el aprendizaje obtenido durante la configuración de impresoras térmicas de 80 mm en Ubuntu/Linux, con el fin de mejorar el agente de impresión local usado por el sistema POS.

El objetivo del agente debe ser detectar, configurar, validar e imprimir tickets en impresoras térmicas USB compatibles con ESC/POS, reduciendo errores comunes como caracteres raros, ancho incorrecto de papel o selección equivocada de driver.

---

## 2. Entorno validado

Se trabajó sobre equipos Linux/Ubuntu recién instalados, usando CUPS como sistema de impresión.

Componentes principales:

```text
Sistema operativo: Ubuntu / Linux
Sistema de impresión: CUPS
Tipo de impresora: térmica 80 mm
Uso: tickets POS
Modo recomendado: RAW
Lenguaje de impresión: ESC/POS
Comando de impresión: lp
```

---

## 3. Impresoras probadas

### Nextep POS80

Detectada inicialmente como:

```text
usb://POS80%20Series%20%20%20%20%20/POS80%20Printer%20USB?serial=83700000000
```

Nombre de cola recomendado:

```text
nextep80
```

### BIXOLON SRP-330II

Detectada como:

```text
usb://BIXOLON/SRP-330II?serial=00000001
```

Nombre de cola recomendado:

```text
bixolon80
```

---

## 4. Aprendizaje principal

El aprendizaje más importante es que para impresoras térmicas POS genéricas o compatibles ESC/POS, no conviene usar drivers gráficos tradicionales de CUPS.

Al usar drivers como:

```text
Generic ESC/P Dot Matrix Printer
Foomatic/epson
IPP Everywhere
PostScript
PDF
PCL
```

pueden aparecer problemas como:

```text
- caracteres raros
- texto corrupto
- impresión ilegible
- formato incorrecto
- pérdida del ancho útil de 80 mm
```

La solución que funcionó correctamente fue crear una cola CUPS en modo:

```text
raw
```

Esto permite enviar comandos ESC/POS directamente a la impresora.

---

## 5. Instalación base recomendada

El agente debe validar que CUPS esté instalado y activo.

Comandos base:

```bash
sudo apt update
sudo apt install cups cups-client system-config-printer -y
sudo systemctl enable cups
sudo systemctl start cups
sudo usermod -aG lpadmin $USER
```

Después de agregar el usuario a `lpadmin`, puede ser necesario cerrar sesión, reiniciar o ejecutar:

```bash
newgrp lpadmin
```

---

## 6. Detección de impresoras

El agente debe usar:

```bash
lpinfo -v
```

para detectar dispositivos de impresión.

Ejemplos reales:

```text
direct usb://POS80%20Series%20%20%20%20%20/POS80%20Printer%20USB?serial=83700000000
direct usb://BIXOLON/SRP-330II?serial=00000001
```

Reglas de detección recomendadas:

```text
Si aparece "usb://POS80" → probablemente impresora térmica genérica 80 mm.
Si aparece "usb://BIXOLON" → impresora BIXOLON.
Si aparece "socket://IP:9100" → impresora térmica por red.
Si no aparece USB → revisar cable, encendido, permisos o conexión.
```

También puede usarse:

```bash
lsusb
```

pero `lpinfo -v` fue más útil para obtener la URI exacta de impresión.

---

## 7. Creación de cola RAW

### Para Nextep POS80

```bash
sudo lpadmin -p nextep80 -E -v 'usb://POS80%20Series%20%20%20%20%20/POS80%20Printer%20USB?serial=83700000000' -m raw
sudo cupsenable nextep80
sudo cupsaccept nextep80
sudo lpoptions -d nextep80
```

### Para BIXOLON SRP-330II

```bash
sudo lpadmin -p bixolon80 -E -v 'usb://BIXOLON/SRP-330II?serial=00000001' -m raw
sudo cupsenable bixolon80
sudo cupsaccept bixolon80
sudo lpoptions -d bixolon80
```

---

## 8. Validación de instalación

Después de crear la cola, el agente debe validar con:

```bash
lpstat -p -d
```

También puede revisar trabajos pendientes:

```bash
lpstat -o
```

Y estado completo:

```bash
lpstat -t
```

---

## 9. Prueba básica de impresión

Prueba mínima:

```bash
echo "PRUEBA DE IMPRESION" | lp -d bixolon80
```

o:

```bash
echo "PRUEBA DE IMPRESION" | lp -d nextep80
```

Si imprime caracteres raros, casi siempre significa que se configuró con driver incorrecto y debe recrearse como `raw`.

---

## 10. Comando ESC/POS funcional

El formato que funcionó correctamente para usar todo el ancho del papel de 80 mm fue:

```bash
printf '\x1b\x40\x1b\x4d\x01'\
'========================================================\n'\
'                     RMAZH TOLUCA                       \n'\
'                  TICKET DE PRUEBA                      \n'\
'========================================================\n'\
'Fecha: 20/04/2026                    Hora: 13:00        \n'\
'Caja : 01                            Cajero: ADMIN      \n'\
'--------------------------------------------------------\n'\
'CANT  DESCRIPCION                          IMPORTE      \n'\
'--------------------------------------------------------\n'\
'1     Playera Negra Premium                250.00       \n'\
'2     Gorra Logo RMAZH                     300.00       \n'\
'1     Sudadera Oversize                    499.00       \n'\
'1     Sticker Pack                          49.00       \n'\
'--------------------------------------------------------\n'\
'SUBTOTAL                                  1098.00       \n'\
'IVA                                          0.00       \n'\
'TOTAL                                     1098.00       \n'\
'--------------------------------------------------------\n'\
'Metodo de pago: EFECTIVO                                 \n'\
'Recibido:                                1200.00        \n'\
'Cambio:                                   102.00        \n'\
'--------------------------------------------------------\n'\
'              Gracias por su compra                    \n'\
'                 Instagram: @rmazh.mx                  \n'\
'\n\n\n\n' | lp -d bixolon80
```

Para Nextep, solo cambia:

```bash
lp -d bixolon80
```

por:

```bash
lp -d nextep80
```

---

## 11. Comandos ESC/POS aprendidos

```text
\x1b\x40
```

Inicializa la impresora. Limpia configuración previa y deja la impresora en estado base.

```text
\x1b\x4d\x01
```

Activa fuente compacta. Fue clave para aprovechar mejor el ancho del papel de 80 mm.

Saltos al final:

```text
\n\n\n\n
```

Ayudan a alimentar papel al terminar el ticket.

---

## 12. Recomendación de ancho de ticket

Para 80 mm, el ancho funcional fue cercano a:

```text
56 caracteres por línea
```

El agente debe formatear tickets con líneas fijas de aproximadamente 56 columnas cuando use:

```text
ESC/POS + fuente compacta
```

Ejemplo:

```text
========================================================
```

equivale a 56 caracteres.

Este ancho funcionó mejor que plantillas de 32 o 42 caracteres, porque aprovecha más el papel.

---

## 13. Reglas de formato recomendadas para el agente

El agente debe construir tickets con alineación fija.

### Encabezado

```text
========================================================
                     RMAZH TOLUCA
                  TICKET DE VENTA
========================================================
```

### Datos operativos

```text
Fecha: 20/04/2026                    Hora: 13:00
Caja : 01                            Cajero: ADMIN
```

### Tabla

```text
--------------------------------------------------------
CANT  DESCRIPCION                          IMPORTE
--------------------------------------------------------
1     Producto ejemplo                      250.00
2     Otro producto                         300.00
--------------------------------------------------------
TOTAL                                      550.00
```

### Footer

```text
--------------------------------------------------------
              Gracias por su compra
                 Instagram: @rmazh.mx
```

---

## 14. Lógica recomendada para Python

El agente no debe depender de impresión PDF para tickets simples. Debe generar texto ESC/POS y enviarlo directamente a CUPS usando `lp`.

Ejemplo conceptual:

```python
import subprocess

printer_name = "bixolon80"

ticket = (
    "\x1b\x40\x1b\x4d\x01"
    "========================================================\n"
    "                     RMAZH TOLUCA                       \n"
    "                  TICKET DE VENTA                       \n"
    "========================================================\n"
    "Fecha: 20/04/2026                    Hora: 13:00        \n"
    "Caja : 01                            Cajero: ADMIN      \n"
    "--------------------------------------------------------\n"
    "CANT  DESCRIPCION                          IMPORTE      \n"
    "--------------------------------------------------------\n"
    "1     Playera Negra Premium                250.00       \n"
    "--------------------------------------------------------\n"
    "TOTAL                                      250.00       \n"
    "--------------------------------------------------------\n"
    "              Gracias por su compra                    \n"
    "\n\n\n\n"
)

subprocess.run(
    ["lp", "-d", printer_name],
    input=ticket.encode("latin-1"),
    check=True
)
```

---

## 15. Recomendaciones para el agente de impresión

El agente debería incluir estas funciones:

```text
1. Detectar impresoras disponibles con lpinfo -v
2. Identificar posibles térmicas USB por nombre o URI
3. Crear cola CUPS en modo raw
4. Habilitar y aceptar trabajos en la cola
5. Definir impresora predeterminada
6. Ejecutar prueba básica
7. Ejecutar prueba ESC/POS ancha
8. Validar si hay trabajos pendientes o cola detenida
9. Permitir seleccionar perfil de impresora
10. Guardar configuración local
```

---

## 16. Perfiles sugeridos

```json
{
  "nextep80": {
    "brand": "Nextep",
    "model": "POS80",
    "cups_queue": "nextep80",
    "mode": "raw",
    "encoding": "latin-1",
    "width_chars": 56,
    "init_command": "\\x1b\\x40\\x1b\\x4d\\x01"
  },
  "bixolon80": {
    "brand": "BIXOLON",
    "model": "SRP-330II",
    "cups_queue": "bixolon80",
    "mode": "raw",
    "encoding": "latin-1",
    "width_chars": 56,
    "init_command": "\\x1b\\x40\\x1b\\x4d\\x01"
  }
}
```

---

## 17. Problemas comunes y solución

### Problema: caracteres raros

Causa probable:

```text
Driver incorrecto en CUPS.
```

Solución:

```text
Eliminar impresora y recrearla en modo raw.
```

Comando:

```bash
sudo lpadmin -x nombre_impresora
sudo lpadmin -p nombre_impresora -E -v 'URI_USB' -m raw
```

---

### Problema: no usa todo el ancho del papel

Causa probable:

```text
Fuente muy grande o ticket formateado con pocas columnas.
```

Solución:

```text
Usar ESC/POS con fuente compacta:
\x1b\x4d\x01
```

y plantilla de aproximadamente 56 caracteres.

---

### Problema: no aparece la impresora

Validar:

```bash
lpinfo -v
lsusb
sudo systemctl status cups
```

Acciones:

```text
- revisar cable USB
- revisar encendido
- cambiar puerto USB
- reiniciar CUPS
- confirmar que tenga papel
```

---

### Problema: los trabajos se quedan pendientes

Validar:

```bash
lpstat -o
lpstat -t
```

Solución:

```bash
sudo cupsenable nombre_impresora
sudo cupsaccept nombre_impresora
sudo systemctl restart cups
```

---

## 18. Recomendación arquitectónica

Para el POS de Atlas/DataX POS, lo recomendable es que el módulo de impresión Linux funcione como un Print Agent local, no como impresión tradicional desde navegador.

Arquitectura sugerida:

```text
POS Web / Atlas ERP
        ↓
Print Agent local en Linux
        ↓
Generador de ticket ESC/POS
        ↓
CUPS raw queue
        ↓
Impresora térmica USB / red
```

Beneficios:

```text
- evita depender del diálogo de impresión del navegador
- permite corte de papel
- permite apertura de cajón
- permite control fino del ancho
- permite tickets rápidos
- reduce errores de driver
```

---

## 19. Reglas finales para implementación

El agente debe priorizar esta ruta:

```text
1. Usar CUPS solo como canal de envío.
2. No depender de drivers gráficos.
3. Crear colas raw para térmicas POS.
4. Generar tickets como texto ESC/POS.
5. Usar fuente compacta para 80 mm.
6. Mantener plantillas de 56 caracteres.
7. Guardar perfiles por impresora.
8. Permitir pruebas desde CLI.
9. Registrar logs de instalación e impresión.
10. Dar mensajes claros al usuario final.
```

---

## 20. Conclusión

La configuración más estable para impresoras térmicas POS en Ubuntu fue:

```text
CUPS + cola raw + ESC/POS + fuente compacta
```

Para Nextep POS80 y BIXOLON SRP-330II, esta configuración permitió imprimir correctamente tickets de 80 mm, evitar caracteres raros y aprovechar el ancho del papel.

La configuración funcional debe convertirse en estándar para el agente de impresión Linux del POS.
