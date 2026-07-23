$ErrorActionPreference = 'Stop'

$appGradle = Get-Content -Raw "$PSScriptRoot\..\app\build.gradle"
$manifest = Get-Content -Raw "$PSScriptRoot\..\app\src\main\AndroidManifest.xml"
$directManifest = Get-Content -Raw "$PSScriptRoot\..\app\src\direct\AndroidManifest.xml"
$directSources = Get-ChildItem "$PSScriptRoot\..\app\src\direct" -Recurse -File | Get-Content -Raw
$playPurchaseController = Get-Content -Raw "$PSScriptRoot\..\app\src\play\java\de\classydl\app\PurchaseControllerFactory.kt"

$checks = [ordered]@{
    'play flavor exists' = $appGradle -match 'play\s*\{'
    'direct flavor exists' = $appGradle -match 'direct\s*\{'
    'stable application id' = $appGradle -match 'applicationId\s+"de\.classydl\.app"'
    'Billing 9.1.0 is play-only' = $appGradle -match "playImplementation 'com\.android\.billingclient:billing-ktx:9\.1\.0'"
    'Pro product id is pinned' = $appGradle -match 'PLAY_PRODUCT_ID.*pro'
    'Billing offer token is selected' = $playPurchaseController -match 'oneTimePurchaseOfferDetailsList'
    'Billing offer token is submitted' = $playPurchaseController -match '\.setOfferToken\(token\)'
    'direct source has no BillingClient' = $directSources -notmatch 'BillingClient|launchBillingFlow'
    'direct manifest removes billing permission' = $directManifest -match 'com\.android\.vending\.BILLING' -and $directManifest -match 'tools:node="remove"'
    'affiliate app links removed' = $manifest -notmatch '/claim/'
    'separate upload key supported' = $appGradle -match 'ANDROID_UPLOAD_KEYSTORE_BASE64'
    'separate app-signing key supported' = $appGradle -match 'ANDROID_APP_SIGNING_KEYSTORE_BASE64'
}

$failed = @($checks.GetEnumerator() | Where-Object { -not $_.Value })
$checks.GetEnumerator() | ForEach-Object {
    $state = if ($_.Value) { 'PASS' } else { 'FAIL' }
    Write-Host "$state - $($_.Key)"
}
if ($failed.Count -gt 0) { exit 1 }
