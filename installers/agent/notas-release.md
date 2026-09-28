## ¿Qué archivo descargo?

| Caja | Archivo | Cómo se instala |
|---|---|---|
| Ubuntu 22.04 o más nuevo (PC normal, 64 bits) | `atlas-print-agent_<versión>_amd64.deb` | `sudo apt install ./atlas-print-agent_<versión>_amd64.deb` |
| Mac con chip Apple (M1, M2, M3, M4…) | `atlas-print-agent-<versión>-arm64.pkg` | doble clic |
| Mac con procesador Intel | `atlas-print-agent-<versión>-x86_64.pkg` | doble clic |
| Windows 10 u 11 | `atlas-print-agent-setup-<versión>.exe` | doble clic |

**¿Mac con chip Apple o Intel?** Menú  → *Acerca de esta Mac*: si dice *Chip Apple M…* es `arm64`; si dice
*Procesador Intel* es `x86_64`. Elegir mal se descubre hasta el doble clic.

Los instaladores no están firmados: Windows mostrará *"Windows protegió su PC"* (→ *Más información* →
*Ejecutar de todas formas*) y macOS pedirá abrirlo con clic derecho → *Abrir*. Detalles en
`installers/agent/README.md`.
