param(
	[ValidateSet('tkinter', 'web', 'all')]
	[string]$Target = 'tkinter',
	[switch]$Windowed,
	[switch]$BundleAll,
	[string]$FfmpegPath,
	[string]$FfprobePath,
	[string]$Aria2Path,
	[string]$QuickJsPath,
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

# Resolve a command to a binary that still works when copied elsewhere.
# Chocolatey exposes tools via shimgen shims in <choco>\bin whose target path
# is relative to the shim's own location - a shim copied into bundled_bins is
# a broken exe on every machine. Follow it to the real binary in <choco>\lib.
function Resolve-RealBinary {
	param([string]$Name)
	$cmd = Get-Command $Name -ErrorAction SilentlyContinue
	if (-not $cmd) { return $null }
	$path = $cmd.Path
	$chocoRoot = $env:ChocolateyInstall
	if (-not $chocoRoot) { $chocoRoot = 'C:\ProgramData\chocolatey' }
	$chocoBin = Join-Path $chocoRoot 'bin'
	if ($path -like "$chocoBin\*") {
		$real = Get-ChildItem -Path (Join-Path $chocoRoot 'lib') -Recurse -Filter "$Name.exe" -ErrorAction SilentlyContinue |
			Select-Object -First 1
		if ($real) { return $real.FullName }
		Write-Warning "$Name resolves to a Chocolatey shim ($path) and no real binary was found under $chocoRoot\lib - not bundling it."
		return $null
	}
	return $path
}

if ($BundleAll) {
	# Pick up ffmpeg AND ffprobe from PATH: yt-dlp needs both for merging
	# best-video+best-audio streams and for MP3 extraction. For audio-only
	# MP3 output, use an ffmpeg build with libmp3lame support.
	$ff = Resolve-RealBinary 'ffmpeg'
	if ($ff) { Copy-Item $ff -Destination $BundledDir }
	$fp = Resolve-RealBinary 'ffprobe'
	if ($fp) { Copy-Item $fp -Destination $BundledDir }
	if ($ff -and -not $fp) {
		Write-Error "ffmpeg was bundled but ffprobe was not found. yt-dlp postprocessing requires both; install a full FFmpeg build."
		exit 7
	}
	$a2 = Resolve-RealBinary 'aria2c'
	if ($a2) { Copy-Item $a2 -Destination $BundledDir }
	$qjs = Resolve-RealBinary 'qjs'
	if ($qjs) { Copy-Item $qjs -Destination $BundledDir }
}

if ($FfmpegPath) {
	if (Test-Path $FfmpegPath) { Copy-Item $FfmpegPath -Destination $BundledDir -ErrorAction Stop }
	else { Write-Error "FFmpeg path not found: $FfmpegPath"; exit 3 }
}

if ($FfprobePath) {
	if (Test-Path $FfprobePath) { Copy-Item $FfprobePath -Destination $BundledDir -ErrorAction Stop }
	else { Write-Error "ffprobe path not found: $FfprobePath"; exit 3 }
}

if ($Aria2Path) {
	if (Test-Path $Aria2Path) { Copy-Item $Aria2Path -Destination $BundledDir -ErrorAction Stop }
	else { Write-Error "aria2c path not found: $Aria2Path"; exit 4 }
}

if ($QuickJsPath) {
	if (Test-Path $QuickJsPath) { Copy-Item $QuickJsPath -Destination (Join-Path $BundledDir 'qjs.exe') -ErrorAction Stop }
	else { Write-Error "QuickJS path not found: $QuickJsPath"; exit 6 }
}

# Validate that every bundled ffmpeg/ffprobe actually executes from its new
# location. A Chocolatey shim copied here "exists" but cannot run - exactly
# the failure mode that shipped a release where every audio download died
# with "ffprobe and ffmpeg not found".
foreach ($tool in @('ffmpeg.exe', 'ffprobe.exe')) {
	$toolPath = Join-Path $BundledDir $tool
	if (Test-Path $toolPath) {
		& $toolPath -version *> $null
		if ($LASTEXITCODE -ne 0) {
			Write-Error "Bundled $tool does not run from $BundledDir (broken shim or wrong architecture?)."
			exit 8
		}
		Write-Host "Validated bundled $tool"
	}
}

function Invoke-ClassyBuild {
	param(
		[string]$SpecFile,
		[string]$ExeName
	)

	Write-Host "Running PyInstaller: $SpecFile"
	uv run pyinstaller --clean --noconfirm $SpecFile
	if ($LASTEXITCODE -ne 0) {
		Write-Error "PyInstaller failed with exit code $LASTEXITCODE"
		exit $LASTEXITCODE
	}

	$ExePath = Join-Path (Join-Path (Get-Location) 'dist') $ExeName
	if (Test-Path $ExePath) {
		Write-Host "Build complete: $ExePath"
	} else {
		Write-Error "Build finished but dist\$ExeName not found"
		exit 2
	}

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
}

if ($Target -eq 'tkinter' -or $Target -eq 'all') {
	Invoke-ClassyBuild -SpecFile 'classydl.spec' -ExeName 'classydl.exe'
}
if ($Target -eq 'web' -or $Target -eq 'all') {
	Invoke-ClassyBuild -SpecFile 'classydl_web.spec' -ExeName 'classydl-web.exe'
}

Write-Host "Done. Included ffmpeg/aria2c/qjs binaries are embedded under bundled_bins."
