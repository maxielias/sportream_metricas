import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json

from activity_details import fetch_activity_details_df, fetch_activity_details, ActivityDetails
import os


st.set_page_config(page_title="Garmin Activity Metrics", layout="wide")

st.title("Métricas de actividades — Activity Details")


@st.cache_data(ttl=300)
def load_activity_list(limit: int = 200, target_user_id: str = None):
    # Returns DataFrame of available activity-details (optionally filtered by target_user_id)
    return fetch_activity_details_df(limit=limit, target_user_id=target_user_id)


@st.cache_data(ttl=300)
def load_activity_objects(limit: int = 200, target_user_id: str = None):
    return fetch_activity_details(limit=limit, target_user_id=target_user_id)


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

    # Load target_user_id from environment variables (if set)
    target_user_id = os.getenv('TARGET_USER_ID') or os.getenv('target_user_id') or os.getenv('targetUserId')

    df = load_activity_list(limit=limit, target_user_id=target_user_id)
    items = load_activity_objects(limit=limit, target_user_id=target_user_id)

    if df is None or df.empty:
        st.warning("No se encontraron actividades. Revisa tus secrets (Streamlit secrets / variables de entorno) y la tabla `webhooks`.")
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
            columns_to_plot = ['heartRate', 'totalDistanceInMeters', 'speedMetersPerSecond', 'elevationInMeters']

            def _palette():
                # Minimal, athletic-focused palette (calm dark + bright accents)
                return {
                    'heartRate': '#FF6B6B',             # energetic coral (HR)
                    'totalDistanceInMeters': '#A3E635', # vivid lime (distance)
                    'speedMetersPerSecond': '#00C2FF',  # electric cyan (speed)
                    'elevationInMeters': '#94A3B8'      # cool gray-blue (elevation)
                }

            pal = _palette()

            # ensure timerDuration exists and is datetime-like
            xcol = 'timerDuration' if 'timerDuration' in samples.columns else None
            if xcol is None:
                st.info('No hay columna `timerDuration` para graficar series temporales.')
            else:
                samples = samples.sort_values(by=xcol)
                present_cols = [c for c in columns_to_plot if c in samples.columns]
                if not present_cols:
                    st.info('Ninguna de las columnas solicitadas está presente en los samples.')
                else:
                    # build subplot with one row per metric
                    rows = len(present_cols)
                    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.03,
                                        subplot_titles=[f"{c}" for c in present_cols])

                    for i, col in enumerate(present_cols, start=1):
                        y = samples[col]
                        fig.add_trace(
                            go.Scatter(
                                x=samples[xcol],
                                y=y,
                                mode='lines',
                                name=col,
                                line=dict(color=pal.get(col, '#111111'), width=2.5),
                                hovertemplate='%{x}<br>' + col + ': %{y}<extra></extra>'
                            ),
                            row=i, col=1
                        )
                        # minimal axis styling
                        fig.update_yaxes(title_text=col, row=i, col=1, showgrid=False)

                    fig.update_layout(
                        template='simple_white',
                        height=220 * rows,
                        margin=dict(l=40, r=20, t=60, b=40),
                        showlegend=False,
                        plot_bgcolor='white'
                    )

                    # subtle horizontal baseline and thin grid for readability
                    for i in range(1, rows + 1):
                        fig.update_yaxes(row=i, col=1, gridcolor='#f2f4f7', zerolinecolor='#e6eef8')

                    st.plotly_chart(fig, width='stretch')

            # map if coordinates available
            if "latitudeInDegree" in samples.columns and "longitudeInDegree" in samples.columns:
                coords = samples.dropna(subset=["latitudeInDegree", "longitudeInDegree"])
                if not coords.empty:
                    st.map(coords.rename(columns={"latitudeInDegree": "lat", "longitudeInDegree": "lon"})[["lat", "lon"]])


if __name__ == "__main__":
    main()
