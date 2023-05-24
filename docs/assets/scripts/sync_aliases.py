from requests import Session
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

OMBI_URL = ''
OMBI_APIKEY = ''

TAUTULLI_URL = ''
TAUTULLI_APIKEY = ''

# Don't Edit Below #
disable_warnings(InsecureRequestWarning)
SESSION = Session()
SESSION.verify = False
HEADERS = {'apiKey': OMBI_APIKEY}
PARAMS = {'apikey': TAUTULLI_APIKEY, 'cmd': 'get_users'}
TAUTULLI_USERS = SESSION.get('{}/api/v2'.format(TAUTULLI_URL.rstrip('/')), params=PARAMS).json()['response']['data']
TAUTULLI_MAPPED = {user['username']: user['friendly_name'] for user in TAUTULLI_USERS
                   if user['user_id'] != 0 and user['friendly_name']}
OMBI_USERS = SESSION.get('{}/api/v1/Identity/Users'.format(OMBI_URL.rstrip('/')), headers=HEADERS).json()

for user in OMBI_USERS:
    if user['userName'] in TAUTULLI_MAPPED and user['alias'] != TAUTULLI_MAPPED[user['userName']]:
        print("{}'s alias in Tautulli ({}) is being updated in Ombi from {}".format(
            user['userName'], TAUTULLI_MAPPED[user['userName']], user['alias'] or 'empty'
        ))
        user['alias'] = TAUTULLI_MAPPED[user['userName']]
        put = SESSION.put('{}/api/v1/Identity'.format(OMBI_URL.rstrip('/')), json=user, headers=HEADERS)
        if put.status_code != 200:
            print('Error updating {}'.format(user['userName']))