"""
Bedrock LLaMA 3 Chatbot
------------------------
A Streamlit chat UI backed by Meta LLaMA 3 models served through
Amazon Bedrock's InvokeModel API.
"""

import json
import boto3
import streamlit as st
from botocore.exceptions import ClientError, NoCredentialsError

# ------------------ PAGE CONFIG ------------------
st.set_page_config(
    page_title="Bedrock LLaMA 3 Chatbot",
    page_icon="🤖",
    layout="wide"
)

# ------------------ CUSTOM UI ------------------
st.markdown("""
<style>
.stApp {
    background-color: #0E1117;
    color: white;
}
.chat-container {
    max-width: 900px;
    margin: auto;
}
.user-msg {
    background-color: #1E88E5;
    padding: 12px 16px;
    border-radius: 12px;
    margin: 8px 0;
    color: white;
}
.bot-msg {
    background-color: #262730;
    padding: 12px 16px;
    border-radius: 12px;
    margin: 8px 0;
    color: white;
}
.title {
    text-align: center;
    color: #4CAF50;
    font-size: 2.2rem;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

# ------------------ TITLE ------------------
st.markdown("<div class='title'>🤖 AWS Bedrock LLaMA 3 Chatbot</div>", unsafe_allow_html=True)
st.caption("ChatGPT-style AI powered by Amazon Bedrock + Meta LLaMA 3")

# ------------------ MODEL OPTIONS ------------------
MODEL_OPTIONS = {
    "LLaMA 3 8B Instruct": "meta.llama3-8b-instruct-v1:0",
    "LLaMA 3 70B Instruct": "meta.llama3-70b-instruct-v1:0",
}

# ------------------ SESSION STATE ------------------
defaults = {
    "chat_history": [],   # list of (role, message) tuples
    "client": None,
    "connected_region": None,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ------------------ SIDEBAR (AWS CONFIG) ------------------
with st.sidebar:
    st.header("⚙️ AWS Configuration")

    with st.expander("Credentials", expanded=st.session_state.client is None):
        aws_access_key = st.text_input("AWS Access Key ID", type="password")
        aws_secret_key = st.text_input("AWS Secret Access Key", type="password")
        aws_session_token = st.text_input(
            "AWS Session Token (optional, for temporary credentials)",
            type="password"
        )
        st.caption(
            "Credentials are kept only in this session's memory and are "
            "never written to disk or logged."
        )

    region = st.selectbox("Region", ["us-east-1", "us-west-2"])
    model_label = st.selectbox("Model", list(MODEL_OPTIONS.keys()))
    model_id = MODEL_OPTIONS[model_label]

    temperature = st.slider("Temperature", 0.0, 1.0, 0.7, 0.05)
    max_tokens = st.slider("Max response length (tokens)", 64, 2048, 512, 64)

    col1, col2 = st.columns(2)
    with col1:
        connect_clicked = st.button("🚀 Connect", use_container_width=True)
    with col2:
        clear_clicked = st.button("🗑️ Clear chat", use_container_width=True)

    if connect_clicked:
        if not aws_access_key or not aws_secret_key:
            st.error("Please provide both an Access Key and Secret Key.")
        else:
            try:
                session_kwargs = dict(
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                    region_name=region,
                )
                if aws_session_token:
                    session_kwargs["aws_session_token"] = aws_session_token

                session = boto3.Session(**session_kwargs)
                client = session.client("bedrock-runtime")

                # Cheap sanity check: list foundation models is a control-plane
                # call, so instead we just trust invoke; store client.
                st.session_state.client = client
                st.session_state.connected_region = region
                st.success("Connected to AWS Bedrock ✅")
            except (ClientError, NoCredentialsError) as e:
                st.error(f"Connection failed: {e}")
            except Exception as e:
                st.error(f"Unexpected error: {e}")

    if clear_clicked:
        st.session_state.chat_history = []
        st.rerun()

    if st.session_state.client:
        st.caption(f"Connected to `{st.session_state.connected_region}`")

# ------------------ FUNCTION: BUILD LLAMA 3 PROMPT ------------------
def build_llama3_prompt(history, system_prompt=None):
    """
    Format the full conversation into LLaMA 3's chat template so the
    model actually sees multi-turn context, not just raw text.
    """
    parts = ["<|begin_of_text|>"]

    if system_prompt:
        parts.append(
            f"<|start_header_id|>system<|end_header_id|>\n{system_prompt}<|eot_id|>"
        )

    for role, msg in history:
        header = "user" if role == "user" else "assistant"
        parts.append(f"<|start_header_id|>{header}<|end_header_id|>\n{msg}<|eot_id|>")

    parts.append("<|start_header_id|>assistant<|end_header_id|>\n")
    return "\n".join(parts)


# ------------------ FUNCTION: CALL BEDROCK ------------------
def get_bedrock_response(history, client, model_id, temperature, max_tokens):
    prompt = build_llama3_prompt(history)

    body = {
        "prompt": prompt,
        "temperature": temperature,
        "top_p": 0.9,
        "max_gen_len": max_tokens,
    }

    response = client.invoke_model(
        modelId=model_id,
        body=json.dumps(body),
        contentType="application/json",
        accept="application/json",
    )

    response_body = json.loads(response["body"].read())
    return response_body.get("generation", "No response generated.").strip()


# ------------------ CHAT UI ------------------
st.markdown("---")

if st.session_state.client:

    # Display existing history
    for role, msg in st.session_state.chat_history:
        css_class = "user-msg" if role == "user" else "bot-msg"
        icon = "🧑" if role == "user" else "🤖"
        label = "You" if role == "user" else "LLaMA 3"
        st.markdown(
            f"<div class='{css_class}'>{icon} {label}: {msg}</div>",
            unsafe_allow_html=True,
        )

    user_input = st.chat_input("Type your message...")

    if user_input:
        st.session_state.chat_history.append(("user", user_input))

        with st.spinner("LLaMA 3 is thinking..."):
            try:
                reply = get_bedrock_response(
                    st.session_state.chat_history,
                    st.session_state.client,
                    model_id,
                    temperature,
                    max_tokens,
                )
                st.session_state.chat_history.append(("assistant", reply))
            except ClientError as e:
                st.error(f"AWS error: {e.response['Error'].get('Message', str(e))}")
            except Exception as e:
                st.error(f"Error: {e}")

        st.rerun()

else:
    st.info("👉 Connect to AWS Bedrock from the sidebar to start chatting")

