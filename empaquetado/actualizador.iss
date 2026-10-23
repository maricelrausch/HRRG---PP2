; Inno Setup 6 - Actualizacion LIVIANA de IngenIA Salud – Triage
; Solo reemplaza la app (sin Ollama, sin modelos, sin Whisper).
; Requiere que el instalador completo ya se haya instalado antes en esa PC.
; Se compila con construir_actualizacion.bat.
; IMPORTANTE: AppVersion debe coincidir con la de instalador.iss.

#define AppName "IngenIA Salud – Triage"
#define AppVersion "0.1.0"
#define AppExe "IngenIA.exe"
#define AppId "{B7E2C4A1-5D3F-4E8A-9C61-2F0D8A7B3E15}"

[Setup]
; Mismo AppId que el instalador completo: actualiza la misma instalación
AppId={{#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Equipo 1 - HRRG - PP2 2C 2026
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\IngenIA Salud Triage
UsePreviousAppDir=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=salida\actualizacion
OutputBaseFilename=Actualizacion_IngenIA_Salud_Triage_{#AppVersion}
SetupIconFile=salida\icono.ico
UninstallDisplayIcon={app}\{#AppExe}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[InstallDelete]
; Borra la app anterior para no dejar librerías viejas mezcladas
Type: filesandordirs; Name: "{app}\_internal"
Type: filesandordirs; Name: "{app}\frontend"

[Files]
Source: "salida\dist\IngenIA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir {#AppName}"; Flags: postinstall nowait skipifsilent

[Code]
function InitializeSetup: Boolean;
begin
  Result := RegKeyExists(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#AppId}_is1');
  if not Result then
    MsgBox('{#AppName} no está instalado en esta PC.' + #13#10 +
           'Primero ejecute el instalador completo.', mbError, MB_OK);
end;
