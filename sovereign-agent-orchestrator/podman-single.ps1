param(
  [ValidateSet('build','start','stop','logs','doctor','shell','pull-models')]
  [string]$Action = 'start',
  [string]$Name = 'sovereign-agent'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$envFile = Join-Path $root 'podman-single.env'

if ($Action -eq 'build') {
  podman build --format docker -t sovereign-agent:local $root
  exit $LASTEXITCODE
}

if (!(Test-Path $envFile)) {
  Copy-Item (Join-Path $root 'podman-single.env.example') $envFile
  throw "Created podman-single.env. Set its secrets, then run this command again."
}

switch ($Action) {
  'start' {
    podman volume exists sovereign-pgdata 2>$null || podman volume create sovereign-pgdata | Out-Null
    podman volume exists sovereign-workspace 2>$null || podman volume create sovereign-workspace | Out-Null
    podman volume exists sovereign-ollama 2>$null || podman volume create sovereign-ollama | Out-Null
    podman rm -f $Name 2>$null | Out-Null
    podman run -d --name $Name --env-file $envFile --restart=unless-stopped `
      -p 127.0.0.1:8080:8080 `
      -v sovereign-pgdata:/var/lib/postgresql/data `
      -v sovereign-workspace:/opt/workspace `
      -v sovereign-ollama:/root/.ollama `
      sovereign-agent:local
  }
  'stop' { podman stop $Name }
  'logs' { podman logs -f $Name }
  'doctor' { podman exec $Name /opt/venv/bin/python /opt/app/cli.py doctor }
  'shell' { podman exec -it $Name /bin/sh }
  'pull-models' { podman exec $Name sh -c 'set -e; ollama pull "$OLLAMA_MODEL"; ollama pull "$OLLAMA_EMBEDDING_MODEL"; for model in $OLLAMA_EXTRA_MODELS; do ollama pull "$model"; done' }
}