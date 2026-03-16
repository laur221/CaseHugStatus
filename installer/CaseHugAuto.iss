; CaseHugAuto installer script (Inno Setup 6)

[Setup]
AppId={{0E1E73D8-5A47-4D8A-AC16-E57D6BA0E7D1}
AppName=CaseHugAuto
AppVersion=1.0.0
AppPublisher=CaseHugAuto
DefaultDirName={autopf}\CaseHugAuto
DefaultGroupName=CaseHugAuto
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=CaseHugAuto-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\CaseHugAuto.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\CaseHugAuto"; Filename: "{app}\CaseHugAuto.exe"
Name: "{autodesktop}\CaseHugAuto"; Filename: "{app}\CaseHugAuto.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\CaseHugAuto.exe"; Description: "{cm:LaunchProgram,CaseHugAuto}"; Flags: nowait postinstall skipifsilent
