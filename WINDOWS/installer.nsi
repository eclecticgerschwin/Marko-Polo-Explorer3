; Marko Polo Explorer - NSIS Setup Script
; Modern User Interface 2 (MUI2)

!include "MUI2.nsh"
!include "LogicLib.nsh"

; General Configuration
Name "Marko Polo Explorer"
OutFile "..\Install_MarkoPoloExplorer.exe"
Unicode True
SetCompressor /SOLID lzma

; Default Installation Folder (Installs in User AppData)
InstallDir "$LOCALAPPDATA\MarkoPoloExplorer"
InstallDirRegKey HKCU "Software\MarkoPoloExplorer" "InstallDir"

; Request User Privileges (No Administrator privileges required)
RequestExecutionLevel user

; UI Settings
!define MUI_ICON "markopolo.ico"
!define MUI_UNICON "markopolo.ico"
!define MUI_HEADERIMAGE
!define MUI_ABORTWARNING

; Welcome Page Configuration
!define MUI_WELCOMEPAGE_TITLE "Welcome to Marko Polo Explorer Setup"
!define MUI_WELCOMEPAGE_TEXT "This wizard will guide you through the installation of Marko Polo Explorer.\r\n\r\nMarko Polo Explorer is a native dual-panel file explorer with camera roll import, drag selection, and EXIF geocoding."

; Setup Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES

; Finish Page Configuration
!define MUI_FINISHPAGE_NOAUTOCLOSE
!define MUI_FINISHPAGE_RUN "$INSTDIR\run_app.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Launch Marko Polo Explorer"
!define MUI_FINISHPAGE_SHOWREADME ""
!define MUI_FINISHPAGE_SHOWREADME_NOTCHECKED
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Create Desktop Shortcut"
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION CreateDesktopShortcut

!insertmacro MUI_PAGE_FINISH

; Uninstaller Pages
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Languages
!insertmacro MUI_LANGUAGE "English"

; Helper function for Desktop Shortcut on Finish Page
Function CreateDesktopShortcut
  CreateShortCut "$DESKTOP\Marko Polo Explorer.lnk" "$INSTDIR\run_app.bat" "" "$INSTDIR\markopolo.ico" 0 SW_SHOWNORMAL
FunctionEnd

; Installation Section
Section "Install Files" SecInstall

  SetOutPath "$INSTDIR"

  ; Copy all program files to INSTDIR
  File /r /x "installer.nsi" /x "Install_MarkoPoloExplorer.exe" /x "*.log" /x "*_session.json" "*.*"

  ; Check if Python is installed; if missing, run bundled python-installer.exe silently
  nsExec::ExecToStack 'python --version'
  Pop $0
  ${If} $0 != 0
    ${If} ${FileExists} "$INSTDIR\python-installer.exe"
      DetailPrint "Installing Python 3.13 runtime dependency..."
      ExecWait '"$INSTDIR\python-installer.exe" /passive InstallAllUsers=1 PrependPath=1 Include_test=0'
      Delete "$INSTDIR\python-installer.exe"
    ${EndIf}
  ${EndIf}

  ; Create Start Menu Shortcut
  CreateDirectory "$SMPROGRAMS\Marko Polo Explorer"
  CreateShortCut "$SMPROGRAMS\Marko Polo Explorer\Marko Polo Explorer.lnk" "$INSTDIR\run_app.bat" "" "$INSTDIR\markopolo.ico" 0 SW_SHOWNORMAL
  CreateShortCut "$SMPROGRAMS\Marko Polo Explorer\Uninstall.lnk" "$INSTDIR\Uninstall.exe" "" "$INSTDIR\Uninstall.exe" 0

  ; Create Default Desktop Shortcut
  CreateShortCut "$DESKTOP\Marko Polo Explorer.lnk" "$INSTDIR\run_app.bat" "" "$INSTDIR\markopolo.ico" 0 SW_SHOWNORMAL

  ; Write Uninstaller
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Write Registry Keys for Windows Add/Remove Programs
  WriteRegStr HKCU "Software\MarkoPoloExplorer" "InstallDir" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MarkoPoloExplorer" "DisplayName" "Marko Polo Explorer"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MarkoPoloExplorer" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MarkoPoloExplorer" "DisplayIcon" "$INSTDIR\markopolo.ico"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MarkoPoloExplorer" "Publisher" "Marko Polo"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MarkoPoloExplorer" "DisplayVersion" "1.0"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MarkoPoloExplorer" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MarkoPoloExplorer" "NoRepair" 1

SectionEnd

; Uninstallation Section
Section "Uninstall"

  Delete "$DESKTOP\Marko Polo Explorer.lnk"
  Delete "$SMPROGRAMS\Marko Polo Explorer\Marko Polo Explorer.lnk"
  Delete "$SMPROGRAMS\Marko Polo Explorer\Uninstall.lnk"
  RMDir "$SMPROGRAMS\Marko Polo Explorer"

  RMDir /r "$INSTDIR"

  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\MarkoPoloExplorer"
  DeleteRegKey HKCU "Software\MarkoPoloExplorer"

SectionEnd
