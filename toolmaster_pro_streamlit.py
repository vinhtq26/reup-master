import streamlit as st


st.set_page_config(
    page_title="ToolMaster Pro - Production Settings",
    page_icon="🛠️",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def init_state() -> None:
    defaults = {
        "save_dir": "/Users/quangtrinh/Downloads/ToolMaster",
        "edit_after_download": True,
        "extract_mp3": False,
        "upload_drive": False,
        "video_speed": 1.0,
        "parallel_downloads": 2,
        "scan_interval": 5,
        "enable_split": False,
        "split_threshold": 120,
        "segment_length": 120,
        "enable_logo": False,
        "logo_path": "/Users/quangtrinh/Downloads/assets/logo.png",
        "logo_position": "Trên phải",
        "logo_scale": 0.15,
        "logo_opacity": 0.85,
        "margin_x": 20,
        "margin_y": 20,
        "auto_subtitle": False,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


init_state()

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] {
        font-family: 'Manrope', sans-serif;
    }
    .stApp {
        background: #F5F1E9;
    }
    .block-container {
        padding-top: 1.2rem;
        padding-bottom: 1.2rem;
        max-width: 1600px;
    }
    div[data-testid="stSidebar"] {
        display: none !important;
    }
    .tm-sidebar {
        background: #101828;
        border-radius: 14px;
        padding: 18px;
        min-height: 86vh;
    }
    .tm-small {
        color: #98A2B3;
        font-size: 11px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        font-weight: 600;
    }
    .tm-brand {
        color: #FFFFFF;
        font-size: 28px;
        font-weight: 800;
        margin: 6px 0 18px;
    }
    .tm-live {
        margin-top: 14px;
        background: #0B1424;
        border: 1px solid #243247;
        border-radius: 12px;
        padding: 14px;
    }
    .tm-live-title {
        color: #FFFFFF;
        font-size: 15px;
        font-weight: 700;
        margin-bottom: 12px;
    }
    .tm-num-green {
        color: #32D583;
        font-size: 24px;
        font-weight: 800;
        line-height: 1;
    }
    .tm-num-red {
        color: #F97066;
        font-size: 24px;
        font-weight: 800;
        line-height: 1;
    }
    .tm-caption {
        color: #98A2B3;
        font-size: 12px;
        margin-top: 4px;
    }
    .tm-note {
        margin-top: 14px;
        color: #CBD5E1;
        font-size: 13px;
        line-height: 1.35;
    }
    .tm-content-title {
        color: #1D2939;
        font-size: 35px;
        font-weight: 800;
        margin: 0;
    }
    .tm-content-subtitle {
        color: #667085;
        font-size: 14px;
        margin: 4px 0 0;
    }
    .tm-card {
        margin-top: 12px;
        background: #FFFFFF;
        border: 1px solid #EAECF0;
        border-radius: 14px;
        padding: 18px 18px 8px;
        box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
    }
    .tm-card-title {
        color: #101828;
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .tm-preview {
        border-radius: 10px;
        border: 1px dashed #D0D5DD;
        background: linear-gradient(160deg, #0F172A, #1E293B);
        height: 170px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #E2E8F0;
        font-weight: 600;
        font-size: 13px;
    }
    div[data-testid="stButton"] > button {
        border-radius: 10px;
        height: 2.6rem;
        border: 1px solid #D0D5DD;
        background: #FFFFFF;
        color: #344054;
        font-weight: 600;
    }
    div[data-testid="stButton"] > button[kind="primary"] {
        background: #D06A4F;
        border: 1px solid #D06A4F;
        color: #FFFFFF;
    }
    .tm-blue-btn div[data-testid="stButton"] > button {
        background: #2E90FA;
        border: 1px solid #2E90FA;
        color: #FFFFFF;
    }
    .tm-gray-btn div[data-testid="stButton"] > button {
        background: #344054;
        border: 1px solid #475467;
        color: #FFFFFF;
    }
    .tm-nav .stButton {
        margin-bottom: 8px;
    }
    .stExpander {
        border: 1px solid #EAECF0 !important;
        border-radius: 10px !important;
        background: #FFFFFF;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


sidebar_col, content_col = st.columns([1, 4], gap="medium")

with sidebar_col:
    st.markdown('<div class="tm-sidebar">', unsafe_allow_html=True)
    st.markdown('<div class="tm-small">COMMERCIAL UI</div>', unsafe_allow_html=True)
    st.markdown('<div class="tm-brand">ToolMaster Pro</div>', unsafe_allow_html=True)
    st.button("Premier desktop workflow", key="btn_premier", use_container_width=True, type="primary")

    st.markdown('<div class="tm-nav">', unsafe_allow_html=True)
    st.button("Download Studio", use_container_width=True, key="menu_download")
    st.button("Channel Raider", use_container_width=True, key="menu_channel")
    st.button(
        "Production Settings",
        use_container_width=True,
        key="menu_production",
        type="primary",
    )
    st.button("Business Insights", use_container_width=True, key="menu_business")
    st.button("Data Vault", use_container_width=True, key="menu_vault")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="tm-live">', unsafe_allow_html=True)
    st.markdown('<div class="tm-live-title">Live snapshot</div>', unsafe_allow_html=True)
    live_col_1, live_col_2 = st.columns(2)
    with live_col_1:
        st.markdown('<div class="tm-num-green">48</div>', unsafe_allow_html=True)
        st.markdown('<div class="tm-caption">Video đang xử lý</div>', unsafe_allow_html=True)
    with live_col_2:
        st.markdown('<div class="tm-num-red">1</div>', unsafe_allow_html=True)
        st.markdown('<div class="tm-caption">Video lỗi</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="tm-note">Gói cước của bạn đang hoạt động ổn định. Có thể mở nhanh thư mục hoặc cài đặt vận hành bên dưới.</div>',
        unsafe_allow_html=True,
    )
    st.button("Mở thư mục lưu", key="live_open_folder", use_container_width=True, type="primary")
    st.markdown('<div class="tm-gray-btn">', unsafe_allow_html=True)
    st.button("Mở cài đặt vận hành", key="live_open_settings", use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with content_col:
    top_left, top_right = st.columns([3, 2], gap="small")
    with top_left:
        st.markdown('<h1 class="tm-content-title">Production Settings</h1>', unsafe_allow_html=True)
        st.markdown(
            '<p class="tm-content-subtitle">Điều chỉnh toàn bộ pipeline để đồng bộ với sản phẩm bạn đang triển khai.</p>',
            unsafe_allow_html=True,
        )
    with top_right:
        btn_col_1, btn_col_2, btn_col_3 = st.columns(3, gap="small")
        with btn_col_1:
            st.button("Ready for delivery", key="btn_ready", use_container_width=True)
        with btn_col_2:
            st.button("6 tháng = 1 phút", key="btn_ratio", use_container_width=True)
        with btn_col_3:
            st.button("Về thư mục lưu", key="btn_to_folder", type="primary", use_container_width=True)

    st.markdown('<div class="tm-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="tm-card-title">Tinh chỉnh pipeline theo đúng gói sản phẩm bạn định bán</div>',
        unsafe_allow_html=True,
    )

    with st.expander("1) Cơ bản", expanded=True):
        dir_col_1, dir_col_2 = st.columns([6, 1], gap="small")
        with dir_col_1:
            st.text_input("Thư mục lưu", key="save_dir")
        with dir_col_2:
            st.markdown('<div class="tm-blue-btn">', unsafe_allow_html=True)
            st.button("Chọn", key="pick_save_dir", use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)

        st.checkbox("Edit video sau khi tải...", key="edit_after_download")
        st.checkbox("Tách MP3 từ video sau khi tải...", key="extract_mp3")
        st.checkbox("Upload Google Drive tự động...", key="upload_drive")

        base_col_1, base_col_2, base_col_3 = st.columns(3)
        with base_col_1:
            st.number_input("Tốc độ video", min_value=0.1, step=0.1, key="video_speed")
        with base_col_2:
            st.selectbox("Parallel downloads", options=[1, 2, 3, 4, 5, 6], key="parallel_downloads")
        with base_col_3:
            st.number_input("Quét kênh mỗi (phút)", min_value=1, step=1, key="scan_interval")

    with st.expander("2) Video Split", expanded=True):
        st.checkbox("Bật cắt video dài", key="enable_split")
        split_col_1, split_col_2 = st.columns(2)
        with split_col_1:
            st.number_input("Ngưỡng cắt (giây)", min_value=10, step=10, key="split_threshold")
        with split_col_2:
            st.number_input("Độ dài mỗi đoạn (giây)", min_value=10, step=10, key="segment_length")

    with st.expander("3) Logo / Watermark", expanded=True):
        st.checkbox("Bật logo/watermark", key="enable_logo")
        wm_left, wm_right = st.columns([3, 2], gap="medium")
        with wm_left:
            logo_col_1, logo_col_2 = st.columns([6, 1], gap="small")
            with logo_col_1:
                st.text_input("Đường dẫn logo", key="logo_path")
            with logo_col_2:
                st.markdown('<div class="tm-blue-btn">', unsafe_allow_html=True)
                st.button("Chọn", key="pick_logo", use_container_width=True)
                st.markdown("</div>", unsafe_allow_html=True)

            st.selectbox("Vị trí", options=["Trên phải", "Trên trái", "Dưới phải", "Dưới trái"], key="logo_position")
            logo_num_1, logo_num_2 = st.columns(2)
            with logo_num_1:
                st.number_input("Scale", min_value=0.01, max_value=1.0, step=0.01, key="logo_scale")
            with logo_num_2:
                st.number_input("Opacity", min_value=0.0, max_value=1.0, step=0.01, key="logo_opacity")

            margin_col_1, margin_col_2 = st.columns(2)
            with margin_col_1:
                st.number_input("Margin X", min_value=0, step=1, key="margin_x")
            with margin_col_2:
                st.number_input("Margin Y", min_value=0, step=1, key="margin_y")
        with wm_right:
            st.markdown('<div class="tm-preview">Preview video</div>', unsafe_allow_html=True)

    with st.expander("4) Subtitle", expanded=False):
        st.checkbox("Bật subtitle tự động", key="auto_subtitle")

    st.markdown("</div>", unsafe_allow_html=True)

