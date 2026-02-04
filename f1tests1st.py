import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
import fastf1
from fastf1 import plotting
import numpy as np
from matplotlib import colormaps
from matplotlib.collections import LineCollection
from matplotlib.colors import ListedColormap
from gnews import GNews
from datetime import timedelta

# Setup
plt.style.use('seaborn-v0_8-darkgrid')
fastf1.plotting.setup_mpl(mpl_timedelta_support=True, color_scheme='fastf1')

st.set_page_config(page_title="Formula 1 Race Statistics", layout="wide")
st.title("🏎️ F1 Stats Visualized")

# --- DATA LOADING FUNCTIONS (With Caching) ---
@st.cache_data
def get_schedule(year):
    return fastf1.get_event_schedule(year)

@st.cache_resource # cache_resource is better for session objects
def load_race_session(year, race_name, race_format_selection):
    session = fastf1.get_session(year, race_name, race_format_selection)
    session.load()
    return session

# --- SIDEBAR SELECTION ---
with st.sidebar:
    st.header("Configuration")
    year_selection = st.number_input("Year", min_value=2018, max_value=2025, value=2024)
    
    schedule = get_schedule(year_selection)
    # Filter out testing events
    race_options = schedule[schedule['EventFormat'] != 'testing']['EventName'].to_list()
    race_selection = st.selectbox("Select Race", race_options, index=0)

    race_format_options = ["Race", "Qualifying"]
    race_format_selection = st.selectbox("Select Format", race_format_options, index = 0)
    if race_format_selection == "Race":
        placeholder = "Race"
        race_format_selection = "R"
    elif race_format_selection == "Qualifying":
        placeholder = "Qualifying"
        race_format_selection = "Q"



# Load Data
with st.spinner(f"Loading {race_selection} data..."):
    race = load_race_session(year_selection, race_selection, race_format_selection)

# --- MAIN INTERFACE ---
st.subheader(f"Comparison: {race_selection} {year_selection} - {placeholder}")

# Driver selection
cols = st.columns(2)
optionsdrivers = race.results["BroadcastName"].to_list()

with cols[0]:
    sorted_drivers = sorted(optionsdrivers, key=lambda x: x[2].lower() if len(x) > 2 else x)
    driver1 = st.selectbox("First Driver", sorted_drivers, index=0)
with cols[1]:
    driver2 = st.selectbox("Second Driver", sorted_drivers, index=1)

# Abbreviation Lookup
d1_abb = race.results.loc[race.results["BroadcastName"] == driver1, "Abbreviation"].values[0]
d2_abb = race.results.loc[race.results["BroadcastName"] == driver2, "Abbreviation"].values[0]




# --- PLOT 1: LAP TIME COMPARISON ---
st.write("### Lap Time Trace")
fig1, ax1 = plt.subplots(figsize=(12, 5))

for driver in (d1_abb, d2_abb):
    laps = race.laps.pick_drivers(driver).pick_quicklaps()
    style = plotting.get_driver_style(identifier=driver, style=['color', 'linestyle'], session=race)
    ax1.plot(laps['LapNumber'], laps['LapTime'], **style, label=driver)

ax1.set_xlabel("Lap Number")
ax1.set_ylabel("Lap Time")
ax1.invert_yaxis() # Faster is up
ax1.legend()
st.pyplot(fig1)

# --- PLOT 2 & 3: TIRE DEGRADATION (Side by Side) ---
st.write("### Tire Compound & Pace")
deg_cols = st.columns(2)

for i, driver_abb in enumerate([d1_abb, d2_abb]):
    driver_name = [driver1, driver2][i]
    laps = race.laps.pick_drivers(driver_abb).pick_quicklaps()
    
    fig, ax = plt.subplots(figsize=(6, 5))
    sns.scatterplot(
        data=laps, x="LapNumber", y="LapTime", hue="Compound", ax=ax,
        palette=fastf1.plotting.get_compound_mapping(session=race),
        s=80, linewidth=0
    )
    ax.invert_yaxis()
    ax.set_title(f"{driver_name} Pace")
    deg_cols[i].pyplot(fig)

# --- PLOT 4 & 5: GEAR CHANGE (Side by Side) ---
st.write(f"### Gear Change on Track - fastest Lap of Driver during {placeholder}")
gear_cols = st.columns(2)

# Correctly loop through driver abbreviations and names
drivers_to_plot = [d1_abb, d2_abb]
driver_names = [driver1, driver2]
custom_gear_colors = [
    "#FF0000", # Gear 1: Red
    "#FF4500", # Gear 2: OrangeRed
    "#FFA500", # Gear 3: Orange
    "#FFD700", # Gear 4: Gold
    "#D9FF2FEB", # Gear 5: GreenYellow
    "#7FFF00", # Gear 6: Chartreuse
    "#00FF00", # Gear 7: Green
    "#008000"  # Gear 8: DarkGreen
]

for i, drv_abb in enumerate(drivers_to_plot):
    # 1. Use pick_drivers (plural)
    driver_laps = race.laps.pick_drivers(drv_abb)
    
    # 2. Safety Check: Ensure the driver actually has laps
    if not driver_laps.empty:
        fastest_lap = driver_laps.pick_fastest()
        
        # 3. Check if pick_fastest actually found a lap
        if fastest_lap is not None:
            tel = fastest_lap.get_telemetry().add_distance()
            
            # Prepare segments for LineCollection
            x = np.array(tel['X'].values)
            y = np.array(tel['Y'].values)
            points = np.array([x, y]).T.reshape(-1, 1, 2)
            segments = np.concatenate([points[:-1], points[1:]], axis=1)
            gear = tel['nGear'].to_numpy().astype(float)

            # Create the plot
            fig, ax = plt.subplots(figsize=(8, 8))
            cmap = ListedColormap(custom_gear_colors)
            
            lc_comp = LineCollection(segments, norm=plt.Normalize(1, 9), cmap=cmap)
            lc_comp.set_array(gear)
            lc_comp.set_linewidth(5)

            ax.add_collection(lc_comp)
            ax.axis('equal')
            ax.set_axis_off()

            ax.set_title(f"{driver_names[i]} - {fastest_lap['LapTime']}", fontsize=14)

            # Add Colorbar
            cbar = fig.colorbar(mappable=lc_comp, ax=ax, label="Gear")
            cbar.set_ticks(np.arange(1.5, 9.5))
            cbar.set_ticklabels(np.arange(1, 9))

            # Display in the correct Streamlit column
            gear_cols[i].pyplot(fig)
        else:
            gear_cols[i].warning(f"No valid lap found for {drv_abb}")
    else:
        gear_cols[i].warning(f"No lap data available for {drv_abb}")

# --- PLOT 6: POSITION CHANGE ---
st.write(f"### Position Change during {race_selection}")
fig, ax = plt.subplots(figsize=(10, 6.9))

if race_format_selection == "R":
    for drv in race.drivers:
        drv_laps = race.laps.pick_drivers(drv)

        abb = drv_laps['Driver'].iloc[0]
        style = fastf1.plotting.get_driver_style(identifier=abb,
                                                style=['color', 'linestyle'],
                                                session=race)

        ax.plot(drv_laps['LapNumber'], drv_laps['Position'],
                label=abb, **style)
    ax.set_ylim([20.5, 0.5])
    ax.set_yticks([1, 5, 10, 15, 20])
    ax.set_title(f"{race.event['EventName']} {race.event.year} - Position Change")
    ax.set_xlabel('Lap')
    ax.set_ylabel('Position')
    ax.legend(bbox_to_anchor=(1.0, 1.02))
    st.pyplot(fig)
else:
    st.write("No Position change during Qualifying")


#plot racelinks - headlines
st.write(f"### Headlines of {race_selection}")

race_date = race.date
race_date_1dayafter = race.date + timedelta(days=1)
google_news = GNews(
    language='en', 
    country='US', 
    start_date=(race_date_1dayafter.year, race_date_1dayafter.month, race_date_1dayafter.day), 
    end_date=(race_date_1dayafter.year, race_date_1dayafter.month, race_date_1dayafter.day)
)
google_news.max_results = 3
all_articles = google_news.get_news(f'{race_selection} {year_selection}')


article_link = {}
for article in all_articles:
    title = article.get("title")
    link = article.get("url")
    article_link[title] = link

for title, link in article_link.items():
    st.write(f"#### {title}")
    st.write(f"url: {link}\n")
