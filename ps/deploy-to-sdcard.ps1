<#
.SYNOPSIS
Stages the Pi touch kiosk on a fresh Raspberry Pi Imager cloud-init boot partition.
.DESCRIPTION
Run after flashing and customizing an unbooted card. Preserves existing user-data
settings and commands, saves an original backup, and adds one firstboot.sh entry.
Use -WhatIf to check the target and configuration without writing to the card.
.EXAMPLE
.\ps\deploy-to-sdcard.ps1 -Drive K:
.EXAMPLE
.\ps\deploy-to-sdcard.ps1 -Drive K: -Server https://lwhittaker.net -Start remote -Scale 1.25
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory)][string]$Drive,
    [string]$Server = 'https://lwhittaker.net',
    [ValidateRange(1.0, 2.0)][double]$Scale = 1.15,
    [ValidateSet('media', 'remote', 'home')][string]$Start = 'media'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-PlainPath([string]$Path) { # Refuse links/junctions in any existing part of a write path.
    $cursor = [IO.Path]::GetFullPath($Path)
    while ($cursor) {
        if (Test-Path -LiteralPath $cursor) {
            $item = Get-Item -LiteralPath $cursor -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw "Refusing a symlink or junction in the target path: $cursor"
            }
        }
        $cursor = [IO.Path]::GetDirectoryName($cursor)
    }
}

function Add-FirstBootCommand([string]$Text) { # Extend Imager's runcmd list without rewriting its other YAML.
    $textLF = ($Text -replace "`r`n", "`n") -replace "`r", "`n"
    $textLF = $textLF.TrimStart([char]0xFEFF)
    if ($textLF -notmatch '^#cloud-config(?:\n|$)') {
        throw 'user-data must start with #cloud-config. This script requires an Imager cloud-init image.'
    }
    if ($textLF -match '(?m)^(?:---|\.\.\.)\s*(?:#.*)?$') {
        throw 'Multiple documents or YAML document markers are not supported; use plain Imager cloud-config.'
    }
    $lines = [Collections.Generic.List[string]]::new()
    foreach ($line in $textLF.TrimEnd("`n").Split("`n")) { $lines.Add($line) }
    $keys = @()
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match '^(?:runcmd|["'']runcmd["''])\s*:') { $keys += $i }
    }
    if ($keys.Count -gt 1) { throw 'user-data contains duplicate runcmd keys; fix them before staging.' }
    $entry = '- [ bash, /boot/firmware/mnemerynne-pitab/firstboot.sh ]'
    if ($keys.Count -eq 0) {
        $lines.Add('runcmd:')
        $lines.Add('  ' + $entry)
    } else {
        $index = $keys[0]
        if ($lines[$index] -match '^runcmd:\s*\[\s*\]\s*(#.*)?$') {
            $comment = $Matches[1]
            $lines[$index] = 'runcmd:' + $(if ($comment) { ' ' + $comment } else { '' })
        } elseif ($lines[$index] -notmatch '^runcmd:\s*(?:#.*)?$') {
            throw 'Only a block runcmd list or runcmd: [] is supported; no changes were made.'
        }
        $end = $index + 1
        $indent = $null
        $alreadyAdded = $false
        while ($end -lt $lines.Count) {
            $line = $lines[$end]
            if ($line -match '^\s*(?:#.*)?$') { $end++; continue }
            if ($line -match '^\S' -and $line -notmatch '^-(?:\s|$)') { break }
            if ($null -eq $indent) {
                if ($line -notmatch '^( *)-(?:\s|$)') {
                    throw 'runcmd must be a YAML list; no changes were made.'
                }
                $indent = $Matches[1]
            }
            if ($line -match "^$indent-(?:\s|$)" -and $line.Trim() -eq $entry) {
                $alreadyAdded = $true  # Ignore comments and literal text mentioning the script.
            }
            $end++
        }
        if (-not $alreadyAdded) {
            if ($null -eq $indent) { $indent = '  ' }
            $lines.Insert($end, $indent + $entry)
        }
    }
    return ($lines -join "`n") + "`n"
}

# Normalize and validate before writing anything, including when called with -WhatIf.
if ($Drive -match '^[A-Za-z]:?$') { $Drive = $Drive[0] + ':\' }
$boot = (Resolve-Path -LiteralPath $Drive).ProviderPath
Assert-PlainPath $boot
if (-not (Test-Path -LiteralPath $boot -PathType Container)) { throw 'Drive must name the boot partition directory.' }
$userData = Join-Path $boot 'user-data'
if (-not (Test-Path -LiteralPath (Join-Path $boot 'cmdline.txt') -PathType Leaf) -or
    -not (Test-Path -LiteralPath $userData -PathType Leaf)) {
    throw "$boot needs cmdline.txt and user-data from Raspberry Pi Imager. Use an unbooted cloud-init image."
}
if ($Server -notmatch '://') { $Server = 'https://' + $Server }
if ($Server -notmatch '^https?://(?:[A-Za-z0-9.-]+|\[[A-Fa-f0-9:]+\])(?::[0-9]{1,5})?/?$') {
    throw 'Server must be an HTTP(S) origin without credentials, a page path, query or fragment.'
}
$uri = [Uri]$Server
if (-not $uri.IsAbsoluteUri -or $uri.Port -lt 1 -or [Uri]::CheckHostName($uri.DnsSafeHost) -eq 'Unknown') {
    throw 'Server must have a valid hostname/IP address and port.'
}
$normalizedServer = $uri.GetLeftPart([UriPartial]::Authority)
$project = Split-Path -Parent $PSScriptRoot
$destination = Join-Path $boot 'mnemerynne-pitab'
$backup = Join-Path $boot 'user-data.mnemerynne-pitab.bak'
$settings = Join-Path $destination 'firstboot.json'
$files = @('install.sh', 'firstboot.sh', 'README.md', 'python/pitab.py', 'python/firstboot.py',
           'assets/userChrome.css', 'assets/touch.css', 'assets/bar.css')
foreach ($target in @($userData, $destination, $backup, $settings)) { Assert-PlainPath $target }
foreach ($relative in $files) {
    if (-not (Test-Path -LiteralPath (Join-Path $project $relative) -PathType Leaf)) {
        throw "Missing package file: $relative"
    }
    Assert-PlainPath (Join-Path $destination $relative)
}
$original = [IO.File]::ReadAllText($userData)
$updated = Add-FirstBootCommand $original
$encoding = [Text.UTF8Encoding]::new($false)

if ($PSCmdlet.ShouldProcess($boot, 'Stage the Mnemerynne Pi kiosk and add its cloud-init first-boot command')) {
    # Copy only known files. No recursive deletion, cache copying or credentials from this computer.
    foreach ($relative in $files) {
        $target = Join-Path $destination $relative
        [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
        $content = [IO.File]::ReadAllText((Join-Path $project $relative)) -replace "`r`n", "`n"
        [IO.File]::WriteAllText($target, $content, $encoding)
    }
    $config = [ordered]@{ server = $normalizedServer; scale = $Scale; start = $Start } | ConvertTo-Json
    [IO.File]::WriteAllText($settings, ($config -replace "`r`n", "`n") + "`n", $encoding)
    if (-not (Test-Path -LiteralPath $backup)) {
        Copy-Item -LiteralPath $userData -Destination $backup  # Keep the original bytes for recovery.
    }
    [IO.File]::WriteAllText($userData, $updated, $encoding)     # Activate the hook only after copying the payload.
    Write-Host "Staged Mnemerynne Pi kiosk on $boot for $normalizedServer"
    Write-Host 'Safely eject the card and boot the Pi. Wi-Fi/user settings come from Imager.'
    Write-Host 'Progress: /var/log/mnemerynne-pitab-firstboot.log'
    Write-Host 'Use a freshly flashed card that has not been booted; cloud-init runs runcmd once.'
}
