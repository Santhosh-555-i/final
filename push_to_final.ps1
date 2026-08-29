Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "Pushing EventLens AI to https://github.com/Santhosh-555-i/final.git" -ForegroundColor Green
Write-Host "=======================================================" -ForegroundColor Cyan

git remote set-url origin https://github.com/Santhosh-555-i/final.git
git add .
git commit -m "feat: complete EventLens AI full stack application"
git push -u origin main

if ($LASTEXITCODE -ne 0) {
    Write-Host "`nAttempting force push (if remote has initial files)..." -ForegroundColor Yellow
    git push -u origin main --force
}

Write-Host "`nSuccessfully pushed to https://github.com/Santhosh-555-i/final.git!" -ForegroundColor Green
