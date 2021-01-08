from core.helpers import Url
from core.helpers import Comparisons
from core.library import Manage
import json
import core
import datetime
import time
from core import searcher
import xml.etree.cElementTree as ET
import re

import logging
logging = logging.getLogger(__name__)


searcher = searcher
date_format = '%a, %d %b %Y %H:%M:%S'
trakt_date_format = '%Y-%m-%dT%H:%M:%S'


def sync():
    ''' Syncs all enabled Trakt lists and rss lists

    Gets list of movies from each enabled Trakt lists

    Adds missing movies to library as Waiting/Default

    Returns bool for success/failure
    '''

    logging.info('Syncing Trakt lists.')

    success = True

    min_score = core.CONFIG['Search']['Watchlists']['traktscore']
    length = core.CONFIG['Search']['Watchlists']['traktlength']
    movies = []

    if core.CONFIG['Search']['Watchlists']['traktrss']:
        sync_rss()

    for k, v in core.CONFIG['Search']['Watchlists']['Traktlists'].items():
        if v is False:
            continue
        movies += [i for i in get_list(k, min_score=min_score, length=length) if i not in movies]

    library = [i['imdbid'] for i in core.sql.get_user_movies()]

    movies = [i for i in movies if ((i['ids']['imdb'] not in library) and (i['ids']['imdb'] != 'N/A'))]

    logging.info('Found {} new movies from Trakt lists.'.format(len(movies)))

    for i in movies:
        imdbid = i['ids']['imdb']
        logging.info('Adding movie {} {} from Trakt'.format(i['title'], imdbid))

        movie = {'id': i['ids']['tmdb'], 'imdbid': i['ids']['imdb'], 'title': i['title'], 'origin': 'Trakt'}
        added = Manage.add_movie(movie)
        try:
            if added['response'] and core.CONFIG['Search']['searchafteradd'] and i['year'] != 'N/A':
                searcher.search(movie)
        except Exception as e:
            logging.error('Movie {} did not get added.'.format(i['title']), exc_info=False)
    return success


def sync_rss():
    ''' Gets list of new movies in user's rss feed(s)

    Returns list of movie dicts
    '''

    try:
        record = json.loads(core.sql.system('trakt_sync_record'))
    except Exception as e:
        record = {}

    for url in core.CONFIG['Search']['Watchlists']['traktrss'].split(','):
        list_id = url.split('.atom')[0].split('/')[-1]

        last_sync = record.get(list_id) or 'Sat, 01 Jan 2000 00:00:00'
        last_sync = datetime.datetime.strptime(last_sync, date_format)

        logging.info('Syncing Trakt RSS watchlist {}. Last sync: {}'.format(list_id, last_sync))
        try:
            feed = Url.open(url).text
            feed = re.sub(r'xmlns=".*?"', r'', feed)
            root = ET.fromstring(feed)
        except Exception as e:
            logging.error('Trakt rss request:\n{}'.format(feed), exc_info=True)
            continue

        d = root.find('updated').text[:19]

        do = datetime.datetime.strptime(d, trakt_date_format)
        record[list_id] = datetime.datetime.strftime(do, date_format)

        for entry in root.iter('entry'):
            try:
                pub = datetime.datetime.strptime(entry.find('published').text[:19], trakt_date_format)
                if last_sync >= pub:
                    break
                else:
                    t = entry.find('title').text

                    title = ' ('.join(t.split(' (')[:-1])

                    year = ''
                    for i in t.split(' (')[-1]:
                        if i.isdigit():
                            year += i
                    year = int(year)

                    logging.info('Searching TheMovieDatabase for {} {}'.format(title, year))
                    movie = Manage.tmdb._search_title('{} {}'.format(title, year))[0]
                    if movie:
                        movie['origin'] = 'Trakt'
                        logging.info('Found new watchlist movie {} {}'.format(title, year))

                        r = Manage.add_movie(movie)

                        if r['response'] and core.CONFIG['Search']['searchafteradd'] and movie['year'] != 'N/A':
                            searcher.search(movie)
                    else:
                        logging.warning('Unable to find {} {} on TheMovieDatabase'.format(title, year))

            except Exception as e:
                logging.error('Unable to parse Trakt RSS list entry.', exc_info=True)

    logging.info('Storing last synced date.')
    if core.sql.row_exists('SYSTEM', name='trakt_sync_record'):
        core.sql.update('SYSTEM', 'data', json.dumps(record), 'name', 'trakt_sync_record')
    else:
        core.sql.write('SYSTEM', {'data': json.dumps(record), 'name': 'trakt_sync_record'})

    logging.info('Trakt RSS sync complete.')

def api_get_token(refresh=False):
    ''' Get Trakt API access token
    refresh(bool): if True, use the refresh_token to get a new access_token without asking the user to re-authenticate.
    '''
    logging.info('Getting Trakt API access token')
    url = 'https://api.trakt.tv/oauth/token'
    ret = ''

    headers = {'Content-Type': 'application/json'}

    data = {'client_id': core.CONFIG['Search']['Watchlists']['traktclientid'],
            'client_secret': core.CONFIG['Search']['Watchlists']['traktclientsecret'],
            'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob',
            'grant_type': 'authorization_code'
            }

    if refresh:
        data['grant_type'] = 'refresh_token'
        data['refresh_token'] = core.sql.system('trakt_refresh_token')
    else:
        data['code'] = core.CONFIG['Search']['Watchlists']['traktdevicecode']

    try:
        r = Url.open(url, headers=headers, post_data=json.dumps(data))
        if r.status_code == 200:
            m = json.loads(r.text)

            if core.sql.row_exists('SYSTEM', name='trakt_access_token'):
                core.sql.update('SYSTEM', 'data', m['access_token'], 'name', 'trakt_access_token')
            else:
                core.sql.write('SYSTEM', {'data': m['access_token'], 'name': 'trakt_access_token'})

            if core.sql.row_exists('SYSTEM', name='trakt_refresh_token'):
                core.sql.update('SYSTEM', 'data', m['refresh_token'], 'name', 'trakt_refresh_token')
            else:
                core.sql.write('SYSTEM', {'data': m['refresh_token'], 'name': 'trakt_refresh_token'})

            ret = m['access_token']

        elif r.status_code == 400:
            logging.error('Error 400: Pending - waiting for the user to authorize your app')
        elif r.status_code == 404:
            logging.error('Error 404: Not Found - invalid device_code')
        elif r.status_code == 409:
            logging.error('Error 409: Already Used - user already approved this code')
        elif r.status_code == 410:
            logging.error('Error 410: Expired - the tokens have expired, restart the process')
            time.sleep(1)
            api_get_token(refresh=True)
        elif r.status_code == 418:
            logging.error('Error 418: Denied - user explicitly denied this code')
    except Exception:
        logging.error('Unable to get Trakt API token.', exc_info=True)

    return ret

def get_list(list_name, min_score=0, length=10):
    ''' Gets list of trending movies from Trakt
    list_name (str): name of Trakt list. Must be one of ('trending', 'popular', 'watched', 'collected', 'anticipated', 'boxoffice', 'watchlist')
    min_score (float): minimum score to accept (max 10)   <optional - default 0>
    length (int): how many results to get from Trakt      <optional - default 10>

    Length is applied before min_score, so actual result count
        can be less than length

    Returns list of dicts of movie info
    '''

    logging.info('Getting Trakt list {}'.format(list_name))

    headers = {'Content-Type': 'application/json',
               'trakt-api-version': '2',
               'trakt-api-key': core.CONFIG['Search']['Watchlists']['traktclientid']
               }

    if list_name not in ('trending', 'popular', 'watched', 'collected', 'anticipated', 'boxoffice', 'watchlist'):
        logging.error('Invalid list_name {}'.format(list_name))
        return []

    url = 'https://api.trakt.tv/movies/{}/?extended=full'.format(list_name)

    if list_name == 'watchlist':
        url = 'https://api.trakt.tv/sync/watchlist/movies'
        try:
            access_token = core.sql.system('trakt_access_token')
        except Exception:
            access_token = api_get_token()
            if access_token == '':
                return []
        headers['Authorization'] = 'Bearer {}'.format(access_token)

    try:
        r = Url.open(url, headers=headers)
        if r.status_code == 200:
            m = json.loads(r.text)
            if list_name == 'popular':
                return [i for i in m[:length] if i['rating'] >= min_score]
            elif list_name == "watchlist":
                return [i['movie'] for i in m]
            return [i['movie'] for i in m[:length] if i['movie']['rating'] >= min_score]
        elif r.status_code == 401:
            logging.error('Error 401: Unauthorized')
            time.sleep(1)
            api_get_token(refresh=True)
            time.sleep(1)
            return get_list(list_name, min_score, length)
        else:
            return []

    except Exception as e:
        logging.error('Unable to get Trakt list.', exc_info=True)
        return []
