$ErrorActionPreference='Stop'
Write-Host 'Finding the self-signed certificate in CurrentUser\\My...'
$c = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -eq 'CN=ClassyDL Local Dev' } | Select-Object -First 1
if ($null -eq $c) { Write-Error 'Certificate not found in store.'; exit 1 }
Write-Host 'Exporting .cer and importing into CurrentUser Trusted Root...'
Export-Certificate -Cert $c -FilePath .\classydl-selfsign.cer | Out-Null
Import-Certificate -FilePath .\classydl-selfsign.cer -CertStoreLocation Cert:\CurrentUser\Root | Out-Null
Write-Host 'Imported. Verifying presence in Root store:'
Get-ChildItem Cert:\CurrentUser\Root | Where-Object { $_.Subject -eq 'CN=ClassyDL Local Dev' } | Select-Object Thumbprint, Subject, NotAfter | Format-List
Write-Host 'Re-checking authenticode signature...'
Get-AuthenticodeSignature .\dist\classydl.exe | Format-List
