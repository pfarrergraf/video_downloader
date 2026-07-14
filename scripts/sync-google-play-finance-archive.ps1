[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][ValidatePattern('^\d{4}-\d{2}$')][string]$Month,
    [Parameter(Mandatory = $true)][string]$SourceAgeFile,
    [string]$ArchiveRoot = "C:\DownloadThat\Finanzarchiv\GooglePlay"
)

$ErrorActionPreference = "Stop"
$resolvedSource = (Resolve-Path -LiteralPath $SourceAgeFile).Path
$year, $monthNumber = $Month.Split('-')
$destination = Join-Path (Join-Path $ArchiveRoot $year) $monthNumber
New-Item -ItemType Directory -Force -Path $destination | Out-Null
$target = Join-Path $destination (Split-Path -Leaf $resolvedSource)
Copy-Item -LiteralPath $resolvedSource -Destination $target -Force

$sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolvedSource).Hash
$targetHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash
if ($sourceHash -ne $targetHash) {
    throw "Hash mismatch after copy. Source=$sourceHash Target=$targetHash"
}
Set-Content -LiteralPath "$target.sha256" -Value "$targetHash  $(Split-Path -Leaf $target)" -Encoding ascii
Write-Host "Verified encrypted archive copy: $target"
