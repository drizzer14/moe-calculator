; 14th_ua's MoE Calculator - Windows installer (Inno Setup 6.x)
;
; What it does, one double-click:
;   1. Detects the World of Tanks install folder (registry + common paths), lets
;      the user confirm/override it, and validates it (version.xml present).
;   2. Resolves the client version (e.g. 2.3.0.1) and targets mods\<version>\.
;   3. Installs the bundled dependencies ONLY if not already present (recursive check):
;      OpenWG GameFace (required) and ModsSettingsAPI (provides the in-game settings
;      panel) -- many users already have both via ModsList/Aslain.
;   4. Cleans old copies of this mod (and stale loose res_mods leftovers), then
;      installs the mod's .wotmod.
;
; Build:  see installer\build_installer.ps1  (needs Inno Setup's ISCC + the mod
;         .wotmod already built into ..\dist by build\build_wotmod.py).

#define ModId         "com.14th_ua.moe_calculator"
#define ModVersion    "1.4.0"
#define ModWotmod     "com.14th_ua.moe_calculator_1.4.0.wotmod"
#define OpenWgWotmod   "net.openwg.gameface_1.1.6.wotmod"
#define MsaWotmod      "aslain.modssettingsapi_1.6.4.wotmod"
#define ModsListWotmod "me.poliroid.modslistapi_1.7.8.wotmod"
; Used by the GitHub update check (see [Code]): the Atom feed + release-asset URLs
; are built from these, and SetupBaseName must match this .exe's filename convention.
#define RepoOwner     "drizzer14"
#define RepoName      "moe-calculator"
#define SetupBaseName "MoECalculator-Setup"

[Setup]
; Unique per-mod GUID (keys the Windows uninstall registry entry). Generated fresh
; for 14th_ua's MoE Calculator; the leading {{ is Inno Setup's escaped literal brace.
AppId={{133C08D2-38CA-49E5-A10F-699EEC194983}
AppName=14th_ua's MoE Calculator
AppVersion={#ModVersion}
AppPublisher=14th_ua
AppPublisherURL=https://github.com/drizzer14/moe-calculator
DefaultDirName={code:DetectWotRoot}
DisableProgramGroupPage=yes
DisableReadyPage=no
DirExistsWarning=no
AppendDefaultDirName=no
UsePreviousAppDir=no
OutputDir=..\dist
OutputBaseFilename={#SetupBaseName}-{#ModVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=14th_ua's MoE Calculator (WoT mod)

[Files]
; The mod itself -> mods\<version>\
Source: "..\dist\{#ModWotmod}"; DestDir: "{code:GetModsVersionDir}"; Flags: ignoreversion
; Bundled OpenWG dependency -> only copied when not already installed, and never
; removed on uninstall (other GameFace mods may depend on it).
Source: "vendor\{#OpenWgWotmod}"; DestDir: "{code:GetModsVersionDir}"; Flags: ignoreversion uninsneveruninstall; Check: NeedOpenWg
; Bundled ModsSettingsAPI dependency (provides the in-game settings panel). Same
; policy: only copied when absent, never removed on uninstall (shared by many mods).
Source: "vendor\{#MsaWotmod}"; DestDir: "{code:GetModsVersionDir}"; Flags: ignoreversion uninsneveruninstall; Check: NeedMsa
; Bundled Mods List API dependency (surfaces the settings in the in-game "Modification
; list" window). Same policy: only copied when absent, never removed on uninstall.
Source: "vendor\{#ModsListWotmod}"; DestDir: "{code:GetModsVersionDir}"; Flags: ignoreversion uninsneveruninstall; Check: NeedModsList

[Messages]
; Repurpose the "Select Destination Location" page for picking the WoT root.
SelectDirLabel3=Setup will install 14th_ua's MoE Calculator into the [name] mods folder of the World of Tanks installation below.
SelectDirBrowseLabel=Confirm your World of Tanks installation folder (the one containing version.xml). To continue, click Next. To choose a different folder, click Browse.

[Code]
var
  GVersion: string;         { resolved game version, e.g. 2.3.0.1 }
  GUpdateChecked: Boolean;   { the GitHub update check has run once this session }
  GRelaunching: Boolean;     { a newer installer was launched; suppress cancel prompt }
  DownloadPage: TDownloadWizardPage;

{ ---- helpers ------------------------------------------------------------- }

function IsWotRoot(Path: string): Boolean;
begin
  Path := RemoveBackslashUnlessRoot(Path);
  Result := (Path <> '') and
            (FileExists(Path + '\version.xml') or
             FileExists(Path + '\WorldOfTanks.exe'));
end;

{ Parse "<version> v.2.3.0.1 #892 </version>" -> "2.3.0.1" }
function ReadGameVersion(Root: string): string;
var
  S: AnsiString;
  ver: string;
  p, i: Integer;
begin
  Result := '';
  if not LoadStringFromFile(Root + '\version.xml', S) then
    Exit;
  p := Pos('v.', S);
  if p = 0 then
    Exit;
  i := p + 2;
  ver := '';
  while (i <= Length(S)) and (((S[i] >= '0') and (S[i] <= '9')) or (S[i] = '.')) do
  begin
    ver := ver + S[i];
    Inc(i);
  end;
  { trim a trailing dot if any }
  while (Length(ver) > 0) and (ver[Length(ver)] = '.') do
    ver := Copy(ver, 1, Length(ver) - 1);
  Result := ver;
end;

{ Best-effort: scan an Uninstall hive for a "World of Tanks" entry. }
function ScanUninstall(RootKey: Integer; SubPath: string): string;
var
  Names: TArrayOfString;
  i: Integer;
  dn, loc: string;
begin
  Result := '';
  if not RegGetSubkeyNames(RootKey, SubPath, Names) then
    Exit;
  for i := 0 to GetArrayLength(Names) - 1 do
  begin
    if RegQueryStringValue(RootKey, SubPath + '\' + Names[i], 'DisplayName', dn) then
    begin
      if Pos('World of Tanks', dn) > 0 then
      begin
        if RegQueryStringValue(RootKey, SubPath + '\' + Names[i], 'InstallLocation', loc) then
        begin
          if IsWotRoot(loc) then
          begin
            Result := RemoveBackslashUnlessRoot(loc);
            Exit;
          end;
        end;
      end;
    end;
  end;
end;

function DetectFromRegistry(): string;
begin
  Result := ScanUninstall(HKLM, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall');
  if Result = '' then
    Result := ScanUninstall(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall');
  if Result = '' then
    Result := ScanUninstall(HKCU, 'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall');
end;

function DetectFromCommonPaths(): string;
var
  cands: TArrayOfString;
  i: Integer;
begin
  Result := '';
  SetArrayLength(cands, 6);
  cands[0] := 'C:\Games\World_of_Tanks_EU';
  cands[1] := 'D:\Games\World_of_Tanks_EU';
  cands[2] := 'C:\Games\World_of_Tanks';
  cands[3] := 'D:\Games\World_of_Tanks';
  cands[4] := ExpandConstant('{autopf}\World_of_Tanks_EU');
  cands[5] := ExpandConstant('{autopf}\World_of_Tanks');
  for i := 0 to GetArrayLength(cands) - 1 do
    if IsWotRoot(cands[i]) then
    begin
      Result := cands[i];
      Exit;
    end;
end;

{ DefaultDirName callback. }
function DetectWotRoot(Param: string): string;
begin
  Result := DetectFromRegistry();
  if Result = '' then
    Result := DetectFromCommonPaths();
  if Result = '' then
    Result := 'C:\Games\World_of_Tanks_EU';  { harmless default; user confirms on the dir page }
end;

{ mods\<version> under the user-confirmed WoT root (the chosen app dir). }
function GetModsVersionDir(Param: string): string;
begin
  if GVersion = '' then
    GVersion := ReadGameVersion(ExpandConstant('{app}'));
  Result := ExpandConstant('{app}') + '\mods\' + GVersion;
end;

{ Recursive search for net.openwg.gameface*.wotmod under a directory. }
function FindOpenWgIn(Dir: string): Boolean;
var
  FR: TFindRec;
begin
  Result := False;
  { files in this dir }
  if FindFirst(Dir + '\net.openwg.gameface*.wotmod', FR) then
  begin
    try
      Result := True;
      Exit;
    finally
      FindClose(FR);
    end;
  end;
  { recurse into subdirs }
  if FindFirst(Dir + '\*', FR) then
  begin
    try
      repeat
        if (FR.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          if (FR.Name <> '.') and (FR.Name <> '..') then
            if FindOpenWgIn(Dir + '\' + FR.Name) then
            begin
              Result := True;
              Exit;
            end;
      until not FindNext(FR);
    finally
      FindClose(FR);
    end;
  end;
end;

{ [Files] Check: copy bundled OpenWG only when it's not already present. }
function NeedOpenWg(): Boolean;
begin
  Result := not FindOpenWgIn(GetModsVersionDir(''));
end;

{ Recursive search for aslain.modssettingsapi*.wotmod under a directory. Deliberately
  NARROW to Aslain's build: a leftover izeberg.modssettingsapi* must NOT read as "MSA
  present" (the user's settings data now lives under Aslain), so we still bundle Aslain. }
function FindMsaIn(Dir: string): Boolean;
var
  FR: TFindRec;
begin
  Result := False;
  { files in this dir }
  if FindFirst(Dir + '\aslain.modssettingsapi*.wotmod', FR) then
  begin
    try
      Result := True;
      Exit;
    finally
      FindClose(FR);
    end;
  end;
  { recurse into subdirs }
  if FindFirst(Dir + '\*', FR) then
  begin
    try
      repeat
        if (FR.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          if (FR.Name <> '.') and (FR.Name <> '..') then
            if FindMsaIn(Dir + '\' + FR.Name) then
            begin
              Result := True;
              Exit;
            end;
      until not FindNext(FR);
    finally
      FindClose(FR);
    end;
  end;
end;

{ [Files] Check: copy bundled ModsSettingsAPI only when none is already present. }
function NeedMsa(): Boolean;
begin
  Result := not FindMsaIn(GetModsVersionDir(''));
end;

{ Recursive search for me.poliroid.modslistapi*.wotmod under a directory. }
function FindModsListIn(Dir: string): Boolean;
var
  FR: TFindRec;
begin
  Result := False;
  { files in this dir }
  if FindFirst(Dir + '\me.poliroid.modslistapi*.wotmod', FR) then
  begin
    try
      Result := True;
      Exit;
    finally
      FindClose(FR);
    end;
  end;
  { recurse into subdirs }
  if FindFirst(Dir + '\*', FR) then
  begin
    try
      repeat
        if (FR.Attributes and FILE_ATTRIBUTE_DIRECTORY) <> 0 then
          if (FR.Name <> '.') and (FR.Name <> '..') then
            if FindModsListIn(Dir + '\' + FR.Name) then
            begin
              Result := True;
              Exit;
            end;
      until not FindNext(FR);
    finally
      FindClose(FR);
    end;
  end;
end;

{ [Files] Check: copy bundled Mods List API only when none is already present. }
function NeedModsList(): Boolean;
begin
  Result := not FindModsListIn(GetModsVersionDir(''));
end;

{ ---- WoT-running guard (file locks) -------------------------------------- }

function IsWotRunning(): Boolean;
var
  rc: Integer;
  tmp: string;
  content: AnsiString;
begin
  Result := False;
  tmp := ExpandConstant('{tmp}\wot_tasklist.txt');
  if Exec(ExpandConstant('{cmd}'),
          '/C tasklist /FI "IMAGENAME eq WorldOfTanks.exe" /NH > "' + tmp + '"',
          '', SW_HIDE, ewWaitUntilTerminated, rc) then
  begin
    if LoadStringFromFile(tmp, content) then
      Result := Pos('WorldOfTanks.exe', content) > 0;
  end;
end;

{ ---- GitHub update check ------------------------------------------------- }

{ Case-insensitive test for a command-line switch (e.g. /SKIPUPDATECHECK). }
function HasCmdParam(const P: string): Boolean;
var
  i: Integer;
begin
  Result := False;
  for i := 1 to ParamCount do
    if CompareText(ParamStr(i), P) = 0 then
    begin
      Result := True;
      Exit;
    end;
end;

{ Pull the newest release tag from a GitHub releases.atom feed -> "0.3.0".
  The first /releases/tag/ link in the feed is the latest release. }
function ParseAtomTag(S: AnsiString): string;
var
  p, i: Integer;
  v: string;
begin
  Result := '';
  p := Pos('/releases/tag/', S);
  if p = 0 then
    Exit;
  i := p + Length('/releases/tag/');
  if (i <= Length(S)) and ((S[i] = 'v') or (S[i] = 'V')) then
    Inc(i);
  v := '';
  while (i <= Length(S)) and (((S[i] >= '0') and (S[i] <= '9')) or (S[i] = '.')) do
  begin
    v := v + S[i];
    Inc(i);
  end;
  while (Length(v) > 0) and (v[Length(v)] = '.') do
    v := Copy(v, 1, Length(v) - 1);
  Result := v;
end;

{ Compare dotted numeric versions component-wise. -1 if A<B, 0 equal, 1 if A>B.
  Length-tolerant: missing components count as 0 (so 0.3 = 0.3.0). }
function VerCompare(A, B: string): Integer;
var
  sa, sb: string;
  pa, pb, na, nb: Integer;
begin
  Result := 0;
  while ((A <> '') or (B <> '')) and (Result = 0) do
  begin
    pa := Pos('.', A);
    if pa > 0 then begin sa := Copy(A, 1, pa - 1); A := Copy(A, pa + 1, Length(A)); end
    else begin sa := A; A := ''; end;
    pb := Pos('.', B);
    if pb > 0 then begin sb := Copy(B, 1, pb - 1); B := Copy(B, pb + 1, Length(B)); end
    else begin sb := B; B := ''; end;
    na := StrToIntDef(sa, 0);
    nb := StrToIntDef(sb, 0);
    if na < nb then Result := -1
    else if na > nb then Result := 1;
  end;
end;

{ Version parsed from "com.14th_ua.moe_calculator_<ver>.wotmod".
  The id itself may contain an underscore, so split on the LAST one. }
function ExtractModVer(FileName: string): string;
var
  i, u, p: Integer;
  s: string;
begin
  u := 0;
  for i := 1 to Length(FileName) do
    if FileName[i] = '_' then
      u := i;
  s := Copy(FileName, u + 1, Length(FileName));
  p := Pos('.wotmod', s);
  if p > 0 then
    s := Copy(s, 1, p - 1);
  Result := s;
end;

{ Highest installed version of THIS mod under Dir, or '' if none present. }
function ReadInstalledModVer(Dir: string): string;
var
  FR: TFindRec;
  v: string;
begin
  Result := '';
  if FindFirst(Dir + '\{#ModId}_*.wotmod', FR) then
  begin
    try
      repeat
        v := ExtractModVer(FR.Name);
        if (v <> '') and ((Result = '') or (VerCompare(v, Result) > 0)) then
          Result := v;
      until not FindNext(FR);
    finally
      FindClose(FR);
    end;
  end;
end;

{ Best-effort latest release version from the repo's Atom feed, or '' on failure.
  The Atom feed needs no API token or User-Agent (unlike api.github.com). }
function FetchLatestTag(): string;
var
  S: AnsiString;
begin
  Result := '';
  try
    DownloadTemporaryFile(
      'https://github.com/{#RepoOwner}/{#RepoName}/releases.atom',
      'moe_calculator_releases.atom', '', nil);
    if LoadStringFromFile(ExpandConstant('{tmp}\moe_calculator_releases.atom'), S) then
      Result := ParseAtomTag(S);
  except
    Result := '';  { offline / feed changed / parse failed -> stay silent }
  end;
end;

{ Download the given installer asset into the temp dir and launch it. True on ok. }
function DownloadAndRun(Url, FileName: string): Boolean;
var
  rc: Integer;
begin
  Result := False;
  DownloadPage.Clear;
  DownloadPage.Add(Url, FileName, '');
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
      Result := True;
    except
      Result := False;
    end;
  finally
    DownloadPage.Hide;
  end;
  if Result then
    Result := Exec(ExpandConstant('{tmp}\' + FileName), '', '',
                   SW_SHOWNORMAL, ewNoWait, rc);
end;

{ If GitHub has a release newer than max(installed, bundled), offer to fetch and
  run it. Returns True when a newer installer was launched (caller should close). }
function MaybeOfferUpdate(): Boolean;
var
  latest, installed, baseline, assetName, assetUrl: string;
begin
  Result := False;
  if HasCmdParam('/SKIPUPDATECHECK') then
    Exit;

  latest := FetchLatestTag();
  if latest = '' then
    Exit;

  baseline := '{#ModVersion}';
  installed := ReadInstalledModVer(GetModsVersionDir(''));
  if (installed <> '') and (VerCompare(installed, baseline) > 0) then
    baseline := installed;

  if VerCompare(latest, baseline) <= 0 then
    Exit;  { already current }

  if MsgBox('A newer version of 14th_ua''s MoE Calculator is available.'#13#10#13#10 +
            'Latest available: ' + latest + #13#10 +
            'This installer: {#ModVersion}'#13#10#13#10 +
            'Download and run the latest installer now?',
            mbConfirmation, MB_YESNO) <> IDYES then
    Exit;

  assetName := '{#SetupBaseName}-' + latest + '.exe';
  assetUrl := 'https://github.com/{#RepoOwner}/{#RepoName}/releases/download/v' +
              latest + '/' + assetName;
  if DownloadAndRun(assetUrl, assetName) then
    Result := True
  else
    MsgBox('Could not download the new installer automatically.'#13#10 +
           'You can get it manually from:'#13#10 +
           'https://github.com/{#RepoOwner}/{#RepoName}/releases/latest'#13#10#13#10 +
           'Setup will continue with the bundled version.',
           mbInformation, MB_OK);
end;

{ ---- wizard flow --------------------------------------------------------- }

procedure InitializeWizard();
begin
  { Pre-create the download page reused by the self-update flow. }
  DownloadPage := CreateDownloadPage('Checking for updates',
    'Downloading the latest installer from GitHub...', nil);
end;

{ Don't show the "Exit Setup?" confirmation when we close to launch the newer one. }
procedure CancelButtonClick(CurPageID: Integer; var Cancel, Confirm: Boolean);
begin
  if GRelaunching then
    Confirm := False;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = wpSelectDir then
  begin
    if not IsWotRoot(ExpandConstant('{app}')) then
    begin
      MsgBox('That folder does not look like a World of Tanks installation ' +
             '(no version.xml found). Please choose your WoT install folder ' +
             '(for example C:\Games\World_of_Tanks_EU).', mbError, MB_OK);
      Result := False;
      Exit;
    end;
    GVersion := ReadGameVersion(ExpandConstant('{app}'));
    if GVersion = '' then
    begin
      MsgBox('Could not read the client version from version.xml in that ' +
             'folder. Please make sure it is your World of Tanks install folder.',
             mbError, MB_OK);
      Result := False;
      Exit;
    end;
    { GVersion + the app dir are now known, so we can read any installed mod
      version. Check GitHub once; if a newer installer exists, fetch and launch
      it, then close this wizard. Best-effort -- silent when offline / current. }
    if not GUpdateChecked then
    begin
      GUpdateChecked := True;
      if MaybeOfferUpdate() then
      begin
        GRelaunching := True;
        Result := False;
        WizardForm.Close;
        Exit;
      end;
    end;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if IsWotRunning() then
    Result := 'World of Tanks is currently running. Please close the game ' +
              'completely (exit the launcher too), then run this installer again.';
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  modsDir, resMods: string;
begin
  if CurStep = ssInstall then
  begin
    modsDir := GetModsVersionDir('');
    { remove older builds of THIS mod (keep filenames stable across versions).
      DEV CAVEAT: this glob (and the FindFirst in ReadInstalledModVer) also match a
      dev "{#ModId}_debug.wotmod" REPL mod. Consumers never have it; on a dev box,
      remove the debug mod before test-running this consumer installer. }
    DelTree(modsDir + '\' + '{#ModId}' + '_*.wotmod', False, True, False);
    { remove our stale loose res_mods leftovers (these would shadow the package) }
    resMods := ExpandConstant('{app}') + '\res_mods\' + GVersion;
    DeleteFile(resMods + '\scripts\client\gui\mods\mod_moe_calculator.py');
    DeleteFile(resMods + '\scripts\client\gui\mods\mod_moe_calculator.pyc');
    DelTree(resMods + '\scripts\client\moe_calculator', True, True, True);
  end;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  { Make the Ready page remind the user to fully restart the client. }
  if CurPageID = wpReady then
    WizardForm.ReadyMemo.Lines.Add(#13#10 +
      'After installing, fully restart World of Tanks to load the mod.');
end;
