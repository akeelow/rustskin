# Local Rust test server for shooting Workshop skins in real game conditions.
#   .\rust-server.ps1           start the server (installs everything on first run)
#   .\rust-server.ps1 -Update   update server + Oxide after a Rust patch, then start
# Then in the Rust client: F1 -> client.connect 127.0.0.1:28015
param([switch]$Update)
$ErrorActionPreference = 'Stop'

$Root     = 'C:\rustserver'                 # outside OneDrive: ~10 GB
$SteamCmd = "$Root\steamcmd\steamcmd.exe"
$Server   = "$Root\server"
$Identity = 'rustshot'
$IdDir    = "$Server\server\$Identity"

if (-not (Test-Path $SteamCmd)) {
    New-Item -ItemType Directory -Force "$Root\steamcmd" | Out-Null
    Invoke-WebRequest https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip -OutFile "$Root\steamcmd\steamcmd.zip"
    Expand-Archive -Force "$Root\steamcmd\steamcmd.zip" "$Root\steamcmd"
}

$fresh = -not (Test-Path "$Server\RustDedicated.exe")
if ($fresh -or $Update) {
    & $SteamCmd +force_install_dir $Server +login anonymous +app_update 258550 validate +quit
    # Oxide must match the server build: always re-apply after a server update
    $zip = "$Root\Oxide.Rust.zip"
    Invoke-WebRequest https://github.com/OxideMod/Oxide.Rust/releases/latest/download/Oxide.Rust.zip -OutFile $zip
    Expand-Archive -Force $zip $Server
}

# Plugin
New-Item -ItemType Directory -Force "$Server\oxide\plugins" | Out-Null
Copy-Item -Force "$PSScriptRoot\SkinShot.cs" "$Server\oxide\plugins\SkinShot.cs"

# Config: owner = the Steam account last logged in on this PC
New-Item -ItemType Directory -Force "$IdDir\cfg" | Out-Null
$vdf = Get-Content 'C:\Program Files (x86)\Steam\config\loginusers.vdf' -Raw
$steamId = ([regex]'"(7656\d{13})"\s*\{[^}]*"MostRecent"\s*"1"').Match($vdf).Groups[1].Value
if (-not $steamId) { $steamId = ([regex]'"(7656\d{13})"').Match($vdf).Groups[1].Value }
"ownerid $steamId `"owner`" `"local test server`"" | Set-Content -Encoding ascii "$IdDir\cfg\users.cfg"
@'
decay.scale 0
server.stability false
env.progresstime false
env.time 12
'@ | Set-Content -Encoding ascii "$IdDir\cfg\server.cfg"

Set-Location $Server
& "$Server\RustDedicated.exe" -batchmode -nographics `
    +server.ip 127.0.0.1 +server.port 28015 `
    +server.level "Procedural Map" +server.seed 20261118 +server.worldsize 1500 `
    +server.maxplayers 4 +server.hostname "rustskin local" +server.identity $Identity `
    +server.description "local skin test" +app.port -1 `
    -logfile "$Root\server.log"
