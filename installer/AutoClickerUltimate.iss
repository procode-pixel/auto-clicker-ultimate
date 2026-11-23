; Optional Inno Setup installer. The GitHub release ships a zip of the PyInstaller folder,
; which already runs without a separate Python install.

#define AppName "Auto Clicker Ultimate"
#define AppVersion "1.0.0"
#define AppExe "AutoClickerUltimate.exe"

[Setup]
AppId={{8B1E6D4A-7C31-4E5A-9F20-2D6A4C0B91E3}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Auto Clicker Ultimate
DefaultDirName={autopf}\AutoClickerUltimate
DefaultGroupName={#AppName}
OutputBaseFilename=AutoClickerUltimate-Setup
OutputDir=..\release
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}
SetupIconFile=..\assets\icon.ico
PrivilegesRequired=lowest

[Files]
Source: "..\dist\AutoClickerUltimate\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
