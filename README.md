# Google Assistant Twilight Light Temperature/Brightness Automator
This project is a prototype that uses Google Assistant to automatically control the brightness Google Assistant connected lights during dawn and dusk.

The algorithm uses a sine function so that transitions start and end slowly, and are quicker half way between start/end of sunrise/sunset. This algorithm is likely inaccurate to how the light curve really works.

Due to the limit of 500 requests per day to the Google Assistant API, during dawn/dusk the lights will only be updated once per minute - so you may notice some slight colour/brightness changes.

## Set up project
* Install portaudio `apt install libportaudio2`
* Create a new Python 3.6+ virtual environment `python3 -m venv venv`
* Activate the virtual environment `source ./venv/bin/activate`
* Install the requirements `pip install -r requirements.txt`

## Setting up credentials
First follow the following two sections:-
* https://github.com/Melvin-Abraham/Google-Assistant-Unofficial-Desktop-Client/wiki/Setup-Authentication-for-Google-Assistant-Unofficial-Desktop-Client#device-registration
* https://github.com/Melvin-Abraham/Google-Assistant-Unofficial-Desktop-Client/wiki/Setup-Authentication-for-Google-Assistant-Unofficial-Desktop-Client#configure-consent-screen

Next copy your OAuth2 client secret json file in to the credentials directory of this repo and run:-
```
$ cd credentials
$ google-oauthlib-tool --save --headless --scope https://www.googleapis.com/auth/assistant-sdk-prototype --credentials ./credentials.json --client-secrets client_secret_whatever.json
```
# Set up local.py configuration
Next modify the local.py file to match your local settings, the `LATITUDE` and `LONGITUDE` should be as close to where your lights are located as possible - Google Maps can give you the GPS coordinates of your address if required.

Update the CITY/COUNTRY/TIMEZONE to match your location as well.

Finally make sure the `LIGHT_NAME` is correct for your light/light group. If, for example, you say `Hey Google, turn on the bedroom light` then the `LIGHT_NAME` is `bedroom light`.

It's important that the machine running the script correctly has the local timezone configured, and the time is synchronized (With NTP)
```
$ sudo dpkg-reconfigure tzdata
```

# Run the script
There is no systemd unit or daemon for this project yet - I've just been running it inside `tmux`.
```
$ tmux
$ source ./venv/bin/activate
$ python main.py
```