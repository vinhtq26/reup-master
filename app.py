import streamlit as st


st.set_page_config(
    page_title="ToolMaster Pro",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def init_state() -> None:
    defaults = {
        "save_dir": "//Users/quangtrinh/Downloads/ToolMaster",
        "enable_edit": True,
        "extract_mp3": True,
        "upload_drive": True,
        "video_speed": 1.0,
        "parallel_downloads": 2,
        "scan_interval": 5,
        "enable_split": True,
        "split_threshold": 120,
        "split_segment": 120,
        "enable_logo": True,
        "logo_path": "//Users/quangtrinh/Downloads/brand/logo-premium.png",
        "logo_position": "Trên phải",
        "logo_scale": 0.15,
        "logo_opacity": 0.85,
        "logo_margin_x": 20,
        "logo_margin_y": 20,
        "enable_subtitle": True,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def inject_css() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');

        :root {
            --bg: #F5F1E9;
            --sidebar: #101828;
            --sidebar-soft: #172233;
            --card: #FFFFFF;
            --line: #E8DED2;
            --text: #1A1D24;
            --muted: #6B7280;
            --accent: #D06A4F;
            --accent-hover: #BC5D43;
            --success: #16A34A;
            --danger: #DC2626;
            --secondary: #EEF0F4;
            --secondary-text: #3C4452;
            --blue-btn: #2C7BE5;
            --blue-btn-hover: #2169C6;
            --radius-xl: 24px;
            --radius-lg: 18px;
            --radius-md: 14px;
            --shadow: 0 18px 50px rgba(16, 24, 40, 0.06);
        }

        html, body, [class*="css"]  {
            font-family: 'Manrope', sans-serif;
        }

        .stApp {
            background: var(--bg);
            color: var(--text);
        }

        [data-testid="stHeader"] {
            display: none;
        }

        [data-testid="stToolbar"] {
            right: 1rem;
        }

        [data-testid="stMainBlockContainer"] {
            max-width: 1540px;
            padding-top: 1.25rem;
            padding-bottom: 2rem;
        }

        .tm-shell {
            padding: 0.25rem 0 0.5rem 0;
        }

        .tm-sidebar {
            background: var(--sidebar);
            color: white;
            border-radius: 28px;
            padding: 26px 22px 22px 22px;
            min-height: 88vh;
            box-shadow: var(--shadow);
        }

        .tm-kicker {
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.12em;
            text-transform: uppercase;
            color: #98A2B3;
            margin-bottom: 8px;
        }

        .tm-brand {
            font-size: 30px;
            line-height: 1.05;
            font-weight: 800;
            color: white;
            margin-bottom: 18px;
        }

        .tm-pill {
            display: inline-block;
            background: var(--accent);
            color: #FFF7F2;
            font-size: 13px;
            font-weight: 700;
            padding: 12px 16px;
            border-radius: 999px;
            margin-bottom: 24px;
        }

        .tm-nav-title {
            color: #98A2B3;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 10px;
        }

        .tm-nav-item {
            display: block;
            width: 100%;
            padding: 14px 16px;
            border-radius: 16px;
            color: #E5E7EB;
            font-size: 15px;
            font-weight: 700;
            margin-bottom: 8px;
            background: transparent;
            border: 1px solid transparent;
        }

        .tm-nav-item.active {
            background: var(--accent);
            color: white;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
        }

        .tm-snapshot {
            background: var(--sidebar-soft);
            border-radius: 22px;
            padding: 18px 16px 16px 16px;
            margin-top: 16px;
            border: 1px solid rgba(255,255,255,0.06);
        }

        .tm-snapshot-title {
            color: white;
            font-size: 16px;
            font-weight: 800;
            margin-bottom: 14px;
        }

        .tm-metrics {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 14px;
        }

        .tm-metric {
            background: rgba(255,255,255,0.04);
            border-radius: 16px;
            padding: 14px 12px;
        }

        .tm-metric-value {
            font-size: 30px;
            line-height: 1;
            font-weight: 800;
            margin-bottom: 6px;
        }

        .tm-metric-label {
            color: #98A2B3;
            font-size: 12px;
            font-weight: 600;
        }

        .tm-success {
            color: #4ADE80;
        }

        .tm-danger {
            color: #F87171;
        }

        .tm-plan {
            color: #D0D5DD;
            font-size: 13px;
            line-height: 1.6;
            margin-bottom: 14px;
        }

        .tm-header-card,
        .tm-main-card {
            background: var(--card);
            border-radius: 26px;
            border: 1px solid var(--line);
            box-shadow: var(--shadow);
        }

        .tm-header-card {
            padding: 26px 28px;
            margin-bottom: 18px;
        }

        .tm-header-title {
            font-size: 36px;
            line-height: 1.08;
            font-weight: 800;
            color: var(--text);
            margin-bottom: 8px;
        }

        .tm-header-subtitle {
            color: var(--muted);
            font-size: 15px;
            line-height: 1.6;
            margin-bottom: 0;
        }

        .tm-section-title {
            font-size: 24px;
            line-height: 1.2;
            font-weight: 800;
            color: var(--text);
            margin-bottom: 6px;
        }

        .tm-section-subtitle {
            color: var(--muted);
            font-size: 14px;
            line-height: 1.6;
            margin-bottom: 2px;
        }

        .tm-main-card {
            padding: 24px 24px 10px 24px;
        }

        .tm-card-caption {
            color: var(--muted);
            font-size: 13px;
            line-height: 1.6;
            margin-bottom: 14px;
        }

        .tm-preview {
            height: 220px;
            border-radius: 18px;
            background:
                linear-gradient(145deg, rgba(208,106,79,0.18), rgba(16,24,40,0.14)),
                linear-gradient(180deg, #F8F4EE, #EAE2D6);
            border: 1px dashed #D2B6A9;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 18px;
            color: #5C6470;
            font-size: 14px;
            font-weight: 700;
        }

        .tm-expander-label {
            font-size: 17px;
            font-weight: 800;
            color: var(--text);
        }

        .stButton > button {
            border-radius: 14px;
            font-weight: 700;
            border: 1px solid transparent;
            min-height: 2.9rem;
        }

        .stButton > button[kind="primary"] {
            background: var(--accent);
            color: white;
        }

        .stButton > button[kind="primary"]:hover {
            background: var(--accent-hover);
            color: white;
        }

        .stButton > button:not([kind="primary"]) {
            background: var(--secondary);
            color: var(--secondary-text);
            border-color: #E4E7EC;
        }

        .tm-blue-button button {
            background: var(--blue-btn) !important;
            color: white !important;
            border-color: var(--blue-btn) !important;
        }

        .tm-blue-button button:hover {
            background: var(--blue-btn-hover) !important;
            border-color: var(--blue-btn-hover) !important;
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        .stNumberInput div[data-baseweb="input"] > div {
            border-radius: 14px !important;
            border-color: #D7DBE2 !important;
            background: #FBFCFE !important;
        }

        .stCheckbox {
            padding-top: 0.35rem;
            padding-bottom: 0.35rem;
        }

        .stExpander {
            border: 1px solid var(--line) !important;
            background: #FCFAF7 !important;
            border-radius: 18px !important;
            margin-bottom: 14px !important;
        }

        .stExpander details summary {
            padding-top: 0.4rem;
            padding-bottom: 0.4rem;
        }

        .tm-tight-bottom {
            margin-bottom: 0.35rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def card_start(extra_class: str = "") -> None:
    st.markdown(f'<div class="tm-main-card {extra_class}">', unsafe_allow_html=True)


def card_end() -> None:
    st.markdown("</div>", unsafe_allow_html=True)


def render_sidebar() -> None:
    st.markdown(
        """
        <div class="tm-sidebar">
            <div class="tm-kicker">COMMERCIAL UI</div>
            <div class="tm-brand">ToolMaster Pro</div>
            <div class="tm-pill">Premier desktop workflow</div>
            <div class="tm-nav-title">Navigation</div>
            <div class="tm-nav-item">Download Studio</div>
            <div class="tm-nav-item">Channel Raider</div>
            <div class="tm-nav-item active">Production Settings</div>
            <div class="tm-nav-item">Business Insights</div>
            <div class="tm-nav-item">Data Vault</div>
            <div class="tm-snapshot">
                <div class="tm-snapshot-title">Live snapshot</div>
                <div class="tm-metrics">
                    <div class="tm-metric">
                        <div class="tm-metric-value tm-success">48</div>
                        <div class="tm-metric-label">Video đang xử lý</div>
                    </div>
                    <div class="tm-metric">
                        <div class="tm-metric-value tm-danger">1</div>
                        <div class="tm-metric-label">Video lỗi</div>
                    </div>
                </div>
                <div class="tm-plan">Gói cước của bạn đang bật chế độ premium workflow cho toàn bộ pipeline.</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.button("Mở thư mục lưu", type="primary", use_container_width=True)
    st.button("Mở cài đặt vận hành", use_container_width=True)


def render_page_header() -> None:
    st.markdown(
        """
        <div class="tm-header-card">
            <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:18px; flex-wrap:wrap;">
                <div>
                    <div class="tm-header-title">Production Settings</div>
                    <p class="tm-header-subtitle">
                        Điều chỉnh toàn bộ pipeline để khớp đúng gói sản phẩm, quy trình xử lý
                        và trải nghiệm vận hành bạn muốn bán ra cho khách hàng.
                    </p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3, c4 = st.columns([3.6, 1.2, 1.2, 1.25], gap="small")
    with c1:
        st.empty()
    with c2:
        st.button("Ready for delivery", use_container_width=True)
    with c3:
        st.button("6 tháng = 1 phút", use_container_width=True)
    with c4:
        st.button("Về thư mục lưu", type="primary", use_container_width=True)


def render_basic_section() -> None:
    with st.expander("1) Cơ bản", expanded=True):
        path_col, button_col = st.columns([5.0, 1.0], gap="small")
        with path_col:
            st.text_input("Thư mục lưu", key="save_dir")
        with button_col:
            st.markdown('<div class="tm-blue-button">', unsafe_allow_html=True)
            st.button("Chọn", key="pick_save_dir", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.checkbox(
            "Edit video sau khi tải để chuẩn hoá file đầu ra",
            key="enable_edit",
        )
        st.checkbox(
            "Tách MP3 từ file processed hoặc từng part sau khi cắt",
            key="extract_mp3",
        )
        st.checkbox(
            "Upload Google Drive theo đúng đầu ra local",
            key="upload_drive",
        )

        a, b, c = st.columns(3, gap="medium")
        with a:
            st.number_input(
                "Tốc độ video",
                key="video_speed",
                min_value=0.5,
                max_value=3.0,
                step=0.05,
                format="%.2f",
            )
        with b:
            st.selectbox(
                "Parallel downloads",
                options=[1, 2, 3, 4, 5],
                key="parallel_downloads",
            )
        with c:
            st.number_input(
                "Quét kênh mỗi (phút)",
                key="scan_interval",
                min_value=1,
                max_value=120,
                step=1,
            )


def render_split_section() -> None:
    with st.expander("2) Video Split", expanded=True):
        st.checkbox("Bật cắt video dài", key="enable_split")
        a, b = st.columns(2, gap="medium")
        with a:
            st.number_input(
                "Ngưỡng cắt (giây)",
                key="split_threshold",
                min_value=10,
                max_value=3600,
                step=10,
            )
        with b:
            st.number_input(
                "Độ dài mỗi đoạn (giây)",
                key="split_segment",
                min_value=10,
                max_value=3600,
                step=10,
            )


def render_logo_section() -> None:
    with st.expander("3) Logo / Watermark", expanded=True):
        st.checkbox("Bật logo / watermark", key="enable_logo")

        left, right = st.columns([1.8, 1.0], gap="large")
        with left:
            path_col, button_col = st.columns([5.0, 1.0], gap="small")
            with path_col:
                st.text_input("Đường dẫn logo", key="logo_path")
            with button_col:
                st.markdown('<div class="tm-blue-button">', unsafe_allow_html=True)
                st.button("Chọn", key="pick_logo_path", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            a, b = st.columns(2, gap="medium")
            with a:
                st.selectbox(
                    "Vị trí logo",
                    options=["Trên phải", "Trên trái", "Dưới phải", "Dưới trái", "Chính giữa"],
                    key="logo_position",
                )
            with b:
                st.number_input(
                    "Scale",
                    key="logo_scale",
                    min_value=0.01,
                    max_value=1.0,
                    step=0.01,
                    format="%.2f",
                )

            c, d = st.columns(2, gap="medium")
            with c:
                st.number_input(
                    "Opacity",
                    key="logo_opacity",
                    min_value=0.05,
                    max_value=1.0,
                    step=0.01,
                    format="%.2f",
                )
            with d:
                st.number_input(
                    "Margin X",
                    key="logo_margin_x",
                    min_value=0,
                    max_value=500,
                    step=1,
                )

            st.number_input(
                "Margin Y",
                key="logo_margin_y",
                min_value=0,
                max_value=500,
                step=1,
            )

        with right:
            st.markdown(
                """
                <div class="tm-preview">
                    Preview watermark<br/>
                    Video mock frame + logo placement preview
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_subtitle_section() -> None:
    with st.expander("4) Subtitle", expanded=False):
        st.checkbox("Bật subtitle tự động", key="enable_subtitle")


def render_content() -> None:
    render_page_header()
    card_start()
    st.markdown(
        """
        <div class="tm-section-title">Tinh chỉnh pipeline theo đúng gói sản phẩm bạn định bán</div>
        <div class="tm-section-subtitle">
            Toàn bộ cấu hình được giữ trong session state để bạn có thể đổi thông số,
            mô phỏng lại workflow và trình bày với khách hàng theo đúng spec sản phẩm.
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_basic_section()
    render_split_section()
    render_logo_section()
    render_subtitle_section()
    card_end()


def main() -> None:
    init_state()
    inject_css()
    st.markdown('<div class="tm-shell">', unsafe_allow_html=True)
    left, right = st.columns([1.15, 4.35], gap="large")
    with left:
        render_sidebar()
    with right:
        render_content()
    st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
