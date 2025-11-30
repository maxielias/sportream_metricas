import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import pydeck as pdk

from activity_details import fetch_activity_details_df, fetch_activity_details, ActivityDetails
from db_connection import get_postgresdb_from_neon_keys
import os
from pathlib import Path
try:
    # load .env in development if present (does nothing if python-dotenv is not installed)
    from dotenv import load_dotenv
    load_dotenv(Path('.') / '.env')
except Exception:
    pass


st.set_page_config(page_title="Garmin Activity Metrics", layout="wide")

st.title("Métricas de actividades — Activity Details")


@st.cache_data(ttl=300)
def load_activity_list(limit: int = 200, target_user_id: str = None):
    # Returns DataFrame of available activity-details (optionally filtered by target_user_id)
    return fetch_activity_details_df(limit=limit, target_user_id=target_user_id)


@st.cache_data(ttl=300)
def load_activity_objects(limit: int = 200, target_user_id: str = None):
    # Build ActivityDetails objects from the DataFrame loader so both
    # representations stay consistent (and so we can detect fallback state).
    df = load_activity_list(limit=limit, target_user_id=target_user_id)
    results = []
    if df is None or df.empty:
        return results
    for _, row in df.iterrows():
        record = {col: row[col] for col in df.columns}
        results.append(ActivityDetails.from_record(record))
    return results


def activity_to_label(rec: pd.Series) -> str:
    cid = rec.get("id")
    created = rec.get("created_at")
    # Try to extract a human-friendly activity name from the payload
    data_val = rec.get("data")
    activity_name = None
    if isinstance(data_val, str):
        try:
            data_val = json.loads(data_val)
        except Exception:
            pass

    if isinstance(data_val, dict):
        # common patterns: activityDetails -> [ { activityName: ... } ]
        try:
            if 'activityDetails' in data_val and isinstance(data_val['activityDetails'], list) and data_val['activityDetails']:
                first = data_val['activityDetails'][0]
                if isinstance(first, dict):
                    activity_name = first.get('activityName') or first.get('activity_name') or first.get('name')
        except Exception:
            activity_name = None

        if not activity_name:
            activity_name = data_val.get('activityName') or data_val.get('activity_name') or data_val.get('name')

    # Build label: prefer "created_at — activityName"; fallback to id if name missing
    created_str = created if created is not None else ''
    if activity_name:
        return f"{created_str} — {activity_name}"
    # fallback: show id and created
    return f"{cid} — {created_str}"


def main():
    st.sidebar.header("Opciones")
    limit = st.sidebar.number_input("Límite de actividades a cargar", min_value=10, max_value=5000, value=200, step=10)
    refresh = st.sidebar.button("Recargar")

    if refresh:
        load_activity_list.clear()
        load_activity_objects.clear()

    # Load target_user_id from environment variables (if set). The app will
    # use it silently; no sidebar controls are shown to alter filtering.
    target_user_id = os.getenv('TARGET_USER_ID') or os.getenv('target_user_id') or os.getenv('targetUserId')
    effective_target = target_user_id or ""

    # Auto-clear cached results if the effective target changed since last run
    prev_target = st.session_state.get("last_effective_target", None)
    if prev_target != effective_target:
        load_activity_list.clear()
        load_activity_objects.clear()
        st.session_state["last_effective_target"] = effective_target

    df = load_activity_list(limit=limit, target_user_id=effective_target)
    items = load_activity_objects(limit=limit, target_user_id=effective_target)

    # No manual DB diagnostics in the sidebar per user request.

    # If the loader performed a fallback (filtered -> unfiltered), show a
    # generic warning but do NOT display the target id in the UI.
    fallback_used = False
    try:
        fallback_used = bool(df.attrs.get('fallback_to_unfiltered', False))
    except Exception:
        fallback_used = False

    if fallback_used:
        st.warning("No se encontró el usuario indicado; se muestran todas las actividades.")

    if df is None or df.empty:
        # If DB has data but the filtered df is empty, show a clearer message
        if effective_target:
            st.warning("No se encontraron actividades para el usuario indicado. Revisa tus secrets y la tabla `webhooks`.")
        else:
            st.warning("No se encontraron actividades. Revisa tus secrets (Streamlit secrets / variables de entorno) y la tabla `webhooks`.")

        # Offer quick raw DB check in-page
        if st.button("Ver conteo crudo (sin filtro)"):
            try:
                db = get_postgresdb_from_neon_keys()
                with db:
                    cnt = db.execute("SELECT count(*) FROM webhooks WHERE type = 'activity-details'", fetchone=True)
                    st.info(f"Filas activity-details (sin filtrar): {cnt[0] if cnt else 0}")
                    rows = db.execute("SELECT id, created_at, (data->>'userId') as userId FROM webhooks WHERE type = 'activity-details' ORDER BY created_at DESC LIMIT 5", fetchall=True)
                    if rows:
                        st.write("Últimas ids (sin filtro):")
                        for r in rows:
                            st.write(f" - {r[0]} @ {r[1]} (userId: {r[2]})")
            except Exception as e:
                st.error(f"No se pudo ejecutar conteo crudo: {e}")
        return

    # Selection
    st.sidebar.markdown(f"**Actividades cargadas:** {len(df)}")
    # Inject small CSS to make the sidebar selectbox font smaller and allow wrapping
    st.sidebar.markdown(
        """
        <style>
        /* Reduce font size for sidebar selectbox options and labels */
        section [data-testid="stSidebar"] .stSelectbox, section [data-testid="stSidebar"] select, section [data-testid="stSidebar"] div[role="listbox"] {
            font-size: 12px !important;
            line-height: 1.15 !important;
        }
        /* Try to allow options to wrap when long */
        div[role="option"] { white-space: normal !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    labels = [activity_to_label(df.iloc[i]) for i in range(len(df))]
    # Use selectbox showing "fecha — activityName" (or fallback). We keep the labels list and
    # map selection back to index so underlying logic is unchanged.
    sel = st.sidebar.selectbox("Seleccionar actividad", options=labels)
    sel_idx = labels.index(sel)

    # show selected summary
    rec = df.iloc[sel_idx]
    st.subheader("Actividad seleccionada")
    col1, col2 = st.columns([2, 3])
    with col1:
        st.write("**ID**:", rec.get("id"))
        st.write("**Created at**:", rec.get("created_at"))
        st.write("**Type**:", rec.get("type"))
    with col2:
        # show a compact summary of the data payload (do not render full JSON)
        data_val = rec.get("data")
        if isinstance(data_val, str):
            try:
                data_val = json.loads(data_val)
            except Exception:
                pass

        st.write("**Data — Resumen (no muestra JSON completo)**")

        def _summarize_payload(obj):
            # Returns a small DataFrame with top-level key, type and length (if applicable)
            if isinstance(obj, dict):
                rows = []
                for k, v in obj.items():
                    t = type(v).__name__
                    try:
                        l = len(v) if (hasattr(v, '__len__') and not isinstance(v, (str, bytes))) else ''
                    except Exception:
                        l = ''
                    rows.append({'key': k, 'type': t, 'len': l})
                if rows:
                    return pd.DataFrame(rows)
                return None
            return None

        summary_df = _summarize_payload(data_val)
        if summary_df is not None and not summary_df.empty:
            st.table(summary_df)
        else:
            # If payload isn't a dict or empty, show a brief scalar preview
            if data_val is None:
                st.write("(vacío)")
            else:
                st.write(f"Tipo: {type(data_val).__name__} — vista previa corta:")
                # show the first ~300 chars for strings or repr for other scalars
                s = data_val
                if isinstance(s, (dict, list)):
                    txt = str(s)[:300]
                else:
                    txt = repr(s)[:300]
                st.text(txt)

    # build ActivityDetails object for selected
    activity_obj = items[sel_idx] if len(items) > sel_idx else None

    st.markdown("---")
    st.subheader("Muestras (samples)")
    if activity_obj is None:
        st.info("No hay objeto `ActivityDetails` disponible para esta fila.")
    else:
        samples = activity_obj.samples_df()
        if samples.empty:
            st.info("No se encontraron samples para esta actividad.")
        else:
            st.dataframe(samples.head(200))

            # Basic quality checks and warnings for potentially incomplete / inconsistent samples
            n_samples = len(samples)
            if n_samples < 20:
                st.warning(f"Actividad con pocos samples ({n_samples}). Es posible que los datos estén incompletos.")

            # Check monotonicity of timerDuration (if present)
            if 'timerDuration' in samples.columns:
                try:
                    td = samples['timerDuration']
                    # if not monotonic increasing, warn (could indicate duplicates or bad ordering)
                    if not td.is_monotonic_increasing:
                        st.warning('La columna `timerDuration` no es monótona creciente — los samples pueden estar desordenados o duplicados.')
                except Exception:
                    pass

            # Check for coordinate completeness
            if "latitudeInDegree" in samples.columns and "longitudeInDegree" in samples.columns:
                coord_count = samples.dropna(subset=["latitudeInDegree", "longitudeInDegree"]).shape[0]
                if coord_count == 0:
                    st.warning('No hay coordenadas en los samples de esta actividad.')
                elif coord_count < max(5, int(0.2 * n_samples)):
                    st.warning(f'Muy pocas coordenadas válidas ({coord_count}/{n_samples}) — el trazado puede ser incompleto.')

            # Modern minimal athletic plots for selected metric columns
            # Define display titles for known metrics
            title_map = {
                'heartRate': 'Heart Rate',
                'totalDistanceInMeters': 'Total Distance In Meters',
                'speedMetersPerSecond': 'Speed Meters Per Second',
                'elevationInMeters': 'Elevation In Meters',
                'airTemperatureCelcius': 'Air Temperature Celcius',
                'powerInWatts': 'Power In Watts'
            }

            def _palette():
                # Minimal, athletic-focused palette (calm dark + bright accents)
                return {
                    'heartRate': '#FF6B6B',             # energetic coral (HR)
                    'totalDistanceInMeters': '#A3E635', # vivid lime (distance)
                    'speedMetersPerSecond': '#00C2FF',  # electric cyan (speed)
                    'elevationInMeters': '#94A3B8',     # cool gray-blue (elevation)
                    'airTemperatureCelcius': '#FFB86B', # warm amber (air temp)
                    'powerInWatts': '#8B5CF6'           # violet for power
                }

            pal = _palette()

            # ensure timerDuration exists and is datetime-like
            xcol = 'timerDuration' if 'timerDuration' in samples.columns else None
            if xcol is None:
                st.info('No hay columna `timerDuration` para graficar series temporales.')
            else:
                samples = samples.sort_values(by=xcol)
                # order: baseline metrics, then air temp, then power (if present)
                base_order = ['heartRate', 'totalDistanceInMeters', 'speedMetersPerSecond', 'elevationInMeters', 'airTemperatureCelcius']
                present_cols = [c for c in base_order if c in samples.columns]
                if 'powerInWatts' in samples.columns:
                    present_cols.append('powerInWatts')

                if not present_cols:
                    st.info('Ninguna de las columnas solicitadas está presente en los samples.')
                else:
                    # build subplot with one row per metric and increased spacing
                    rows = len(present_cols)
                    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                                        subplot_titles=[title_map.get(c, c) for c in present_cols])

                    for i, col in enumerate(present_cols, start=1):
                        y = samples[col]
                        fig.add_trace(
                            go.Scatter(
                                x=samples[xcol],
                                y=y,
                                mode='lines',
                                name=col,
                                line=dict(color=pal.get(col, '#111111'), width=2.5),
                                hovertemplate='%{x}<br>' + title_map.get(col, col) + ': %{y}<extra></extra>'
                            ),
                            row=i, col=1
                        )
                        # axis title uses friendly name
                        fig.update_yaxes(title_text=title_map.get(col, col), row=i, col=1, showgrid=False)

                    # increase total height so subplots do not overlap
                    total_height = max(300, 240 * rows)
                    fig.update_layout(
                        template='simple_white',
                        height=total_height,
                        margin=dict(l=40, r=20, t=80, b=40),
                        showlegend=False,
                        plot_bgcolor='white'
                    )

                    # subtle horizontal baseline and thin grid for readability
                    for i in range(1, rows + 1):
                        fig.update_yaxes(row=i, col=1, gridcolor='#f2f4f7', zerolinecolor='#e6eef8')

                    st.plotly_chart(fig, use_container_width=True)

            # map if coordinates available
            if "latitudeInDegree" in samples.columns and "longitudeInDegree" in samples.columns:
                coords = samples.dropna(subset=["latitudeInDegree", "longitudeInDegree"]).copy()
                if not coords.empty:
                    coords = coords.rename(columns={"latitudeInDegree": "lat", "longitudeInDegree": "lon"})
                    # use pydeck ScatterplotLayer to control point size (smaller points)
                    try:
                        mid_lat = float(coords['lat'].mean())
                        mid_lon = float(coords['lon'].mean())
                    except Exception:
                        mid_lat = coords['lat'].iloc[0]
                        mid_lon = coords['lon'].iloc[0]

                    # compute bounds and choose a zoom that fits all points but stays closer
                    lat_min = float(coords['lat'].min())
                    lat_max = float(coords['lat'].max())
                    lon_min = float(coords['lon'].min())
                    lon_max = float(coords['lon'].max())
                    lat_span = lat_max - lat_min
                    lon_span = lon_max - lon_min
                    max_span = max(lat_span, lon_span)

                    # heuristic zoom mapping: smaller span -> higher zoom
                    if max_span <= 0.005:
                        zoom = 16
                    elif max_span <= 0.02:
                        zoom = 15
                    elif max_span <= 0.05:
                        zoom = 14
                    elif max_span <= 0.15:
                        zoom = 13
                    elif max_span <= 0.5:
                        zoom = 12
                    elif max_span <= 1.5:
                        zoom = 11
                    else:
                        zoom = 9

                    center_lat = (lat_min + lat_max) / 2.0
                    center_lon = (lon_min + lon_max) / 2.0

                    # smaller point radius so markers don't cover the map
                    layer = pdk.Layer(
                        "ScatterplotLayer",
                        data=coords,
                        get_position='[lon, lat]',
                        get_radius=6,
                        radius_scale=1,
                        get_fill_color=[2, 119, 189, 200],
                        pickable=True
                    )

                    view_state = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=zoom, pitch=0)
                    deck = pdk.Deck(layers=[layer], initial_view_state=view_state, height=420)
                    st.pydeck_chart(deck)

                    # simple legend below the map (color swatch + label)
                    try:
                        swatch = "<span style='display:inline-block;width:14px;height:14px;background:rgb(2,119,189);margin-right:8px;border-radius:3px;'></span>"
                        st.markdown(f"<div style='display:flex;align-items:center'>{swatch}<span>Samples</span></div>", unsafe_allow_html=True)
                    except Exception:
                        pass


if __name__ == "__main__":
    main()
