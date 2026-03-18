param(
	[switch]$Windowed,
	[switch]$BundleAll,
	[string]$FfmpegPath,
	[string]$Aria2Path,
	[string]$SignCert,      # path to .pfx for signing (optional)
	[string]$SignPassword,  # password for .pfx (optional)
	[string]$SignToolPath = "C:\Program Files (x86)\Windows Kits\10\bin\x64\signtool.exe"
)

$ErrorActionPreference = "Stop"

# Ensure build requirements are installed and synced
uv sync --extra build

Write-Host "Preparing build (this may take a few minutes)..."

# Prepare bundled_bins folder if requested or if specific binaries were passed
$BundledDir = Join-Path (Get-Location) 'bundled_bins'
if (Test-Path $BundledDir) { Remove-Item -Recurse -Force $BundledDir }
New-Item -ItemType Directory -Path $BundledDir | Out-Null

if ($BundleAll) {
	# Try to pick up ffmpeg and aria2c from PATH if available
	try {
		$ff = Get-Command ffmpeg -ErrorAction SilentlyContinue
		if ($ff) { Copy-Item $ff.Path -Destination $BundledDir }
	} catch {}
	try {
		$a2 = Get-Command aria2c -ErrorAction SilentlyContinue
		if ($a2) { Copy-Item $a2.Path -Destination $BundledDir }
	} catch {}
}

if ($FfmpegPath) {
	if (Test-Path $FfmpegPath) { Copy-Item $FfmpegPath -Destination $BundledDir -ErrorAction Stop }
	else { Write-Error "FFmpeg path not found: $FfmpegPath"; exit 3 }
}

if ($Aria2Path) {
	if (Test-Path $Aria2Path) { Copy-Item $Aria2Path -Destination $BundledDir -ErrorAction Stop }
	else { Write-Error "aria2c path not found: $Aria2Path"; exit 4 }
}

# Run PyInstaller using the spec which now includes bundled_bins if present
Write-Host "Running PyInstaller..."
uv run pyinstaller --clean --noconfirm classydl.spec

if ($LASTEXITCODE -ne 0) {
	Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
	exit $LASTEXITCODE
}

$ExePath = Join-Path (Join-Path (Get-Location) 'dist') 'classydl.exe'
if (Test-Path $ExePath) {
	Write-Host "Build complete: $ExePath"
} else {
	Write-Error "Build finished but dist\\classydl.exe not found"
	exit 2
}

# Optional signing step (requires signtool or equivalent)
if ($SignCert) {
	if (-not (Test-Path $SignToolPath)) { Write-Warning "signtool not found at $SignToolPath; skipping signing" }
	elseif (-not (Test-Path $SignCert)) { Write-Error "Sign certificate not found: $SignCert"; exit 5 }
	else {
		Write-Host "Signing executable with $SignCert..."
		$args = @('sign', '/f', $SignCert, '/tr', 'http://timestamp.digicert.com', '/td', 'sha256', '/fd', 'sha256')
		if ($SignPassword) { $args += @('/p', $SignPassword) }
		$args += $ExePath
		& "$SignToolPath" @args
		if ($LASTEXITCODE -ne 0) { Write-Warning "signtool returned exit code $LASTEXITCODE" }
		else { Write-Host "Signing completed." }
	}
}

Write-Host "Done. If you included ffmpeg/aria2c they are embedded under bundled_bins inside the packaged app." 
