"""
GitHub Push Helper for SmartShelf.
Pushes the local committed repository to:
https://github.com/saran-assr/library_management_system.git
"""
import os
import sys
from pathlib import Path
from dulwich import porcelain
from dulwich.repo import Repo

REPO_URL_BASE = "github.com/saran-assr/library_management_system.git"

def push_to_github(token=None):
    # 1. Check CLI argument or environment variable
    token = token or os.getenv("GITHUB_TOKEN")

    # 2. Check if token.txt exists in the project folder
    token_file = Path("token.txt")
    if not token and token_file.exists():
        try:
            token = token_file.read_text(encoding="utf-8").strip()
            print("[INFO] Read token from token.txt")
        except Exception:
            pass

    # 3. Interactive prompt using input() (shows visible input)
    if not token:
        print("GitHub Personal Access Token is required.")
        print("Tip: In Windows Command Prompt, right-click to paste, or paste token into token.txt")
        print()
        try:
            token = input("Paste your GitHub Personal Access Token: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            return False

    if not token:
        print("Error: No token provided.")
        return False

    auth_remote = f"https://{token}@{REPO_URL_BASE}"
    repo = Repo(".")

    print(f"\nPushing branch 'main' to https://github.com/saran-assr/library_management_system.git ...")
    try:
        porcelain.push(repo, auth_remote, b"refs/heads/main:refs/heads/main")
        print("\n========================================================")
        print("SUCCESS! Your code has been pushed to GitHub:")
        print("https://github.com/saran-assr/library_management_system")
        print("========================================================\n")

        # Clean up token.txt if it existed
        if token_file.exists():
            try:
                token_file.unlink()
                print("Cleaned up temporary token.txt.")
            except Exception:
                pass
        return True
    except Exception as e:
        print(f"\nPush failed: {e}")
        return False

if __name__ == "__main__":
    cli_token = sys.argv[1] if len(sys.argv) > 1 else None
    push_to_github(cli_token)
