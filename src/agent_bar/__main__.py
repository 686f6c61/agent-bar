"""agent-bar CLI entry point.

Usage:
  agent-bar                      run the panel indicator daemon
  agent-bar hook --cli <name>    hook bridge (called by the CLIs, not by users)
  agent-bar install-hooks        register hooks in Kimi/Claude/Codex configs
  agent-bar uninstall-hooks      remove them
  agent-bar stats                print today's/week's token usage
"""

from __future__ import annotations

import argparse
import shutil
import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-bar", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"agent-bar {__version__}")
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("run", help="run the panel indicator daemon")

    p_hook = sub.add_parser("hook", help="hook bridge invoked by the CLIs")
    p_hook.add_argument("--cli", required=True, choices=["kimi", "claude", "codex"])
    p_hook.add_argument("payload", nargs="?", default=None,
                        help="JSON payload (Codex passes it as argv; others use stdin)")

    sub.add_parser("install-hooks", help="register hooks in the three CLI configs")
    sub.add_parser("uninstall-hooks", help="remove hooks from the three CLI configs")
    sub.add_parser("stats", help="print token usage summary")
    sub.add_parser("doctor", help="check environment, hooks and service status")

    args = parser.parse_args(argv)

    if args.cmd == "hook":
        from .bridge import run_hook
        return run_hook(args.cli, args.payload)

    if args.cmd == "install-hooks":
        from .hooks_install import install_all
        bin_path = shutil.which("agent-bar") or sys.argv[0]
        for line in install_all(bin_path):
            print(line)
        return 0

    if args.cmd == "uninstall-hooks":
        from .hooks_install import uninstall_all
        for line in uninstall_all():
            print(line)
        return 0

    if args.cmd == "stats":
        from .config import Config
        from .paths import stats_db
        from .pricing import cost_all, fmt_cost
        from .stats import Stats, sum_total
        from .tokens import fmt_tokens, total_tokens
        cfg = Config.load()
        st = Stats(stats_db())
        today, week = st.today(), st.week()
        print(f"Today: {fmt_tokens(sum_total(today))} tokens"
              f"  ({fmt_cost(cost_all(today, cfg.prices), cfg.currency)})")
        for cli, u in sorted(today.items()):
            from .pricing import cost as cli_cost
            print(f"  {cli:8s} {fmt_tokens(total_tokens(u)):>8s}"
                  f"  {fmt_cost(cli_cost(cli, u, cfg.prices), cfg.currency)}")
            print(f"           in {fmt_tokens(u['input'])}"
                  f" · out {fmt_tokens(u['output'])}"
                  f" · cache-read {fmt_tokens(u['cache_read'])}"
                  f" · cache-write {fmt_tokens(u['cache_write'])}")
        print(f"Week:  {fmt_tokens(sum_total(week))} tokens"
              f"  ({fmt_cost(cost_all(week, cfg.prices), cfg.currency)})")
        print("\nNote: cache-read tokens are re-sent context billed at a lower"
              " rate; they dominate the total but not the cost.")
        return 0

    if args.cmd == "doctor":
        from .doctor import run as doctor_run
        return doctor_run()

    # default: run the daemon
    from .app import main as app_main
    app_main()
    return 0


if __name__ == "__main__":
    sys.exit(main())
