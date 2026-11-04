import streamlit as st
import sqlite3
from datetime import date

# Page configuration
st.set_page_config(page_title="Easy Kcal", page_icon="🍎", layout="centered")

DB_NAME = "tracker.db"

# --- DATABASE FUNCTIONS ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def verify_user(username, password):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND password_hash = ?", (username, password)).fetchone()
    conn.close()
    return user

def get_user_meals(user_id):
    conn = get_db_connection()
    meals = conn.execute("SELECT * FROM meals_config WHERE user_id = ?", (user_id,)).fetchall()
    conn.close()
    return meals

def save_user_meal(user_id, meal_name, calories, protein, is_adherence):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO meals_config (user_id, meal_name, calories, protein, is_adherence)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, meal_name, calories, protein, is_adherence))
    conn.commit()
    conn.close()

def get_daily_log(user_id, entry_date):
    conn = get_db_connection()
    log = conn.execute("SELECT * FROM daily_logs WHERE user_id = ? AND entry_date = ?", (user_id, str(entry_date))).fetchone()
    conn.close()
    return log

def save_daily_log(user_id, entry_date, meals_eaten, other_calories, workout_done, notes):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO daily_logs (user_id, entry_date, diet_meals, workout, other_calories, notes)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, entry_date) 
        DO UPDATE SET diet_meals = excluded.diet_meals,
                      workout = excluded.workout,
                      other_calories = excluded.other_calories,
                      notes = excluded.notes
    """, (user_id, str(entry_date), meals_eaten, workout_done, other_calories, notes))
    conn.commit()
    conn.close()

# --- SESSION / LOGIN ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = None
    st.session_state["username"] = None

if not st.session_state["logged_in"]:
    st.markdown("<h2 style='text-align: center;'>🍎 Easy Kcal</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Please log in to your account</p>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        username_input = st.text_input("Username")
        password_input = st.text_input("Password", type="password")
        submit_login = st.form_submit_button("Sign In")
        
        if submit_login:
            user = verify_user(username_input, password_input)
            if user:
                st.session_state["logged_in"] = True
                st.session_state["user_id"] = user["id"]
                st.session_state["username"] = user["username"]
                st.rerun()
            else:
                st.error("Incorrect username or password.")
    st.stop()

# --- HEADER (APP NAME) ---
user_id = st.session_state["user_id"]

st.markdown("""
    <div style='background-color: #6B2E2E; padding: 18px; border-radius: 10px; color: white; text-align: center; margin-bottom: 15px;'>
        <h1 style='margin: 0; font-size: 26px; letter-spacing: 1px;'>🍎 Easy Kcal</h1>
    </div>
""", unsafe_allow_html=True)

# Navigation tabs
tab_diary, tab_results, tab_ai = st.tabs(["📅 Diary", "📊 Results", "🤖 Diet AI"])

# ==========================================
# TAB 1: DIARY
# ==========================================
with tab_diary:
    selected_date = st.date_input("Entry Date", value=date.today())
    
    # Load user data & daily logs for the selected date
    meals_cfg = get_user_meals(user_id)
    meals_dict = {m["meal_name"]: m for m in meals_cfg}
    existing_log = get_daily_log(user_id, selected_date)
    
    saved_meals = existing_log["diet_meals"].split(",") if existing_log and existing_log["diet_meals"] else []
    saved_workouts = existing_log["workout"].split(",") if existing_log and existing_log["workout"] else []
    saved_other_cal = existing_log["other_calories"] if existing_log else 0
    saved_notes = existing_log["notes"] if existing_log else ""

    # Synchronize widget states in session_state when date changes
    if "last_synced_date" not in st.session_state or st.session_state["last_synced_date"] != selected_date:
        st.session_state["last_synced_date"] = selected_date
        for m in meals_cfg:
            meal_name = m["meal_name"]
            st.session_state[f"meal_{meal_name}"] = meal_name in saved_meals
        st.session_state["input_other_cal"] = int(saved_other_cal)
        workout_options_init = ["Abs", "Shoulders + Back", "Cardio", "Quad + Pantu", "Butt", "Arms"]
        st.session_state["input_workout"] = [w for w in saved_workouts if w in workout_options_init]
        st.session_state["input_notes"] = saved_notes

    # --- CALCULATIONS FOR TOP CARDS (Whole numbers rounded) ---
    target_kcal = st.session_state.get(f"target_kcal_{user_id}", 2000)
    target_protein = st.session_state.get(f"target_protein_{user_id}", 130.0)

    diet_kcal_sum = sum(meals_dict[m]["calories"] for m in saved_meals if m in meals_dict)
    diet_prot_sum = sum(meals_dict[m]["protein"] for m in saved_meals if m in meals_dict and meals_dict[m]["protein"])
    
    spent_kcal = round(diet_kcal_sum + saved_other_cal)
    remaining_kcal = round(target_kcal - spent_kcal)
    protein_to_go = round(max(0.0, target_protein - diet_prot_sum))

    # --- TOP METRIC CARDS ---
    col1, col2, col3 = st.columns(3)
    col1.metric(label="🔥 Spent Kcal", value=f"{spent_kcal} kcal")
    col2.metric(label="🎯 Remaining Kcals", value=f"{remaining_kcal} kcal")
    col3.metric(label="🥩 Protein to Go", value=f"{protein_to_go}g")

    st.markdown("---")

    # --- DAY OR WEEK VIEW SELECTOR ---
    view_mode = st.radio("View Mode", options=["Day View", "Week View"], horizontal=True, key="view_mode_selector")

    if view_mode == "Day View":
        # MEALS SECTION
        st.markdown("### 🥗 Meals")
        if not meals_cfg:
            st.info("No meals added yet. Expand '⚙️ Edit Diet & Goals' below to add your meals.")
        else:
            cols = st.columns(2)
            current_selected_meals = []
            for i, m in enumerate(meals_cfg):
                col = cols[i % 2]
                meal_name = m["meal_name"]
                is_checked = meal_name in saved_meals
                if col.checkbox(meal_name, value=is_checked, key=f"meal_{meal_name}"):
                    current_selected_meals.append(meal_name)
            
            # Auto-save meal changes
            if set(current_selected_meals) != set(saved_meals):
                save_daily_log(user_id, selected_date, ",".join(current_selected_meals), saved_other_cal, ",".join(saved_workouts), saved_notes)
                st.rerun()

        # OTHER CALORIES (nested inside meals view without separate header title)
        other_calories = st.number_input("🍔 Other Calories (extra outside plan):", min_value=0, value=int(saved_other_cal), step=10, key="input_other_cal")
        if other_calories != saved_other_cal:
            save_daily_log(user_id, selected_date, ",".join(saved_meals), other_calories, ",".join(saved_workouts), saved_notes)
            st.rerun()
        
        st.markdown("---")
        # WORKOUT SECTION
        st.markdown("### 🏋️ Workout")
        workout_options = ["Abs", "Shoulders + Back", "Cardio", "Quad + Pantu", "Butt", "Arms"]
        selected_workouts = st.multiselect(
            "Select workouts done today:",
            options=workout_options,
            default=[w for w in saved_workouts if w in workout_options],
            key="input_workout"
        )
        if set(selected_workouts) != set(saved_workouts):
            save_daily_log(user_id, selected_date, ",".join(saved_meals), saved_other_cal, ",".join(selected_workouts), saved_notes)
            st.rerun()
        
        st.markdown("---")
        # NOTES SECTION
        st.markdown("### 📝 Notes")
        notes = st.text_area("Daily Notes:", value=saved_notes, key="input_notes")
        if notes != saved_notes:
            save_daily_log(user_id, selected_date, ",".join(saved_meals), saved_other_cal, ",".join(saved_workouts), notes)
            st.rerun()

    else:
        # WEEK VIEW OVERVIEW
        st.subheader("🗓️ Weekly Summary Overview")
        st.info("Showing weekly aggregated stats and log history...")

    # --- HIDDEN BY DEFAULT: EDIT DIET & GOALS EXPANDER ---
    st.markdown("---")
    with st.expander("⚙️ Edit Diet & Goals"):
        st.markdown("#### Set Your Daily Targets")
        new_target_kcal = st.number_input("Total Daily Calorie Goal (kcal)", min_value=500, max_value=6000, value=int(target_kcal), step=50, key="setting_target_kcal")
        new_target_protein = st.number_input("Total Daily Protein Goal (g)", min_value=0.0, max_value=400.0, value=float(target_protein), step=5.0, key="setting_target_protein")
        
        if st.button("💾 Save Goals"):
            st.session_state[f"target_kcal_{user_id}"] = new_target_kcal
            st.session_state[f"target_protein_{user_id}"] = new_target_protein
            st.success("Goals updated successfully!")
            st.rerun()

        st.markdown("---")
        st.markdown("#### Add New Meal to Diet")
        with st.form("add_meal_form"):
            new_meal_name = st.text_input("Meal Name")
            new_calories = st.number_input("Calories (kcal) *Mandatory*", min_value=0, step=10)
            new_protein = st.number_input("Protein (g) *Optional*", min_value=0.0, step=1.0)
            
            if st.form_submit_button("➕ Add Meal"):
                if new_meal_name:
                    save_user_meal(user_id, new_meal_name, new_calories, new_protein, 1)
                    st.success(f"Added {new_meal_name}!")
                    st.rerun()
                else:
                    st.error("Please enter a meal name.")

# ==========================================
# TAB 2 & 3
# ==========================================
with tab_results:
    st.subheader("Results & Progress")
with tab_ai:
    st.subheader("Diet AI Assistant")