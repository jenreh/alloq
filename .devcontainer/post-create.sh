#!/bin/bash
set -e

cd "$WORKSPACE"
# Configure git to allow the workspace as a safe directory
git config --global --add safe.directory "$WORKSPACE"
for host in https://github.com https://gist.github.com; do
	git config --global --remove-section "credential.$host" 2>/dev/null || true
done

# The volume only copies the image's folders when it is new; recreate any missing ones
mkdir -p "$HOME"/.persist/{cache,uv,claude,copilot}

echo "Setting up zsh"
mkdir -p /home/vscode/.mcp
cp "$WORKSPACE"/.devcontainer/.zsh_plugins.txt "$HOME"/.zsh_plugins.txt
cp "$WORKSPACE"/.devcontainer/.zshrc "$HOME"/.zshrc
# Clone the plugins now (in parallel), so the first terminal opens without a delay
zsh -i -c exit >/dev/null 2>&1 &
zsh_pid=$!

# Installs Python, syncs deps, builds the pre-commit envs and migrates the database
echo "Initializing project"
task init

wait "$zsh_pid" || echo "zsh plugin setup failed; the first terminal retries it"
