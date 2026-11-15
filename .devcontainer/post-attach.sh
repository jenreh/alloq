#!/bin/bash
# Installs the agent marketplaces and plugins listed in the project settings of
# Copilot (.github/copilot/settings.json) and Claude Code (.claude/settings.json).
# Runs on every attach; entries that are already installed fail quietly.

cd "$WORKSPACE" || exit 0

# install_plugins <cli> <settings file> <name>
install_plugins() {
	local cli=$1 settings=$2 name=$3 repo plugin
	command -v "$cli" >/dev/null || return 0
	[[ -f $settings ]] || return 0

	echo "Installing $name agent plugins"
	for repo in $(jq -r '.extraKnownMarketplaces[].source | select(.source == "github") | .repo' "$settings"); do
		echo "Adding $name marketplace: $repo"
		"$cli" plugin marketplace add "$repo" >/dev/null 2>&1 || true
	done
	for plugin in $(jq -r '.enabledPlugins | to_entries[] | select(.value) | .key' "$settings"); do
		echo "Installing $name plugin: $plugin"
		"$cli" plugin install "$plugin" >/dev/null 2>&1 || true
	done
}

install_plugins copilot "$WORKSPACE/.github/copilot/settings.json" Copilot
install_plugins claude "$WORKSPACE/.claude/settings.json" "Claude Code"
exit 0
