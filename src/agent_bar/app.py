"""GTK AppIndicator daemon: panel icon, live token label, multi-session menu."""

from __future__ import annotations

import html
import signal
import time

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk, Pango

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
except ValueError:
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AppIndicator

from .adapters.base import STATUS_DONE, STATUS_IDLE, STATUS_NEEDS_YOU, STATUS_WORKING
from . import autostart
from .config import Config
from .notify import notify
from .paths import assets_dir
from .pricing import context_pct, cost_all, fmt_cost
from .sound import play_alert
from .stats import sum_total
from .tokens import fmt_tokens, total_tokens
from .watcher import SessionStore

CLI_LABEL = {"kimi": "Kimi", "claude": "Claude", "codex": "Codex", "grok": "Grok"}
STATUS_LABEL = {
    STATUS_WORKING: "working",
    STATUS_NEEDS_YOU: "needs you",
    STATUS_IDLE: "idle",
    STATUS_DONE: "done",
}

MENU_REFRESH_S = 30  # re-render menu so "x min ago" lines age


def fmt_elapsed(since: float) -> str:
    mins = int((time.time() - since) // 60)
    if mins < 1:
        return "just now"
    if mins < 60:
        return f"{mins} min ago"
    return f"{mins // 60} h {mins % 60} min ago"


class AgentBarApp:
    def __init__(self) -> None:
        self.cfg = Config.load()
        self.store = SessionStore()
        self.store.add_listener(self.refresh)

        self.ind = AppIndicator.Indicator.new(
            "agent-bar", "agent-bar-off",
            AppIndicator.IndicatorCategory.SYSTEM_SERVICES,
        )
        self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self._apply_icon_theme()
        self.ind.set_label("", "100%")

        self._tick_n = 0
        self._attention = False
        self._working = False
        self._notified: set[tuple[str, str]] = set()  # (session key, question)

        self.menu = Gtk.Menu()
        self.ind.set_menu(self.menu)
        self.refresh()

    def _apply_icon_theme(self) -> None:
        theme = "sym" if self.cfg.style == "symbolic" else "color"
        icon_path = str(assets_dir() / theme)
        self.ind.set_icon_theme_path(icon_path)
        # menu images use the GTK icon theme, not the AppIndicator one
        Gtk.IconTheme.get_default().append_search_path(icon_path)

    # --- main loop ---

    def run(self) -> None:
        self.store.start()
        GLib.timeout_add(self.cfg.spinner_ms, self._animate)
        GLib.timeout_add_seconds(MENU_REFRESH_S, self._refresh_menu_timer)
        signal.signal(signal.SIGINT, lambda *_: self.quit())
        Gtk.main()

    def quit(self, *_args) -> None:
        self.store.stop()
        Gtk.main_quit()

    # --- panel state ---

    def _aggregate_status(self) -> str:
        order = [STATUS_NEEDS_YOU, STATUS_WORKING, STATUS_IDLE, STATUS_DONE]
        statuses = {s.status for s in self.store.sessions.values()}
        for st in order:
            if st in statuses:
                return st
        return STATUS_DONE

    def _attention_icon(self) -> str:
        n = len(self.store.attention_sessions())
        if n <= 1:
            return "agent-bar-attention"
        if n > 9:
            return "agent-bar-attention-plus"
        return f"agent-bar-attention-{n}"

    def refresh(self) -> None:
        status = self._aggregate_status()
        sessions = self.store.sessions
        self._attention = status == STATUS_NEEDS_YOU
        self._working = status == STATUS_WORKING

        if not sessions:
            self.ind.set_icon_full("agent-bar-off", "agent-bar: no sessions")
        elif self._attention:
            self.ind.set_icon_full(self._attention_icon(), "agent-bar: needs you")
        elif self._working:
            frame = 1 if not self.cfg.spinner else (self._tick_n % 3) + 1
            self.ind.set_icon_full(f"agent-bar-work-{frame}", "agent-bar: working")
        elif status == STATUS_IDLE:
            self.ind.set_icon_full("agent-bar-idle", "agent-bar: idle")
        else:
            self.ind.set_icon_full("agent-bar-done", "agent-bar: done")

        today = self.store.today_total(self.cfg.count_cache_read)
        label = fmt_tokens(today) if (self.cfg.show_label and today) else ""
        self.ind.set_label(label, "999.9M")

        self._maybe_alert()
        self._rebuild_menu()

    def _animate(self) -> bool:
        """Single fast timer: spinner frames + attention blink + config reload."""
        self._tick_n += 1
        if self._tick_n % max(1, 2000 // self.cfg.spinner_ms) == 0:
            self._maybe_reload_config()
        if self._attention:
            steps = max(1, self.cfg.pulse_ms // self.cfg.spinner_ms)
            icon = self._attention_icon() if (self._tick_n // steps) % 2 == 0 \
                else "agent-bar-blank"
            self.ind.set_icon_full(icon, "agent-bar: needs you")
        elif self._working and self.cfg.spinner:
            self.ind.set_icon_full(
                f"agent-bar-work-{(self._tick_n % 3) + 1}", "agent-bar: working")
        return True

    def _refresh_menu_timer(self) -> bool:
        self._rebuild_menu()
        return True

    # --- live config reload (picks up edits within ~2 s) ---

    def _maybe_reload_config(self) -> None:
        from .config import CONFIG_PATH
        try:
            mtime = CONFIG_PATH.stat().st_mtime
        except OSError:
            return
        if mtime == getattr(self, "_cfg_mtime", None):
            return
        self._cfg_mtime = mtime
        old_style = self.cfg.style
        self.cfg = Config.load()
        if self.cfg.style != old_style:
            self._apply_icon_theme()
        self.refresh()

    # --- alerts ---

    def _maybe_alert(self) -> None:
        active = set()
        for st in self.store.attention_sessions():
            question = st.question or "Waiting for your input"
            active.add((st.key, question))
            if (st.key, question) not in self._notified:
                self._notified.add((st.key, question))
                cli = CLI_LABEL.get(st.cli, st.cli)
                if self.cfg.notifications:
                    notify(f"{cli} needs you", question, urgency="critical")
                if self.cfg.sound:
                    play_alert()
        self._notified &= active

    # --- menu ---

    def _session_item(self, st) -> Gtk.MenuItem:
        cli = CLI_LABEL.get(st.cli, st.cli)
        toks = fmt_tokens(total_tokens(st.tokens, self.cfg.count_cache_read)) if st.tokens else "0"
        top = (f"{cli} · {STATUS_LABEL.get(st.status, st.status)}"
               f" · {toks} tok · {fmt_elapsed(st.updated_at)}")
        ctx = context_pct(st.cli, self.store.last_context(st), self.cfg.context_window)
        if ctx is not None:
            top += f" · ctx {ctx:.0f}%"
        title = st.title or st.cwd.rsplit("/", 1)[-1] or st.session_id[:12]
        detail = st.question or title

        item = Gtk.MenuItem()
        hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        dot = Gtk.Image.new_from_icon_name(f"dot-{st.cli}", Gtk.IconSize.MENU)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        l1 = Gtk.Label(label=top, xalign=0)
        l2 = Gtk.Label(xalign=0)
        l2.set_markup(f"<small>{html.escape(detail[:110])}</small>")
        l2.set_ellipsize(Pango.EllipsizeMode.END)
        l2.get_style_context().add_class("dim-label")
        vbox.pack_start(l1, False, False, 0)
        vbox.pack_start(l2, False, False, 0)
        hbox.pack_start(dot, False, False, 0)
        hbox.pack_start(vbox, True, True, 0)
        item.add(hbox)
        if st.question:
            item.connect("activate", self._show_question, st)
        return item

    def _rebuild_menu(self) -> None:
        if self.menu.get_visible():
            return  # don't yank the menu while the user is browsing it
        for child in self.menu.get_children():
            self.menu.remove(child)
            child.destroy()

        sessions = sorted(
            self.store.sessions.values(),
            key=lambda s: (s.status != STATUS_NEEDS_YOU, s.status != STATUS_WORKING,
                           s.cli, s.session_id),
        )
        if not sessions:
            item = Gtk.MenuItem(label="No active sessions")
            item.set_sensitive(False)
            self.menu.append(item)

        for st in sessions:
            self.menu.append(self._session_item(st))

        self.menu.append(Gtk.SeparatorMenuItem())

        today = self.store.stats().today()
        week = self.store.stats().week()
        inc_cache = self.cfg.count_cache_read
        per_cli = ", ".join(
            f"{CLI_LABEL.get(k, k)} {fmt_tokens(total_tokens(v, inc_cache))}"
            for k, v in sorted(today.items())
        )
        cost_txt = ""
        if self.cfg.show_cost:
            cost_txt = (f" · {fmt_cost(cost_all(today, self.cfg.prices), self.cfg.currency)}"
                        f" today")
        stats_item = Gtk.MenuItem(
            label=f"Today: {fmt_tokens(sum_total(today, inc_cache))}"
                  + (f" ({per_cli})" if per_cli else "")
                  + f" · Week: {fmt_tokens(sum_total(week, inc_cache))}"
                  + cost_txt
        )
        stats_item.set_sensitive(False)
        self.menu.append(stats_item)

        if today:
            bd = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}
            for u in today.values():
                for k in bd:
                    bd[k] += u.get(k, 0)
            detail = Gtk.MenuItem(
                label=f"   in {fmt_tokens(bd['input'])} · out {fmt_tokens(bd['output'])}"
                      f" · cache {fmt_tokens(bd['cache_read'])}"
                      + ("" if inc_cache else " (excluded)"))
            detail.set_sensitive(False)
            self.menu.append(detail)

        top = Gtk.MenuItem(label="Top sessions")
        submenu = Gtk.Menu()
        for day, cli, title, sid, total in self.store.stats().top_sessions():
            row = Gtk.MenuItem(
                label=f"{fmt_tokens(total)} · {CLI_LABEL.get(cli, cli)} · "
                      f"{(title or sid[:12])[:40]} ({day[5:]})"
            )
            row.set_sensitive(False)
            submenu.append(row)
        if not submenu.get_children():
            empty = Gtk.MenuItem(label="No data yet")
            empty.set_sensitive(False)
            submenu.append(empty)
        top.set_submenu(submenu)
        self.menu.append(top)

        self.menu.append(Gtk.SeparatorMenuItem())
        self.menu.append(self._build_settings_menu())
        quit_item = Gtk.MenuItem(label="Quit agent-bar")
        quit_item.connect("activate", self.quit)
        self.menu.append(quit_item)

        self.menu.show_all()

    # --- settings submenu ---

    def _build_settings_menu(self) -> Gtk.MenuItem:
        settings = Gtk.MenuItem(label="Settings")
        sub = Gtk.Menu()

        for label, attr in (("Show token counter", "show_label"),
                            ("Include cache-read in totals", "count_cache_read"),
                            ("Animate while working", "spinner"),
                            ("Desktop notifications", "notifications"),
                            ("Alert sound", "sound"),
                            ("Show cost estimate", "show_cost")):
            item = Gtk.CheckMenuItem(label=label)
            item.set_active(getattr(self.cfg, attr))
            item.connect("toggled", self._on_toggle, attr)
            sub.append(item)

        if autostart.available():
            login_item = Gtk.CheckMenuItem(label="Launch at login")
            login_item.set_active(autostart.is_enabled())
            login_item.connect("toggled", self._on_autostart)
            sub.append(login_item)

        sub.append(Gtk.SeparatorMenuItem())

        r_sym = Gtk.RadioMenuItem(label="Symbolic icons (GNOME style)")
        r_col = Gtk.RadioMenuItem.new_with_label_from_widget(r_sym, "Color icons")
        (r_sym if self.cfg.style == "symbolic" else r_col).set_active(True)
        r_sym.connect("toggled", self._on_style, "symbolic")
        r_col.connect("toggled", self._on_style, "color")
        sub.append(r_sym)
        sub.append(r_col)

        blink = Gtk.MenuItem(label="Attention blink speed")
        bsub = Gtk.Menu()
        prev = None
        for label, ms in (("Slow", 900), ("Normal", 600), ("Fast", 350)):
            r = (Gtk.RadioMenuItem(label=label) if prev is None
                 else Gtk.RadioMenuItem.new_with_label_from_widget(prev, label))
            if abs(self.cfg.pulse_ms - ms) < 150:
                r.set_active(True)
            r.connect("toggled", self._on_pulse, ms)
            bsub.append(r)
            prev = r
        blink.set_submenu(bsub)
        sub.append(blink)

        settings.set_submenu(sub)
        return settings

    def _on_toggle(self, item, attr: str) -> None:
        setattr(self.cfg, attr, item.get_active())
        self.cfg.save()
        self.refresh()

    def _on_autostart(self, item) -> None:
        ok = autostart.set_enabled(item.get_active())
        if not ok:  # revert the checkbox if systemd refused
            item.set_active(not item.get_active())

    def _on_style(self, item, style: str) -> None:
        if not item.get_active():
            return
        self.cfg.style = style
        self.cfg.save()
        self._apply_icon_theme()
        self.refresh()

    def _on_pulse(self, item, ms: int) -> None:
        if not item.get_active():
            return
        self.cfg.pulse_ms = ms
        self.cfg.save()

    def _show_question(self, _item, st) -> None:
        cli = CLI_LABEL.get(st.cli, st.cli)
        notify(f"{cli} needs you", st.question or "", urgency="critical")


def main() -> None:
    AgentBarApp().run()
