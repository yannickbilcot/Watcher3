import logging
import datetime
import PTN

from base64 import b16encode
import core
from core.helpers import Url
import json

logging = logging.getLogger(__name__)


def score(releases, imdbid=None, imported=False):
    ''' Scores and filters scene releases
    releases (list): dicts of release metadata to score
    imdbid (str): imdb identification number                    <optional -default None>
    impored (bool): indicate if search result is faked import   <optional -default False>

    If imported is True imdbid can be ignored. Otherwise imdbid is required.

    If imported, uses modified 'base' quality profile so releases
        cannot be filtered out.

    Iterates over the list and filters movies based on Words.
    Scores movie based on reslution priority, title match, and
        preferred words,

    Word groups are split in to a list of lists:
    [['word'], ['word2', 'word3'], 'word4']

    Adds 'score' key to each dict in releases and applies score.

    Returns list of result dicts
    '''
    if len(releases) == 0:
        logging.info('No releases to score.')
        return releases

    logging.info('Scoring {} releases.'.format(len(releases)))

    if imdbid is None and imported is False:
        logging.warning('Imdbid required if result is not library import.')
        return releases

    year = None
    title = None

    if imported:
        logging.debug('Releases are of origin "Import", using custom default quality profile.')
        titles = []
        check_size = False
        movie_details = {'year': '\n'}
        filters = {'requiredwords': '', 'preferredwords': '', 'ignoredwords': ''}
        quality = import_quality()
        category = {'requiredwords': '', 'preferredwords': '', 'ignoredwords': ''}
    else:
        movie_details = core.sql.get_movie_details('imdbid', imdbid)
        quality_profile = movie_details['quality']
        category_name = movie_details['category']
        logging.debug('Scoring based on quality profile {}'.format(quality_profile))
        check_size = True
        year = movie_details.get('year')
        title = movie_details.get('title').lower()

        if quality_profile in core.CONFIG['Quality']['Profiles']:
            quality = core.CONFIG['Quality']['Profiles'][quality_profile]
        else:
            quality = core.CONFIG['Quality']['Profiles'][core.config.default_profile()]

        if category_name in core.CONFIG['Categories']:
            category = core.CONFIG['Categories'][category_name]
        else:
            category = {'requiredwords': '', 'preferredwords': '', 'ignoredwords': ''}

        filters = json.loads(movie_details['filters'])

    sources = quality['Sources']

    required_groups = words_to_list(quality['requiredwords']) + words_to_list(filters['requiredwords']) + words_to_list(category['requiredwords'])
    preferred_groups = words_to_list(quality['preferredwords']) + words_to_list(filters['preferredwords']) + words_to_list(category['preferredwords'])
    ignored_groups = words_to_list(quality['ignoredwords']) + words_to_list(filters['ignoredwords']) + words_to_list(category['ignoredwords'])

    # Begin scoring and filtering
    reset(releases)
    if ignored_groups and ignored_groups != ['']:
        if title:
            ignored_groups = [word_group for word_group in ignored_groups if not all(word in title for word in word_group)]
            logging.debug('ignored groups not in movie title: {}'.format(ignored_groups))
        releases = remove_ignored(releases, ignored_groups)

    if required_groups and required_groups != ['']:
        releases = keep_required(releases, required_groups)

    if core.CONFIG['Search']['retention'] > 0 and any(i['type'] == 'nzb' for i in releases):
        releases = retention_check(releases)

    if any(i['type'] in ('torrent', 'magnet') for i in releases):
        if core.CONFIG['Search']['mintorrentseeds'] > 0:
            releases = seed_check(releases)
        if core.CONFIG['Search']['freeleechpoints'] > 0 or core.CONFIG['Search']['requirefreeleech']:
            releases = freeleech(releases)

    releases = score_sources(releases, sources, check_size=check_size)

    if quality['scoretitle']:
        titles = [movie_details.get('title')]
        if movie_details.get('alternative_titles'):
            titles += movie_details['alternative_titles'].split(',')
        releases = fuzzy_title(releases, titles, year=year)

    if preferred_groups and preferred_groups != ['']:
        releases = score_preferred(releases, preferred_groups)

    logging.info('Finished scoring releases.')

    return releases

def words_to_list(words):
    return [i.split('&') for i in words.lower().replace(' ', '').split(',') if i != '']

def reset(releases):
    ''' Sets all result's scores to 0
    releases (dict): scene release metadata to score

    returns dict
    '''
    logging.debug('Resetting release scores to 0.')
    for i, d in enumerate(releases):
        releases[i]['score'] = 0


def remove_ignored(releases, group_list):
    ''' Remove releases with ignored groups of 'words'
    releases (list[dict]): scene release metadata to score and filter
    group_list (list[list[str]]): forbidden groups of words

    group_list must be formatted as a list of lists ie:
        [['word1'], ['word2', 'word3']]

    Iterates through releases and removes every entry that contains any
        group of words in group_list

    Returns list[dict]
    '''

    keep = []

    logging.info('Filtering Ignored Words.')
    for r in releases:
        if r['type'] == 'import' and r not in keep:
            keep.append(r)
            continue
        cond = False
        for word_group in group_list:
            if all(word in r['title'].lower() for word in word_group):
                logging.debug('{} found in {}, removing from releases.'.format(word_group, r['title']))
                cond = True
                break
        if cond is False and r not in keep:
            keep.append(r)

    logging.info('Keeping {} releases.'.format(len(keep)))

    return keep


def keep_required(releases, group_list):
    ''' Remove releases without required groups of 'words'
    releases (list[dict]): scene release metadata to score and filter
    group_list (list[list[str]]): required groups of words

    group_list must be formatted as a list of lists ie:
        [['word1'], ['word2', 'word3']]

    Iterates through releases and removes every entry that does not
        contain any group of words in group_list

    Returns list[dict]
    '''

    keep = []

    logging.info('Filtering Required Words.')
    logging.debug('Required Words: {}'.format(str(group_list)))
    for r in releases:
        if r['type'] == 'import' and r not in keep:
            keep.append(r)
            continue
        for word_group in group_list:
            if all(word in r['title'].lower() for word in word_group) and r not in keep:
                logging.debug('{} found in {}, keeping this search result.'.format(word_group, r['title']))
                keep.append(r)
                break
            else:
                continue

    logging.info('Keeping {} releases.'.format(len(keep)))

    return keep


def retention_check(releases):
    ''' Remove releases older than 'retention' days
    releases (list[dict]): scene release metadata to score and filter
    retention (int): days of retention limit

    Iterates through releases and removes any nzb entry that was
        published more than 'retention' days ago

    returns list[dict]
    '''

    today = datetime.datetime.today()

    logging.info('Checking retention [threshold = {} days].'.format(core.CONFIG['Search']['retention']))
    keep = []
    for result in releases:
        if result['type'] == 'nzb':
            pubdate = datetime.datetime.strptime(result['pubdate'], '%d %b %Y')
            age = (today - pubdate).days
            if age < core.CONFIG['Search']['retention']:
                keep.append(result)
            else:
                logging.debug('{} published {} days ago, removing search result.'.format(result['title'], age))
        else:
            keep.append(result)

    logging.info('Keeping {} releases.'.format(len(keep)))
    return keep


def seed_check(releases):
    ''' Remove any torrents with fewer than 'seeds' seeders
    releases (list[dict]): scene release metadata to score and filter

    Gets required seeds from core.CONFIG

    Returns list[dict]
    '''

    logging.info('Checking torrent seeds.')
    keep = []
    for result in releases:
        if result['type'] in ('torrent', 'magnet'):
            if int(result['seeders']) >= core.CONFIG['Search']['mintorrentseeds']:
                keep.append(result)
            else:
                logging.debug('{} has {} seeds, removing search result.'.format(result['title'], result['seeders']))
        else:
            keep.append(result)

    logging.info('Keeping {} releases.'.format(len(keep)))
    return keep


def freeleech(releases):
    ''' Adds points to freeleech torrents
    releases (list[dict]): scene release metadata to score and filter

    Returns list[dict]
    '''
    logging.info('Checking torrent Freeleech info.')
    points = core.CONFIG['Search']['freeleechpoints']
    for release in releases[:]:
        if not release['type'] in ('magnet', 'torrent'):
            continue
            if release['freeleech'] == 1:
                if core.CONFIG['Search']['requirefreeleech']:
                    continue
            logging.debug('Adding {} Freeleech points to {}.'.format(points, release['title']))
            release['score'] += points
        elif core.CONFIG['Search']['requirefreeleech']:
            logging.debug('{} is not Freeleech, removing search result.'.format(release['title']))
            releases.remove(release)

            logging.info('Keeping {} releases.'.format(len(releases)))

    return releases


def score_preferred(releases, group_list):
    ''' Increase score for each group of 'words' match
    releases (list[dict]): scene release metadata to score and filter
    group_list (list): preferred groups of words

    group_list must be formatted as a list of lists ie:
        [['word1'], ['word2', 'word3']]

    Iterates through releases and adds 10 points to every
        entry for each word group it contains

    Returns list[dict]
    '''

    logging.info('Scoring Preferred Words.')

    if not group_list or group_list == ['']:
        return

    for r in releases:
        for word_group in group_list:
            if all(word in r['title'].lower() for word in word_group):
                logging.debug('{} found in {}, adding 10 points.'.format(word_group, r['title']))
                r['score'] += 10
            else:
                continue
    return releases


def fuzzy_title(releases, titles, year='\n'):
    ''' Score and remove releases based on title match
    releases (list[dict]): scene release metadata to score and filter
    titles (list): titles to match against
    year (str): year of movie release           <optional -default '\n'>

    If titles is an empty list every result is treated as a perfect match
    Matches releases based on release_title.split(year)[0]. If year is not passed,
        matches on '\n', which will include the entire string.

    Iterates through releases and removes any entry that does not
        fuzzy match 'title' > 70.
    Adds fuzzy_score / 20 points to ['score']

    Returns list[dict]
    '''

    logging.info('Checking title match.')

    keep = []
    if titles == [] or titles == [None]:
        logging.debug('No titles available to compare, scoring all as perfect match.')
        for result in releases:
            result['score'] += 20
            keep.append(result)
    else:
        for result in releases:
            if result['type'] == 'import' and result not in keep:
                logging.debug('{} is an Import, sorting as a perfect match.'.format(result['title']))
                result['score'] += 20
                keep.append(result)
                continue

            rel_title_ss = result.get('ptn', PTN.parse(result['title']))['title']

            logging.debug('Comparing release substring {} with titles {}.'.format(rel_title_ss, titles))
            matches = [_fuzzy_title(rel_title_ss, title) for title in titles]
            if any(match > 70 for match in matches):
                result['score'] += int(max(matches) / 5)
                keep.append(result)
            else:
                logging.debug('{} best title match was {}%, removing search result.'.format(result['title'], max(matches)))

    logging.info('Keeping {} releases.'.format(len(keep)))
    return keep


def _fuzzy_title(a, b):
    ''' Determines how much of a is in b
    a (str): String to match against b
    b (str): String to match a against

    Order of a and b matters.

    A is broken down and words are compared against B's words.

    ie:
    _fuzzy_title('This is string a', 'This is string b and has extra words.')
    Returns 75 since 75% of a is in b.

    Returns int
    '''

    a = a.replace('&', 'and')
    b = b.replace('&', 'and')
    a = a.replace('\'', '')
    b = b.replace('\'', '')
    a = a.replace(':', '')
    b = b.replace(':', '')

    a_words = Url.normalize(a).split(' ')
    b_words = Url.normalize(b).split(' ')

    m = 0
    a_len = len(a_words)

    for i in a_words:
        if i in b_words:
            b_words.remove(i)
            m += 1

    return int((m / a_len) * 100)


def score_sources(releases, sources, check_size=True):
    ''' Score releases based on quality/source preferences
    releases (list[dict]): scene release metadata to score and filter
    sources (dict): sources from user config
    check_size (bool): whether or not to filter based on size

    Iterates through releases and removes any entry that does not
        fit into quality criteria (source-resoution, filesize)
    Adds to ['score'] based on priority of match

    Returns list[dict]
    '''

    logging.info('Filtering resolution and size requirements.')
    score_range = len(core.SOURCES) + 1

    sizes = core.CONFIG['Quality']['Sources']

    keep = []
    for result in releases:
        result_res = result['resolution']
        logging.debug('Scoring and filtering {} based on resolution {}.'.format(result['title'], result_res))
        size = result['size'] / 1000000
        if result['type'] == 'import' and result['resolution'] not in sources:
            keep.append(result)
            continue

        for k, v in sources.items():
            if v[0] is False and result['type'] != 'import':
                continue
            priority = v[1]
            if check_size:
                min_size = sizes[k]['min']
                max_size = sizes[k]['max']
            else:
                min_size = 0
                max_size = Ellipsis

            if result_res == k:
                logging.debug('{} matches source {}, checking size.'.format(result['title'], k))

                if result['type'] != 'import' and not (min_size < size < max_size):
                    logging.debug('Removing {}, size {} not in range {}-{}.'.format(result['title'], size, min_size, max_size))
                    break

                result['score'] += abs(priority - score_range) * 40
                keep.append(result)
            else:
                continue

    logging.info('Keeping {} releases.'.format(len(keep)))
    return keep


def import_quality():
    ''' Creates quality profile for imported releases

    Creates import profile that mimics the base profile, but it incapable
        of removing releases.

    Returns dict
    '''
    profile = core.config.base_profile

    profile['ignoredwords'] = ''
    profile['requiredwords'] = ''

    for i in profile['Sources']:
        profile['Sources'][i][0] = True

    return profile


def generate_simulacrum(movie):
    ''' Generates phony search result for imported movies
    movie (dict): movie info

    movie will use 'release_title' key if found, else 'title' to generate fake release

    Resturns dict to match SEARCHRESULTS table
    '''

    logging.info('Creating "fake" search result for imported movie {}'.format(movie['title']))

    result = {'status': 'Finished',
              'info_link': '#',
              'pubdate': None,
              'title': None,
              'imdbid': movie['imdbid'],
              'torrentfile': None,
              'indexer': 'Library Import',
              'date_found': str(datetime.date.today()),
              'score': None,
              'type': 'import',
              'downloadid': None,
              'guid': None,
              'resolution': movie.get('resolution'),
              'size': movie.get('size') or 0,
              'releasegroup': movie.get('releasegroup') or '',
              'freeleech': 0
              }

    title = '{}.{}.{}.{}.{}.{}'.format(movie['title'],
                                       movie['year'],
                                       movie.get('resolution') or '.',  # Kind of a hacky way to make sure it doesn't print None in the title
                                       movie.get('audiocodec') or '.',
                                       movie.get('videocodec') or '.',
                                       movie.get('releasegroup') or '.'
                                       )

    while len(title) > 0 and title[-1] == '.':
        title = title[:-1]

    while '..' in title:
        title = title.replace('..', '.')

    result['title'] = title

    result['guid'] = movie.get('guid') or 'import{}'.format(b16encode(title.encode('ascii', errors='ignore')).decode('utf-8').zfill(16)[:16]).lower()

    return result
