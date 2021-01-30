import logging
from datetime import datetime, date
from bs4 import BeautifulSoup
import re
import core
from core.helpers import Url

logging = logging.getLogger(__name__)

def base_url():
    url = core.CONFIG['Indexers']['Torrent']['torrentgalaxy']['url']
    if not url:
        url = 'https://torrentgalaxy.to'
    elif url[-1] == '/':
        url = url[:-1]
    return url

def search(imdbid, term, ignore_if_imdbid_cap = False, page = 0):
    if ignore_if_imdbid_cap:
        return []
    proxy_enabled = core.CONFIG['Server']['Proxy']['enabled']

    if page == 0:
        logging.info('Searching TorrentGalaxy for {}.'.format(term))

    host = base_url()
    url = '{}/torrents.php?c42=1&c3=1&c4=1&search={}&lang=0&sort=id&order=desc&page={}'.format(host, imdbid, page)

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
        logging.error('TorrentGalaxy search failed.', exc_info=True)
        return []

def get_rss():
    return []

units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
def _size(size):
    size = size.replace(',','')
    number, unit = [string.strip() for string in size.split()]
    return int(float(number)*units[unit])

def _date(selector):
    ret = None
    pubdate = selector.get_text()

    if ':' in pubdate:
        # 24/12/18 13:55
        pubdate = pubdate + ' -0700'
        ret = datetime.strftime(datetime.strptime(pubdate, "Added %d/%m/%y %H:%M %z"), '%d %b %Y')

    elif 'ago' in pubdate:
        # 20Mins ago
        ret = date.today().strftime('%d %b %Y')

    return ret

def _title(selector):
    title_full = selector.attrs['title']
    title_text = selector.get_text()
    title_href = selector.attrs['href']
    title_href = title_href.replace('-quot-', ' ')
    title_href = title_href.replace('-', ' ')

    if title_full:
        title = title_full
    elif title_text:
        title = title_text
    else:
        title = title_href
        
    return title

def _parse(html, imdbid, term, page):
    logging.info('Parsing TorrentGalaxy (page {}) results.'.format(page+1))

    soup = BeautifulSoup(html, 'html.parser')
    rows = soup.select('div.tgxtable > div:has(div[class="tgxtablecell shrink"])')

    results = []
    for row in rows:
        result = {}
        try:
            result['score'] = 0
            result['size'] = _size(row.select_one('div span[style^="border-radius"]').get_text())
            result['status'] = 'Available'
            result['pubdate'] = _date(row.select_one('div td:last-of-type'))
            result['title'] = _title(row.select_one('div a[href^="/torrent/"]'))
            result['imdbid'] = imdbid
            result['indexer'] = 'TorrentGalaxy'
            result['info_link'] = '{}{}'.format(base_url(), row.select_one('div a[href^="/torrent/"]').attrs['href'])
            result['torrentfile'] = row.select_one('div a[href^="magnet:?"]').attrs['href']
            result['guid'] = result['torrentfile'].split('&')[0].split(':')[-1]
            result['type'] = 'magnet'
            result['downloadid'] = None
            result['freeleech'] = 0
            result['download_client'] = None
            result['seeders'] = int(row.select_one('div span[title="Seeders/Leechers"] font b').get_text().replace(',',''))
            result['leechers'] = int(row.select_one('div span[title="Seeders/Leechers"] font:nth-child(2) b').get_text().replace(',',''))

            results.append(result)
        except Exception:
            logging.error('Error parsing TorrentGalaxy HTML.', exc_info=True)
            continue

    next_page = soup.select_one('li.page-item.active + li')
    if next_page:
        if next_page.get_text() != 'Next':
            results += search(imdbid, term, page=page+1)
 
    if page == 0:
        logging.info('Found {} results from TorrentGalaxy.'.format(len(results)))

    return results
