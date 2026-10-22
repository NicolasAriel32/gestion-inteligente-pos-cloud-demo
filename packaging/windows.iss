#ifndef AppVersion
  #define AppVersion "0.5.1"
#endif
[Setup]
AppId={{F95EAEE3-B79F-4501-9C08-02EF49B75021}
AppName=Gestión Inteligente POS
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\GestionInteligentePOS
DefaultGroupName=Gestión Inteligente POS
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
OutputDir=..\dist\installer
OutputBaseFilename=GestionInteligentePOS-{#AppVersion}-F6-candidate-setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
AppMutex=Local\GestionInteligentePOS
CloseApplications=no
RestartApplications=no
UninstallDisplayIcon={app}\GestionInteligentePOS.exe
[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
[Files]
Source: "..\dist\GestionInteligentePOS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "PRIMER_INICIO.txt"; DestDir: "{app}"; Flags: ignoreversion
[Tasks]
Name: "desktopicon"; Description: "Crear acceso en el escritorio"; Flags: unchecked
[Icons]
Name: "{group}\Gestión Inteligente POS"; Filename: "{app}\GestionInteligentePOS.exe"
Name: "{group}\Preparar o actualizar base local"; Filename: "{app}\GestionInteligentePOS.exe"; Parameters: "--prepare"
Name: "{group}\Recuperar restauración interrumpida"; Filename: "{app}\GestionInteligentePOS.exe"; Parameters: "--recover-restore"
Name: "{group}\Primeros pasos para probar sin internet"; Filename: "{app}\PRIMER_INICIO.txt"
Name: "{autodesktop}\Gestión Inteligente POS"; Filename: "{app}\GestionInteligentePOS.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\GestionInteligentePOS.exe"; Parameters: "--prepare"; Description: "Preparar base local (requiere confirmación explícita)"; Flags: postinstall skipifsilent
; No [UninstallDelete]: datos/backups/configuración fuera de {app} se conservan.
