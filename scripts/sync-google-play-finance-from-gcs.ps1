[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BucketName,
    [ValidatePattern('^\d{4}-\d{2}$')][string]$Month = (Get-Date).AddMonths(-1).ToString('yyyy-MM'),
    [string]$ArchiveRoot = "C:\DownloadThat\Finanzarchiv\GooglePlay"
)

$ErrorActionPreference = "Stop"
$temporary = Join-Path $env:TEMP "downloadthat-finance-$Month"
New-Item -ItemType Directory -Force -Path $temporary | Out-Null
$name = "downloadthat-google-play-finance-$Month.tar.gz.age"
$source = "gs://$BucketName/google-play/$Month/$name"
$local = Join-Path $temporary $name
gcloud storage cp $source $local
& "$PSScriptRoot\sync-google-play-finance-archive.ps1" -Month $Month -SourceAgeFile $local -ArchiveRoot $ArchiveRoot
Remove-Item -LiteralPath $local -Force
