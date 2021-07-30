import asyncio
import datetime
import math
import queue
from tempfile import NamedTemporaryFile

import speech_recognition as sr
import timesched
from astral import LocationInfo
from astral.sun import sun
from assistant.pushtotalk import create_assistant

try:
    from local import *
except Exception as e:
    pass

tzinfo = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo

ASSISTANTS = queue.SimpleQueue()
SLEEP_SECONDS = 60


def run_command(query, need_response=False):
    try:
        assistant = ASSISTANTS.get_nowait()
    except queue.Empty:
        assistant = create_assistant('test', 'test', credentials='./credentials/credentials.json')

    try:
        with NamedTemporaryFile(suffix='.wav') as f:
            assistant.assist(query, f.name)

            if not need_response:
                return None

            with sr.AudioFile(f.name) as source:
                r = sr.Recognizer()
                audio_data = r.record(source)
                return r.recognize_google(audio_data)
    finally:
        ASSISTANTS.put(assistant)


def get_ratio(start, end, now):
    a = start.timestamp()
    b = end.timestamp()
    now = now.timestamp()

    invert = start > end

    start = min(a, b)
    end = max(a, b)

    now = min(now, end)

    dur = end - start
    now = now - start

    rads = now / dur * math.radians(180) + math.radians(90 if invert else 270)

    return 0.5 + (math.sin(rads) / 2)


def get_light_temperature(start, end, now):
    min_temp = 1000
    max_temp = 10000

    r = get_ratio(start, end, now)

    return int((max_temp - min_temp) * r + min_temp)


def get_light_brightness(start, end, now):
    min_bright = 1
    max_bright = 100

    r = get_ratio(start, end, now)

    return int((max_bright - min_bright) * r + min_bright)


async def set_brightness(brightness):
    print(
        datetime.datetime.now(tzinfo),
        "Setting brightness:    ", brightness, " - ",
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: run_command(f"set the {LIGHT_NAME} to {brightness}%", True)
        )
    )


async def set_temp(temp):
    print(
        datetime.datetime.now(tzinfo),
        "Setting temperature:   ", temp, " - ",
        await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: run_command(f"set the {LIGHT_NAME} to {temp}k", True)
        )
    )


async def perform_light_adjust(start, end, now):
    brightness = get_light_brightness(start, end, now)
    temp = get_light_temperature(start, end, now)

    consumer_task = asyncio.ensure_future(set_brightness(brightness))
    producer_task = asyncio.ensure_future(set_temp(temp))

    await asyncio.wait(
        [consumer_task, producer_task],
        return_when=asyncio.ALL_COMPLETED,
    )


async def run_light(start, end):
    now = min(start, end)
    while now < max(start, end):
        await asyncio.sleep(SLEEP_SECONDS)

        now = datetime.datetime.now(tzinfo)
        await perform_light_adjust(start, end, now)

    # Set the final state
    await perform_light_adjust(start, end, now)


def run(start, end):
    if end > start:
        print("Starting sunrise transition...")
    else:
        print("Starting sunset transition...")
        
    asyncio.get_event_loop().run_until_complete(run_light(start, end))

    print("Transition complete.")


while True:
    city = LocationInfo(CITY, COUNTRY, TIMEZONE, LATITUDE, LONGITUDE)

    sun_today = sun(
        city.observer,
        date=datetime.datetime.today(),
        tzinfo=tzinfo
    )

    sun_tomorrow = sun(
        city.observer,
        date=datetime.datetime.today() + datetime.timedelta(days=1),
        tzinfo=tzinfo
    )

    _sun = {}

    now = datetime.datetime.now(tzinfo)
    _sun["dawn"] = sun_today["dawn"] if now < sun_today["dawn"] else sun_tomorrow["dawn"]
    _sun["sunrise"] = sun_today["sunrise"] if now < sun_today["dawn"] else sun_tomorrow["sunrise"]

    _sun["sunset"] = sun_today["sunset"] if now < sun_today["sunset"] else sun_tomorrow["sunset"]
    _sun["dusk"] = sun_today["dusk"] if now < sun_today["sunset"] else sun_tomorrow["dusk"]

    print((
        f'Next Dawn:    {_sun["dawn"]}\n'
        f'Next Sunrise: {_sun["sunrise"]}\n'
        '\n'
        f'Next Sunset:  {_sun["sunset"]}\n'
        f'Next Dusk:    {_sun["dusk"]}\n'
    ))

    s = timesched.Scheduler()
    s.oneshot(_sun["dawn"].time(), 0, run, _sun["dawn"], _sun["sunrise"])
    s.oneshot(_sun["sunset"].time(), 0, run, _sun["dusk"], _sun["sunset"])

    s.run()
