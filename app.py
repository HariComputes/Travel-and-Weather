from flask import Flask, render_template, send_from_directory
import requests
from pyowm import OWM
import polyline
import os
import datetime
import json

# Load secrets from JSON file
with open("secrets.json") as f:
    secrets = json.load(f)

# Access secrets
GOOGLE_API_KEY = secrets["GOOGLE_API_KEY"]
OPENWEATHER_API_KEY = secrets["OPENWEATHER_API_KEY"]
HOME_LOCATION = secrets["HOME_LOCATION"]
WORK_LOCATION = secrets["WORK_LOCATION"]

app = Flask(__name__)
owm = OWM(OPENWEATHER_API_KEY)

def datentime_fetch():
    datentimevar = datetime.datetime.now()
    return datentimevar.strftime("%d/%m/%y %I:%M %p")

def geocode(address):
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": address, "key": GOOGLE_API_KEY}
    r = requests.get(url, params=params).json()
    loc = r["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]

def get_route():
    origin = geocode(HOME_LOCATION)
    dest = geocode(WORK_LOCATION)
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
        "origin": {"location": {"latLng": {"latitude": origin[0], "longitude": origin[1]}}},
        "destination": {"location": {"latLng": {"latitude": dest[0], "longitude": dest[1]}}},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    r = requests.post(url, headers=headers, json=body).json()
    route = r["routes"][0]
    leg = route["legs"][0]
    duration = int(leg["duration"].replace("s", "")) // 60
    static = int(route["staticDuration"].replace("s", "")) // 60
    distance = route["distanceMeters"] / 1000
    path = polyline.decode(route["polyline"]["encodedPolyline"])
    midpoint = ((origin[0] + dest[0]) / 2, (origin[1] + dest[1]) / 2)
    return {
        "duration": duration,
        "static": static,
        "distance": f"{distance:.1f} km",
        "path": path,
        "coords": {
            "Home": origin,
            "Midpoint": midpoint,
            "Work": dest
        }
    }

'''
def get_weather(lat, lon):
    mgr = owm.weather_manager()
    one_call = mgr.one_call(lat=lat, lon=lon)
    current = one_call.current
    temp = current.temperature("celsius")["temp"]
    desc = current.detailed_status.capitalize()
    precip = one_call.forecast_hourly[0].precipitation_probability if one_call.forecast_hourly else None
    return f"{temp:.1f}°C, {desc}" + (f", 🌧️ {precip * 100:.0f}% chance" if precip else "")
'''

def get_weather(lat, lon):
    mgr = owm.weather_manager()
    one_call = mgr.one_call(lat=lat, lon=lon)
    current = one_call.current
    temp = current.temperature("celsius")["temp"]
    desc = current.detailed_status.capitalize()
    hourly = one_call.forecast_hourly
    precip = hourly[0].precipitation_probability if hourly else None
    precip_text = f", 🌧️ {precip * 100:.0f}% chance" if precip is not None else ""
    return f"{temp:.1f}°C, {desc}{precip_text}"



def get_route_steps():
    origin = geocode(HOME_LOCATION)
    dest = geocode(WORK_LOCATION)
    url = "https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": f"{origin[0]},{origin[1]}",
        "destination": f"{dest[0]},{dest[1]}",
        "mode": "driving",
        "departure_time": "now",
        "key": GOOGLE_API_KEY
    }
    r = requests.get(url, params=params).json()
    leg = r["routes"][0]["legs"][0]
    steps = []
    color = "blue"
    for step in leg["steps"]:
        path = polyline.decode(step["polyline"]["points"])
        dur = step.get("duration", {}).get("value", 0)
        traf = step.get("duration_in_traffic", {}).get("value", dur)
        ratio = traf / dur if dur else 1
        color = "blue" if ratio < 1.1 else "orange" if ratio < 1.5 else "red"
        steps.append({"path": path, "color": color})
    midpoint = ((origin[0] + dest[0]) / 2, (origin[1] + dest[1]) / 2)
    return {
        "steps": steps,
        "coords": {
            "Home": origin,
            "Midpoint": midpoint,
            "Work": dest
        }
    }

def get_weather_icon(lat, lon):
    mgr = owm.weather_manager()
    one_call = mgr.one_call(lat=lat, lon=lon)
    current = one_call.current
    icon = current.weather_icon_name
    temp = current.temperature("celsius")["temp"]
    desc = current.detailed_status.capitalize()
    hourly = one_call.forecast_hourly
    precip = hourly[0].precipitation_probability if hourly else None
    precip_text = f"🌧️ {precip * 100:.0f}% chance" if precip is not None else ""
    return {
        "icon": f"https://openweathermap.org/img/wn/{icon}@2x.png",
        "label": f"{temp:.1f}°C\n {desc}\n{precip_text}"
    }

def get_weather_icon_8h_later(lat, lon):
    mgr = owm.weather_manager()
    one_call = mgr.one_call(lat=lat, lon=lon)
    hourly = one_call.forecast_hourly

    if len(hourly) >= 9:
        forecast = hourly[8]  # 8 hours later
        icon = forecast.weather_icon_name
        temp = forecast.temperature("celsius")["temp"]
        desc = forecast.detailed_status.capitalize()
        precip = forecast.precipitation_probability
        precip_text = f"🌧️ {precip * 100:.0f}% chance" if precip is not None else ""
        return {
            "icon": f"https://openweathermap.org/img/wn/{icon}@2x.png",
            "label": f"{temp:.1f}°C\n {desc}\n{precip_text}"
        }
    else:
        return {
            "icon": None,
            "label": "Forecast data for 8 hours later is unavailable."
        }



@app.route("/")
def index():
    route = get_route_steps()
    routecalc = get_route()
    datentime = datentime_fetch()
    weather = {
        name: get_weather_icon(*coords)
        for name, coords in route["coords"].items()
    }
    weatherfuture = {
        name: get_weather_icon_8h_later(*coords)
        for name, coords in route["coords"].items()
    }
    return render_template("index.html",
        datentime=datentime,
        route=route,
        routecalc=routecalc,
        weather=weather,
        weatherfuture=weatherfuture,
        google_api_key=GOOGLE_API_KEY
    )



'''
@app.route("/")
def index():
    route = get_route()
    weather = {
        name: get_weather(*coords)
        for name, coords in route["coords"].items()
    }
    return render_template("index.html",
        route=route,
        weather=weather,
        google_api_key=GOOGLE_API_KEY,
        home=HOME_LOCATION,
        work=WORK_LOCATION
    )
'''
@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')

if __name__ == "__main__":
    app.run(debug=True,host='0.0.0.0')
