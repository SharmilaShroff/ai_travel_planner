import streamlit as st
from google import genai
import openrouteservice
from geopy.geocoders import Nominatim
import folium
from streamlit_folium import st_folium
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from datetime import datetime

# ================= CONFIG =================
st.set_page_config(page_title="AI Travel Planner 🎒", layout="wide")

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
ORS_API_KEY = st.secrets["ORS_API_KEY"]

genai_client = genai.Client(api_key=GEMINI_API_KEY)
ors_client = openrouteservice.Client(key=ORS_API_KEY)

if "generated_plan" not in st.session_state:
    st.session_state.generated_plan = None

st.title("🎒 AI Travel Planner for Students")
st.write("Plan smart. Travel smarter. Budget-friendly vibes only 😎")

# ================= INPUT UI =================
col1, col2 = st.columns(2)

with col1:
    from_location = st.text_input("From Location")
    to_location = st.text_input("To Location")
    start_date = st.date_input("Start Date")
    end_date = st.date_input("End Date")
    group_size = st.number_input("Group Size", min_value=1, value=1)

with col2:
    food_pref = st.selectbox("Food Preference", ["Veg", "Non-Veg"])
    guide_needed = st.selectbox("Need Guide?", ["Yes", "No"])
    trip_type = st.selectbox("Trip Type", ["Adventure", "Relax", "Cultural", "Party"])

# ================= BUDGET LOGIC =================
def calculate_budget(days, group_size, trip_type, guide_needed):
    # Base costs per day
    stay_per_day = 800
    food_per_day = 400
    local_transport_per_day = 300

    # Trip type adjustment
    trip_multiplier = 1

    if trip_type == "Adventure":
        trip_multiplier = 1.4
    elif trip_type == "Party":
        trip_multiplier = 1.5
    elif trip_type == "Cultural":
        trip_multiplier = 1.2
    elif trip_type == "Relax":
        trip_multiplier = 1.1

    # Base cost per person
    base_cost = days * (stay_per_day + food_per_day + local_transport_per_day)
    misc = 1000

    total_per_person = (base_cost + misc) * trip_multiplier

    # Guide cost
    if guide_needed == "Yes":
        guide_cost_per_day = 1500
        guide_share = (guide_cost_per_day * days) / group_size
        total_per_person += guide_share

    # Group discount
    if group_size >= 5:
        total_per_person *= 0.9  # 10% discount

    group_total = total_per_person * group_size

    return int(total_per_person), int(group_total)

# ================= AI PLAN =================
def generate_plan(days):
    guide_section = ""
    if guide_needed == "Yes":
        guide_section = """
Include:
Local Tour Guides:
- Name
- Contact
- Approx daily cost
"""

    prompt = f"""
Create a student-friendly travel itinerary.

From: {from_location}
To: {to_location}
Days: {days}
Group size: {group_size}
Food preference: {food_pref}
Trip type: {trip_type}

Structure day-wise.

Include:
- Places
- Food spots
- Adventure options
- Travel tips
- Safety tips
- Emergency numbers (India)

{guide_section}
"""

    response = genai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return response.text

# ================= ROUTE MAP =================
def show_route_map():
    geolocator = Nominatim(user_agent="travel_app")

    from_geo = geolocator.geocode(from_location)
    to_geo = geolocator.geocode(to_location)

    if not from_geo or not to_geo:
        st.warning("Could not locate one of the places.")
        return

    m = folium.Map(
        location=[(from_geo.latitude + to_geo.latitude) / 2,
                  (from_geo.longitude + to_geo.longitude) / 2],
        zoom_start=4
    )

    folium.Marker(
        [from_geo.latitude, from_geo.longitude],
        popup="Start"
    ).add_to(m)

    folium.Marker(
        [to_geo.latitude, to_geo.longitude],
        popup="Destination"
    ).add_to(m)

    # If same country → use ORS road route
    if from_geo.raw.get("display_name") and to_geo.raw.get("display_name"):

        try:
            route = ors_client.directions(
                coordinates=[
                    [from_geo.longitude, from_geo.latitude],
                    [to_geo.longitude, to_geo.latitude]
                ],
                profile='driving-car',
                format='geojson'
            )

            geometry = route["features"][0]["geometry"]["coordinates"]
            route_coords = [(lat, lon) for lon, lat in geometry]
            folium.PolyLine(route_coords).add_to(m)

        except:
            # If ORS fails (like international)
            folium.PolyLine(
                [
                    [from_geo.latitude, from_geo.longitude],
                    [to_geo.latitude, to_geo.longitude]
                ],
                dash_array="5,5"
            ).add_to(m)

    st.subheader("🗺 Route Map")
    st_folium(m, height=500)
# ================= PDF =================
def create_pdf(content):
    file_path = "travel_plan.pdf"
    doc = SimpleDocTemplate(file_path, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    for line in content.split("\n"):
        clean_line = line.encode("latin-1", "ignore").decode("latin-1")
        if clean_line.strip() == "":
            elements.append(Spacer(1, 6))
        else:
            elements.append(Paragraph(clean_line, styles["Normal"]))
            elements.append(Spacer(1, 8))

    doc.build(elements)
    return file_path

# ================= BUTTON =================
if st.button("Generate Travel Plan ✈"):
    if from_location and to_location:
        days = max((end_date - start_date).days, 1)

        with st.spinner("Generating your travel plan..."):
            plan = generate_plan(days)
            st.session_state.generated_plan = plan
    else:
        st.warning("Please enter both From and To locations.")

# ================= DISPLAY =================
if st.session_state.generated_plan:

    days = max((end_date - start_date).days, 1)
    per_person, group_total = calculate_budget(
    days,
    group_size,
    trip_type,
    guide_needed
)

    st.subheader("🧠 AI Travel Plan")
    st.write(st.session_state.generated_plan)

    st.subheader("💰 Calculated Budget (Logic Based)")
    st.write(f"Per Person: ₹{per_person}")
    st.write(f"Group Total: ₹{group_total}")

    show_route_map()

    pdf = create_pdf(st.session_state.generated_plan)
    with open(pdf, "rb") as f:
        st.download_button(
            "Download Travel Plan as PDF 📄",
            f,
            file_name="AI_Travel_Plan.pdf"

        )
