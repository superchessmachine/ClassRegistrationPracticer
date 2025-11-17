import time
from datetime import datetime, timedelta
from typing import List, Optional

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components


APP_NAME = "SuperRegistrationMachine"
DEFAULT_WINDOW_SECONDS = 10.0  # default: from 6:59:50 to 7:00:00
RESET_DELAY = 3.0  # auto-restart delay after clicking
TARGET_TIME = datetime(2000, 1, 1, 7, 0, 0)  # purely display, not real clock
RESULT_DIGITS = 5


def get_base_time(window_seconds: float) -> datetime:
    return TARGET_TIME - timedelta(seconds=window_seconds)


def format_clock(elapsed: float, show_millis: bool, window_seconds: float) -> str:
    base = get_base_time(window_seconds) + timedelta(seconds=max(0.0, elapsed))
    # allow flexible fractional precision
    digits = st.session_state.get("precision_digits", 3 if show_millis else 2)
    digits = max(0, min(5, int(digits)))
    if digits == 0:
        return base.strftime("%I:%M:%S %p").lstrip("0")
    raw = base.strftime("%I:%M:%S.%f %p").lstrip("0")
    time_part, meridiem = raw.split(" ")
    trimmed = time_part[:- (6 - digits)]  # drop extra microsecond digits
    return f"{trimmed} {meridiem}"


def format_remaining(seconds: float, show_millis: bool, *, digits_override: Optional[int] = None) -> str:
    total = max(0.0, seconds)
    h = int(total // 3600)
    m = int((total % 3600) // 60)
    s = total % 60
    base_digits = st.session_state.get("precision_digits", 3 if show_millis else 2)
    digits = digits_override if digits_override is not None else base_digits
    digits = max(0, min(5, int(digits)))
    frac_fmt = f"{s:0{3 + digits}.{digits}f}" if digits else f"{int(s):02d}"
    return f"{h:02d}:{m:02d}:{frac_fmt}"


def init_state() -> None:
    if "round_started_at" not in st.session_state:
        st.session_state.round_started_at = time.time()
        st.session_state.last_result: Optional[str] = None
        st.session_state.last_status: Optional[str] = None
        st.session_state.reaction_times_ms: List[float] = []
        st.session_state.reaction_times_standard: List[float] = []
        st.session_state.next_reset_at: Optional[float] = None
        st.session_state.window_seconds = DEFAULT_WINDOW_SECONDS
        st.session_state.precision_digits = 3


def reset_attempt() -> None:
    st.session_state.round_started_at = time.time()
    st.session_state.last_result = None
    st.session_state.last_status = None
    st.session_state.next_reset_at = None


def elapsed_seconds() -> float:
    return max(0.0, time.time() - st.session_state.round_started_at)


def register_click() -> None:
    elapsed = elapsed_seconds()
    window_seconds = float(st.session_state.get("window_seconds", DEFAULT_WINDOW_SECONDS))
    precision_digits = int(st.session_state.get("precision_digits", 3))
    show_ms = precision_digits >= 3
    if elapsed < window_seconds:
        remaining = window_seconds - elapsed
        st.session_state.last_status = "warning"
        st.session_state.last_result = (
            f"Too early! {format_remaining(remaining, show_ms, digits_override=RESULT_DIGITS)} "
            "remain before 7:00:00."
        )
    else:
        reaction = elapsed - window_seconds
        if show_ms:
            st.session_state.reaction_times_ms.append(reaction)
        else:
            st.session_state.reaction_times_standard.append(reaction)
        st.session_state.last_status = "success"
        st.session_state.last_result = (
            f"Registered {reaction:.5f}s after 7:00:00. Nice reflexes!"
        )
    st.session_state.next_reset_at = time.time() + RESET_DELAY


def maybe_auto_reset() -> None:
    if st.session_state.next_reset_at:
        remaining = st.session_state.next_reset_at - time.time()
        if remaining <= 0:
            reset_attempt()
            st.experimental_rerun()
        else:
            # poll the timer by asking the client to request a rerun
            interval_ms = max(300, int(min(remaining, 1.0) * 1000))
            components.html(
                f"<script>setTimeout(() => window.parent.postMessage({{isStreamlitMessage:true, type:'streamlit:requestRerun'}}, '*'), {interval_ms});</script>",
                height=0,
                width=0,
            )


def cool_styles() -> None:
    st.markdown(
        """
        <style>
        .main {
            background: radial-gradient(circle at 20% 20%, #0f172a 0, #020617 35%, #000 70%);
            color: #e2e8f0;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }
        div.stButton > button {
            border-radius: 999px;
            padding: 0.75rem 1.35rem;
            border: 1px solid #38bdf8;
            background: linear-gradient(90deg, #06b6d4, #2563eb);
            color: #0b1220;
            font-weight: 700;
            letter-spacing: 0.02em;
        }
        div.stTab { margin-top: 0.5rem; }
        .countdown-box {
            padding: 1.2rem 1.6rem;
            border-radius: 20px;
            background: linear-gradient(135deg, rgba(56, 189, 248, 0.12), rgba(94, 234, 212, 0.08));
            border: 1px solid rgba(148, 163, 184, 0.3);
        }
        .clock-face {
            font-size: 4rem;
            font-variant-numeric: tabular-nums;
            font-weight: 800;
            text-align: center;
            color: #e0f2fe;
            text-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
        }
        .ready {
            color: #34d399;
            text-shadow: 0 0 22px rgba(52, 211, 153, 0.75);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def countdown_card() -> None:
    precision = st.select_slider(
        "Timer precision (decimal places)",
        options=[1, 2, 3, 4, 5],
        value=int(st.session_state.get("precision_digits", 3)),
        key="precision_digits",
        help="Choose how many decimal digits the timer displays.",
    )
    show_ms = precision >= 3
    default_window = float(st.session_state.get("window_seconds", DEFAULT_WINDOW_SECONDS))
    window_seconds = st.slider(
        "Seconds before 7:00:00 to start",
        min_value=2.0,
        max_value=30.0,
        value=default_window,
        step=0.5,
        key="window_seconds",
        on_change=reset_attempt,
        help="Adjust how far before 7:00:00 the countdown begins.",
    )
    base_time = get_base_time(window_seconds)
    elapsed = elapsed_seconds()
    remaining = window_seconds - elapsed
    ready = remaining <= 0.0
    display_time = format_clock(elapsed, show_ms, window_seconds)

    components.html(
        f"""
        <style>
        .trainer-box {{
            padding: 1.2rem 1.6rem;
            border-radius: 20px;
            background: linear-gradient(135deg, rgba(56, 189, 248, 0.12), rgba(94, 234, 212, 0.08));
            border: 1px solid rgba(148, 163, 184, 0.3);
        }}
        .trainer-clock {{
            font-size: 4rem;
            font-variant-numeric: tabular-nums;
            font-weight: 800;
            text-align: center;
            color: #e0f2fe;
            text-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
            transition: color 0.3s ease, text-shadow 0.3s ease;
        }}
        .trainer-ready {{
            color: #34d399;
            text-shadow: 0 0 22px rgba(52, 211, 153, 0.75);
        }}
        </style>
        <div class="trainer-box">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:1rem; flex-wrap:wrap;">
                <div style="flex:1; min-width:220px;">
                    <div style="color:#94a3b8; font-weight:600;">Counting up to 7:00:00</div>
                    <div id="countdown-clock" class="trainer-clock">{display_time}</div>
                    <div id="countdown-status" style="color:{'#34d399' if ready else '#cbd5e1'}; font-weight:700;">{"HIT REGISTER NOW" if ready else "Wait for 7:00:00"}</div>
                </div>
                <div style="flex:1; min-width:220px; text-align:right; color:#cbd5e1;">
                    <div style="font-size:2.5rem; font-weight:800;">7:00:00 AM</div>
                    <div style="opacity:0.7;">Simulated window</div>
                </div>
            </div>
        </div>
        <script>
        (function() {{
            const startTs = {int(st.session_state.round_started_at * 1000)};
            const windowMs = {int(window_seconds * 1000)};
            const clockEl = document.getElementById('countdown-clock');
            const statusEl = document.getElementById('countdown-status');
            const targetMs = Date.UTC(2000, 0, 1, 7, 0, 0, 0);
            const baseMs = targetMs - windowMs;
            const precisionDigits = {precision};

            function format(remainingMs) {{
                const dt = new Date(baseMs + Math.max(0, remainingMs));
                const pad = (n) => n.toString().padStart(2, "0");
                const hours = pad(dt.getUTCHours());
                const minutes = pad(dt.getUTCMinutes());
                const secondsWhole = pad(dt.getUTCSeconds());
                if (precisionDigits > 0) {{
                    const millis = dt.getUTCMilliseconds().toString().padStart(3, "0");
                    const padded = (millis + "0000").slice(0, precisionDigits);
                    return `${{hours}}:${{minutes}}:${{secondsWhole}}.${{padded}}`;
                }}
                return `${{hours}}:${{minutes}}:${{secondsWhole}}`;
            }}

            function tick() {{
                const now = Date.now();
                const elapsedMs = now - startTs;
                const ready = elapsedMs >= windowMs;
                if (clockEl) {{
                    clockEl.textContent = format(elapsedMs);
                    clockEl.className = ready ? "trainer-clock trainer-ready" : "trainer-clock";
                }}
                if (statusEl) {{
                    statusEl.textContent = ready ? "HIT REGISTER NOW" : "Wait for 7:00:00";
                    statusEl.style.color = ready ? "#34d399" : "#cbd5e1";
                }}
                requestAnimationFrame(tick);
            }}

            tick();
        }})();
        </script>
        """,
        height=220,
    )

    st.button(
        "REGISTER",
        on_click=register_click,
        type="primary",
        use_container_width=True,
    )

    st.button(
        "🔄 Reset to next window",
        on_click=reset_attempt,
        help="Clear messages and jump to the next 7:00 AM slot.",
    )

    if st.session_state.last_result:
        if st.session_state.last_status == "warning":
            st.warning(st.session_state.last_result)
        else:
            st.success(st.session_state.last_result)
        st.caption("Resetting for the next attempt in about 3 seconds…")

    st.caption(
        f"Window: {base_time.strftime('%I:%M:%S').lstrip('0')} → 7:00:00 • "
        f"Precision: {precision} decimal place{'s' if precision != 1 else ''}"
    )


def stats_tab() -> None:
    st.subheader("Performance pulse")
    if st.button("Reset statistics", type="secondary"):
        st.session_state.reaction_times_ms = []
        st.session_state.reaction_times_standard = []
        st.experimental_rerun()

    ms_times = st.session_state.reaction_times_ms
    standard_times = st.session_state.reaction_times_standard
    max_time = 0.0
    if ms_times:
        max_time = max(max_time, max(ms_times))
    if standard_times:
        max_time = max(max_time, max(standard_times))
    y_domain = [0, max_time * 1.05] if max_time > 0 else None

    col_ms, col_standard = st.columns(2)

    def render_stats_block(col, title: str, times: List[float]) -> None:
        with col:
            st.markdown(f"#### {title}")
            if not times:
                st.info("No reaction times yet in this mode.")
                return

            data = pd.DataFrame({"reaction_s": times})
            metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
            metrics_col1.metric("Attempts", len(times))
            metrics_col2.metric("Mean (s)", f"{np.mean(times):.3f}")
            metrics_col3.metric("Best (s)", f"{np.min(times):.3f}")

            hist = (
                alt.Chart(data)
                .mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6)
                .encode(
                    alt.X("reaction_s:Q", bin=alt.Bin(maxbins=12), title="Reaction time (s)"),
                    alt.Y("count()", title="Attempts"),
                    tooltip=[alt.Tooltip("count()", title="Attempts"), "reaction_s:Q"],
                )
                .properties(height=200)
            )
            mean_line = (
                alt.Chart(pd.DataFrame({"mean": [np.mean(times)]}))
                .mark_rule(color="#38bdf8", strokeDash=[6, 4])
                .encode(x="mean:Q")
            )
            st.altair_chart(hist + mean_line, use_container_width=True)

            streak = data.reset_index().rename(columns={"index": "attempt"})
            line = (
                alt.Chart(streak)
                .mark_line(point=True)
                .encode(
                    x=alt.X("attempt:Q", title="Attempt #"),
                    y=alt.Y(
                        "reaction_s:Q",
                        title="Reaction time (s)",
                        scale=alt.Scale(domain=y_domain) if y_domain else alt.Undefined,
                    ),
                    tooltip=["attempt", "reaction_s:Q"],
                )
                .properties(height=180)
            )
            st.altair_chart(line, use_container_width=True)

    render_stats_block(col_ms, "Milliseconds mode", ms_times)
    render_stats_block(col_standard, "Hundredths mode", standard_times)

    st.caption("Lower is better. Nail runs in each mode to see separate stats side-by-side.")


def main() -> None:
    st.set_page_config(page_title=APP_NAME, page_icon="⏱️")
    cool_styles()
    init_state()
    maybe_auto_reset()

    st.title(APP_NAME)
    st.write(
        "Practice the final stretch before **7:00:00 AM**. Adjust how early the clock starts "
        "so you can squeeze in more runs or take your time."
    )

    countdown_tab, stats_view = st.tabs(["⏱️ Countdown", "📊 Stats"])

    with countdown_tab:
        countdown_card()
    with stats_view:
        stats_tab()


if __name__ == "__main__":
    main()
