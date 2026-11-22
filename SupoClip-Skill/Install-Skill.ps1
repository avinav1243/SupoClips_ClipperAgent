param(
    [ValidateSet('Codex', 'Claude', 'Both')][string]$Agent = 'Both',
    [string]$DestinationRoot = $env:USERPROFILE
)
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'supoclip-campaign'
if (-not (Test-Path -LiteralPath (Join-Path $source 'SKILL.md'))) { throw 'Extract the entire package before installing.' }
$roots = @()
if ($Agent -in 'Codex','Both') { $roots += Join-Path $DestinationRoot '.codex\skills' }
if ($Agent -in 'Claude','Both') { $roots += Join-Path $DestinationRoot '.claude\skills' }
foreach ($root in $roots) {
    $target = Join-Path $root 'supoclip-campaign'
    if (Test-Path -LiteralPath $target) { throw "Skill already exists at $target. Review the existing version before replacing it." }
}
foreach ($root in $roots) {
    New-Item -ItemType Directory -Path $root -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination (Join-Path $root 'supoclip-campaign') -Recurse
    Write-Output "Installed SupoClip Campaign in $root"
}
