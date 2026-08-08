import streamlit as st

# Task HD-5.3: Mobile viewport polish. All rules are scoped to a mobile
# viewport via a media query so the desktop Dispatch portal is untouched.
MOBILE_CSS = """
<style>
@media (max-width: 768px) {
  /* Slim down the app header chrome on phones */
  .stApp header[data-testid="stHeader"] {
    min-height: 3rem;
  }

  /* Touch-friendly tap targets (>=44px) for every button */
  .stButton > button,
  .stFormSubmitButton > button,
  button[data-testid="stBaseButton-secondary"],
  button[data-testid="stBaseButton-primary"] {
    min-height: 3rem;
    border-radius: 0.75rem;
    font-size: 1.05rem;
    font-weight: 600;
  }

  /* Primary actions get a slightly larger hit area */
  button[data-testid="stBaseButton-primary"] {
    min-height: 3.25rem;
  }

  /* Inputs and selectors: comfortable tap targets */
  .stTextInput input,
  .stTextArea textarea,
  [data-baseweb="input"] input {
    min-height: 2.75rem;
    font-size: 1.05rem;
  }
  [data-baseweb="select"] > div {
    min-height: 2.75rem;
  }

  /* Uploader and date/time pickers breathe on narrow screens */
  .stFileUploader section,
  [data-testid="stFileUploaderDropzone"] {
    min-height: 5rem;
  }

  /* Status chips / cards: roomier padding, rounded feel */
  [data-testid="stVerticalBlockBorderWrapper"],
  [data-testid="stDataFrame"] {
    border-radius: 0.75rem;
  }

  /* Prevent horizontal scroll from long load numbers / refs */
  [data-testid="stMarkdownContainer"] code,
  [data-testid="stMarkdownContainer"] pre {
    white-space: normal;
    word-break: break-word;
  }

  /* Stack split horizontal blocks to avoid cramped 2/3-col layouts */
  [data-testid="stHorizontalBlock"] {
    flex-wrap: wrap;
    gap: 0.6rem;
  }

  /* Status indicators: pill-shaped chips read well on a narrow viewport */
  [data-testid="stMarkdownContainer"] code {
    background: rgba(255, 255, 255, 0.08);
    padding: 0.2rem 0.5rem;
    border-radius: 0.5rem;
    display: inline-block;
  }

  /* Card headings breathe so statuses are scannable while driving */
  [data-testid="stMarkdownContainer"] h1,
  [data-testid="stMarkdownContainer"] h2,
  [data-testid="stMarkdownContainer"] h3 {
    line-height: 1.4;
  }

  /* Bordered status cards get roomier inner padding */
  [data-testid="stVerticalBlockBorderWrapper"] {
    padding: 0.6rem 0.9rem;
  }

  /* Expanders (e.g. repair photo, register vehicle) are full-width tap rows */
  [data-testid="stExpander"] details > summary {
    min-height: 3rem;
  }

  /* Dropdown option rows: comfortable 44px tap rows on phones */
  [data-baseweb="popover"] li,
  [data-baseweb="menu"] li {
    min-height: 2.5rem;
    padding: 0.5rem 0.75rem;
  }

  /* Radio (Owner hat-switcher) & checkbox labels: touch-friendly */
  [role="radiogroup"] label,
  label[data-baseweb="checkbox"] {
    min-height: 2.5rem;
  }

  /* One-tap controls: no double-tap zoom, no text selection flash */
  .stButton > button,
  button[data-testid="stBaseButton-secondary"],
  button[data-testid="stBaseButton-primary"] {
    touch-action: manipulation;
    -webkit-user-select: none;
    user-select: none;
  }

  /* Kill horizontal scrolling from wide dataframes / long refs */
  body {
    overflow-x: hidden;
  }

  /* Bottom safe-area clearance so the last action isn't under the nav bar */
  .block-container {
    padding-top: 1.25rem;
    padding-bottom: 4rem;
  }

  /* Alerts & toasts render as rounded, readable cards */
  [data-testid="stAlert"],
  [data-testid="stToastViewport"] {
    border-radius: 0.75rem;
  }
}
</style>
"""


def inject_styles() -> None:
    """Injects the mobile-first stylesheet into the Streamlit app.

    Purely presentational and safe to call at the top of any view; the media
    query guarantees desktop layouts are unaffected.
    """
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)