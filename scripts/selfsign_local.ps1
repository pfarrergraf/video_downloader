$ErrorActionPreference='Stop'
Write-Host "Creating self-signed code-signing certificate..."
$cert = New-SelfSignedCertificate -Subject "CN=ClassyDL Local Dev" -Type CodeSigningCert -KeyExportPolicy Exportable -KeySpec Signature -NotAfter (Get-Date).AddYears(5) -CertStoreLocation "Cert:\CurrentUser\My"
Write-Host "Exporting PFX to classydl-selfsign.pfx (random password)..."
# Generate a short random password and export it so the user can reuse the PFX if needed
$pfxPassPlain = -join ((33..126) | Get-Random -Count 20 | ForEach-Object {[char]$_})
$pfxPass = ConvertTo-SecureString -String $pfxPassPlain -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath .\classydl-selfsign.pfx -Password $pfxPass | Out-Null
Set-Content -Path .\classydl-selfsign.pfx.pass.txt -Value $pfxPassPlain -Encoding ASCII
Write-Host "Signing dist\classydl.exe with the generated certificate..."
$sig = Set-AuthenticodeSignature -FilePath .\dist\classydl.exe -Certificate $cert -HashAlgorithm sha256
Write-Host "Signature status: $($sig.Status)"
Write-Host "Signature status message: $($sig.StatusMessage)"
Write-Host "Signature details:"
Get-AuthenticodeSignature .\dist\classydl.exe | Format-List
