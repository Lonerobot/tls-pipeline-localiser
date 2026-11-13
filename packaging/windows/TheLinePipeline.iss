#define AppName "THE LINE Pipeline"
#define AppExeName "TheLinePipeline.exe"
#define AppId "{{6E2F7FC2-6776-4D0B-A7E7-743E1018C25E}"
#define RepoRoot AddBackslash(SourcePath) + "..\.."

#ifndef AppBuildDir
  #define AppBuildDir AddBackslash(RepoRoot) + "dist\TheLinePipeline"
#endif

#ifndef AppVersion
  #define AppVersion "0.1.7"
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

[Code]
function JsonPath(const Path: String): String;
begin
  Result := Path;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
  Result := '"' + Result + '"';
end;

procedure InitializePipelineConfig(const Root: String);
var
  ConfigPath, BundlesPath, Document: String;
begin
  ConfigPath := AddBackslash(Root) + 'config.json';
  if FileExists(ConfigPath) then
    Exit;

  BundlesPath := AddBackslash(Root) + 'bundles';
  if not ForceDirectories(Root) then
    RaiseException('Could not create the pipeline folder: ' + Root);
  if not ForceDirectories(BundlesPath) then
    RaiseException('Could not create the bundle download folder: ' + BundlesPath);

  Document := '{' + #13#10 +
    '    "schema_version": 1,' + #13#10 +
    '    "remote_repository": ' + JsonPath('P:\pipeline\repository') + ',' + #13#10 +
    '    "bundle_repository": ' + JsonPath(BundlesPath) + #13#10 +
    '}' + #13#10;
  if not SaveStringToFile(ConfigPath, Utf8Encode(Document), False) then
    RaiseException('Could not write the pipeline configuration: ' + ConfigPath);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Root: String;
begin
  if CurStep = ssPostInstall then
  begin
    Root := Trim(GetEnv('TLS_PIPELINE'));
    if Root = '' then
      Root := ExpandConstant('{localappdata}\TheLine\pipeline');
    InitializePipelineConfig(Root);
  end;
end;
