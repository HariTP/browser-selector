#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef AppArch
  #define AppArch "x86_64"
#endif
[Setup]
AppId=BrowserSelector
AppName=Browser Selector
AppVersion={#AppVersion}
AppPublisher=HariTP
AppPublisherURL=https://github.com/HariTP/browser-selector
DefaultDirName={localappdata}\Programs\Browser Selector
DefaultGroupName=Browser Selector
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=browser-selector-{#AppVersion}-windows-{#AppArch}-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\browser-selector.exe
ArchitecturesAllowed=x64compatible

[Files]
Source: "..\dist\browser-selector\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Browser Selector"; Filename: "{app}\browser-selector.exe"
Name: "{group}\Configure Browser Selector"; Filename: "{app}\browser-selector.exe"; Parameters: "--setup"

[Run]
Filename: "{app}\browser-selector.exe"; Parameters: "--setup"; Description: "Choose Browser Selector as the default browser"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\Classes\BrowserSelector.URL"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Clients\StartMenuInternet\BrowserSelector"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "Browser Selector"; ValueData: "Software\Clients\StartMenuInternet\BrowserSelector\Capabilities"; Flags: uninsdeletevalue
