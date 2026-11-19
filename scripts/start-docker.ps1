$ErrorActionPreference = 'Stop'
$repositoryPath = Split-Path -Parent $PSScriptRoot
$dockerCommand = Get-Command docker.exe -ErrorAction SilentlyContinue
$dockerExecutable = if ($dockerCommand) { $dockerCommand.Source } else {
    @(
        "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe",
        "$env:ProgramFiles\Docker\Docker\resources\bin\docker.exe"
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $dockerExecutable) { throw 'Docker Desktop was not found. Install and start Docker Desktop first.' }
$environmentFile = Join-Path $repositoryPath '.env'
if (-not (Test-Path -LiteralPath $environmentFile)) {
    Copy-Item -LiteralPath (Join-Path $repositoryPath '.env.example') -Destination $environmentFile
}
$previousPath = $env:PATH
try {
    # Credential helpers must be discoverable, including in terminals opened before Docker was installed.
    $env:PATH = (Split-Path -Parent $dockerExecutable) + ';' + $env:PATH
    & $dockerExecutable compose --project-directory $repositoryPath -f (Join-Path $repositoryPath 'docker-compose.yml') up --build -d --wait --wait-timeout 120
    if ($LASTEXITCODE -ne 0) { throw 'Docker Compose failed. Inspect the build output or run docker compose logs.' }
    Write-Output 'MeetingIntel AI: http://localhost:3000'
    Write-Output 'API documentation: http://localhost:8000/docs'
}
finally { $env:PATH = $previousPath }
