$ErrorActionPreference='Stop'
$c = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -eq 'CN=ClassyDL Local Dev' } | Select-Object -First 1
if ($null -eq $c) { Write-Error 'Self-signed cert not found'; exit 1 }
$sig = Set-AuthenticodeSignature -FilePath .\dist\classydl.exe -Certificate $c -HashAlgorithm sha256
Write-Host "Status: $($sig.Status)"
Write-Host "Message: $($sig.StatusMessage)"
