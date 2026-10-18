; Inno Setup script for the Windows installer.
;
; Built by scripts/build.py after PyInstaller, which passes the version with
; /DAppVersion. It packs dist\ConsultaVacantesMEP as it is, licenses included,
; so whatever the build put in that folder is what gets installed.
;
; Installs for the current user only, under AppData\Local\Programs, so no
; administrator rights are asked for: the computers this is meant for are often
; shared or managed ones where nobody has them. The application writes its
; workbooks to Documents and its logs to AppData, never beside itself, so the
; install folder is never written to after installation.
;
; Requires Inno Setup 6.3 or newer, for the x64compatible architecture name.

#define AppName "Consulta Vacantes MEP"
#define AppExe "Consulta Vacantes MEP.exe"
#define AppUrl "https://github.com/andresvm18/consulta-vacantes-mep"

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Fixed for the life of the application: it is how Windows recognises a newer
; installer as an update of this one rather than a second program.
AppId={{1161F6A7-31FA-4690-BBC9-1E7DA6AF1691}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Andres Viquez Marchena
AppPublisherURL={#AppUrl}
AppSupportURL={#AppUrl}/issues
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=..\src\consulta_vacantes_mep\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
OutputDir=..\dist
OutputBaseFilename=Instalar-Consulta-Vacantes-MEP-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; An update replaces the bundled runtime wholesale. Copying over it would leave
; behind any file a newer build no longer ships, mixed in with the ones it does.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\ConsultaVacantesMEP\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent