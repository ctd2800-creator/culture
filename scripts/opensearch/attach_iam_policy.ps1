# Attach IAM policies for OpenSearch (run once; needs iam:CreatePolicy + iam:AttachUserPolicy)
Param(
    [string]$UserName = "Seungyoon-Choi",
    [string]$AccountId = "956723945403"
)

$ErrorActionPreference = "Continue"
$ManageDoc = Join-Path $PSScriptRoot "iam-culture-opensearch-manage.json"
$DataDoc = Join-Path $PSScriptRoot "iam-culture-opensearch-data.json"

function Ensure-Policy {
    param([string]$Name, [string]$File)
    $arn = "arn:aws:iam::${AccountId}:policy/$Name"
    aws iam get-policy --policy-arn $arn *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Policy exists: $Name"
        return $arn
    }
    Write-Host "Creating policy: $Name"
    $createdJson = aws iam create-policy --policy-name $Name --policy-document "file://$File" --output json
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Could not create policy $Name (admin may have attached permissions already)."
        return $arn
    }
    $created = $createdJson | ConvertFrom-Json
    return $created.Policy.Arn
}

$manageArn = Ensure-Policy "CultureOpenSearchManage" $ManageDoc
$dataArn = Ensure-Policy "CultureOpenSearchData" $DataDoc

Write-Host "Attaching policies to user $UserName ..."
aws iam attach-user-policy --user-name $UserName --policy-arn $manageArn
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Could not attach $manageArn (may already be attached or IAM admin required)."
}
aws iam attach-user-policy --user-name $UserName --policy-arn $dataArn
if ($LASTEXITCODE -ne 0) {
    Write-Warning "Could not attach $dataArn (may already be attached or IAM admin required)."
}
Write-Host "Done. If OpenSearch permissions are already granted, run create_domain.ps1 next."
