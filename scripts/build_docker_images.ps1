# BenchMax Local Docker Image Builder (PowerShell)
# Builds benchmax-python, benchmax-node, benchmax-gcc from local Dockerfiles.
param(
    [switch]$ForceRebuild,
    [switch]$SkipNode,
    [switch]$SkipGCC
)

$ErrorActionPreference = "Stop"
$dockerDir = Join-Path $PSScriptRoot "..\backend\docker"

function Write-Info   { param($m) Write-Host "[INFO]  $m" -ForegroundColor Cyan }
function Write-Success{ param($m) Write-Host "[OK]    $m" -ForegroundColor Green }
function Write-Warn   { param($m) Write-Host "[WARN]  $m" -ForegroundColor Yellow }
function Write-Error  { param($m) Write-Host "[ERROR] $m" -ForegroundColor Red }

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  BenchMax — Local Docker Image Builder (PowerShell)"
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed. Install Docker Desktop first."
    exit 1
}
try { $docker info >$null 2>$null; if ($LASTEXITCODE) { Write-Error "Docker daemon not running" }; } catch { Write-Error $_ }
Write-Success "Docker available"

$images = @(
    @{ Name="benchmax-python"; Dockerfile="Dockerfile.python" },
    @{ Name="benchmax-node";   Dockerfile="Dockerfile.node"  },
    @{ Name="benchmax-gcc";    Dockerfile="Dockerfile.gcc"   }
)
if ($SkipNode)    { $images = $images | Where-Object { $_.Name -ne "node" } }
if ($SkipGCC)     { $images = $images | Where-Object { $_.Name -ne "gcc"  } }

Write-Host ""
foreach ($img in $images) {
    Write-Info "Building $($img.Name)..."
    $dfPath = Join-Path $dockerDir $img.Dockerfile
    if (-not (Test-Path $dfPath)) { Write-Warn "$($img.Name): Dockerfile not found"; continue }

    $args = @("build", "-f", $dfPath, "-t", "$($img.Name):latest", ".")
    if ($ForceRebuild) { $args += "--no-cache" }

    try {
        & docker $args
        Write-Success "$($img.Name):latest built locally"
    } catch {
        Write-Error "Build failed for $($img.Name)"
    }
}

Write-Host ""
$successCount = 0; $failCount = 0
foreach ($img in @(@{ Name="benchmax-python"; Dockerfile="Dockerfile.python" }, @{ Name="benchmax-node";   Dockerfile="Dockerfile.node"  }, @{ Name="benchmax-gcc";    Dockerfile="Dockerfile.gcc"   })) {
    $exists = docker image inspect $img.Name:latest >$null 2>$null; if ($LASTEXITCODE) { $exists=$false }
    if ($exists) { Write-Success "$($img.Name):latest (${(docker image inspect $img.Name:latest --format '{{.Size}}' | ForEach-Object {[math]::Round($_/(1MB))})}MB)" }; else { Write-Warn "$($img.Name) not found locally" }
    if ($exists) { $successCount++ } else { $failCount++ }
}

Write-Host ""
if ($failCount -gt 0) {
    Write-Warn "You can still run benchmarks — executor falls back to public base images."
    exit 1
}
Write-Success "All local images built successfully!"
