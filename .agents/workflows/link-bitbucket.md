---
description: Link local repository to Bitbucket and push changes
---

This workflow guides you through linking your local repository to a Bitbucket remote and pushing your commits.

### 1. Create a repository on Bitbucket
1. Go to [bitbucket.org](https://bitbucket.org) → **Create repository**.
2. Give it a name and click **Create repository**.
3. Copy the remote URL (HTTPS or SSH).

### 2. Add the remote in Antigravity
If you haven't added the remote yet, you can do so via the UI or by running:
```bash
git remote add origin <BITBUCKET_URL>
```
*Note: If `origin` already exists, you may want to rename it or use a different name like `bitbucket`.*

### 3. Push local commits
// turbo
```bash
git push -u origin $(git branch --show-current)
```

### Authentication Tip
If using HTTPS, use an **App Password**:
1. Bitbucket → Personal settings → App passwords → Create app password.
2. Grant **read/write** repository permissions.
3. Use the generated password when prompted.

If using SSH, ensure your public key is added under **Personal settings → SSH keys**.
