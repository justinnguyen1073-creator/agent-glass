# Agent Glass — Plasma 6

Formerly **Codex Glass**. Tracks Codex and Claude Code usage side by side, with combined spending.

A native KDE Plasma widget for your Codex account's 5-hour and weekly usage, with Liquid Glass styling and desktop/panel support.

**No CodexBar required.** The widget uses your existing Codex installation and ChatGPT sign-in. It does not ask for credentials or require a paid API key.

## Installation

### Requirements

- KDE Plasma 6 on Linux (tested with Plasma 6.7.5 on Fedora KDE Wayland).
- Python 3 and KDE's Plasma5Support executable data engine.
- An existing Codex installation that supports `codex app-server`, signed in with your ChatGPT account. API-key-only authentication does not provide these subscription usage limits.

On Fedora, install the desktop dependencies if needed:

```sh
sudo dnf install git python3 plasma-workspace plasma5support
```

If you already use Codex, keep your existing installation and sign-in. No separate usage tracker or additional login is needed. If Codex itself is missing, follow [OpenAI's Codex CLI instructions](https://developers.openai.com/codex/cli).

### Install the widget

```sh
git clone https://github.com/justinnguyen1073-creator/agent-glass.git
cd agent-glass
./install.sh
```

The installer registers only `org.local.codexglass2` in your personal Plasma widget directory. It does not edit panels, change desktop configuration, modify other widgets, or restart Plasma.

Right-click the desktop or enter panel edit mode, choose **Add Widgets**, search **Agent Glass**, and drag it into place. In a panel, click the compact indicator to open the full view.

### Upgrading from the original Codex Glass

**Add the new widget named “Agent Glass”.** It has a new package ID (`org.local.codexglass2`) so Plasma loads the redesigned QML from a fresh path. In a long-running Plasma session, upgrading the original package on disk can leave its old QML component cached, even when its settings page is updated. Removing and re-adding the original name may still reuse that cached component.

The installer deliberately leaves the old widget and its placement intact. Once you have added Agent Glass, remove the old instance through desktop edit mode. The new widget starts with fresh settings; no Plasma restart or manual desktop configuration edit is required.

### Configure

Right-click → **Configure Agent Glass** to choose:

- Refresh interval: default 60 seconds, configurable from 15 to 3600 seconds.
- Appearance: glass or solid background. Glass matches the Liquid Glass widgets with white lettering, wallpaper-driven color, and a default 10% tint. Solid mode supports follow-system, dark, or light appearance.
- Glass controls: corner radius, roundness, tint opacity, blur, refraction thickness/index/strength, chromatic aberration, reflections, and optional animated-wallpaper capture.
- Bar values: usage consumed or allowance remaining. Both percentages remain explicitly labeled in the full view; the panel percentage follows this setting and represents the 5-hour window.
- Codex executable: leave blank for auto-detection, or provide the absolute path to your existing Codex CLI/app-server executable.

Auto-detection checks PATH, common user installation locations, and nvm installations. For npm/nvm installs it uses the matching Node executable when available, so Plasma does not need to load your shell configuration. A Codex desktop installation with a bundled CLI can use that executable through the path setting; the graphical desktop launcher itself is not an app-server executable.

## Claude usage

If you use Claude Code, a **Claude** section appears under Codex with your plan's 5-hour and weekly usage. It reuses Claude Code's existing sign-in (`~/.claude/.credentials.json`), sends that token only to Anthropic's usage endpoint, and never refreshes or stores it — if the sign-in expires, open Claude Code once.

The spending face adds Claude Code's local history (`~/.claude/projects`) to Codex's: totals, token counts and the daily chart cover both agents, with a per-agent split line and stacked chart bars. Claude is priced at Anthropic list rates, including 5-minute/1-hour cache writes and cache reads.

## Flip to spending

Tap the expanded widget to flip it over; tap again or use the back arrow to return to usage. Space/Return work when the card has focus. The refresh button refreshes without flipping. Panel users first click the compact indicator to expand the widget.

At widths of 440 px or more, token totals switch from M/B abbreviations to full locale-formatted counts. At 440×480 px (or a wide 700×400 px layout), input/cache/output/unpriced counts and chart details appear. Taller views also show the pricing snapshot and scope. Compact views keep those details in tooltips.

The back shows today's and the last 30 local calendar days' **list-price estimate in USD**, token totals, and a daily cost chart. Hover a bar for its date/value, the token total for input/cache/output details, or the estimate subtitle for the calculation basis.

Spending is calculated locally from `CODEX_HOME/sessions` and `archived_sessions` (default `~/.codex`). Owned `token_usage_record` entries are authoritative and deduplicated by response identity. Their legacy `token_count` notifications are reconciled as mirrors, so they are not counted again. Older logs use request-level usage with cumulative-counter safeguards. Thread ownership, explicit subagent ordinals, and session IDs exclude copied parent history and duplicate archives. Cached input is discounted and reasoning output is already included in output tokens. Calendar buckets use the desktop's local timezone. No prompts, tool results, session IDs, file paths, or model identifiers are returned to QML or sent anywhere.

These are **hypothetical API-equivalent token-cost estimates, not subscription charges, exact savings, or an invoice**. They include known long-context pricing (the whole request switches tiers above 272,000 input tokens), date-aware historical rates, cached-input discounts, cache writes, and published Fast multipliers when local metadata identifies priority processing. Optional local trace metadata is read through a read-only SQLite connection; prompts stay inside SQLite and are not returned to the helper. Unsupported model/tier combinations remain unpriced. Tool charges, nonlocal history, CodexBar custom overrides, and external-provider mirrors are outside this widget's estimate. Unknown pricing is explicitly labeled as an unpriced token count and the dollar total as the priced portion. No-history/no-priced-usage states display a dash instead of inventing costs. Prices are a bundled snapshot verified on 2026-10-15 from [OpenAI's pricing page](https://developers.openai.com/api/docs/pricing) and the [GPT-5.5 model page](https://developers.openai.com/api/docs/models/gpt-5.5); updating the widget updates that snapshot. The accounting behavior and rate snapshot are also cross-checked against [CodexBar](https://github.com/steipete/CodexBar). No CodexBar runtime dependency was added; see [third-party notices](THIRD_PARTY_NOTICES.md).

## Update, package, or remove

To update an existing source installation:

```sh
git pull --ff-only
./install.sh
```

For the original-to-v2 migration, add **Agent Glass** as described above. Future updates within the same package ID can still be affected by Plasma's in-memory QML cache; the installer never restarts your session automatically.

To build an installable archive using Python's standard library:

```sh
python3 build-package.py
```

In Plasma, use Add Widgets → Get New Widgets → Install Widget From Local File and select `dist/agent-glass.plasmoid`.

Remove instances using Plasma's edit mode. To uninstall the package:

```sh
kpackagetool6 --type Plasma/Applet --remove org.local.codexglass2
```

## Data and privacy

The small Python helper opens a private stdio connection to `codex app-server --listen stdio://`. After the initialization handshake, it calls only `account/rateLimits/read`, then terminates its own server process group. It never starts a conversation, sends a model prompt, or redeems reset credits. The entire request has a 40-second deadline.

This uses the [documented Codex app-server interface](https://developers.openai.com/codex/app-server). The verified response contains `rateLimitsByLimitId.codex` (preferred) or the legacy `rateLimits`. The helper selects `primary`/`secondary` windows by `windowDurationMins: 300` and `10080`, reads `usedPercent`, and converts Unix `resetsAt` timestamps to ISO dates. It never assumes primary always means five hours or substitutes another model's limit bucket. A missing or invalid matching window is **Unavailable**, distinct from 0% used.

Codex manages its existing authentication; the helper never reads token files or asks for passwords. Only sanitized usage values and a successful retrieval timestamp reach QML. Account IDs, identity, credits, credentials, and raw diagnostics are discarded. The widget does not persist usage data; Codex retains control of its own normal caches/logs. Failed refreshes preserve the last successful values in memory and mark them stale. Reset dates use the desktop's local timezone, including its timezone label.

## Troubleshooting

- **Codex not found:** select the absolute path to your existing Codex executable in widget settings. A terminal can locate it with `command -v codex`.
- **Sign-in error:** sign in to Codex using your ChatGPT account through your normal Codex workflow, then refresh. API-key-only login cannot provide these account limits.
- **Unsupported usage method:** update your Codex installation to a version supporting `account/rateLimits/read`.
- **Offline / timeout / stale:** check connectivity and retry. For sanitized diagnostics, run `python3 contents/code/usage.py` from this repository; optionally add `--codex /absolute/path/to/codex`.
- **Unavailable:** the account did not report a valid window matching that duration. The widget does not fabricate missing values.
- **No desktop frost:** wallpaper refraction requires Plasma's wallpaper containment. Panels and standalone viewers use a translucent fallback. Unsupported wallpaper renderers may also fall back. Solid mode improves contrast independently of the wallpaper.

The widget uses KDE's [Plasma 6 compatibility DataSource API](https://develop.kde.org/docs/plasma/widget/porting_kf6/) to invoke its fixed local helper.

## Verification

Run the account-independent tests:

```sh
python3 tests/test_usage.py
python3 tests/test_spending.py
```

Tests cover parsing, bucket selection, missing windows, invalid percentages/reset dates, authentication/network errors, executable discovery, privacy, and the real stdio transport with a simulated server (handshake, notifications, fragmented messages, unexpected requests, EOF, and timeout cleanup).

An independent frozen copy of native Codex logs has been compared with CodexBar: today, 30-day totals, every daily bucket, and input/cache/output/total token counts match (cost differences below $0.000001 from output rounding). This verifies that dataset, not every possible CodexBar data source or future log format. A developer-only `tests/compare_codexbar.py` accepts a frozen history root and CodexBar JSON for repeatable comparisons.

Live direct Codex retrieval has been verified with Codex CLI 0.163.0. QML compilation and standalone rendering/data connection checks cover the widget views; actual desktop wallpaper refraction must be checked after adding the widget to a containment.

## Attribution and license

ChatGPT/OpenAI and Claude logos come from [Simple Icons](https://simpleicons.org) (CC0) and are trademarks of OpenAI and Anthropic; this project is not affiliated with either.

GPL-3.0-or-later; see [LICENSE](LICENSE). The unmodified `contents/ui/components/LiquidGlass.qml` and shader sources/binaries are from Jaxparrow07's [liquidglass-kde-widgets](https://github.com/jaxparrow07/liquidglass-kde-widgets) project. They are vendored copies for this separate package, with no changes to the original project or installed widgets. All corresponding shader sources are included.

This is an independent community widget, unaffiliated with OpenAI or KDE.
