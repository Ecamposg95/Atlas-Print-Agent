; Instalador del agente de impresión Atlas para Windows.
; Por usuario, sin UAC: instala en %LOCALAPPDATA%\Programs\AtlasPrintAgent y registra
; una tarea programada al inicio de sesión (registrar.ps1).
; Compilar desde la raíz, con ATLAS_VERSION definida:
;   $env:ATLAS_VERSION = python installers\agent\version_agente.py
;   & "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" installers\agent\windows\atlas-print-agent.iss

#define Version GetEnv("ATLAS_VERSION")
#if Version == ""
  #error "Define ATLAS_VERSION antes de compilar"
#endif

[Setup]
AppId={{28FFA762-984A-4E97-8200-EAA05330F3BD}
AppName=Agente de Impresión Atlas
AppVersion={#Version}
AppPublisher=Atlas Technologies
DefaultDirName={localappdata}\Programs\AtlasPrintAgent
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\..\dist
OutputBaseFilename=atlas-print-agent-setup-{#Version}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=Agente de Impresión Atlas
UninstallDisplayIcon={app}\atlas-print-agent.exe
CloseApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
Source: "..\..\..\dist\agent\atlas-print-agent\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "registrar.ps1"; DestDir: "{app}\instalador"; Flags: ignoreversion
Source: "tarea.xml"; DestDir: "{app}\instalador"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\Agente de Impresión Atlas"; Filename: "{app}\atlas-print-agent.exe"
Name: "{userdesktop}\Agente de Impresión Atlas"; Filename: "{app}\atlas-print-agent.exe"

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\instalador\registrar.ps1"" -Quitar"; Flags: runhidden waituntilterminated; RunOnceId: "QuitarTarea"

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codigo: Integer;
begin
  // Una actualización no puede reemplazar el .exe mientras corre, y el disparador
  // de cada minuto lo relanzaría a media copia: primero se apaga la tarea.
  // registrar.ps1 la vuelve a registrar (y habilitar) al final.
  Exec('schtasks.exe', '/End /TN "Atlas Print Agent"', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Exec('schtasks.exe', '/Change /TN "Atlas Print Agent" /DISABLE', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Exec('taskkill.exe', '/F /IM atlas-print-agent.exe', '', SW_HIDE, ewWaitUntilTerminated, Codigo);
  Result := '';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Codigo: Integer;
  Parametros: String;
begin
  if CurStep = ssPostInstall then
  begin
    WizardForm.StatusLabel.Caption := 'Arrancando el agente y comprobando que responda...';
    Parametros := '-NoProfile -ExecutionPolicy Bypass -File "' + ExpandConstant('{app}\instalador\registrar.ps1') +
                  '" -Exe "' + ExpandConstant('{app}\atlas-print-agent.exe') + '" -Version "{#Version}"';
    if (not Exec('powershell.exe', Parametros, '', SW_HIDE, ewWaitUntilTerminated, Codigo)) or (Codigo <> 0) then
      MsgBox('El agente quedó instalado pero NO respondió en https://127.0.0.1:9100/health.' + #13#10 + #13#10 +
             'La caja todavía no imprime. Revisa este archivo y llama a soporte:' + #13#10 +
             ExpandConstant('{localappdata}\AtlasPrintAgent\instalador.log'),
             mbCriticalError, MB_OK);
  end;
end;
