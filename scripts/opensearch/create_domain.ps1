# Culture OpenSearch domain bootstrap (ap-northeast-2)
# Usage (PowerShell, from culture/):
#   .\scripts\opensearch\attach_iam_policy.ps1   # admin: IAM policy attach
#   .\scripts\opensearch\create_domain.ps1       # create domain culture-schema
#   python scripts\import_schema_vectors.py        # bulk import from JSONL

Param(
    [string]$Region = "ap-northeast-2",
    [string]$DomainName = "culture-schema",
    [string]$AccountId = "956723945403",
    [string]$IamUser = "Seungyoon-Choi",
    [string]$EngineVersion = "OpenSearch_2.11",
    [string]$InstanceType = "t3.small.search",
    [int]$VolumeSizeGb = 20,
    [switch]$SkipWait
)

$ErrorActionPreference = "Stop"
$Root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$PolicyPath = Join-Path $PSScriptRoot "domain-access-policy.json"
$AccessPolicy = Get-Content $PolicyPath -Raw
$AccessPolicy = $AccessPolicy -replace "956723945403", $AccountId
$AccessPolicy = $AccessPolicy -replace "Seungyoon-Choi", $IamUser
$AccessPolicy = $AccessPolicy -replace "culture-schema", $DomainName

Write-Host "Creating OpenSearch domain: $DomainName ($Region)"

$existing = aws opensearch list-domain-names --region $Region --output json 2>$null | ConvertFrom-Json
if ($existing -and ($existing.DomainNames | Where-Object { $_.DomainName -eq $DomainName })) {
    Write-Host "Domain already exists: $DomainName"
} else {
    $accessPolicyMin = ($AccessPolicy | ConvertFrom-Json | ConvertTo-Json -Compress -Depth 10)
    $policyFile = Join-Path $env:TEMP ("culture-opensearch-policy-{0}.json" -f [guid]::NewGuid().ToString())
    [System.IO.File]::WriteAllText($policyFile, $accessPolicyMin, (New-Object System.Text.UTF8Encoding $false))

    aws opensearch create-domain `
        --region $Region `
        --domain-name $DomainName `
        --engine-version $EngineVersion `
        --cluster-config "InstanceType=$InstanceType,InstanceCount=1,DedicatedMasterEnabled=false,ZoneAwarenessEnabled=false" `
        --ebs-options "EBSEnabled=true,VolumeType=gp3,VolumeSize=$VolumeSizeGb" `
        --access-policies "file://$policyFile" `
        --domain-endpoint-options "EnforceHTTPS=true,TLSSecurityPolicy=Policy-Min-TLS-1-2-2019-07" `
        --node-to-node-encryption-options Enabled=true `
        --encryption-at-rest-options Enabled=true

    Remove-Item $policyFile -Force -ErrorAction SilentlyContinue
    if ($LASTEXITCODE -ne 0) {
        throw "create-domain failed (exit $LASTEXITCODE)"
    }
    Write-Host "create-domain requested."
}

if (-not $SkipWait) {
    Write-Host "Waiting for domain to become active (10-20 min)..."
    for ($i = 0; $i -lt 120; $i++) {
        $info = aws opensearch describe-domain --domain-name $DomainName --region $Region --output json | ConvertFrom-Json
        $status = $info.DomainStatus
        $state = $status.Processing
        $created = $status.Created
        $endpoint = $status.Endpoint
        Write-Host ("  [{0}/120] Created={1} Processing={2} Endpoint={3}" -f ($i+1), $created, $state, $endpoint)
        if ($created -and -not $state -and $endpoint) { break }
        Start-Sleep -Seconds 30
    }
}

$final = aws opensearch describe-domain --domain-name $DomainName --region $Region --output json 2>$null | ConvertFrom-Json
if (-not $final) {
    Write-Warning "Domain not found yet. Creation may still be in progress."
    exit 1
}
$endpointHost = $final.DomainStatus.Endpoint
if (-not $endpointHost) {
    Write-Warning "Endpoint not ready yet. Re-run later or check AWS Console."
    exit 1
}

Write-Host ""
Write-Host "OpenSearch endpoint: https://$endpointHost"
Write-Host "Add to culture/.env.local:"
Write-Host "OPENSEARCH_HOST=$endpointHost"
Write-Host "OPENSEARCH_INDEX=culture-schema-meta"
Write-Host "OPENSEARCH_REGION=$Region"
Write-Host "OPENSEARCH_USE_IAM=1"
Write-Host ""
Write-Host "Then run:"
Write-Host "  python scripts/index_schema_metadata.py --recreate-index"
Write-Host "  python scripts/import_schema_vectors.py"
