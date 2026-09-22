# Atlas Labels: ejecutable para Windows

Genera un `.exe` que abre la app de etiquetas con doble clic, sin terminal ni Python visible.

## Generar

En PowerShell, en la raíz del repo, con el Python de Windows instalado:

```powershell
.\installers\labels\build_exe.ps1
```

El script instala PyInstaller y las dependencias, produce `dist\Atlas Labels.exe` y deja el acceso directo `Atlas Labels` en el escritorio.

## Notas

- El `.exe` no está firmado; Windows Defender o el antivirus pueden pedir confirmación la primera vez. Si lo bloquea, agrega una exclusión para `dist\Atlas Labels.exe`.
- El binario pesa entre 15 y 25 MB porque incluye Python y Tkinter.
- Hay que regenerarlo cada vez que cambie el código de `atlas_labels/`.
- La impresora preferida se sigue guardando en `%USERPROFILE%\.atlas_labels.json`.
