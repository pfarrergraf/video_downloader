[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$ProjectId,
    [Parameter(Mandatory = $true)][string]$BucketName,
    [string]$Location = "europe-west3",
    [switch]$SkipAuditLogging,
    [switch]$LockRetention,
    [string]$LockConfirmation
)

$ErrorActionPreference = "Stop"
if ($BucketName -notmatch '^downloadthat-finance-archive-[a-z0-9.-]+$') {
    throw "BucketName must start with downloadthat-finance-archive-."
}
if ($LockRetention -and $LockConfirmation -ne "LOCK-10-YEARS") {
    throw "Retention locking is irreversible. Re-run with -LockConfirmation LOCK-10-YEARS."
}

gcloud config set project $ProjectId | Out-Null
$bucketUri = "gs://$BucketName"
$exists = gcloud storage buckets describe $bucketUri 2>$null
if (-not $exists) {
    gcloud storage buckets create $bucketUri --project=$ProjectId --location=$Location --uniform-bucket-level-access
}
gcloud storage buckets update $bucketUri --uniform-bucket-level-access
gcloud storage buckets update $bucketUri --versioning
gcloud storage buckets update $bucketUri --retention-period=3650d

if (-not $SkipAuditLogging) {
    $policyPath = Join-Path $env:TEMP "downloadthat-gcp-policy-$ProjectId.json"
    $policy = gcloud projects get-iam-policy $ProjectId --format=json | ConvertFrom-Json
    if (-not ($policy.PSObject.Properties.Name -contains "auditConfigs")) {
        $policy | Add-Member -NotePropertyName auditConfigs -NotePropertyValue @()
    }
    $auditConfig = @($policy.auditConfigs | Where-Object { $_.service -eq "storage.googleapis.com" }) | Select-Object -First 1
    if (-not $auditConfig) {
        $auditConfig = [pscustomobject]@{ service = "storage.googleapis.com"; auditLogConfigs = @() }
        $policy.auditConfigs = @($policy.auditConfigs) + $auditConfig
    }
    $existingTypes = @($auditConfig.auditLogConfigs | ForEach-Object { $_.logType })
    foreach ($type in @("ADMIN_READ", "DATA_READ", "DATA_WRITE")) {
        if ($type -notin $existingTypes) {
            $auditConfig.auditLogConfigs = @($auditConfig.auditLogConfigs) + [pscustomobject]@{ logType = $type }
        }
    }
    $policy | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $policyPath -Encoding utf8
    gcloud projects set-iam-policy $ProjectId $policyPath | Out-Null
    Remove-Item -LiteralPath $policyPath -Force
}

if ($LockRetention) {
    gcloud storage buckets update $bucketUri --lock-retention-period --quiet
}

Write-Host "Archive bucket configured: $bucketUri"
Write-Host "Cloud Storage audit logging configured: $(-not $SkipAuditLogging.IsPresent)"
Write-Host "Retention locked: $($LockRetention.IsPresent)"
