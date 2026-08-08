; Inno Setup Script for Marko Polo Explorer
#define MyAppName "Marko Polo Explorer"
#define MyAppVersion "1.0"
#define MyAppPublisher "Marko Polo"
#define MyAppURL "http://marko.com.hr/markopolo/"
#define MyAppExeName "run_app.bat"

[Setup]
AppId={{D37B4A10-6B8E-4B1C-8D4C-7E3F1A2B3C4D}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={userappdata}\MarkoPoloExplorer
DisableProgramGroupPage=yes
OutputBaseFilename=Install_MarkoPoloExplorer
OutputDir=.
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
SetupIconFile=markopolo.ico

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "*.nsi,*.iss,*.log,*_session.json,Install_MarkoPoloExplorer.exe"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\markopolo.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\markopolo.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\python-installer.exe"; Parameters: "/passive InstallAllUsers=1 PrependPath=1 Include_test=0"; StatusMsg: "Installing Python 3.13 runtime..."; Check: NeedsPython; Flags: waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: shellexec postinstall skipifsilent

[Code]
function NeedsPython(): Boolean;
var
  ResultCode: Integer;
begin
  Result := not Exec('python.exe', '--version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;
