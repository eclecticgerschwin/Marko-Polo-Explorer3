; Inno Setup Script for Marko Polo Explorer Standalone Build
; Packages the PyInstaller standalone build folder into a Windows installer

#define MyAppName "Marko Polo Explorer"
#define MyAppVersion "1.0"
#define MyAppPublisher "Marko Polo"
#define MyAppURL "http://marko.com.hr/markopolo/"
#define MyAppExeName "MarkoPoloExplorer.exe"

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
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checked

[Files]
; The PyInstaller standalone directory contents (no Python needed!)
Source: "dist\MarkoPoloExplorer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\markopolo.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\markopolo.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
