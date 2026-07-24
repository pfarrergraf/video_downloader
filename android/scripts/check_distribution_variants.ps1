$ErrorActionPreference = 'Stop'

$appGradle = Get-Content -Raw "$PSScriptRoot\..\app\build.gradle"
$manifest = Get-Content -Raw "$PSScriptRoot\..\app\src\main\AndroidManifest.xml"
$directManifest = Get-Content -Raw "$PSScriptRoot\..\app\src\direct\AndroidManifest.xml"
$directSources = Get-ChildItem "$PSScriptRoot\..\app\src\direct" -Recurse -File | Get-Content -Raw
$playPurchaseController = Get-Content -Raw "$PSScriptRoot\..\app\src\play\java\de\classydl\app\PurchaseControllerFactory.kt"
$serverRuntime = Get-Content -Raw "$PSScriptRoot\..\app\src\main\java\de\classydl\app\ServerRuntime.kt"
$androidBuildWorkflow = Get-Content -Raw "$PSScriptRoot\..\..\.github\workflows\android-build.yml"
$androidReleaseWorkflow = Get-Content -Raw "$PSScriptRoot\..\..\.github\workflows\android-release.yml"

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
    'yt-dlp EJS package is bundled' = $appGradle -match 'install "yt-dlp-ejs==0\.8\.0"'
    'QuickJS runtime is passed to Python' = $serverRuntime -match 'libqjs\.so' -and $serverRuntime -match 'resolveJsRuntimeBinary'
    'debug workflow packages QuickJS' = $androidBuildWorkflow -match 'libqjs\.so' -and $androidBuildWorkflow -match 'quickjs_exec_test\.sh'
    'release workflow packages QuickJS' = $androidReleaseWorkflow -match 'libqjs\.so'
}

$failed = @($checks.GetEnumerator() | Where-Object { -not $_.Value })
$checks.GetEnumerator() | ForEach-Object {
    $state = if ($_.Value) { 'PASS' } else { 'FAIL' }
    Write-Host "$state - $($_.Key)"
}
if ($failed.Count -gt 0) { exit 1 }
