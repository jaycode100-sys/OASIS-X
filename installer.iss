; ── OASIS-X Inno Setup Script ──
; Creates a professional installer with bootstrapper
; Compile with Inno Setup 6+: iscc installer.iss

#define MyAppName "OASIS-X"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Swift Solutions"
#define MyAppURL "https://github.com/jaycode100-sys/OASIS-X"
#define MyAppExeName "OASIS-X.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=installer\Output
OutputBaseFilename=OASIS-X-Setup-{#MyAppVersion}
SetupIconFile=static\oasis.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1

[Files]
Source: "dist\OASIS-X\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\OASIS-X\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Check if Ollama is installed
function IsOllamaInstalled: Boolean;
begin
  Result := FileExists(ExpandConstant('{autopf}\Ollama\ollama.exe')) or 
            FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe'));
end;

// Warn if Ollama not found
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if not IsOllamaInstalled then
    begin
      MsgBox('Ollama was not detected on your system.'#13#10#13#10 +
             'OASIS-X requires Ollama for AI features (Nexus Chat, fault diagnosis).'#13#10 +
             'Download from: https://ollama.com/download'#13#10#13#10 +
             'The application will still work for monitoring without Ollama.', 
             mbInformation, MB_OK);
    end;
  end;
end;
