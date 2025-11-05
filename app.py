import streamlit as st
import os
import random
from datetime import datetime
from st_supabase_connection import SupabaseConnection
import threading

# ---------------- CONFIG ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "GTSD-220-test")
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")

CLASSES = {
    "okay": "**Okay / No Defect**",
    "obscured": "Stickers / Graffiti",
    "deterioration": "Weathering / Aging",
    "blurred": "Motion Blur",
    "occluded": "Occlusion",
    "quality": "Low Image Quality",
    "weather": "Adverse Lighting / Weather",
    "angle": "Unusual Perspective"
}

CLASS_EXPLANATIONS = {
    "okay": "Sign in good condition.",
    "obscured": "Covered by stickers or graffiti, partially blocking the sign.",
    "deterioration": "Natural wear like fading, peeling, or rust.",
    "blurred": "Motion blur from moving platforms, softening edges.",
    "occluded": "Partially blocked by objects like foliage or vehicles.",
    "quality": "Low image quality due to resolution or sensor noise.",
    "weather": "Challenging lighting or weather conditions, e.g., glare, rain.",
    "angle": "Captured from unusual or high angles, causing perspective distortions."
}

st.set_page_config(page_title="Street Sign Conditions", page_icon="🚦", layout="centered")

# ---------------- SUPABASE ----------------
conn = st.connection("supabase", type=SupabaseConnection)
TABLE_NAME = "labels"

def save_label_bg(user, image, label):
    """Save label in a background thread."""
    def _save():
        conn.table("labels").insert(
            [{"user": user,
              "image": image,
              "label": label,
              "timestamp": datetime.now().isoformat()}],
            count="None"
        ).execute()
    threading.Thread(target=_save, daemon=True).start()

@st.cache_data(ttl=30)
def fetch_labels():
    rows = conn.table(TABLE_NAME).select("*").execute().data
    return rows

def get_unlabeled_images(all_images):
    """
    Return images labeled by less than 2 users.
    """
    rows = fetch_labels()  # gecachte Daten
    counts = {}
    for r in rows:
        counts[r["image"]] = counts.get(r["image"], set())
        counts[r["image"]].add(r["user"])
    return [img for img in all_images if len(counts.get(img, set())) < 2]

def get_count(min_users=1):
    rows = fetch_labels()  # gecachte Daten
    counts = {}
    for r in rows:
        counts[r["image"]] = counts.get(r["image"], set())
        counts[r["image"]].add(r["user"])
    if min_users == 1:
        return sum(1 for users in counts.values() if len(users) >= 1)
    else:
        return sum(1 for users in counts.values() if len(users) >= min_users)

# ---------------- UTILS ----------------
@st.cache_data
def load_images_list():
    valid_exts = (".jpg", ".jpeg", ".png")
    image_paths = []
    for root, _, files in os.walk(IMAGE_DIR):
        for file in files:
            if file.lower().endswith(valid_exts):
                image_paths.append(os.path.join(root, file))
    return image_paths

def show_example_images():
    with st.expander("ℹ️ Example images per defect class"):
        for class_key, class_label in CLASSES.items():
            class_path = os.path.join(EXAMPLES_DIR, class_key)
            if os.path.isdir(class_path):
                st.markdown(f"**{class_label}**")
                st.caption(CLASS_EXPLANATIONS[class_key])
                images = [f for f in os.listdir(class_path) if f.lower().endswith((".jpg", ".png", ".jpeg"))]
                sample_images = random.sample(images, min(4, len(images)))
                cols = st.columns(len(sample_images))
                for col, img_file in zip(cols, sample_images):
                    col.image(os.path.join(class_path, img_file), width='stretch')
                
def select_random_image(unlabeled):
    return random.choice(unlabeled) if unlabeled else None

# ---------------- SESSION ----------------
if "user" not in st.session_state:
    st.session_state.user = None
if "current_image" not in st.session_state:
    st.session_state.current_image = None

# ---------------- UI ----------------
st.title("🚦 Street Sign Conditions")
st.markdown(
    """
    Help improve traffic sign recognition!<br>
    Select the type of defect for each street sign image and click <b>Submit</b>.<br>
    """,
    unsafe_allow_html=True
)

# --- Examples ---
show_example_images()


# --- Login ---
if st.session_state.user is None:
    name = st.text_input("Enter your name:")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        if st.button("Start"):
            if name.strip():
                st.session_state.user = name.strip()
                st.rerun()
            else:
                st.warning("Please enter your name.")


# --- Main labeling ---
if st.session_state.user:
    all_images = load_images_list()
    unlabeled = get_unlabeled_images(all_images)
    
    if not unlabeled:
        st.balloons()
        st.write("🎉 All images have been labeled twice! Thank you.")
    else:
        if st.session_state.current_image is None:
            st.session_state.current_image = select_random_image(unlabeled)

        img_path = st.session_state.current_image
        col_img, col_labels = st.columns([5, 3], gap="large")

        with col_img:
            st.image(img_path, width='stretch')

        with col_labels:
            radio_key = f"label_{img_path}"
            st.markdown("<style>[role=radiogroup]{ gap:0.6rem; }</style>", unsafe_allow_html=True)

            label_choice = st.radio(
                "Choose a label:",
                options=CLASSES.values(),
                key=radio_key,
                index=0
            )
            current_class = [k for k, v in CLASSES.items() if v == label_choice][0]
            st.caption(CLASS_EXPLANATIONS[current_class])

            if st.button("✅ Submit"):
                rel_path = os.path.relpath(img_path, IMAGE_DIR)
                save_label_bg(st.session_state.user, rel_path, label_choice)
                st.session_state.current_image = select_random_image(get_unlabeled_images(all_images))
                #st.success("Saved!")
                st.rerun()

        # --- Progress bars ---
        user_count_once = get_count(1)
        user_count_twice = get_count(2)
        total_images = len(all_images)

        st.progress(min(user_count_once / total_images, 1.0))
        st.caption(f"{user_count_once} out of {total_images} images have been labeled by at least 1 user")

        #st.progress(min(user_count_twice / total_images, 1.0))
        #st.caption(f"{user_count_twice} of {total_images} images labeled by at least 2 users")

        if st.button("🔄 Skip image"):
            st.session_state.current_image = select_random_image(unlabeled)
            st.rerun()
