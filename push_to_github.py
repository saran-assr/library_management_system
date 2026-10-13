"""
GitHub Push Helper for SmartShelf.
Pushes the local committed repository to:
https://github.com/saran-assr/library_management_system.git
"""
import os
import sys
import getpass
from dulwich import porcelain
from dulwich.repo import Repo

REPO_URL_BASE = "github.com/saran-assr/library_management_system.git"

def push_to_github(token=None):
    token = token or os.getenv("GITHUB_TOKEN")
    if not token:
        print("GitHub Personal Access Token (classic token with 'repo' scope) is required.")
        print("You can generate one at: https://github.com/settings/tokens")
        print()
        token = getpass.getpass("Enter your GitHub Personal Access Token: ").strip()

    if not token:
        print("Error: No token provided.")
        return False

    auth_remote = f"https://{token}@{REPO_URL_BASE}"
    repo = Repo(".")

    print(f"Pushing branch 'main' to https://github.com/saran-assr/library_management_system.git ...")
    try:
        porcelain.push(repo, auth_remote, b"refs/heads/main:refs/heads/main")
        print("SUCCESS! Your code has been pushed to GitHub:")
        print("https://github.com/saran-assr/library_management_system")
        return True
    except Exception as e:
        print(f"Push failed: {e}")
        return False

if __name__ == "__main__":
    cli_token = sys.argv[1] if len(sys.argv) > 1 else None
    push_to_github(cli_token)
