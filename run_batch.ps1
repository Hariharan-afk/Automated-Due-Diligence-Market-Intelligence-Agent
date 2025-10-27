# PowerShell script to run the pipeline for multiple companies
# Usage: .\run_batch.ps1

Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "Batch Processing Multiple Companies" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# List of companies to process
$companies = @(
    "Apple Inc",
    "Microsoft Corporation",
    "Alphabet Inc",
    "Tesla Inc",
    "NVIDIA Corporation",
    "Amazon.com Inc",
    "Meta Platforms Inc"
)

$successCount = 0
$failCount = 0
$results = @()

# Process each company
foreach ($company in $companies) {
    Write-Host "---------------------------------------" -ForegroundColor Yellow
    Write-Host "Processing: $company" -ForegroundColor Yellow
    Write-Host "---------------------------------------" -ForegroundColor Yellow

    # Run the pipeline for this company
    python scripts/run_pipeline.py --company "$company"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ SUCCESS: $company" -ForegroundColor Green
        $successCount++
        $results += [PSCustomObject]@{
            Company = $company
            Status = "Success"
        }
    } else {
        Write-Host "❌ FAILED: $company" -ForegroundColor Red
        $failCount++
        $results += [PSCustomObject]@{
            Company = $company
            Status = "Failed"
        }
    }

    Write-Host ""
}

# Print summary
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "BATCH PROCESSING SUMMARY" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "Total Companies: $($companies.Count)" -ForegroundColor White
Write-Host "Successful: $successCount" -ForegroundColor Green
Write-Host "Failed: $failCount" -ForegroundColor Red
Write-Host ""

# Print detailed results
Write-Host "Detailed Results:" -ForegroundColor Cyan
$results | Format-Table -AutoSize

Write-Host ""
Write-Host "All data saved to data/company_data.db" -ForegroundColor Cyan
Write-Host "You can query the database to see all companies processed" -ForegroundColor Cyan
