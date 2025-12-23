import tkinter as tk
from tkinter import ttk, messagebox
from tkintermapview import TkinterMapView
import requests
import polyline
from pyowm import OWM
import traceback
import datetime

# -----------------------------------------------------------
# CONFIG
# -----------------------------------------------------------
GOOGLE_API_KEY = "AIzaSyA-AK5acbFY9QDVYBZgfxicB1KZjtcN1As"
OPENWEATHER_API_KEY = "9c70c5699c1b91674b784539f5e807c2"

HOME_LOCATION = "58 Glyn Farm Road, B32 1NP"
WORK_LOCATION = "Horiba Test Automation, Worcester"

# -----------------------------------------------------------
# GOOGLE API HELPERS (REST)
# -----------------------------------------------------------

def geocode_address(address: str):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_API_KEY}
    r = requests.get(url, params=params)
    data = r.json()
    if data.get("status") != "OK" or not data.get("results"):
        raise ValueError(f"Failed to geocode '{address}': {data.get('status')}")
    loc = data["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]

def get_route_info(origin_latlng, dest_latlng):
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": GOOGLE_API_KEY,
        "X-Goog-FieldMask": (
            "routes.duration,routes.staticDuration,routes.distanceMeters,"
            "routes.polyline.encodedPolyline,routes.legs"
        ),
    }
    body = {
        "origin": {"location": {"latLng": {"latitude": origin_latlng[0], "longitude": origin_latlng[1]}}},
        "destination": {"location": {"latLng": {"latitude": dest_latlng[0], "longitude": dest_latlng[1]}}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }

    resp = requests.post(url, headers=headers, json=body)
    if resp.status_code != 200:
        raise ValueError(f"Routes API error {resp.status_code}: {resp.text}")

    data = resp.json()
    if "routes" not in data or not data["routes"]:
        raise ValueError("No routes found in response.")

    route = data["routes"][0]
    leg = route["legs"][0]

    # Duration with traffic
    duration_sec = int(leg["duration"].replace("s", "")) if "duration" in leg else 0
    # Static duration (no traffic)
    static_sec = int(route["staticDuration"].replace("s", "")) if "staticDuration" in route else duration_sec

    distance_meters = route.get("distanceMeters", 0)

    # Decode polyline
    route_path = []
    if "encodedPolyline" in route.get("polyline", {}):
        route_path = polyline.decode(route["polyline"]["encodedPolyline"])

    # Determine traffic severity
    delay_ratio = duration_sec / static_sec if static_sec else 1
    if delay_ratio < 1.1:
        traffic_color = "green"
    elif delay_ratio < 1.5:
        traffic_color = "orange"
    else:
        traffic_color = "red"

    start_lat = leg["startLocation"]["latLng"]["latitude"]
    start_lng = leg["startLocation"]["latLng"]["longitude"]
    end_lat = leg["endLocation"]["latLng"]["latitude"]
    end_lng = leg["endLocation"]["latLng"]["longitude"]

    start_coords = (start_lat, start_lng)
    end_coords = (end_lat, end_lng)
    mid_coords = ((start_lat + end_lat) / 2, (start_lng + end_lng) / 2)

    return {
        "duration": f"{duration_sec // 60} min",
        "distance": f"{distance_meters / 1000:.1f} km",
        "route_path_coords": route_path,
        "start_coords": start_coords,
        "end_coords": end_coords,
        "traffic_color": traffic_color,
        "weather_coords": {
            "Home": start_coords,
            "Midpoint": mid_coords,
            "Work": end_coords,
        },
    }

# -----------------------------------------------------------
# WEATHER (OpenWeather)
# -----------------------------------------------------------

#def get_weather_data(coords, owm_client):
#    lat, lon = coords
#    mgr = owm_client.weather_manager()
#    try:
#        obs = mgr.weather_at_coords(lat, lon)
#        w = obs.weather
#        temp = w.temperature("celsius")["temp"]
#        desc = w.detailed_status.capitalize()
#        return f"🌡️ {temp:.1f}°C, {desc}"
#    except Exception as e:
#        return f"Weather error: {e}"

def get_weather_data(coords, owm_client):
    lat, lon = coords
    mgr = owm_client.weather_manager()
    try:
        one_call = mgr.one_call(lat=lat, lon=lon)
        current = one_call.current
        temp = current.temperature("celsius")["temp"]
        desc = current.detailed_status.capitalize()

        # Precipitation chance from hourly forecast (next hour)
        hourly = one_call.forecast_hourly
        precip_chance = hourly[0].precipitation_probability if hourly else None

        if precip_chance is not None:
            precip_text = f", Chance of rain: {precip_chance * 100:.0f}%"
        else:
            precip_text = ""

        return f" {temp:.1f}°C, {desc}{precip_text}"
    except Exception as e:
        return f"Weather error: {e}"




# -----------------------------------------------------------
# GUI APP
# -----------------------------------------------------------

class DynamicDriveWeatherApp:
    def __init__(self, master):
        self.master = master
        master.title("Drive Time & Weather Dashboard")

        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=3)
        master.grid_columnconfigure(1, weight=1)

        self.weather_client = OWM(OPENWEATHER_API_KEY)

        self.map_frame = ttk.Frame(master, padding=5)
        self.map_frame.grid(row=0, column=0, sticky="nsew")
        self.info_frame = ttk.Frame(master, padding=10)
        self.info_frame.grid(row=0, column=1, sticky="ew")

        self.map_widget = TkinterMapView(self.map_frame, width=900, height=500)
        self.map_widget.pack(fill="both", expand=True)
        self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")

        ttk.Label(self.info_frame, text="Route Summary", font=("Arial", 14, "bold")).pack(anchor="w")
        self.time_label = ttk.Label(self.info_frame, text="Drive Time: Calculating...")
        self.time_label.pack(anchor="w")
        self.distance_label = ttk.Label(self.info_frame, text="Distance: Calculating...")
        self.distance_label.pack(anchor="w")

        ttk.Separator(self.info_frame, orient="horizontal").pack(fill="x", pady=10)
        ttk.Label(self.info_frame, text="Weather", font=("Arial", 14, "bold")).pack(anchor="w")

        self.weather_labels = {}
        for place in ["Home", "Midpoint", "Work"]:
            lbl = ttk.Label(self.info_frame, text=f"{place}: Fetching...")
            lbl.pack(anchor="w")
            self.weather_labels[place] = lbl

        #ttk.Button(self.info_frame, text="Refresh", command=self.load_data).pack(anchor="e",side="bottom", pady=5)

        # Spacer to push the button to the bottom
        ttk.Label(self.info_frame, text="").pack(expand=True)

        # Centered Refresh button at the bottom
        refresh_btn = ttk.Button(self.info_frame, text="Refresh", command=self.load_data)
        refresh_btn.pack(side="bottom", pady=10)



        self.load_data()
        self.schedule_auto_refresh()

    def schedule_auto_refresh(self):
        now = datetime.datetime.now()
        if 6 <= now.hour < 10:
            self.load_data()
        # Schedule next check in 5 minutes (300,000 ms)
        self.master.after(300000, self.schedule_auto_refresh)

    def load_data(self):
        try:
            home_coords = geocode_address(HOME_LOCATION)
            work_coords = geocode_address(WORK_LOCATION)
            route_info = get_route_info(home_coords, work_coords)

            self.time_label.config(text=f"Drive Time: {route_info['duration']}")
            self.distance_label.config(text=f"Distance: {route_info['distance']}")

            self.map_widget.delete_all_marker()
            self.map_widget.delete_all_path()

            for name, coords in route_info["weather_coords"].items():
                weather = get_weather_data(coords, self.weather_client)
                self.weather_labels[name].config(text=f"{name}: {weather}")
                self.map_widget.set_marker(coords[0], coords[1], text=f"{name} ({weather})")

#            if route_info["route_path_coords"]:
#                self.map_widget.set_path(route_info["route_path_coords"], color="blue", width=4)

            if route_info["route_path_coords"]:
                self.map_widget.set_path(
                    route_info["route_path_coords"],
                    color=route_info["traffic_color"],
                    width=4
                )



            # ✅ FIXED BOUNDING BOX LOGIC
            latitudes = [route_info["start_coords"][0], route_info["end_coords"][0]]
            longitudes = [route_info["start_coords"][1], route_info["end_coords"][1]]
            top_left = (max(latitudes), min(longitudes))
            bottom_right = (min(latitudes), max(longitudes))
            self.map_widget.fit_bounding_box(top_left, bottom_right)

        except Exception as e:
            print("Error loading data:", e)
            print(traceback.format_exc())
            messagebox.showerror("Error", f"Failed to load data:\n{e}")

# -----------------------------------------------------------
# MAIN
# -----------------------------------------------------------

def main():
    root = tk.Tk()
    app = DynamicDriveWeatherApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
