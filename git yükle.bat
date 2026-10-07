git remote -v
git remote set-url origin git@github.com:afetacil58/takip.git
git fetch origin
git checkout main
git pull --rebase origin main
git status
git add .
git commit -m "Initial setup"
git push -u origin main