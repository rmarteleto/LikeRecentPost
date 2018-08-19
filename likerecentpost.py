"""Like most recent post of users in the input file"""
import json
import codecs
import datetime
import time
import os.path
import tenacity

from instagram_private_api import (
    Client, ClientError, ClientLoginError,
    ClientCookieExpiredError, ClientLoginRequiredError,
    __version__ as client_version)

USER_NAME = ''
PASSWORD = ''
SETTINGS_FILE = '.cache'
INPUT_FILE = 'input.txt'

def to_json(python_object):
    """Convert python object to json"""
    if isinstance(python_object, bytes):
        return {'__class__': 'bytes',
                '__value__': codecs.encode(python_object, 'base64').decode()}
    raise TypeError(repr(python_object) + ' is not JSON serializable')


def from_json(json_object):
    """Convert json object to python"""
    if '__class__' in json_object and json_object['__class__'] == 'bytes':
        return codecs.decode(json_object['__value__'].encode(), 'base64')
    return json_object

def onlogin_callback(instagram_api, new_settings_file):
    """Instagram login callback function"""
    cache_settings = instagram_api.settings
    with open(new_settings_file, 'w') as outfile:
        json.dump(cache_settings, outfile, default=to_json)
        print('SAVED: {0!s}'.format(new_settings_file))


@tenacity.retry(wait=(tenacity.wait_fixed(2) + tenacity.wait_random(0, 3)), \
                stop=tenacity.stop_after_attempt(5), \
                reraise=True)
def like_user_recent_photo(instagram_api, name):
    """Like most recent post by user"""
    rank_token = Client.generate_uuid()
    result = instagram_api.search_users(name, rank_token)
    if result['num_results'] <= 0:
        print(f'ERROR: User {name} not found')
    else:
        user = result['users'][0]
        if user['friendship_status']['is_private'] is True:
            print(f'User {name} is private')
        else:
            feed = instagram_api.user_feed(user['pk'])
            first_item = feed["items"][0]
            if "comment_likes_enabled" in first_item and \
               first_item["comment_likes_enabled"] is False:
                print(f'User {name} most recent post has disabled for likes and comments')
            elif first_item["has_liked"]:
                print(f'User {name} most recent post has already been liked')
            else:
                instagram_api.post_like(first_item["id"])
                print(f'You just liked the most recent post of user {name}')


def process_input_file(instagram_api):
    """Read the input file and process users"""
    with open(INPUT_FILE, 'r') as f:
        names = f.readlines()
        for name in names:
            name = name.strip()
            name = name.strip('@')
            if name != '':
                try:
                    like_user_recent_photo(instagram_api, name)
                    time.sleep(2)
                except Exception:
                    print(f'ERROR: Unable to process most recent post of user {name}')

if __name__ == '__main__':

    # check if input exists
    if not os.path.isfile(INPUT_FILE):
        print(f'{INPUT_FILE} doesn\'t exist')
        exit(9)

    device_id = None

    try:
        if not os.path.isfile(SETTINGS_FILE):
            print('Unable to find file: {0!s}'.format(SETTINGS_FILE))
            api = Client(USER_NAME, PASSWORD, on_login=lambda x: onlogin_callback(x, SETTINGS_FILE))
        else:
            with open(SETTINGS_FILE) as file_data:
                cached_settings = json.load(file_data, object_hook=from_json)
            print('Reusing settings: {0!s}'.format(SETTINGS_FILE))

            device_id = cached_settings.get('device_id')
            # reuse auth settings
            api = Client(USER_NAME, PASSWORD, settings=cached_settings)
    except (ClientCookieExpiredError, ClientLoginRequiredError) as e:
        print('ClientCookieExpiredError/ClientLoginRequiredError: {0!s}'.format(e))

        # Login expired
        # Do relogin but use default ua, keys and such
        api = Client(
            USER_NAME, PASSWORD,
            device_id=device_id,
            on_login=lambda x: onlogin_callback(x, SETTINGS_FILE))

    except ClientLoginError as e:
        print('ClientLoginError {0!s}'.format(e))
        exit(9)
    except ClientError as e:
        print('ClientError {0!s} (Code: {1:d}, Response: {2!s})' \
              .format(e.msg, e.code, e.error_response))
        exit(9)
    except Exception as e:
        print('Unexpected Exception: {0!s}'.format(e))
        exit(99)

    print('Cookie Expiry: {0!s}' \
          .format(datetime.datetime.fromtimestamp(api.cookie_jar.auth_expires) \
                  .strftime('%Y-%m-%dT%H:%M:%SZ')))

    process_input_file(api)
