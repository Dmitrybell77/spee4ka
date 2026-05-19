#define AppName "Спичка"
#define AppVersion "1.0.14"
#define AppPublisher "Спичка"
#define AppURL "https://spee4ka.ru"
#define AppExeName "Spee4ka.exe"

[Setup]
AppId={{F7A3B9C1-D2E4-4F56-8A7B-C3D5E6F78901}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Spee4ka
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist_installer
OutputBaseFilename=Spee4ka_Setup
Compression=lzma2/ultra64
SolidCompression=yes
SetupIconFile=..\spee4ka.ico
UninstallDisplayIcon={app}\spee4ka.ico
LicenseFile=EULA.txt
WizardStyle=modern
PrivilegesRequired=lowest
CloseApplications=force
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
; Launcher exe
Source: "..\Spee4ka.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\spee4ka.ico"; DestDir: "{app}"; Flags: ignoreversion

; Embedded Python
Source: "python\*"; DestDir: "{app}\python"; Flags: ignoreversion recursesubdirs createallsubdirs

; App files
Source: "..\main.py";            DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\settings_window.py"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\first_run.py";       DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\crypto_utils.py";    DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\license_manager.py";    DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\activation_window.py"; DestDir: "{app}\app"; Flags: ignoreversion
Source: "..\config.json";        DestDir: "{app}\app"; Flags: ignoreversion onlyifdoesntexist
Source: "..\env.template";       DestDir: "{app}\app"; DestName: ".env"; Flags: ignoreversion onlyifdoesntexist

[Dirs]
Name: "{app}\app\models"
Name: "{app}\app\logs"

[Icons]
Name: "{group}\{#AppName}";       Filename: "{app}\{#AppExeName}"
Name: "{group}\Удалить Спичку";   Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Запустить Спичку"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -NonInteractive -Command ""Get-WmiObject Win32_Process | Where-Object {{ $_.ExecutablePath -like '*Spee4ka*' }} | ForEach-Object {{ $_.Terminate() }}"""; Flags: runhidden; RunOnceId: "KillSpee4ka"

[Code]
function InitializeSetup(): Boolean;
var
  RC: Integer;
  PSCmd: String;
begin
  // Only kill processes that live in our install dir — never global pythonw/python.exe,
  // which would close the user's IDE, Jupyter etc.
  Exec('taskkill.exe', '/F /IM Spee4ka.exe', '', SW_HIDE, ewWaitUntilTerminated, RC);
  PSCmd :=
    '-NoProfile -NonInteractive -Command "' +
    'Get-WmiObject Win32_Process | ' +
    'Where-Object { $_.ExecutablePath -like ''*\Spee4ka\*'' } | ' +
    'ForEach-Object { $_.Terminate() | Out-Null }"';
  Exec('powershell.exe', PSCmd, '', SW_HIDE, ewWaitUntilTerminated, RC);
  Sleep(1500);
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then begin
    // Remove autostart shortcut on uninstall prep - handled by app itself
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  StartupShortcut: String;
begin
  if CurUninstallStep = usPostUninstall then begin
    StartupShortcut := ExpandConstant('{userstartup}\Spee4ka.lnk');
    if FileExists(StartupShortcut) then
      DeleteFile(StartupShortcut);
  end;
end;
