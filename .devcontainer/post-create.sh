#!/bin/bash
set -e

cd "$WORKSPACE"
# Configure git to allow the workspace as a safe directory
git config --global --add safe.directory "$WORKSPACE"
# The ~/.gitconfig copied from the Mac points the GitHub credential helper at
# /opt/homebrew/bin/gh; drop it so VS Code's forwarded credential helper is used
for host in https://github.com https://gist.github.com; do
	git config --global --remove-section "credential.$host" 2>/dev/null || true
done

echo "Setting up zsh"
mkdir -p /home/vscode/.mcp
cp "$WORKSPACE"/.devcontainer/.zsh_plugins.txt "$HOME"/.zsh_plugins.txt
cp "$WORKSPACE"/.devcontainer/.zshrc "$HOME"/.zshrc
# Clone the plugins now, so the first terminal opens without a delay
zsh -i -c exit

echo "Initializing project"
task init

echo "Running database migrations"
uv run alembic upgrade head
