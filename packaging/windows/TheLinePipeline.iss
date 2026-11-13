#define AppName "THE LINE Pipeline"
#define AppExeName "TheLinePipeline.exe"
#define AppId "{{6E2F7FC2-6776-4D0B-A7E7-743E1018C25E}"
#define RepoRoot AddBackslash(SourcePath) + "..\.."

#ifndef AppBuildDir
  #define AppBuildDir AddBackslash(RepoRoot) + "dist\TheLinePipeline"
#endif

#ifndef AppVersion
  #define AppVersion "0.1.1"
#endif

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=THE LINE
DefaultDirName={localappdata}\Programs\TheLinePipeline
DefaultGroupName=THE LINE Pipeline
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
UninstallDisplayIcon={app}\{#AppExeName}
OutputDir={#RepoRoot}\dist\installer
OutputBaseFilename=TheLinePipeline-Setup-{#AppVersion}-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "autostart"; Description: "Start THE LINE Pipeline when I sign in"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "{#AppBuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\THE LINE Pipeline"; Filename: "{app}\{#AppExeName}"; WorkingDir: "{app}"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "TheLinePipeline"; ValueData: """{app}\{#AppExeName}"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch THE LINE Pipeline"; Flags: nowait postinstall skipifsilent
