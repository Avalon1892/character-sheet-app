#define AppName "Character Sheet App"
#define AppVersion "0.1.0"
#ifndef SourceDir
  #define SourceDir "..\.artifacts\transportable\dist\Character Sheet App"
#endif
#ifndef OutputDir
  #define OutputDir "..\.artifacts\transportable"
#endif

[Setup]
AppId={{6A048ED4-0529-4E6B-A885-9A47C987C0DC}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Georg
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=Character-Sheet-App-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\Character Sheet App.exe
ChangesAssociations=no
CloseApplications=yes
RestartApplications=no

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Character Sheet App"; Filename: "{app}\Character Sheet App.exe"
Name: "{autodesktop}\Character Sheet App"; Filename: "{app}\Character Sheet App.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Run]
Filename: "{app}\Character Sheet App.exe"; Description: "Open Character Sheet App"; Flags: nowait postinstall skipifsilent

