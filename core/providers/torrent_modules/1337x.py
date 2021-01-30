import logging
from datetime import datetime, date
from bs4 import BeautifulSoup
import re
import core
from urllib.parse import urlparse
from base64 import b16encode
from core.helpers import Url

logging = logging.getLogger(__name__)

'''
Does not supply rss feed -- backlog searches only.
'''

def base_url():
    url = core.CONFIG['Indexers']['Torrent']['1337x']['url']
    if not url:
        url = 'https://1337x.to'
    elif url[-1] == '/':
        url = url[:-1]
    return url

def search(imdbid, term, ignore_if_imdbid_cap = False, page = 1):
    proxy_enabled = core.CONFIG['Server']['Proxy']['enabled']

    if page == 1:
        logging.info('Searching 1337x for {}.'.format(term))

    host = base_url()
    url = '{}/search/{}/{}/'.format(host, term, page)

    try:
        if proxy_enabled and core.proxy.whitelist(host) is True:
            response = Url.open(url, proxy_bypass=True).text
        else:
            response = Url.open(url).text

        if response:
            return _parse(response, imdbid, term, page)
        else:
            return []
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception:
        logging.error('1337x search failed.', exc_info=True)
        return []

def get_rss():
    return []

def get_hash_and_magnet(url):
    ''' Get hash and magnet from URL link
    url (str): torrent info_link url

    Returns tuple with str of lower-case torrent hash, and magnet uri
    ''' 
    proxy_enabled = core.CONFIG['Server']['Proxy']['enabled']
    
    host = urlparse(url)
    host = '{}://{}'.format(host.scheme, host.netloc)

    try:
        if proxy_enabled and core.proxy.whitelist(host) is True:
            response = Url.open(url, proxy_bypass=True).text
        else:
            response = Url.open(url).text

        if response:
            soup = BeautifulSoup(response, 'html.parser')
            magnet = soup.select_one('a[href^="magnet:?"]').attrs['href']
            hash = magnet.split('&')[0].split(':')[-1].lower()
            return (hash, magnet)
        else:
            return ()
    except (SystemExit, KeyboardInterrupt):
        raise
    except Exception:
        logging.error('1337x get magnet failed.', exc_info=True)
        return ()


units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
def _size(size):
    size = size.replace(',','')
    number, unit = [string.strip() for string in size.split()]
    return int(float(number)*units[unit])

def _date(selector):
    ret = None
    pubdate = re.sub(r"(?<=\d)(st|nd|rd|th)\b", '', selector.get_text())

    if ':' not in pubdate and "'" not in pubdate:
        # (within this year) 7am Sep. 14th
        pubdate = ' '.join(pubdate.split(' ')[1:])
        ret = datetime.strftime(datetime.strptime(pubdate, "%b. %d"), '%d %b {}'.format(date.today().year))

    elif "'" in pubdate:
        # (more than a year ago) Apr. 18th '11
        ret = datetime.strftime(datetime.strptime(pubdate, "%b. %d '%y"), '%d %b %Y')            

    elif ':' in pubdate:
        # (today) 12:25am
        ret = date.today().strftime('%d %b %Y')

    return ret

def _title(selector):
    title_text = selector.get_text()
    title_href = selector.attrs['href'].split('/')[3]

    title = title_href if title_href else title_text
    title = re.sub(r"(-+)\b", ' ', title)
    title = title.replace('u000f', '') 
    return title

def _parse(html, imdbid, term, page):
    logging.info('Parsing 1337x (page {}) results.'.format(page))

    soup = BeautifulSoup(html, 'html.parser')
    rows = soup.select('tbody tr')

    results = []
    for row in rows:
        result = {}
        try:
            result['score'] = 0
            result['size'] = _size(row.select_one('td.size').find(text=True, recursive=False))
            result['status'] = 'Available'
            result['pubdate'] = _date(row.select_one('td.coll-date'))
            result['title'] = _title(row.select_one('td.name a[href^="/torrent/"]'))
            result['imdbid'] = imdbid
            result['indexer'] = '1337x'
            result['info_link'] = '{}{}'.format(base_url(), row.select_one('td.name a[href^="/torrent/"]').attrs['href'])
            result['torrentfile'] = None
            result['guid'] = 'redirect{}'.format(urlparse(result['info_link']).path.split('/')[2])
            result['type'] = 'magnet'
            result['downloadid'] = None
            result['freeleech'] = 0
            result['download_client'] = None
            result['seeders'] = int(row.select_one('td.seeds').get_text())
            result['leechers'] = int(row.select_one('td.leeches').get_text())

            results.append(result)
        except Exception:
            logging.error('Error parsing 1337x HTML.', exc_info=True)
            continue
        
    if soup.select_one('li.last a'):
        results += search(imdbid, term, page=page+1)
    
    if page == 1:
        logging.info('Found {} results from 1337x.'.format(len(results)))

    return results
