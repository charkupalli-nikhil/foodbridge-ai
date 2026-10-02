import os
import subprocess

def run(cmd):
    return subprocess.check_output(cmd, shell=True).decode('utf-8').strip()

def main():
    # Get the latest 4 commits from origin/main
    log = run("git log -n 4 --format=%H origin/main")
    commits = log.split()
    commits = [c.replace("'", "") for c in commits]
    commits.reverse() # Oldest first

    if len(commits) != 4:
        print("Expected 4 commits")
        return

    messages = [
        "feat: implement Phase 2 NGO Verification UI",
        "feat: implement Phase 3 Admin dashboard and backend fixes",
        "feat: implement Phase 3 ML Image Analysis integrations",
        "feat: implement Phase 4 Smart Matching and Phase 5 Notifications"
    ]

    # Reset hard to origin/main~4
    print("Resetting to origin/main~4...")
    os.system("git reset --hard origin/main~4")

    # Cherry pick each commit and amend the message
    for i in range(4):
        commit = commits[i]
        msg = messages[i]
        print(f"Cherry-picking {commit} with new message: {msg}")
        
        # Cherry-pick without committing
        res = os.system(f"git cherry-pick {commit} --no-commit")
        if res != 0:
            print("Cherry pick failed! Aborting.")
            return
            
        # Commit with the new message
        res = os.system(f'git commit -m "{msg}"')
        if res != 0:
            print("Commit failed! Aborting.")
            return

    print("Success! History rewritten.")
    print("Remember to run 'git push --force' to update the remote repository.")

if __name__ == "__main__":
    main()
