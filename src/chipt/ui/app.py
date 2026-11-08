"""Chipt MVP Streamlit UI: Find -> Claim -> Analyse (spec §4).

Throwaway UI (Next.js replaces it in V1). Talks to the backend only over HTTP.
Run with: uv run streamlit run src/chipt/ui/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# `streamlit run` puts only this file's directory on sys.path. Add `src/` so `chipt` imports
# even when the venv's editable-install .pth is skipped (macOS hidden-flag issue, see README).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import altair as alt
import pandas as pd
import streamlit as st

from chipt.schemas import AnalysisOut, AnalysisPoint, ResultOut
from chipt.ui import api_client as api
from chipt.ui.api_client import ApiError

ANY = "Any"

# Vega expression: seconds -> [H:]MM:SS for axis labels.
TIME_LABEL_EXPR = (
    "(datum.value >= 3600 ? floor(datum.value / 3600) + ':' : '') + "
    "pad('' + floor((datum.value % 3600) / 60), 2, '0', 'left') + ':' + "
    "pad('' + floor(datum.value % 60), 2, '0', 'left')"
)
PACE_LABEL_EXPR = (
    "floor(datum.value / 60) + ':' + pad('' + floor(datum.value % 60), 2, '0', 'left')"
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def fmt_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "-"
    s = int(round(abs(seconds)))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def fmt_signed(seconds: float | int | None) -> str:
    if seconds is None:
        return "-"
    sign = "+" if seconds > 0 else "-" if seconds < 0 else "±"
    return f"{sign}{fmt_duration(seconds)}"


@st.cache_data(ttl=60, show_spinner=False)
def cached_filters():
    return api.get_filters()


def show_api_error(exc: Exception) -> None:
    st.error(f"**Couldn't load data.** {exc}")


def results_frame(results: list[ResultOut], with_score: bool = False) -> pd.DataFrame:
    rows = []
    for r in results:
        row = {"id": r.id}
        if with_score:
            row["Match"] = round(getattr(r, "score", 0.0) * 100)
        row |= {
            "Name": r.athlete_name,
            "Event": r.event_name,
            "Date": r.event_date,
            "Discipline": r.discipline.value,
            "Distance": r.distance_label,
            "Chip time": r.chip_time,
            "Age group": r.age_group,
            "Gender": r.gender,
            "Rank": r.overall_rank,
            "Provider": r.provider_name,
        }
        rows.append(row)
    return pd.DataFrame(rows)


COMMON_COLUMN_CONFIG = {
    "id": None,  # hide
    "Date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
    "Rank": st.column_config.NumberColumn("Rank", format="%d"),
    "Match": st.column_config.ProgressColumn(
        "Match", help="Name match confidence", format="%d%%", min_value=0, max_value=100
    ),
}


def apply_claim_changes(to_claim: list[int], to_unclaim: list[int]) -> None:
    errors = []
    for rid in to_claim:
        try:
            api.claim(rid)
        except ApiError as exc:
            errors.append(f"claim #{rid}: {exc}")
    for rid in to_unclaim:
        try:
            api.unclaim(rid)
        except ApiError as exc:
            errors.append(f"unclaim #{rid}: {exc}")
    ok_claim = len(to_claim) - sum(e.startswith("claim") for e in errors)
    ok_unclaim = len(to_unclaim) - sum(e.startswith("unclaim") for e in errors)
    msg = []
    if ok_claim:
        msg.append(f"Claimed {ok_claim} result{'s' if ok_claim != 1 else ''}")
    if ok_unclaim:
        msg.append(f"unclaimed {ok_unclaim}")
    if msg:
        st.session_state["flash"] = ", ".join(msg).capitalize() + "."
    if errors:
        st.session_state["flash_error"] = "Some changes failed: " + "; ".join(errors)
    # Force data editors to reset so they reflect fresh server state.
    st.session_state["editor_gen"] = st.session_state.get("editor_gen", 0) + 1


def show_flash() -> None:
    if msg := st.session_state.pop("flash", None):
        st.success(msg)
    if err := st.session_state.pop("flash_error", None):
        st.error(err)


# --------------------------------------------------------------------------- #
# Page: Find & Claim
# --------------------------------------------------------------------------- #


def page_find() -> None:
    st.header("Find & claim your results")
    st.caption("Search by name, then tick the results that are yours and save.")
    show_flash()

    try:
        filters = cached_filters()
    except ApiError as exc:
        show_api_error(exc)
        return

    providers = {p.name: p.slug for p in filters.providers}
    prev = st.session_state.get("search_params", {})

    with st.form("search"):
        name = st.text_input("Name *", value=prev.get("name", ""), placeholder="e.g. Jane Smith")
        c1, c2, c3, c4 = st.columns(4)
        discipline = c1.selectbox("Discipline", [ANY] + [d.value for d in filters.disciplines])
        provider = c2.selectbox("Provider", [ANY] + list(providers))
        race = c3.selectbox("Race", [ANY] + filters.races)
        age_group = c4.selectbox("Age group", [ANY] + filters.age_groups)
        submitted = st.form_submit_button("Search", type="primary")

    if submitted:
        if not name.strip():
            st.warning("Please enter a name to search for.")
            return
        st.session_state["search_params"] = {
            "name": name.strip(),
            "discipline": None if discipline == ANY else discipline,
            "provider": None if provider == ANY else providers[provider],
            "race": None if race == ANY else race,
            "age_group": None if age_group == ANY else age_group,
        }
        st.session_state["editor_gen"] = st.session_state.get("editor_gen", 0) + 1

    params = st.session_state.get("search_params")
    if not params:
        return

    # Always re-query so claimed state is fresh (never cached).
    try:
        results = api.search(**params)
    except ApiError as exc:
        show_api_error(exc)
        return

    if not results:
        st.info(f"No results found for **{params['name']}**. Try a different spelling or fewer filters.")
        return

    st.write(f"**{len(results)}** candidate result{'s' if len(results) != 1 else ''}, best match first.")
    df = results_frame(results, with_score=True)
    df.insert(0, "Mine", [r.claimed for r in results])

    edited = st.data_editor(
        df,
        key=f"search_editor_{st.session_state.get('editor_gen', 0)}",
        hide_index=True,
        width="stretch",
        disabled=[c for c in df.columns if c != "Mine"],
        column_config={
            **COMMON_COLUMN_CONFIG,
            "Mine": st.column_config.CheckboxColumn("Mine", help="Tick results that are yours"),
        },
    )

    was = dict(zip(df["id"], df["Mine"]))
    now = dict(zip(edited["id"], edited["Mine"]))
    to_claim = [int(i) for i, v in now.items() if v and not was[i]]
    to_unclaim = [int(i) for i, v in now.items() if not v and was[i]]

    label = "Save changes"
    if to_claim or to_unclaim:
        label += f" (+{len(to_claim)} / -{len(to_unclaim)})"
    if st.button(label, type="primary", disabled=not (to_claim or to_unclaim)):
        apply_claim_changes(to_claim, to_unclaim)
        st.rerun()


# --------------------------------------------------------------------------- #
# Page: My Results
# --------------------------------------------------------------------------- #


def page_my_results() -> None:
    st.header("My results")
    show_flash()

    try:
        results = api.my_results()
    except ApiError as exc:
        show_api_error(exc)
        return

    if not results:
        st.info("You haven't claimed any results yet.")
        st.page_link(PAGE_FIND, label="Find your results", icon=":material/search:")
        return

    results = sorted(results, key=lambda r: r.event_date, reverse=True)
    st.write(f"**{len(results)}** claimed result{'s' if len(results) != 1 else ''}.")
    df = results_frame(results)
    df.insert(0, "Unclaim", False)

    edited = st.data_editor(
        df,
        key=f"mine_editor_{st.session_state.get('editor_gen', 0)}",
        hide_index=True,
        width="stretch",
        disabled=[c for c in df.columns if c != "Unclaim"],
        column_config={
            **COMMON_COLUMN_CONFIG,
            "Unclaim": st.column_config.CheckboxColumn("Unclaim", help="Tick to remove from your results"),
        },
    )
    to_unclaim = [int(i) for i in edited.loc[edited["Unclaim"], "id"]]
    if st.button(
        f"Unclaim selected ({len(to_unclaim)})", type="primary", disabled=not to_unclaim
    ):
        apply_claim_changes([], to_unclaim)
        st.rerun()

    with st.expander("Result detail"):
        options = {f"{r.event_name} ({r.event_date}) - {r.chip_time}": r.id for r in results}
        choice = st.selectbox("Result", list(options))
        if choice:
            try:
                detail = api.get_result(options[choice])
            except ApiError as exc:
                show_api_error(exc)
            else:
                st.markdown(f"[View on {detail.provider_name}]({detail.source_url})")
                st.json(detail.model_dump(mode="json"), expanded=False)


# --------------------------------------------------------------------------- #
# Page: Analysis
# --------------------------------------------------------------------------- #


def points_frame(points: list[AnalysisPoint]) -> pd.DataFrame:
    df = pd.DataFrame([p.model_dump() for p in points])
    df["event_date"] = pd.to_datetime(df["event_date"])
    df["PB"] = df["is_pb"].map({True: "PB", False: "Result"})
    df["pace"] = df["pace"].fillna("-")
    return df


def time_chart(df: pd.DataFrame, field: str, title: str, label_expr: str) -> alt.Chart:
    tooltip = [
        alt.Tooltip("event_name:N", title="Event"),
        alt.Tooltip("event_date:T", title="Date", format="%d %b %Y"),
        alt.Tooltip("chip_time:N", title="Chip time"),
        alt.Tooltip("pace:N", title="Pace (/km)"),
    ]
    x = alt.X("event_date:T", title="Event date", scale=alt.Scale(padding=15))
    y = alt.Y(
        f"{field}:Q",
        title=title,
        scale=alt.Scale(zero=False, nice=False, padding=20),
        axis=alt.Axis(labelExpr=label_expr),
    )
    line = alt.Chart(df).mark_line(color="#8aa4c8").encode(x=x, y=y)
    color = alt.Color(
        "PB:N",
        scale=alt.Scale(domain=["Result", "PB"], range=["#1f77b4", "#e4572e"]),
        legend=alt.Legend(title=None, orient="top"),
    )
    points = alt.Chart(df).mark_point(filled=True, size=70).encode(x=x, y=y, color=color, tooltip=tooltip)
    pb = (
        alt.Chart(df[df["is_pb"]])
        .mark_point(filled=True, size=240, shape="diamond")
        .encode(x=x, y=y, color=color, tooltip=tooltip)
    )
    return (line + points + pb).properties(height=360)


TREND_LABELS = {
    "improving": "Improving",
    "declining": "Declining",
    "flat": "Flat",
    "insufficient_data": "Not enough data",
}


def render_metrics(a: AnalysisOut) -> None:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Personal best",
        a.pb.chip_time if a.pb else "-",
        help=f"{a.pb.event_name}, {a.pb.event_date}" if a.pb else None,
    )
    c2.metric(
        "Most recent",
        a.most_recent.chip_time if a.most_recent else "-",
        help=f"{a.most_recent.event_name}, {a.most_recent.event_date}" if a.most_recent else None,
    )
    vs = a.most_recent_vs_pb_seconds
    c3.metric(
        "Most recent vs PB",
        "PB" if vs == 0 else fmt_signed(vs),
        delta="Your latest race is your PB" if vs == 0 else None,
        delta_color="off",
        delta_arrow="off" if vs == 0 else "auto",
        help="Positive = slower than your PB",
    )
    slope = a.trend_seconds_per_year
    delta = None
    if slope is not None and a.trend != "insufficient_data":
        delta = f"{fmt_signed(slope)} per year"
    # Faster (negative seconds) is good, so invert delta colouring.
    c4.metric("Trend", TREND_LABELS.get(a.trend, a.trend), delta=delta, delta_color="inverse")


def page_analysis() -> None:
    st.header("Analysis")
    st.caption("Your chip times over time, comparing like with like (same discipline and distance).")

    try:
        default = api.analysis()
    except ApiError as exc:
        show_api_error(exc)
        return

    if default is None or not default.available_groups:
        st.info("Nothing to analyse yet: claim some of your results first.")
        st.page_link(PAGE_FIND, label="Find your results", icon=":material/search:")
        return

    groups = default.available_groups
    labels = [f"{g.discipline.value.title()} / {g.distance_label} ({g.count})" for g in groups]
    default_idx = next(
        (
            i
            for i, g in enumerate(groups)
            if g.discipline == default.discipline and g.distance_label == default.distance_label
        ),
        0,
    )
    idx = st.selectbox(
        "Comparison group", range(len(groups)), index=default_idx, format_func=lambda i: labels[i]
    )
    g = groups[idx]

    if idx == default_idx:
        a = default
    else:
        try:
            a = api.analysis(g.discipline.value, g.distance_label)
        except ApiError as exc:
            show_api_error(exc)
            return
        if a is None:
            st.warning("No claimed results in this group.")
            return

    if not a.points:
        st.info("No results in this group.")
        return

    render_metrics(a)

    df = points_frame(a.points)
    st.subheader("Finish time")
    st.caption("Chip time per race. Lower on the chart = faster.")
    st.altair_chart(
        time_chart(df, "chip_time_seconds", "Chip time (lower is faster)", TIME_LABEL_EXPR),
        width="stretch",
    )

    has_pace = df["pace_seconds_per_km"].notna().any()
    if has_pace:
        st.subheader("Pace")
        st.caption("Minutes per km. Lower = faster.")
        st.altair_chart(
            time_chart(
                df[df["pace_seconds_per_km"].notna()],
                "pace_seconds_per_km",
                "Pace, min/km (lower is faster)",
                PACE_LABEL_EXPR,
            ),
            width="stretch",
        )

    table = pd.DataFrame(
        {
            "Date": df["event_date"].dt.date,
            "Event": df["event_name"],
            "Chip time": df["chip_time"],
            **({"Pace (/km)": df["pace"]} if has_pace else {}),
            "PB": df["is_pb"].map({True: "PB", False: ""}),
        }
    ).sort_values("Date", ascending=False)
    st.dataframe(table, hide_index=True, width="stretch")


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #

st.set_page_config(page_title="Chipt", page_icon=":material/timer:", layout="wide")

PAGE_FIND = st.Page(page_find, title="Find & Claim", icon=":material/search:", url_path="find", default=True)
PAGE_MINE = st.Page(page_my_results, title="My Results", icon=":material/list:", url_path="my-results")
PAGE_ANALYSIS = st.Page(page_analysis, title="Analysis", icon=":material/show_chart:", url_path="analysis")

with st.sidebar:
    st.title("Chipt")
    st.caption("All your race results in one place.")

nav = st.navigation([PAGE_FIND, PAGE_MINE, PAGE_ANALYSIS])

with st.sidebar:
    if not api.health():
        st.error(f"API unreachable at {api._base_url()}")

nav.run()
