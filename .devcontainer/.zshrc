# ~/.zshrc in the dev container. Same setup as on the Mac: antidote loads the plugins
# from ~/.zsh_plugins.txt (Zephyr for the basics, jenreh/zsh-utils for the rest) and
# the prompt is starship with the transient prompt.

typeset -U path
path=(~/bin ~/.local/bin $path)

# Plugins
export AUTOSWITCH_SILENT=1    # zsh-autoswitch-virtualenv: no message when switching
export ANTIDOTE_HOME=~/.cache/antidote
# zsh-utils writes these completions to ~/.zfunc and refreshes them on tool updates
zstyle ':zsh-utils:completion' generate 'ngrok completion' 'task --completion zsh'
source /usr/local/share/antidote/antidote.zsh
antidote load ~/.zsh_plugins.txt

# fzf-tab group headers: _description prefers Zephyr's ':completion:*' format over the
# '[%d]' descriptions format zsh-utils sets, and fzf-tab shows its %F escapes literally
# (e.g. in `git <Tab>`). Runs after the zsh-utils hook, which also uses post_zshrc.
function _fzf-tab-plain-headers {
  zstyle -d ':completion:*' format
  zstyle -d ':completion:*:corrections' format
}
add-post-zshrc-hook _fzf-tab-plain-headers

# Aliases
alias ll='ls -lh'
alias la='ls -lAh'
alias l='ls -CF'
alias lt='ls -lAht'            # newest first
alias mkdir='mkdir -p'
alias df='df -h'
alias du='du -h'
alias c='clear'
alias path='print -l $path'
alias reload='exec zsh'
alias g='git'
alias gst='git status -sb'
alias gdf='git diff'
alias glg='git log --oneline --graph --decorate -20'
alias gp='git pull'
alias gco='git checkout'
