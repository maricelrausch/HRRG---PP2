; Inno Setup 6 - Instalador offline de IngenIA Salud
; Se compila desde construir.bat (requiere haber generado la carpeta salida\).

#define AppName "IngenIA Salud – Triage"
#define AppVersion "0.1.0"
#define AppExe "IngenIA.exe"

[Setup]
AppId={{B7E2C4A1-5D3F-4E8A-9C61-2F0D8A7B3E15}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Equipo 1 - HRRG - PP2 2C 2026
; Instalación por usuario: no pide permisos de administrador y la carpeta es escribible
PrivilegesRequired=lowest
DefaultDirName={localappdata}\Programs\IngenIA Salud Triage
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=salida\instalador
OutputBaseFilename=Instalador_IngenIA_Salud_Triage_{#AppVersion}
SetupIconFile=salida\icono.ico
UninstallDisplayIcon={app}\{#AppExe}
WizardStyle=modern
; Los modelos ya vienen comprimidos: compresión rápida
Compression=lzma2/fast
SolidCompression=no
; Más de 2 GB: se parte en setup.exe + setup-1.bin, setup-2.bin...
DiskSpanning=yes
DiskSliceSize=2000000000

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
; Aplicación (PyInstaller + frontend)
Source: "salida\dist\IngenIA\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Modelo de voz (faster-whisper small)
Source: "salida\modelos\whisper-small\*"; DestDir: "{app}\modelos\whisper-small"; Flags: ignoreversion recursesubdirs createallsubdirs
; Modelos de Ollama (MedGemma, qwen2.5, embeddinggemma) en la carpeta estándar de Ollama
Source: "salida\modelos_ollama\*"; DestDir: "{%USERPROFILE}\.ollama\models"; Flags: onlyifdoesntexist uninsneveruninstall recursesubdirs createallsubdirs
; Instalador de Ollama (solo si no está instalado)
Source: "salida\OllamaSetup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: not OllamaInstalado

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autoprograms}\{#AppName} - Crear usuario"; Filename: "{app}\{#AppExe}"; Parameters: "crear-profesional"; WorkingDir: "{app}"
Name: "{autoprograms}\{#AppName} - Cambiar contraseña"; Filename: "{app}\{#AppExe}"; Parameters: "cambiar-password"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: escritorio

[Run]
Filename: "{tmp}\OllamaSetup.exe"; Parameters: "/VERYSILENT /NORESTART /SUPPRESSMSGBOXES"; StatusMsg: "Instalando Ollama (motor de IA)..."; Flags: waituntilterminated; Check: not OllamaInstalado
Filename: "{app}\{#AppExe}"; Description: "Abrir {#AppName}"; Flags: postinstall nowait skipifsilent

; Los datos clínicos, usuarios y claves (%USERPROFILE%\.hrrg_pp2 y .hrrg_pp2_claves)
; NO se borran al desinstalar, a propósito.

[Code]
function OllamaInstalado: Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe'));
end;
