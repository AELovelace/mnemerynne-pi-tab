<# Tests the stager against simulated boot partitions inside .test-output; no SD card is required. #>
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$project = Split-Path -Parent $PSScriptRoot
$testRoot = Join-Path $project ('.test-output/sdcard-' + [guid]::NewGuid().ToString('N'))
$stager = Join-Path $PSScriptRoot 'deploy-to-sdcard.ps1'
$encoding = [Text.UTF8Encoding]::new($false)
$hook = '- [ bash, /boot/firmware/mnemerynne-pitab/firstboot.sh ]'
$passed = 0

function Assert-True([bool]$Condition, [string]$Message) { # Stop at the first failed expectation.
    if (-not $Condition) { throw $Message }
}
function New-BootFixture([string]$Name, [string]$UserData) { # Build only a test directory, never a physical drive.
    $folder = Join-Path $testRoot $Name
    [IO.Directory]::CreateDirectory($folder) | Out-Null
    [IO.File]::WriteAllText((Join-Path $folder 'cmdline.txt'), 'console=serial0,115200 root=PARTUUID=test', $encoding)
    [IO.File]::WriteAllText((Join-Path $folder 'user-data'), $UserData, $encoding)
    [IO.File]::WriteAllText((Join-Path $folder 'network-config'), '# preserve fixture network settings', $encoding)
    return $folder
}

$original = "#cloud-config`r`nhostname: pi-tab`r`nruncmd:`r`n  - [ echo, before ]`r`n`r`n  # keep this comment`r`n  - |`r`n    echo keep-multiline`r`n`r`nfinal_message: ready`r`n"
$boot = New-BootFixture 'block-list' $original
& $stager -Drive $boot -Server lwhittaker.net -Scale 1.25 -Start remote
$updated = [IO.File]::ReadAllText((Join-Path $boot 'user-data'))
Assert-True ($updated.Contains("  $hook`nfinal_message: ready")) 'Hook must be inside runcmd before the next top-level key.'
Assert-True ($updated.Contains('    echo keep-multiline')) 'Existing multiline commands must survive.'
Assert-True ([IO.File]::ReadAllText((Join-Path $boot 'user-data.mnemerynne-pitab.bak')) -ceq $original) 'Original backup must preserve bytes and line endings.'
Assert-True (-not $updated.Contains("`r")) 'Updated cloud-config must use LF.'
$bytes = [IO.File]::ReadAllBytes((Join-Path $boot 'user-data'))
Assert-True ($bytes[0] -eq 35) 'Cloud-config must start with #, not a UTF-8 BOM.'
$config = Get-Content -Raw -LiteralPath (Join-Path $boot 'mnemerynne-pitab/firstboot.json') | ConvertFrom-Json
Assert-True ($config.server -eq 'https://lwhittaker.net' -and $config.scale -eq 1.25 -and $config.start -eq 'remote') 'Overrides must reach firstboot.json.'
Assert-True ([IO.File]::ReadAllText((Join-Path $boot 'network-config')) -ceq '# preserve fixture network settings') 'Network settings changed.'
Assert-True ([IO.File]::ReadAllText((Join-Path $boot 'cmdline.txt')) -ceq 'console=serial0,115200 root=PARTUUID=test') 'Kernel command line changed.'
$passed++

& $stager -Drive $boot
Assert-True ([IO.File]::ReadAllText((Join-Path $boot 'user-data')) -ceq $updated) 'Restaging must not duplicate or move the command.'
Assert-True ([IO.File]::ReadAllText((Join-Path $boot 'user-data.mnemerynne-pitab.bak')) -ceq $original) 'Restaging must not overwrite the original backup.'
$passed++

foreach ($case in @(
    @('no-list', "#cloud-config`nhostname: pi-tab`n"),
    @('empty-list', "#cloud-config`nruncmd: [] # keep me`nfinal_message: ready`n"),
    @('indentless', "#cloud-config`nruncmd:`n- [ echo, before ]`n# root comment`nfinal_message: ready`n"),
    @('comment-only', "#cloud-config`n# /boot/firmware/mnemerynne-pitab/firstboot.sh`nruncmd:`n  # comment`n"))) {
    $fixture = New-BootFixture $case[0] $case[1]
    & $stager -Drive $fixture
    $text = [IO.File]::ReadAllText((Join-Path $fixture 'user-data'))
    Assert-True ($text.Contains($hook)) "Hook missing for $($case[0])."
    & $stager -Drive $fixture
    Assert-True ([IO.File]::ReadAllText((Join-Path $fixture 'user-data')) -ceq $text) "Idempotence failed for $($case[0])."
    if ($case[0] -eq 'indentless') { Assert-True ($text.Contains("`n$hook`nfinal_message:")) 'Indentless list indentation must be retained.' }
    if ($case[0] -eq 'empty-list') { Assert-True ($text.Contains('runcmd: # keep me')) 'An inline comment was lost.' }
    $passed++
}

$fixture = New-BootFixture 'whatif' "#cloud-config`nhostname: pi-tab`n"
$before = [IO.File]::ReadAllText((Join-Path $fixture 'user-data'))
& $stager -Drive $fixture -WhatIf
Assert-True (-not (Test-Path -LiteralPath (Join-Path $fixture 'mnemerynne-pitab'))) '-WhatIf wrote a payload.'
Assert-True ([IO.File]::ReadAllText((Join-Path $fixture 'user-data')) -ceq $before) '-WhatIf changed user-data.'
$passed++

foreach ($case in @(
    @('inline-list', "#cloud-config`nruncmd: [[echo, existing]]`n"),
    @('duplicate-keys', "#cloud-config`nruncmd: []`nruncmd: []`n"),
    @('wrong-header', "#!/bin/bash`necho existing`n"),
    @('mapping', "#cloud-config`nruncmd:`n  wrong: mapping`n"))) {
    $fixture = New-BootFixture $case[0] $case[1]
    $rejected = $false
    try { & $stager -Drive $fixture } catch { $rejected = $true }
    Assert-True $rejected "Unsafe fixture was accepted: $($case[0])."
    Assert-True ([IO.File]::ReadAllText((Join-Path $fixture 'user-data')) -ceq $case[1]) 'Rejected input was modified.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $fixture 'mnemerynne-pitab'))) 'Rejected input wrote payload files.'
    $passed++
}

$fixture = New-BootFixture 'invalid-origin' "#cloud-config`nhostname: pi-tab`n"
$rejected = $false
try { & $stager -Drive $fixture -Server 'https://lwhittaker.net/media' } catch { $rejected = $true }
Assert-True $rejected 'A server URL containing a path was accepted.'
Assert-True (-not (Test-Path -LiteralPath (Join-Path $fixture 'mnemerynne-pitab'))) 'Invalid URL wrote files.'
$passed++
Write-Host "Passed $passed SD-card staging scenarios. Fixtures retained at $testRoot"
