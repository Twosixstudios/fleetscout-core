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
}
</style>
"""


def inject_styles() -> None:
    """Injects the mobile-first stylesheet into the Streamlit app.

    Purely presentational and safe to call at the top of any view; the media
    query guarantees desktop layouts are unaffected.
    """
    st.markdown(MOBILE_CSS, unsafe_allow_html=True)