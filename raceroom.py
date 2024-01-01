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
CAR_IDS = ['class-1703']
FINISHED_CLASSES = []
COUNT = 1500
MAX_ERRORS = 100
SLEEP_TIME = MAX_ERRORS / 100
DRIVER_NAMES = ['Mathieu Blanchard', 'Florian Gauthier']



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
                display_error('file', car_id, track_id)
            else:
                sleep(SLEEP_TIME)
                errors += 1


def display_error(error, car_id, track_id):
    car_name = get_car_name(GAME_DATA, car_id)
    track_name = get_track_name(GAME_DATA, track_id)
    raise Exception(f'Too many errors while getting the {error} | car = {car_name} | track = {track_name}')


def get_data(track_id, car_id):
    errors = 0
    while True:
        if errors > MAX_ERRORS:
            display_error('data', car_id, track_id)
        wr, tot = None, 0
        data = []
        for i in range(len(DRIVER_NAMES)):
            data.append([0, 0])
        file = get_json(track_id, car_id)
        context = file['context']['c']['results']
        if len(context) == 0:
            if track_id == 10274 or car_id not in FINISHED_CLASSES:
                return 0, 0, data
            else:
                sleep(SLEEP_TIME)
                errors += 1
                continue
        wr = context[0]['laptime']
        wr = wr.split('s')[0].split('m ')
        wr = get_lap_time_sec(wr)
        for c in context:
            tot += 1
            for i in range(len(DRIVER_NAMES)):
                if c['driver']['name'] == DRIVER_NAMES[i]:
                    lap_time = c['laptime'].split('s')[0].split('m ')
                    lap_time = get_lap_time_sec(lap_time)
                    rank = tot
                    data[i] = [lap_time, rank]
        if data[0] == [0, 0] and car_id in FINISHED_CLASSES:
            sleep(SLEEP_TIME)
            errors += 1
            continue
        else:
            return wr, tot, data


def save_data(car_id):
    car_name = get_car_name(GAME_DATA, car_id)
    credentials = get_credentials()
    service = build('sheets', 'v4', credentials=credentials)
    sheets = service.spreadsheets()
    for i in range(len(DRIVER_NAMES)):
        letter = chr(12 * i + 65)
        sheets.values().update(spreadsheetId=SPREADSHEET_ID, range=f'{car_name}!{letter}2',
                               valueInputOption='USER_ENTERED', body={'values': [HEADER]}).execute()
    n = []
    recommended_track = []
    for i in range(len(DRIVER_NAMES)):
        n.append(1)
        recommended_track.append(['', 0, 0])
    for t in TRACKS:
        sleep(SLEEP_TIME)
        wr, tot, data = get_data(t[1], car_id)
        if t[1] != 10274:
            print('Car: ' + car_name + ' | Track: ' + t[0])
            for i in range(len(DRIVER_NAMES)):
                values = [n[i]] + [t[0]] + [wr] + data[i] + [tot]
                letter = chr(12 * i + 65)
                if data[i] != [0, 0]:
                    sheets.values().update(spreadsheetId=SPREADSHEET_ID, range=f'{car_name}!{letter}{n[i] + 2}',
                                           valueInputOption='USER_ENTERED', body={'values': [values]}).execute()
                    print('Driver: ' + DRIVER_NAMES[i] + ' saved successfully')
                    n[i] += 1
                else:
                    if wr != 0:
                        float_wr = float(wr.replace(',', '.'))
                    else:
                        float_wr = 0
                    if tot >= 5 and (recommended_track[i][1] == 0 or recommended_track[i][1] > float_wr):
                        recommended_track[i] = [t[0]] + [float_wr, tot]
                        print(f'{recommended_track[i]} {DRIVER_NAMES[i]}')
    for i in range(len(DRIVER_NAMES)):
        if recommended_track[i][1] != 0:
            print(f'Recommended track for {DRIVER_NAMES[i]} : \n'
                  f'Name : {recommended_track[i][0]}\n'
                  f'World Record : {recommended_track[i][1]}\n'
                  f'Total players : {recommended_track[i][2]}\n')


def save_all_cars():
    for car in CAR_IDS:
        save_data(car)


def main():
    save_all_cars()


if __name__ == '__main__':
    main()
