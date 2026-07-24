param(
    [Parameter(Mandatory = $true)]
    [string]$AdminToken,
    [Parameter(Mandatory = $true)]
    [string]$Label,
    [ValidateSet('owner', 'tester')]
    [string]$GrantType = 'tester',
    [ValidateRange(1, 3650)]
    [int]$ExpiresInDays = 14,
    [string]$ApiBase = 'https://downloadthat.app'
)

$ErrorActionPreference = 'Stop'
$body = @{ label = $Label; grant_type = $GrantType }
if ($GrantType -eq 'tester') { $body.expires_in_days = $ExpiresInDays }
$response = Invoke-RestMethod -Method Post -Uri "$($ApiBase.TrimEnd('/'))/api/admin/tester-grants" `
    -Headers @{ Authorization = "Bearer $AdminToken" } `
    -ContentType 'application/json' -Body ($body | ConvertTo-Json)
$response | ConvertTo-Json -Depth 5
