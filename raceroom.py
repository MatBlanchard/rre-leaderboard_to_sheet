import os
from time import sleep
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import json
import requests


def get_game_data():
    with open(RACEROOM_DIRECTORY + 'Game/GameData/General/r3e-data.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def get_all_tracks(json_file):
    results = {}
    track_list = json_file['tracks']
    for i in track_list:
        track_name = track_list[i]['Name']
        for j in track_list[i]['layouts']:
            results.update({track_name + " - " + j['Name']: j['Id']})
    return sorted(results.items(), key=lambda t: t[0])


SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = '1PmMP5DASYRGCNKJcykAJTsy_h7NlmBwZ0XiGm1z1MGI'
RACEROOM_DIRECTORY = 'D:/SteamLibrary/steamapps/common/raceroom racing experience/'
GAME_DATA = get_game_data()
TRACKS = get_all_tracks(GAME_DATA)
HEADER = ['N°', 'Nom du circuit', 'World record', 'Mon temps', 'Classement', 'Total']
CAR_IDS = ['class-1703', 8257, 11536, 5818, 10914, 5051, 11342]
FINISHED_CLASSES = [10914, 5051, 11342]
COUNT = 1500
MAX_ERRORS = 30
SLEEP_TIME = 0.2


def get_credentials():
    credentials = None
    if os.path.exists('token.json'):
        credentials = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            credentials = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(credentials.to_json())
    return credentials


def get_lap_time_sec(lap_time):
    if len(lap_time) == 2:
        return '{:.3f}'.format(float(lap_time[0]) * 60 + float(lap_time[1])).replace('.', ',')
    else:
        return '{:.3f}'.format(float(lap_time[0])).replace('.', ',')


def get_car_name(json_file, car_id):
    if type(car_id) == str:
        car_id = car_id.split('class-')[1]
        return json_file['classes'][car_id]['Name']
    else:
        return json_file['cars'][str(car_id)]['Name']


def get_track_name(json_file, track_id):
    layout = json_file['layouts'][str(track_id)]
    track = json_file['tracks'][str(layout['Track'])]['Name']
    layout_name = layout['Name']
    return f'{track} - {layout_name}'


def get_json(track_id, car_id):
    errors = 0
    while True:
        url = 'https://game.raceroom.com/leaderboard/listing/0?start=0&count=' + \
              str(COUNT) + '&track=' + str(track_id) + '&car_class=' + str(car_id)
        page = requests.get(url, headers={'X-Requested-With': 'XMLHttpRequest'})
        if page.ok:
            return json.loads(page.text)
        else:
            if errors > MAX_ERRORS:
                car_name = get_car_name(GAME_DATA, car_id)
                track_name = get_track_name(GAME_DATA, track_id)
                raise Exception(f'Too many errors while getting the file | car = {car_name} | track = {track_name}')
            else:
                sleep(SLEEP_TIME)
                errors += 1


def get_data(track_id, car_id):
    errors = 0
    while True:
        if errors > MAX_ERRORS:
            car_name = get_car_name(GAME_DATA, car_id)
            track_name = get_track_name(GAME_DATA, track_id)
            raise Exception(f'Too many errors while getting the data | car = {car_name} | track = {track_name}')
        wr, lap_time, rank, i = None, None, None, 0
        file = get_json(track_id, car_id)
        context = file['context']['c']['results']
        if len(context) == 0:
            if track_id == 10274 or car_id not in FINISHED_CLASSES:
                return []
            else:
                sleep(SLEEP_TIME)
                errors += 1
                continue
        wr = context[0]['laptime']
        wr = wr.split('s')[0].split('m ')
        wr = get_lap_time_sec(wr)
        for c in context:
            i += 1
            if c['driver']['name'] == 'Mathieu Blanchard':
                lap_time = c['laptime'].split('s')[0].split('m ')
                lap_time = get_lap_time_sec(lap_time)
                rank = i
        if not rank:
            if car_id in FINISHED_CLASSES:
                sleep(SLEEP_TIME)
                errors += 1
                continue
            else:
                return []
        else:
            return [wr, lap_time, rank, i]


def save_data(car_id):
    car_name = get_car_name(GAME_DATA, car_id)
    credentials = get_credentials()
    service = build('sheets', 'v4', credentials=credentials)
    sheets = service.spreadsheets()
    sheets.values().update(spreadsheetId=SPREADSHEET_ID, range=f'{car_name}!A1',
                           valueInputOption='USER_ENTERED', body={'values': [HEADER]}).execute()
    n = 1
    for t in TRACKS:
        data = [n] + [t[0]] + get_data(t[1], car_id)
        if len(data) == len(HEADER):
            sheets.values().update(spreadsheetId=SPREADSHEET_ID, range=f'{car_name}!A{n + 1}',
                                   valueInputOption='USER_ENTERED', body={'values': [data]}).execute()
            print("Car: " + car_name + " | Track: " + t[0] + " saved successfully")
            n += 1
            sleep(1)


def save_all_cars():
    for car in CAR_IDS:
        save_data(car)


def main():
    save_all_cars()


if __name__ == '__main__':
    main()
