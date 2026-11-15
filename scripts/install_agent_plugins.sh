#!/usr/bin/env bash
# Installs the agent marketplaces and plugins listed in .claude/settings.json
# (the single source of truth) into every agent CLI found on PATH:
# Claude Code, GitHub Copilot CLI and Codex. VS Code Copilot reads
# .claude/settings.json itself. Entries that are already installed fail quietly.

cd "$(dirname "$0")/.." || exit 0
settings=.claude/settings.json

if ! command -v jq >/dev/null; then
	echo "jq not found; skipping agent plugin install" >&2
	exit 0
fi

marketplaces=$(jq -r '.extraKnownMarketplaces[]?.source | select(.source == "github") | .repo' "$settings")
plugins=$(jq -r '.enabledPlugins // {} | to_entries[] | select(.value) | .key' "$settings")

# install_plugins <cli> <install verb...>
install_plugins() {
	local cli=$1 repo plugin
	shift
	command -v "$cli" >/dev/null || return 0

	for repo in $marketplaces; do
		echo "$cli: adding marketplace $repo"
		"$cli" plugin marketplace add "$repo" >/dev/null 2>&1 || true
	done
	for plugin in $plugins; do
		echo "$cli: installing plugin $plugin"
		"$cli" plugin "$@" "$plugin" >/dev/null 2>&1 || true
	done
}

install_plugins claude install
install_plugins copilot install
install_plugins codex add
exit 0
