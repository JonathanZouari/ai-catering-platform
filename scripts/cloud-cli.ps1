# Use the catering project's locally encrypted, git-ignored scoped token.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string[]] $CliArguments,
    [string] $CliPath = (Join-Path $env:TEMP 'supabase-catering-cli/supabase.exe')
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$tokenPath = Join-Path $projectRoot 'supabase/.temp/cli-token.dpapi'
if (!(Test-Path -LiteralPath $CliPath)) { throw 'Provide -CliPath for the installed Supabase CLI.' }
if (!(Test-Path -LiteralPath $tokenPath)) { throw 'The local scoped CLI token has not been configured.' }
$previousToken = $env:SUPABASE_ACCESS_TOKEN
try {
    $secureToken = Get-Content -Raw -LiteralPath $tokenPath | ConvertTo-SecureString
    $env:SUPABASE_ACCESS_TOKEN = [System.Net.NetworkCredential]::new('', $secureToken).Password
    & $CliPath --workdir $projectRoot @CliArguments
    $resultCode = $LASTEXITCODE
} finally {
    $env:SUPABASE_ACCESS_TOKEN = $previousToken
}
if ($resultCode -ne 0) { throw "Supabase CLI failed with exit code $resultCode." }
