"""Fieldwatch: Flask + SQLite backend.

Run: pip install -r requirements.txt, then python app.py.
On first launch, the terminal asks you to create an administrator password.
The SQLite database is created automatically beside this file.

Optional environment variables (no credentials are included in this source):
GOOGLE_GEOCODING_KEY - server-side Google Geocoding key.
FIREBASE_CONFIG - Firebase web app configuration as a JSON string.
FCM_VAPID_KEY - Firebase browser push public key.
FCM_SERVICE_ACCOUNT - Firebase service account JSON (keep it private).
SITE_ORIGIN - public HTTPS origin, used in notification links.
COOKIE_SECURE=1 - use secure cookies when deployed behind HTTPS.
ADMIN_PASSWORD - optional initial administrator password instead of a prompt.
"""
import getpass
import hashlib
import json
import math
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
from flask import Flask, g, jsonify, render_template, request, send_from_directory, session
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

ROOT = Path(__file__).resolve().parent
# Read credentials before configuring the server; shell values take precedence.
load_dotenv(ROOT / '.env', encoding='utf-8-sig')
app = Flask(__name__, template_folder=str(ROOT / 'templates'), static_folder=str(ROOT / 'static'))
app.config.update(
    DATABASE=str(ROOT / 'fieldwatch.db'),
    MAX_CONTENT_LENGTH=64 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE') == '1',
    PERMANENT_SESSION_LIFETIME=timedelta(hours=24),
)

# The factual state/LGA data is embedded to avoid a separate configuration file.
# Source: https://gist.github.com/devhammed/0bb9eeac9ff22c895100d072f489dc98
STATES = [{'state': 'Adamawa',
  'alias': 'adamawa',
  'lgas': ['Demsa',
           'Fufure',
           'Ganye',
           'Gayuk',
           'Gombi',
           'Grie',
           'Hong',
           'Jada',
           'Larmurde',
           'Madagali',
           'Maiha',
           'Mayo Belwa',
           'Michika',
           'Mubi North',
           'Mubi South',
           'Numan',
           'Shelleng',
           'Song',
           'Toungo',
           'Yola North',
           'Yola South']},
 {'state': 'Akwa Ibom',
  'alias': 'akwa_ibom',
  'lgas': ['Abak',
           'Eastern Obolo',
           'Eket',
           'Esit Eket',
           'Essien Udim',
           'Etim Ekpo',
           'Etinan',
           'Ibeno',
           'Ibesikpo Asutan',
           'Ibiono-Ibom',
           'Ikot Abasi',
           'Ika',
           'Ikono',
           'Ikot Ekpene',
           'Ini',
           'Mkpat-Enin',
           'Itu',
           'Mbo',
           'Nsit-Atai',
           'Nsit-Ibom',
           'Nsit-Ubium',
           'Obot Akara',
           'Okobo',
           'Onna',
           'Oron',
           'Udung-Uko',
           'Ukanafun',
           'Oruk Anam',
           'Uruan',
           'Urue-Offong/Oruko',
           'Uyo']},
 {'state': 'Anambra',
  'alias': 'anambra',
  'lgas': ['Aguata',
           'Anambra East',
           'Anaocha',
           'Awka North',
           'Anambra West',
           'Awka South',
           'Ayamelum',
           'Dunukofia',
           'Ekwusigo',
           'Idemili North',
           'Idemili South',
           'Ihiala',
           'Njikoka',
           'Nnewi North',
           'Nnewi South',
           'Ogbaru',
           'Onitsha North',
           'Onitsha South',
           'Orumba North',
           'Orumba South',
           'Oyi']},
 {'state': 'Ogun',
  'alias': 'ogun',
  'lgas': ['Abeokuta North',
           'Abeokuta South',
           'Ado-Odo/Ota',
           'Egbado North',
           'Ewekoro',
           'Egbado South',
           'Ijebu North',
           'Ijebu East',
           'Ifo',
           'Ijebu Ode',
           'Ijebu North East',
           'Imeko Afon',
           'Ikenne',
           'Ipokia',
           'Odeda',
           'Obafemi Owode',
           'Odogbolu',
           'Remo North',
           'Ogun Waterside',
           'Shagamu']},
 {'state': 'Ondo',
  'alias': 'ondo',
  'lgas': ['Akoko North-East',
           'Akoko North-West',
           'Akoko South-West',
           'Akoko South-East',
           'Akure North',
           'Akure South',
           'Ese Odo',
           'Idanre',
           'Ifedore',
           'Ilaje',
           'Irele',
           'Ile Oluji/Okeigbo',
           'Odigbo',
           'Okitipupa',
           'Ondo West',
           'Ose',
           'Ondo East',
           'Owo']},
 {'state': 'Rivers',
  'alias': 'rivers',
  'lgas': ['Abua/Odual',
           'Ahoada East',
           'Ahoada West',
           'Andoni',
           'Akuku-Toru',
           'Asari-Toru',
           'Bonny',
           'Degema',
           'Emuoha',
           'Eleme',
           'Ikwerre',
           'Etche',
           'Gokana',
           'Khana',
           'Obio/Akpor',
           'Ogba/Egbema/Ndoni',
           'Ogu/Bolo',
           'Okrika',
           'Omuma',
           'Opobo/Nkoro',
           'Oyigbo',
           'Port Harcourt',
           'Tai']},
 {'state': 'Bauchi',
  'alias': 'bauchi',
  'lgas': ['Alkaleri',
           'Bauchi',
           'Bogoro',
           'Damban',
           'Darazo',
           'Dass',
           'Gamawa',
           'Ganjuwa',
           'Giade',
           'Itas/Gadau',
           "Jama'are",
           'Katagum',
           'Kirfi',
           'Misau',
           'Ningi',
           'Shira',
           'Tafawa Balewa',
           'Toro',
           'Warji',
           'Zaki']},
 {'state': 'Benue',
  'alias': 'benue',
  'lgas': ['Agatu',
           'Apa',
           'Ado',
           'Buruku',
           'Gboko',
           'Guma',
           'Gwer East',
           'Gwer West',
           'Katsina-Ala',
           'Konshisha',
           'Kwande',
           'Logo',
           'Makurdi',
           'Obi',
           'Ogbadibo',
           'Ohimini',
           'Oju',
           'Okpokwu',
           'Oturkpo',
           'Tarka',
           'Ukum',
           'Ushongo',
           'Vandeikya']},
 {'state': 'Borno',
  'alias': 'borno',
  'lgas': ['Abadam',
           'Askira/Uba',
           'Bama',
           'Bayo',
           'Biu',
           'Chibok',
           'Damboa',
           'Dikwa',
           'Guzamala',
           'Gubio',
           'Hawul',
           'Gwoza',
           'Jere',
           'Kaga',
           'Kala/Balge',
           'Konduga',
           'Kukawa',
           'Kwaya Kusar',
           'Mafa',
           'Magumeri',
           'Maiduguri',
           'Mobbar',
           'Marte',
           'Monguno',
           'Ngala',
           'Nganzai',
           'Shani']},
 {'state': 'Bayelsa',
  'alias': 'bayelsa',
  'lgas': ['Brass',
           'Ekeremor',
           'Kolokuma/Opokuma',
           'Nembe',
           'Ogbia',
           'Sagbama',
           'Southern Ijaw',
           'Yenagoa']},
 {'state': 'Cross River',
  'alias': 'cross_river',
  'lgas': ['Abi',
           'Akamkpa',
           'Akpabuyo',
           'Bakassi',
           'Bekwarra',
           'Biase',
           'Boki',
           'Calabar Municipal',
           'Calabar South',
           'Etung',
           'Ikom',
           'Obanliku',
           'Obubra',
           'Obudu',
           'Odukpani',
           'Ogoja',
           'Yakuur',
           'Yala']},
 {'state': 'Delta',
  'alias': 'delta',
  'lgas': ['Aniocha North',
           'Aniocha South',
           'Bomadi',
           'Burutu',
           'Ethiope West',
           'Ethiope East',
           'Ika North East',
           'Ika South',
           'Isoko North',
           'Isoko South',
           'Ndokwa East',
           'Ndokwa West',
           'Okpe',
           'Oshimili North',
           'Oshimili South',
           'Patani',
           'Sapele',
           'Udu',
           'Ughelli North',
           'Ukwuani',
           'Ughelli South',
           'Uvwie',
           'Warri North',
           'Warri South',
           'Warri South West']},
 {'state': 'Ebonyi',
  'alias': 'ebonyi',
  'lgas': ['Abakaliki',
           'Afikpo North',
           'Ebonyi',
           'Afikpo South',
           'Ezza North',
           'Ikwo',
           'Ezza South',
           'Ivo',
           'Ishielu',
           'Izzi',
           'Ohaozara',
           'Ohaukwu',
           'Onicha']},
 {'state': 'Edo',
  'alias': 'edo',
  'lgas': ['Akoko-Edo',
           'Egor',
           'Esan Central',
           'Esan North-East',
           'Esan South-East',
           'Esan West',
           'Etsako Central',
           'Etsako East',
           'Etsako West',
           'Igueben',
           'Ikpoba Okha',
           'Orhionmwon',
           'Oredo',
           'Ovia North-East',
           'Ovia South-West',
           'Owan East',
           'Owan West',
           'Uhunmwonde']},
 {'state': 'Ekiti',
  'alias': 'ekiti',
  'lgas': ['Ado Ekiti',
           'Efon',
           'Ekiti East',
           'Ekiti South-West',
           'Ekiti West',
           'Emure',
           'Gbonyin',
           'Ido Osi',
           'Ijero',
           'Ikere',
           'Ilejemeje',
           'Irepodun/Ifelodun',
           'Ikole',
           'Ise/Orun',
           'Moba',
           'Oye']},
 {'state': 'Enugu',
  'alias': 'enugu',
  'lgas': ['Awgu',
           'Aninri',
           'Enugu East',
           'Enugu North',
           'Ezeagu',
           'Enugu South',
           'Igbo Etiti',
           'Igbo Eze North',
           'Igbo Eze South',
           'Isi Uzo',
           'Nkanu East',
           'Nkanu West',
           'Nsukka',
           'Udenu',
           'Oji River',
           'Uzo Uwani',
           'Udi']},
 {'state': 'Federal Capital Territory',
  'alias': 'abuja',
  'lgas': ['Abaji', 'Bwari', 'Gwagwalada', 'Kuje', 'Kwali', 'Municipal Area Council']},
 {'state': 'Gombe',
  'alias': 'gombe',
  'lgas': ['Akko',
           'Balanga',
           'Billiri',
           'Dukku',
           'Funakaye',
           'Gombe',
           'Kaltungo',
           'Kwami',
           'Nafada',
           'Shongom',
           'Yamaltu/Deba']},
 {'state': 'Jigawa',
  'alias': 'jigawa',
  'lgas': ['Auyo',
           'Babura',
           'Buji',
           'Biriniwa',
           'Birnin Kudu',
           'Dutse',
           'Gagarawa',
           'Garki',
           'Gumel',
           'Guri',
           'Gwaram',
           'Gwiwa',
           'Hadejia',
           'Jahun',
           'Kafin Hausa',
           'Kazaure',
           'Kiri Kasama',
           'Kiyawa',
           'Kaugama',
           'Maigatari',
           'Malam Madori',
           'Miga',
           'Sule Tankarkar',
           'Roni',
           'Ringim',
           'Yankwashi',
           'Taura']},
 {'state': 'Oyo',
  'alias': 'oyo',
  'lgas': ['Afijio',
           'Akinyele',
           'Atiba',
           'Atisbo',
           'Egbeda',
           'Ibadan North',
           'Ibadan North-East',
           'Ibadan North-West',
           'Ibadan South-East',
           'Ibarapa Central',
           'Ibadan South-West',
           'Ibarapa East',
           'Ido',
           'Ibarapa North',
           'Irepo',
           'Iseyin',
           'Itesiwaju',
           'Iwajowa',
           'Kajola',
           'Lagelu',
           'Ogbomosho North',
           'Ogbomosho South',
           'Ogo Oluwa',
           'Olorunsogo',
           'Oluyole',
           'Ona Ara',
           'Orelope',
           'Ori Ire',
           'Oyo',
           'Oyo East',
           'Saki East',
           'Saki West',
           'Surulere Oyo State']},
 {'state': 'Imo',
  'alias': 'imo',
  'lgas': ['Aboh Mbaise',
           'Ahiazu Mbaise',
           'Ehime Mbano',
           'Ezinihitte',
           'Ideato North',
           'Ideato South',
           'Ihitte/Uboma',
           'Ikeduru',
           'Isiala Mbano',
           'Mbaitoli',
           'Isu',
           'Ngor Okpala',
           'Njaba',
           'Nkwerre',
           'Nwangele',
           'Obowo',
           'Oguta',
           'Ohaji/Egbema',
           'Okigwe',
           'Orlu',
           'Orsu',
           'Oru East',
           'Oru West',
           'Owerri Municipal',
           'Owerri North',
           'Unuimo',
           'Owerri West']},
 {'state': 'Kaduna',
  'alias': 'kaduna',
  'lgas': ['Birnin Gwari',
           'Chikun',
           'Giwa',
           'Ikara',
           'Igabi',
           'Jaba',
           "Jema'a",
           'Kachia',
           'Kaduna North',
           'Kaduna South',
           'Kagarko',
           'Kajuru',
           'Kaura',
           'Kauru',
           'Kubau',
           'Kudan',
           'Lere',
           'Makarfi',
           'Sabon Gari',
           'Sanga',
           'Soba',
           'Zangon Kataf',
           'Zaria']},
 {'state': 'Kebbi',
  'alias': 'kebbi',
  'lgas': ['Aleiro',
           'Argungu',
           'Arewa Dandi',
           'Augie',
           'Bagudo',
           'Birnin Kebbi',
           'Bunza',
           'Dandi',
           'Fakai',
           'Gwandu',
           'Jega',
           'Kalgo',
           'Koko/Besse',
           'Maiyama',
           'Ngaski',
           'Shanga',
           'Suru',
           'Sakaba',
           'Wasagu/Danko',
           'Yauri',
           'Zuru']},
 {'state': 'Kano',
  'alias': 'kano',
  'lgas': ['Ajingi',
           'Albasu',
           'Bagwai',
           'Bebeji',
           'Bichi',
           'Bunkure',
           'Dala',
           'Dambatta',
           'Dawakin Kudu',
           'Dawakin Tofa',
           'Doguwa',
           'Fagge',
           'Gabasawa',
           'Garko',
           'Garun Mallam',
           'Gezawa',
           'Gaya',
           'Gwale',
           'Gwarzo',
           'Kabo',
           'Kano Municipal',
           'Karaye',
           'Kibiya',
           'Kiru',
           'Kumbotso',
           'Kunchi',
           'Kura',
           'Madobi',
           'Makoda',
           'Minjibir',
           'Nasarawa',
           'Rano',
           'Rimin Gado',
           'Rogo',
           'Shanono',
           'Takai',
           'Sumaila',
           'Tarauni',
           'Tofa',
           'Tsanyawa',
           'Tudun Wada',
           'Ungogo',
           'Warawa',
           'Wudil']},
 {'state': 'Kogi',
  'alias': 'kogi',
  'lgas': ['Ajaokuta',
           'Adavi',
           'Ankpa',
           'Bassa',
           'Dekina',
           'Ibaji',
           'Idah',
           'Igalamela Odolu',
           'Ijumu',
           'Kogi',
           'Kabba/Bunu',
           'Lokoja',
           'Ofu',
           'Mopa Muro',
           'Ogori/Magongo',
           'Okehi',
           'Okene',
           'Olamaboro',
           'Omala',
           'Yagba East',
           'Yagba West']},
 {'state': 'Osun',
  'alias': 'osun',
  'lgas': ['Aiyedire',
           'Atakunmosa West',
           'Atakunmosa East',
           'Aiyedaade',
           'Boluwaduro',
           'Boripe',
           'Ife East',
           'Ede South',
           'Ife North',
           'Ede North',
           'Ife South',
           'Ejigbo',
           'Ife Central',
           'Ifedayo',
           'Egbedore',
           'Ila',
           'Ifelodun',
           'Ilesa East',
           'Ilesa West',
           'Irepodun',
           'Irewole',
           'Isokan',
           'Iwo',
           'Obokun',
           'Odo Otin',
           'Ola Oluwa',
           'Olorunda',
           'Oriade',
           'Orolu',
           'Osogbo']},
 {'state': 'Sokoto',
  'alias': 'sokoto',
  'lgas': ['Gudu',
           'Gwadabawa',
           'Illela',
           'Isa',
           'Kebbe',
           'Kware',
           'Rabah',
           'Sabon Birni',
           'Shagari',
           'Silame',
           'Sokoto North',
           'Sokoto South',
           'Tambuwal',
           'Tangaza',
           'Tureta',
           'Wamako',
           'Wurno',
           'Yabo',
           'Binji',
           'Bodinga',
           'Dange Shuni',
           'Goronyo',
           'Gada']},
 {'state': 'Plateau',
  'alias': 'plateau',
  'lgas': ['Bokkos',
           'Barkin Ladi',
           'Bassa',
           'Jos East',
           'Jos North',
           'Jos South',
           'Kanam',
           'Kanke',
           'Langtang South',
           'Langtang North',
           'Mangu',
           'Mikang',
           'Pankshin',
           "Qua'an Pan",
           'Riyom',
           'Shendam',
           'Wase']},
 {'state': 'Taraba',
  'alias': 'taraba',
  'lgas': ['Ardo Kola',
           'Bali',
           'Donga',
           'Gashaka',
           'Gassol',
           'Ibi',
           'Jalingo',
           'Karim Lamido',
           'Kumi',
           'Lau',
           'Sardauna',
           'Takum',
           'Ussa',
           'Wukari',
           'Yorro',
           'Zing']},
 {'state': 'Yobe',
  'alias': 'yobe',
  'lgas': ['Bade',
           'Bursari',
           'Damaturu',
           'Fika',
           'Fune',
           'Geidam',
           'Gujba',
           'Gulani',
           'Jakusko',
           'Karasuwa',
           'Machina',
           'Nangere',
           'Nguru',
           'Potiskum',
           'Tarmuwa',
           'Yunusari',
           'Yusufari']},
 {'state': 'Zamfara',
  'alias': 'zamfara',
  'lgas': ['Anka',
           'Birnin Magaji/Kiyaw',
           'Bakura',
           'Bukkuyum',
           'Bungudu',
           'Gummi',
           'Gusau',
           'Kaura Namoda',
           'Maradun',
           'Shinkafi',
           'Maru',
           'Talata Mafara',
           'Tsafe',
           'Zurmi']},
 {'state': 'Lagos',
  'alias': 'lagos',
  'lgas': ['Agege',
           'Ajeromi-Ifelodun',
           'Alimosho',
           'Amuwo-Odofin',
           'Badagry',
           'Apapa',
           'Epe',
           'Eti Osa',
           'Ibeju-Lekki',
           'Ifako-Ijaiye',
           'Ikeja',
           'Ikorodu',
           'Kosofe',
           'Lagos Island',
           'Mushin',
           'Lagos Mainland',
           'Ojo',
           'Oshodi-Isolo',
           'Shomolu',
           'Surulere Lagos State']},
 {'state': 'Katsina',
  'alias': 'katsina',
  'lgas': ['Bakori',
           'Batagarawa',
           'Batsari',
           'Baure',
           'Bindawa',
           'Charanchi',
           'Danja',
           'Dandume',
           'Dan Musa',
           'Daura',
           'Dutsi',
           'Dutsin Ma',
           'Faskari',
           'Funtua',
           'Ingawa',
           'Jibia',
           'Kafur',
           'Kaita',
           'Kankara',
           'Kankia',
           'Katsina',
           'Kurfi',
           'Kusada',
           "Mai'Adua",
           'Malumfashi',
           'Mani',
           'Mashi',
           'Matazu',
           'Musawa',
           'Rimi',
           'Sabuwa',
           'Safana',
           'Sandamu',
           'Zango']},
 {'state': 'Kwara',
  'alias': 'kwara',
  'lgas': ['Asa',
           'Baruten',
           'Edu',
           'Ilorin East',
           'Ifelodun',
           'Ilorin South',
           'Ekiti Kwara State',
           'Ilorin West',
           'Irepodun',
           'Isin',
           'Kaiama',
           'Moro',
           'Offa',
           'Oke Ero',
           'Oyun',
           'Pategi']},
 {'state': 'Nasarawa',
  'alias': 'nasarawa',
  'lgas': ['Akwanga',
           'Awe',
           'Doma',
           'Karu',
           'Keana',
           'Keffi',
           'Lafia',
           'Kokona',
           'Nasarawa Egon',
           'Nasarawa',
           'Obi',
           'Toto',
           'Wamba']},
 {'state': 'Niger',
  'alias': 'niger',
  'lgas': ['Agaie',
           'Agwara',
           'Bida',
           'Borgu',
           'Bosso',
           'Chanchaga',
           'Edati',
           'Gbako',
           'Gurara',
           'Katcha',
           'Kontagora',
           'Lapai',
           'Lavun',
           'Mariga',
           'Magama',
           'Mokwa',
           'Mashegu',
           'Moya',
           'Paikoro',
           'Rafi',
           'Rijau',
           'Shiroro',
           'Suleja',
           'Tafa',
           'Wushishi']},
 {'state': 'Abia',
  'alias': 'abia',
  'lgas': ['Aba North',
           'Arochukwu',
           'Aba South',
           'Bende',
           'Isiala Ngwa North',
           'Ikwuano',
           'Isiala Ngwa South',
           'Isuikwuato',
           'Obi Ngwa',
           'Ohafia',
           'Osisioma',
           'Ugwunagbo',
           'Ukwa East',
           'Ukwa West',
           'Umuahia North',
           'Umuahia South',
           'Umu Nneochi']}]
INCIDENT_TYPES = ['Developing dispute', 'Threat or intimidation', 'Crop damage',
                  'Blocked access route', 'Water or grazing dispute', 'Violence or attack', 'Other']


def database():
    """One connection per request; all user values are bound as SQL parameters."""
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'], timeout=20)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db


@app.teardown_appcontext
def close_database(_error):
    connection = g.pop('db', None)
    if connection is not None:
        connection.close()


def rows(sql, args=()):
    return [dict(row) for row in database().execute(sql, args).fetchall()]


def one(sql, args=()):
    row = database().execute(sql, args).fetchone()
    return dict(row) if row else None


def write(sql, args=()):
    cursor = database().execute(sql, args)
    database().commit()
    return cursor


def initialise_database():
    """Create the small application schema automatically on a fresh installation."""
    database().executescript('''
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL, state TEXT NOT NULL, lga TEXT NOT NULL,
            community TEXT NOT NULL, preference TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', phone_verified INTEGER NOT NULL DEFAULT 0,
            lat REAL NOT NULL, lng REAL NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS communities (
            id TEXT PRIMARY KEY, state TEXT NOT NULL, lga TEXT NOT NULL, name TEXT NOT NULL,
            UNIQUE(state,lga,name));
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, farm_id TEXT,
            type TEXT NOT NULL, description TEXT NOT NULL, community TEXT NOT NULL,
            lat REAL NOT NULL, lng REAL NOT NULL, observed TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'submitted', mediator TEXT NOT NULL DEFAULT '',
            outcome TEXT NOT NULL DEFAULT '', created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY, report_id TEXT NOT NULL REFERENCES reports(id),
            status TEXT NOT NULL, note TEXT NOT NULL, created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
            report_id TEXT NOT NULL REFERENCES reports(id), message TEXT NOT NULL,
            channel TEXT NOT NULL, status TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '',
            created TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS push_tokens (
            token TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS attempts (
            key TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
        CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status);
        CREATE INDEX IF NOT EXISTS idx_notices_user ON notifications(user_id,created);
        CREATE INDEX IF NOT EXISTS idx_tokens_user ON push_tokens(user_id);
        CREATE INDEX IF NOT EXISTS idx_events_report ON events(report_id);
    ''')
    # Preserve older database columns for compatibility; delivery is now push-only.
    write("UPDATE users SET preference='push' WHERE preference!='push'")
    # Keep the session-signing secret stable across restarts, outside the source code.
    saved = one("SELECT value FROM settings WHERE key='session_secret'")
    if not saved:
        write('INSERT INTO settings(key,value) VALUES(?,?)', ('session_secret', secrets.token_hex(32)))
        saved = one("SELECT value FROM settings WHERE key='session_secret'")
    app.secret_key = saved['value']
    initial_password = os.getenv('ADMIN_PASSWORD')
    if initial_password and not setting('admin_password'):
        if len(initial_password) < 10:
            raise RuntimeError('ADMIN_PASSWORD must contain at least 10 characters.')
        save_setting('admin_password', generate_password_hash(initial_password))


def setting(key, default=''):
    found = one('SELECT value FROM settings WHERE key=?', (key,))
    return found['value'] if found else default


def map_defaults():
    """These saved defaults define the opening view for this deployment."""
    return {'lat': float(setting('default_lat', 7.732)),
            'lng': float(setting('default_lng', 8.539)),
            'zoom': int(setting('default_zoom', 13)),
            'type': setting('default_type', 'roadmap')}


def call_contacts():
    """Only contact labels and dialling numbers are published; no placeholder numbers."""
    try:
        return json.loads(setting('call_contacts', '[]'))
    except ValueError:
        return []


def save_setting(key, value):
    write('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',
          (key, str(value)))


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier():
    return secrets.token_hex(12)


def current_user():
    user_id = session.get('user_id')
    if user_id == 'admin':
        return {'id': 'admin', 'name': 'Administrator', 'status': 'approved'}
    return one('SELECT id,name,phone,state,lga,community,status,lat,lng '
               'FROM users WHERE id=?', (user_id,)) if user_id else None


def required(value, label, maximum=200):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f'Enter a valid {label}.')
    return value.strip()


def coordinates(data):
    try:
        lat, lng = float(data['lat']), float(data['lng'])
    except (KeyError, TypeError, ValueError):
        raise ValueError('Select a location on the map.')
    if not math.isfinite(lat) or not math.isfinite(lng) or abs(lat) > 85 or abs(lng) > 180:
        raise ValueError('Select a valid map location.')
    return lat, lng


def metres_between(lat1, lng1, lat2, lng2):
    """Great-circle distance is sufficient for this point-based assignment prototype."""
    a, b = math.radians(lat1), math.radians(lat2)
    h = math.sin((b-a)/2)**2 + math.cos(a)*math.cos(b)*math.sin(math.radians(lng2-lng1)/2)**2
    return 6371000 * 2 * math.asin(math.sqrt(min(1, h)))


def throttle(key, maximum):
    expiry = time.time() + 900
    record = one('SELECT * FROM attempts WHERE key=?', (key,))
    count = record['count'] + 1 if record and record['expires'] > time.time() else 1
    if record and record['expires'] > time.time():
        expiry = record['expires']
    write('INSERT INTO attempts VALUES(?,?,?) ON CONFLICT(key) DO UPDATE SET '
          'count=excluded.count,expires=excluded.expires', (key, count, expiry))
    if count > maximum:
        raise ValueError('Too many attempts. Please try again in 15 minutes.')


def deliver(notification):
    """Deliver a queued notification and persist an honest, reviewable result."""
    status, detail = 'unavailable', 'Service is not connected'
    try:
        if notification['channel'] == 'push' and os.getenv('FCM_SERVICE_ACCOUNT'):
            tokens = rows('SELECT token FROM push_tokens WHERE user_id=?', (notification['user_id'],))
            if not tokens:
                detail = 'No push-enabled device registered'
            else:
                # Imported only when push is configured; credentials stay on the server.
                from google.oauth2 import service_account
                from google.auth.transport.requests import Request as GoogleRequest
                account = json.loads(os.environ['FCM_SERVICE_ACCOUNT'])
                credentials = service_account.Credentials.from_service_account_info(
                    account, scopes=['https://www.googleapis.com/auth/firebase.messaging'])
                credentials.refresh(GoogleRequest())
                accepted, temporary = False, False
                for device in tokens:
                    message = {'token': device['token'], 'notification': {
                        'title': 'Fieldwatch advisory', 'body': notification['message']},
                        'webpush': {'notification': {'tag': notification['id']}}}
                    if os.getenv('SITE_ORIGIN', '').startswith('https://'):
                        message['webpush']['fcm_options'] = {'link': os.environ['SITE_ORIGIN']}
                    result = requests.post(f"https://fcm.googleapis.com/v1/projects/{account['project_id']}/messages:send",
                        headers={'Authorization': f'Bearer {credentials.token}'}, json={'message': message}, timeout=15)
                    accepted = accepted or result.ok
                    temporary = temporary or result.status_code >= 500 or result.status_code == 429
                    if result.status_code == 404:
                        write('DELETE FROM push_tokens WHERE token=?', (device['token'],))
                status = 'accepted' if accepted else 'retry' if temporary else 'failed'
                detail = 'Accepted by push provider; reading unconfirmed' if accepted else 'Push provider could not accept this notification'
    except (requests.RequestException, ValueError, KeyError):
        app.logger.exception('Notification delivery failed')
        status, detail = 'retry', 'Delivery error; retry from the notification log'
    except Exception:
        app.logger.exception('Push service configuration failed')
        status, detail = 'failed', 'Check notification service configuration'
    write('UPDATE notifications SET status=?,detail=? WHERE id=?', (status, detail, notification['id']))
    return status


def queue_notification(user, report_id, message, event_status):
    channel = 'push'
    notification_id = f"{user['id']}:{report_id}:{event_status}:{channel}"
    # The primary key prevents duplicate messages when an officer saves the same status twice.
    if one('SELECT id FROM notifications WHERE id=?', (notification_id,)):
        return
    write('INSERT OR IGNORE INTO notifications VALUES(?,?,?,?,?,?,?,?)',
          (notification_id, user['id'], report_id, message, channel, 'queued', '', now()))
    deliver(one('SELECT * FROM notifications WHERE id=?', (notification_id,)))


@app.before_request
def protect_mutations():
    # A session CSRF token protects all POST requests, including login and registration.
    if 'csrf' not in session:
        session['csrf'] = secrets.token_hex(24)
    if request.method == 'POST':
        if not secrets.compare_digest(request.headers.get('X-CSRF-Token', ''), session['csrf']):
            return jsonify(error='Your session expired. Refresh the page and try again.'), 403
        if request.headers.get('Origin') and request.headers['Origin'].rstrip('/') != request.host_url.rstrip('/'):
            return jsonify(error='Invalid request origin.'), 403


@app.get('/')
def home():
    return render_template('index.html')


@app.get('/admin')
def admin_page():
    return render_template('admin.html')


@app.get('/firebase-messaging-sw.js')
def push_worker():
    # Root URL grants the worker scope over the whole app; the file stays in static/scripts.
    return send_from_directory(ROOT / 'static' / 'scripts', 'firebase-messaging-sw.js',
                               mimetype='application/javascript', max_age=0)


@app.get('/api/fieldwatch')
def read_application():
    user = current_user()
    if request.args.get('view') == 'admin':
        if not user or user['id'] != 'admin':
            return jsonify(error='Administrator login required.'), 403
        reports = rows('SELECT * FROM reports ORDER BY created DESC')
        window = float(setting('window_hours', 24)) * 3600
        radius, threshold = float(setting('radius', 2000)), int(setting('threshold', 3))
        recent = [r for r in reports if r['status'] not in ('resolved', 'rejected')
                  and time.time() - datetime.fromisoformat(r['created']).timestamp() <= window]
        # Session references reduce accidental duplicate counting but are not verified identities.
        warnings = [r for r in recent if len({x['user_id'] for x in recent
                     if metres_between(r['lat'], r['lng'], x['lat'], x['lng']) <= radius}) >= threshold]
        return jsonify(users=rows('SELECT id,name,phone,state,lga,community,status,lat,lng,created FROM users ORDER BY created DESC'),
            reports=reports, events=rows('SELECT * FROM events ORDER BY created DESC'), warnings=warnings,
            notifications=rows("SELECT n.*,u.name FROM notifications n JOIN users u ON u.id=n.user_id WHERE n.channel='push' ORDER BY n.created DESC LIMIT 200"),
            contacts=call_contacts(),
            settings={key: setting(key, default) for key, default in [('maps_key',''),('radius','2000'),('window_hours','24'),('threshold','3'),('default_lat','7.732'),('default_lng','8.539'),('default_zoom','13'),('default_type','roadmap')]},
            services={'maps': bool(setting('maps_key')), 'push': bool(os.getenv('FCM_SERVICE_ACCOUNT') and os.getenv('FIREBASE_CONFIG') and os.getenv('FCM_VAPID_KEY'))})
    try:
        firebase = json.loads(os.getenv('FIREBASE_CONFIG', 'null'))
    except ValueError:
        firebase = None
    return jsonify(me=user, states=STATES, types=INCIDENT_TYPES,
        farms=rows("SELECT id,community,lat,lng FROM users WHERE status='approved'"),
        reports=rows("SELECT id,type,community,lat,lng,status,created FROM reports WHERE status IN ('under_review','mediation') ORDER BY created DESC"),
        communities=rows('SELECT * FROM communities ORDER BY name'),
        notices=rows("SELECT id,message,created,status FROM notifications WHERE user_id=? AND channel='push' ORDER BY created DESC LIMIT 20", (user['id'],)) if user else [],
        mapSettings=map_defaults(), contacts=call_contacts(),
        mapsKey=setting('maps_key'), firebase=firebase, vapidKey=os.getenv('FCM_VAPID_KEY', ''))


@app.post('/api/fieldwatch')
def update_application():
    """Dispatch small form actions; authorisation is checked here, never just in JavaScript."""
    data = request.get_json(silent=True) or {}
    action, user = data.get('action'), current_user()
    try:
        if action in ('register', 'admin_add'):
            if action == 'admin_add' and (not user or user['id'] != 'admin'):
                return jsonify(error='Administrator access required.'), 403
            throttle('register:' + request.remote_addr, 10)
            import re
            phone = re.sub(r'[\s()-]', '', required(data.get('phone'), 'phone number', 20))
            phone = '+234' + phone[1:] if phone.startswith('0') else phone
            if not re.fullmatch(r'\+234[789]\d{9}', phone):
                raise ValueError('Enter a Nigerian mobile number, e.g. 08012345678.')
            name = required(data.get('name'), 'full name', 100)
            password = required(data.get('password'), 'password', 128)
            if len(password) < 10:
                raise ValueError('Use at least 10 characters for your password.')
            state = next((s for s in STATES if s['state'] == data.get('state')), None)
            if not state or data.get('lga') not in state['lgas']:
                raise ValueError('Choose a valid state and LGA.')
            community = required(data.get('community'), 'community', 100)
            lat, lng = coordinates(data)
            user_id = identifier()
            try:
                write('INSERT INTO users(id,name,phone,password,state,lga,community,preference,lat,lng,created) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                    (user_id,name,phone,generate_password_hash(password),data['state'],data['lga'],community,'push',lat,lng,now()))
            except sqlite3.IntegrityError:
                raise ValueError('This phone number is already registered. Please log in.')
            if action == 'register':
                session['user_id'], session.permanent = user_id, True
            return jsonify(ok=True, message='Registration saved. Your plot is awaiting approval.')

        if action == 'login':
            throttle('login:' + request.remote_addr, 12)
            if data.get('admin'):
                stored = setting('admin_password')
                if not stored or not check_password_hash(stored, str(data.get('password', ''))):
                    return jsonify(error='Incorrect administrator password.'), 401
                session['user_id'] = 'admin'
            else:
                phone = ''.join(str(data.get('phone', '')).split())
                phone = '+234'+phone[1:] if phone.startswith('0') else phone
                found = one('SELECT id,password FROM users WHERE phone=?', (phone,))
                if not found or not check_password_hash(found['password'], str(data.get('password', ''))):
                    return jsonify(error='Phone number or password is incorrect.'), 401
                session['user_id'] = found['id']
            session.permanent = True
            return jsonify(ok=True)
        if action == 'logout':
            session.pop('user_id', None)
            return jsonify(ok=True)
        if action == 'lookup_area':
            state = next((s for s in STATES if s['state'] == data.get('state')), None)
            if not state or data.get('lga') not in state['lgas']:
                raise ValueError('Select a valid state and LGA.')
            key = os.getenv('GOOGLE_GEOCODING_KEY')
            if not key:
                raise ValueError('Connect Google Maps or configure the server Geocoding key to locate an LGA.')
            response = requests.get('https://maps.googleapis.com/maps/api/geocode/json',
                params={'address': f"{data['lga']} Local Government Area, {data['state']}, Nigeria", 'components': 'country:NG', 'key': key}, timeout=10)
            result = response.json().get('results', [])
            if not result:
                raise ValueError('This LGA could not be located automatically.')
            return jsonify(result[0]['geometry']['location'])
        if action == 'geocode':
            lat,lng = coordinates(data)
            key = os.getenv('GOOGLE_GEOCODING_KEY')
            if not key:
                return jsonify(label='',message='Enter the community and landmark manually.')
            result = requests.get('https://maps.googleapis.com/maps/api/geocode/json',params={'latlng':f'{lat},{lng}','key':key},timeout=10).json()
            results = result.get('results',[])
            parts = results[0].get('address_components',[]) if results else []
            label = next((p['long_name'] for p in parts if set(p['types']) & {'neighborhood','sublocality','locality'}),'')
            return jsonify(label=label)
        elif action == 'report':
            # Reporting is public. A random session reference is not a farmer account.
            if 'reporter_id' not in session:
                session['reporter_id'] = 'guest:' + identifier()
            reporter_id = user['id'] if user else session['reporter_id']
            lat,lng = coordinates(data)
            if data.get('type') not in INCIDENT_TYPES:
                raise ValueError('Choose an incident type.')
            try:
                observed = datetime.fromisoformat(data.get('observed','').replace('Z','+00:00'))
                if observed.tzinfo is None: raise ValueError()
                if observed.timestamp()>time.time()+60: raise ValueError()
            except (ValueError,TypeError):
                raise ValueError('Choose a valid observation time, not in the future.')
            if data.get('farmId') and not one("SELECT id FROM users WHERE id=? AND status='approved'",(data['farmId'],)):
                raise ValueError('Selected farm is unavailable.')
            write('INSERT INTO reports(id,user_id,farm_id,type,description,community,lat,lng,observed,created) VALUES(?,?,?,?,?,?,?,?,?,?)',
                  (identifier(),reporter_id,data.get('farmId'),data['type'],required(data.get('description'),'description',2000),
                   required(data.get('community'),'community or landmark',150),lat,lng,observed.isoformat(),now()))
            return jsonify(ok=True,message='Report received. An officer will review it before issuing an advisory.')

        if not user:
            return jsonify(error='Please log in first.'), 401

        if action == 'push':
            token = required(data.get('token'), 'push token', 4096)
            write('INSERT INTO push_tokens VALUES(?,?) ON CONFLICT(token) DO UPDATE SET user_id=excluded.user_id', (token,user['id']))
        elif action == 'change_password':
            new_password = required(data.get('new_password'),'new password',128)
            if len(new_password)<10:
                raise ValueError('Use at least 10 characters.')
            stored = setting('admin_password') if user['id']=='admin' else one('SELECT password FROM users WHERE id=?',(user['id'],))['password']
            if not check_password_hash(stored,str(data.get('old_password',''))):
                raise ValueError('Your current password is incorrect.')
            if user['id']=='admin': save_setting('admin_password',generate_password_hash(new_password))
            else: write('UPDATE users SET password=? WHERE id=?',(generate_password_hash(new_password),user['id']))
        else:
            if user['id'] != 'admin':
                return jsonify(error='Administrator access required.'),403
            if action == 'approve':
                if data.get('status') not in ('pending','approved','rejected'):
                    raise ValueError('Invalid approval status.')
                write('UPDATE users SET status=? WHERE id=?',(data['status'],data.get('id')))
            elif action == 'community':
                state=next((s for s in STATES if s['state']==data.get('state')),None)
                if not state or data.get('lga') not in state['lgas']:
                    raise ValueError('Select a valid state and LGA.')
                write('INSERT OR IGNORE INTO communities VALUES(?,?,?,?)',
                      (identifier(),data['state'],data['lga'],required(data.get('name'),'community name',100)))
            elif action == 'settings':
                radius,hours,threshold=float(data['radius']),float(data['window_hours']),int(data['threshold'])
                if not (100<=radius<=100000 and 1<=hours<=168 and 2<=threshold<=50):
                    raise ValueError('Use 100–100,000 metres, 1–168 hours and 2–50 reporters.')
                lat, lng = coordinates({'lat': data.get('default_lat', setting('default_lat', 7.732)),
                                        'lng': data.get('default_lng', setting('default_lng', 8.539))})
                zoom = int(data.get('default_zoom', setting('default_zoom', 13)))
                map_type = data.get('default_type', setting('default_type', 'roadmap'))
                if not 1 <= zoom <= 20 or map_type not in ('roadmap','satellite','hybrid','terrain'):
                    raise ValueError('Select a zoom level from 1 to 20 and a valid map view.')
                # Validate all fields before saving any settings.
                for key,value in [('radius',radius),('window_hours',hours),('threshold',threshold),
                                  ('maps_key',str(data.get('maps_key','')).strip()),('default_lat',lat),
                                  ('default_lng',lng),('default_zoom',zoom),('default_type',map_type)]:
                    save_setting(key,value)
            elif action == 'save_contact':
                import re
                label = required(data.get('label'), 'contact name or office', 100)
                phone = re.sub(r'[\s()-]', '', required(data.get('phone'), 'phone number', 30))
                if not re.fullmatch(r'\+?[0-9]{3,15}', phone):
                    raise ValueError('Enter a valid telephone number, including the country code if needed.')
                contacts = call_contacts()
                contact_id = data.get('id') or identifier()
                contact = {'id': contact_id, 'label': label, 'phone': phone}
                if data.get('id') and not any(c['id'] == contact_id for c in contacts):
                    raise ValueError('Contact not found.')
                contacts = [contact if c['id'] == contact_id else c for c in contacts]
                if not data.get('id'):
                    contacts.append(contact)
                save_setting('call_contacts', json.dumps(contacts))
            elif action == 'delete_contact':
                contacts = [c for c in call_contacts() if c['id'] != data.get('id')]
                save_setting('call_contacts', json.dumps(contacts))
            elif action == 'update_report':
                if data.get('status') not in ('under_review','mediation','resolved','rejected'):
                    raise ValueError('Invalid report status.')
                report=one('SELECT * FROM reports WHERE id=?',(data.get('id'),))
                if not report: raise ValueError('Report not found.')
                note=required(data.get('note'),'action or outcome',2000)
                mediator=str(data.get('mediator','')).strip()[:150]
                if data['status']=='mediation' and not mediator:
                    raise ValueError('Assign a mediator before starting mediation.')
                with database():
                    database().execute('UPDATE reports SET status=?,mediator=?,outcome=? WHERE id=?',(data['status'],mediator,note,report['id']))
                    database().execute('INSERT INTO events VALUES(?,?,?,?,?)',(identifier(),report['id'],data['status'],note,now()))
                # Saving a verified or resolved case immediately sends advisories.
                if data['status']!='rejected':
                    # Broadcast to every registered account, including pending accounts.
                    # A device must have enabled push to receive a desktop alert.
                    for recipient in rows("SELECT * FROM users"):
                        message=f"{'Resolved' if data['status']=='resolved' else 'Verified report'}: {report['type']}, near {report['community']}. Status: {data['status'].replace('_',' ')}. Open Fieldwatch for updates."
                        queue_notification(recipient,report['id'],message,data['status'])
            elif action == 'retry':
                notification=one('SELECT * FROM notifications WHERE id=?',(data.get('id'),))
                if not notification or notification['channel'] != 'push' or notification['status'] not in ('retry','failed','unavailable','queued'):
                    raise ValueError('This notification cannot be retried.')
                deliver(notification)
            else:
                raise ValueError('Unknown action.')
        return jsonify(ok=True)
    except (ValueError,KeyError,TypeError) as error:
        return jsonify(error=str(error) if isinstance(error,ValueError) else 'Some required information is missing or invalid.'),400
    except requests.RequestException:
        app.logger.exception('External service request failed')
        return jsonify(error='External service unavailable. Please try again.'),503
    except sqlite3.Error:
        database().rollback()
        app.logger.exception('Database request failed')
        return jsonify(error='Could not save changes. Please try again.'),503


@app.after_request
def response_headers(response):
    if request.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='strict-origin-when-cross-origin'
    return response


with app.app_context():
    initialise_database()

if __name__ == '__main__':
    with app.app_context():
        if not setting('admin_password'):
            print('First-time setup: create your administrator password (10+ characters).')
            while True:
                first=getpass.getpass('New administrator password: ')
                second=getpass.getpass('Confirm password: ')
                if len(first)>=10 and first==second:
                    save_setting('admin_password',generate_password_hash(first))
                    break
                print('Passwords must match and contain at least 10 characters.')
    # Debugging is off by default. Flask still prints backend errors in this terminal.
    app.run(host='127.0.0.1',port=5000,debug=False)
