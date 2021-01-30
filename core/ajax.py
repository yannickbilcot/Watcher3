import json
import logging
import os
import threading
import time
import cherrypy
import datetime
import core
from core import config, library, searchresults, searcher, snatcher, notification, plugins, downloaders
from core.library import Metadata, Manage
from core.movieinfo import TheMovieDatabase, YouTube
from core.providers import torrent, newznab
from core.helpers import Conversions
import backup
from gettext import gettext as _
logging = logging.getLogger(__name__)


class Errors():
    ''' Namespace for common error messages used in AJAX responses '''
    database_write = _('Unable to write to database.')
    database_read = _('Unable to read {} details from database.')
    tmdb_not_found = _('Unable to find {} on TheMovieDB.')


class Ajax(object):
    ''' These are all the methods that handle ajax post/get requests from the browser.

    Except in special circumstances, all should return an 'ajax-style response', which is a
        dict with a response key to indicate success, and additional keys for expected data output.

        For example {'response': False, 'error': 'something broke'}
                    {'response': True, 'results': ['this', 'is', 'the', 'output']}

    '''

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def library(self, sort_key, sort_direction, limit=50, offset=0, status=None, category=None):
        ''' Get 50 movies from library
        sort_key (str): column name to sort by
        sort_direction (str): direction to sort [ASC, DESC]

        limit: int number of movies to get                  <optional - default 50>
        offset: int list index postition to start slice     <optional - default 0>
        status (list): filter movies with these statuses only <optional>
        category (str): filter movies with this category only <optional>

        Gets a movies slice, length by limit, from library sorted by sort key

        Returns list of dicts of movies
        '''
        if status and not isinstance(status, list):
            status = [status]
        if status and 'Finished' in status:
            status.append('Disabled')

        return core.sql.get_user_movies(sort_key, sort_direction.upper(), limit, offset, status, category)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def library_counters(self, category=None):
        ''' Get movies counters group by status, filtered by category
        category (str): Count movies with this category <optional>
        '''

        status_count = core.sql.get_library_count('status', 'category', category)
        status_count['Finished'] = status_count.get('Finished', 0) + status_count.get('Disabled', 0)
        if 'Disabled' in status_count:
            del status_count['Disabled']

        return status_count

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def search_tmdb(self, search_term):
        ''' Search tmdb for movies
        search_term (str): title and year of movie (Movie Title 2016)

        Returns list of dicts that contain tmdb's data.
        '''

        results = TheMovieDatabase.search(search_term)
        if results:
            Manage.add_status_to_search_movies(results)
        else:
            logging.info('No Results found for {}'.format(search_term))

        return results

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def tmdb_categories(self, cat, tmdbid=None):
        ''' Get categories of movies from TMDB

        Returns list of dicts of movies
        '''
        results = TheMovieDatabase.get_category(cat, tmdbid)[:8]
        if results:
            Manage.add_status_to_search_movies(results)
        else:
            logging.info('No Results found for {}'.format(cat))

        return results

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def quick_titles(self):
        return core.sql.quick_titles()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_search_results(self, imdbid, quality=None):
        ''' Gets search results for movie
        imdbid (str): imdb id #
        quality (str): quality profile for movie    <optional - default None>

        Passes request to sql.get_search_results() then filters out unused download methods.

        Returns dict ajax-style response
        '''

        results = Manage.search_results(imdbid, quality=quality)

        if not results:
            ne = core.scheduler_plugin.task_list['Movie Search'].next_execution
            ne = Conversions.human_datetime(ne) if ne else '[Disabled]'
            return {'response': False, 'next': ne}
        else:
            for i in results:
                i['size'] = Conversions.human_file_size(i['size'])
            return {'response': True, 'results': results}

    @cherrypy.expose
    def get_trailer(self, title, year):
        ''' Gets trailer embed url from youtube
        title (str): title of movie
        year (str/int): year of movie release

        Returns str
        '''
        return YouTube.trailer('{} {}'.format(title, year))

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def add_wanted_movie(self, data):
        ''' Adds movie to library
        data (str): json-formatted dict of known movie data

        Calls library.Manage.add_movie to add to library.

        Returns dict ajax-style response
        '''
        movie = json.loads(data)

        response = Manage.add_movie(movie, full_metadata=False)

        if response['response'] and core.CONFIG['Search']['searchafteradd'] and movie['year'] != 'N/A':
            threading.Thread(target=searcher._t_search_grab, args=(movie,)).start()

        return response

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def save_settings(self, data):
        ''' Saves settings to config file
        data (dict): of Section with nested dict of keys and values:
        {'Section': {'key': 'val', 'key2': 'val2'}, 'Section2': {'key': 'val'}}

        All dicts must contain the full tree or data will be lost.

        Fires off additional methods if neccesary, ie scheduler restart/reloads

        Returns dict ajax-style response
        '''

        logging.info('Saving settings.')
        data = json.loads(data)

        save_data = {}
        for key in data:
            if data[key] != core.CONFIG[key]:
                save_data[key] = data[key]

        if not save_data:
            return {'response': True, 'message': _('Settings saved.')}

        try:
            config.write(save_data)
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception as e:
            logging.error('Writing config.', exc_info=True)
            return {'response': False, 'error': _('Unable to write to config file.')}

        return {'response': True, 'message': _('Settings saved.')}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def remove_movie(self, imdbid):
        ''' Removes movie
        imdbid (str): imdb id #

        Returns dict ajax-style response
        '''

        return Manage.remove_movie(imdbid)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def delete_movie_file(self, imdbid):
        ''' Deletes movie file for imdbid
        imdbid (str): imdb id #

        Returns dict ajax-style response
        '''

        logging.info('Deleting file for {}.'.format(imdbid))

        f = core.sql.get_movie_details('imdbid', imdbid).get('finished_file')

        try:
            logging.debug('Finished file for {} is {}'.format(imdbid, f))
            if os.path.exists(f):
                os.unlink(f)
            core.sql.update_multiple_values('MOVIES', {'finished_date': None, 'finished_score': None, 'finished_file': None}, 'imdbid', imdbid)
            return {'response': True, 'message': _('Deleted movie file {}.').format(f)}
        except Exception as e:
            logging.error('Unable to delete file {}'.format(f), exc_info=True)
            return {'response': False, 'error': str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def search(self, imdbid):
        ''' Search indexers for specific movie.
        imdbid (str): imdb id #

        Gets movie data from database and sends to searcher.search()

        Returns dict ajax-style response
        '''
        logging.info('Starting user-requested backlog search for {}'.format(imdbid))

        movie = core.sql.get_movie_details('imdbid', imdbid)

        if not movie:
            return {'response': False, 'error': Errors.database_read.format(imdbid)}
        else:
            success = searcher.search(movie)
            status = core.sql.get_movie_details('imdbid', imdbid)['status']

            if success:
                results = core.sql.get_search_results(imdbid, movie['quality'], rejected=True)

                for i in results:
                    i['size'] = Conversions.human_file_size(i['size'])

                r = {'response': True, 'results': results, 'movie_status': status}

                if len(results) == 0:
                    ne = core.scheduler_plugin.task_list['Movie Search'].next_execution
                    r['next'] = Conversions.human_datetime(ne) if ne else '[Disabled]'

                return r
            else:
                return {'response': False, 'error': Errors.database_read.format(imdbid), 'movie_status': status}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def manual_download(self, year, guid, kind):
        ''' Sends search result to downloader manually
        guid (str): download link for nzb/magnet/torrent file.
        kind (str): type of download (torrent, magnet, nzb)

        Returns dict ajax-style response
        '''

        torrent_enabled = core.CONFIG['Downloader']['Sources']['torrentenabled']

        usenet_enabled = core.CONFIG['Downloader']['Sources']['usenetenabled']

        if kind == 'nzb' and not usenet_enabled:
            return {'response': False, 'error': _('Link is NZB but no Usent client is enabled.')}
        elif kind in ('torrent', 'magnet') and not torrent_enabled:
            return {'response': False, 'error': _('Link is Torrent/Magnet but no Torrent client is enabled.')}

        data = dict(core.sql.get_single_search_result('guid', guid))
        if data:
            data['year'] = year
            return snatcher.download(data)
        else:
            return {'response': False, 'error': Errors.database_read.format(kind)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def mark_bad(self, guid, imdbid, cancel_download=False):
        ''' Marks guid as bad in SEARCHRESULTS and MARKEDRESULTS
        guid (str): guid of download to mark
        imdbid (str): imdb id # of movie
        cancel_download (bool): send command to download client to cancel download

        Returns dict ajax-style response
        '''

        sr_orig = core.sql.get_single_search_result('guid', guid)

        sr = Manage.searchresults(guid, 'Bad')
        Manage.markedresults(guid, 'Bad', imdbid=imdbid)

        if sr:
            response = {'response': True, 'message': _('Marked release as Bad.')}
        else:
            response = {'response': False, 'error': Errors.database_write}

        response['movie_status'] = Manage.movie_status(imdbid)
        if not response['movie_status']:
            response['error'] = (Errors.database_write)
            response['response'] = False

        if cancel_download:
            cancelled = False

            if sr_orig.get('status') != 'Snatched':
                return response

            client = sr_orig['download_client'] if sr_orig else None
            downloadid = sr_orig['downloadid'] if sr_orig else None
            if not client:
                logging.info('Download client not found, cannot cancel download.')
                return response
            else:
                cancelled = getattr(downloaders, client).cancel_download(downloadid)

            if not cancelled:
                response['response'] = False
                response['error'] = response.get('error', '') + _(' Could not remove download from client.')

        return response

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def unmark_bad(self, guid, imdbid):
        ''' Removes bad mark for guid in SEARCHRESULTS and MARKEDRESULTS
        guid (str): guid of download to mark
        imdbid (str): imdb id # of movie

        Returns dict ajax-style response
        '''

        logging.info('Removing {} from MARKEDRESULTS.'.format(guid.split('&')[0]))
        if not core.sql.delete('MARKEDRESULTS', 'guid', guid):
            logging.info('Removing MARKEDRESULTS {} failed.'.format(guid.split('&')[0]))
            return {'response': False, 'error': Errors.database_write}
        else:
            logging.info('Successfully removed {} from MARKEDRESULTS.'.format(guid.split('&')[0]))

        sr = Manage.searchresults(guid, 'Available')
        if sr:
            response = {'response': True, 'message': _('Marked release as Available.')}
        else:
            response = {'response': False, 'error': Errors.database_write}

        response['movie_status'] = Manage.movie_status(imdbid)
        if not response['movie_status']:
            response['error'] = (Errors.database_write)
            response['response'] = False

        return response

    @cherrypy.expose
    def notification_remove(self, index):
        ''' Removes notification from core.notification
        index (str/int): index of notification to remove

        'index' will be of type string since it comes from ajax request.
            Therefore we convert to int here before passing to Notification

        Simply calls Notification module.

        Does not return
        '''

        notification.remove(int(index))

        return

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def update_check(self):
        ''' Manually check for updates

        Returns list:
            [0] dict ajax-style response
            [1] dict of core notifications
        '''

        response = core.updater.update_check()
        if response['status'] == 'current':
            n = [[{'message': _('No updates available.')}, {'type': 'primary'}]]
            return [response, n]
        else:
            return [response, core.NOTIFICATIONS]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def test_downloader_connection(self, mode, data):
        ''' Test connection to downloader.
        mode (str): which downloader to test.
        data (dict): connection information (url, port, login, etc)

        Executes staticmethod in the chosen downloader's class.

        Returns dict ajax-style response
        '''

        response = {}

        data = json.loads(data)

        test = getattr(downloaders, mode).test_connection(data)

        if test is True:
            response['response'] = True
            response['message'] = _('Connection successful.')
        else:
            response['response'] = False
            response['error'] = test

        return response

    @cherrypy.expose
    def server_status(self, mode):
        ''' Check or modify status of CherryPy server_status
        mode (str): command or request of state

        Restarts or Shuts Down server in separate thread.
            Delays by one second to allow browser to redirect.

        If mode == 'online', asks server for status.
            (ENGINE.started, ENGINE.stopped, etc.)

        Returns nothing for mode == restart || shutdown
        Returns str server state if mode == online
        '''

        if mode == 'restart':
            threading.Timer(1, core.restart).start()
            return

        elif mode == 'shutdown':
            threading.Timer(1, core.shutdown).start()
            return

        elif mode == 'online':
            return str(cherrypy.engine.state)

    @cherrypy.expose
    def update_server(self, mode):
        ''' Starts and executes update process.
        mode (str): 'set_true' or 'update_now'

        This method has two major functions based on mode

        set_true:
            Sets core.UPDATING to True, the browser should then automatically redirect
                the user to the update page that calls update_server('update_now')

        update_now:
            Starts update process:
                * Stops task scheduler to cancel all Timers
                * Waits for in-process tasks to finish. Yields to browser a list of
                    currently-running tasks every 1.5 seconds
                * Yields updating message to browser. Calls update method
                * Sets core.UPDATING to False
                * Yields response from update method to browser
                    If False, starts scheduler plugin again to get back to a normal state
                    If True, calls restart method. Browser is responsible for redirecting
                        afer the server is back up.

        Returns dict ajax-style response
        '''

        if mode == 'set_true':
            core.UPDATING = True
            return json.dumps({'response': True})
        if mode == 'update_now':
            logging.info('Update process started.')

            core.scheduler_plugin.stop()

            active_tasks = [k for k, v in core.scheduler_plugin.task_list.items() if v.running]

            while len(active_tasks) > 0:
                yield json.dumps({'response': True, 'status': 'waiting', 'active_tasks': active_tasks})
                active_tasks = [k for k, v in core.scheduler_plugin.task_list.items() if v.running]
                time.sleep(1.5)

            yield json.dumps({'response': True, 'status': 'updating'})

            update_status = core.updater.execute_update()
            core.UPDATING = False

            if update_status is False:
                logging.error('Update Failed.')
                yield json.dumps({'response': False, 'error': _('Unable to complete update.')})
                core.scheduler_plugin.restart()

            elif update_status is True:
                yield json.dumps({'response': True, 'status': 'complete'})
                self.server_status('restart')

        else:
            return json.dumps({'response': False})

    update_server._cp_config = {'response.stream': True, 'tools.gzip.on': False}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def update_movie_options(self, quality, category, status, language, title, filters, imdbid):
        ''' Updates quality settings for individual title
        quality (str): name of new quality
        category (str): name of new category
        status (str): management state ('automatic', 'disabled')
        language (str): name of language to download movie
        title (str): movie title
        filters (str): JSON.stringified dict of filter words
        imdbid (str): imdb identification number

        Returns dict ajax-style response
        '''

        success = {'response': True, 'message': _('Movie options updated.')}

        if not Manage.update_movie_options(imdbid, quality, category, language, title, filters):
            return {'response': False, 'error': Errors.database_write}

        logging.info('Updating status to {} for {}.'.format(status, imdbid))

        if status == 'Automatic':
            if not core.sql.update('MOVIES', 'status', 'Waiting', 'imdbid', imdbid):
                return {'response': False, 'error': Errors.database_write}
            new_status = Manage.movie_status(imdbid)
            if not new_status:
                return {'response': False, 'error': Errors.database_write}
            else:
                success['status'] = new_status
                return success
        elif status == 'Disabled':
            if not core.sql.update('MOVIES', 'status', 'Disabled', 'imdbid', imdbid):
                return {'response': False, 'error': Errors.database_write}
            else:
                success['status'] = 'Disabled'
                return success

    @cherrypy.expose
    def get_log_text(self, logfile):
        ''' Gets log file contents
        logfile (str): name of log file to read

        logfile should be filename only, not the path to the file

        Returns str
        '''

        logging.info('Dumping log file {} to text.'.format(logfile))

        with open(os.path.join(core.LOG_DIR, logfile), 'r') as f:
            log_text = ''.join(reversed(f.readlines()))

        return log_text

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def indexer_test(self, indexer, apikey, mode):
        ''' Tests connection to newznab indexer
        indexer (str): url of indexer
        apikey (str): indexer's api key
        mode (str): newznab or torznab

        Returns dict ajax-style response
        '''

        if mode == 'newznab':
            return newznab.NewzNab.test_connection(indexer, apikey)
        elif mode == 'torznab':
            return torrent.Torrent.test_connection(indexer, apikey)
        else:
            return {'response': False, 'error': _('Invalid test mode.')}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_plugin_conf(self, folder, conf):
        ''' Calls plugin_conf_popup to render html
        folder (str): folder to read config file from
        conf (str): filename of config file (ie 'my_plugin.conf')

        Returns string
        '''
        c = os.path.join(core.PLUGIN_DIR, folder, conf)

        logging.info('Reading plugin config {}'.format(c))

        try:
            with open(c) as f:
                config = json.load(f)
        except Exception as e:
            logging.error('Unable to read config file.', exc_info=True)
            return ''

        return plugins.render_config(config)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def save_plugin_conf(self, folder, filename, config):
        ''' Calls plugin_conf_popup to render html
        folder (str): folder to store config file
        filename (str): filename of config file (ie 'my_plugin.conf')
        config (str): json data to store in conf file

        Returns dict ajax-style response
        '''

        conf_file = os.path.join(core.PROG_PATH, core.PLUGIN_DIR, folder, filename)

        logging.info('Saving plugin config as {}'.format(conf_file))

        config = json.loads(config)

        response = {'response': True, 'message': _('Settings saved.')}

        try:
            with open(conf_file, 'w') as output:
                json.dump(config, output, indent=2)
        except Exception as e:
            response = {'response': False, 'error': str(e)}

        return response

    @cherrypy.expose
    def scan_library_directory(self, directory, minsize, recursive, skipduplicatedirs, maxresults):
        ''' Calls library to scan directory for movie files
        directory (str): directory to scan
        minsize (str/int): minimum file size in mb, coerced to int
        recursive (bool): whether or not to search subdirs
        skipduplicatedirs (bool): whether or not to skip duplicate dirs
        maxresults (str/int): maximum result count, coerced to int

        Finds all files larger than minsize in directory.
        Removes all movies from gathered list that are already in library.

        If error, yields {'error': reason} and stops Iteration
        If movie has all metadata, yields:
            {'complete': {<metadata>}}
        If missing imdbid or resolution, yields:
            {'incomplete': {<knownn metadata>}}

        All metadata dicts include:
            'path': 'absolute path to file'
            'progress': '10 of 250'

        Yeilds dict ajax-style response
        '''

        recursive = json.loads(recursive)
        minsize = int(minsize)
        # Note - do not limit the result set here, or we might get stuck looking at files we already have
        files = core.library.ImportDirectory.scan_dir(directory, minsize, recursive)
        if files.get('error'):
            yield json.dumps({'error': files['error']})
            raise StopIteration()
        user_movies = core.sql.get_user_movies()
        library_files = [i['finished_file'] for i in user_movies]
        library = [i['imdbid'] for i in user_movies]
        files = [file for file in files['files'] if file not in library_files]

        skipduplicatedirs = json.loads(skipduplicatedirs)
        if skipduplicatedirs:
            # Build dict of dir:[files]
            library_file_dirs = {}
            for f in library_files:
                if f:
                    fd = os.path.dirname(f)
                    library_file_dirs.setdefault(fd, []).append(f)

            # Log all possible duplicate dirs to help with manual maintenance
            for f in files:
                fd = os.path.dirname(f)
                if fd in library_file_dirs:
                    logging.info('## {} directory already in library'.format(f))
                    for x in library_file_dirs[fd]:
                        logging.info('## {}'.format(x))

            # Remove the files which have duplicate dirs (likely to be the same imdbid)
            # This avoids doing a metadata probe which is then ignored
            files = [f for f in files if os.path.dirname(f) not in library_file_dirs]

            # We do not need the dict any more, so release the memory
            del library_file_dirs

        # Limit the number of results
        # We do this here instead of at the scan so we skip files we have already imported
        if maxresults:
            maxresults = int(maxresults)
            if maxresults > 0:
                files = files[0:maxresults]

        length = len(files)

        if length == 0:
            yield json.dumps({'response': None})
            raise StopIteration()

        logging.info('Parsing {} directory scan results.'.format(length))
        for index, path in enumerate(files):
            logging.info('Gathering metatadata for {}'.format(path))
            metadata = {}
            response = {'progress': [index + 1, length]}
            try:
                metadata = Metadata.from_file(path)

                if not metadata.get('imdbid'):
                    metadata['imdbid'] = ''
                    logging.info('IMDB unknown for import {}'.format(metadata['title']))
                    response['response'] = 'incomplete'
                elif metadata['imdbid'] in library:
                    logging.info('{} ({}) already in library, ignoring.'.format(metadata['title'], path))
                    response['response'] = 'in_library'
                    # Log all possible duplicate files to help with manual maintenance
                    for i in user_movies:
                        if i['imdbid'] == metadata['imdbid']:
                            logging.info('## {} {}'.format(i['imdbid'], i['finished_file']))
                elif not metadata.get('resolution'):
                    logging.info('Resolution/Source unknown for import {}'.format(metadata['title']))
                    response['response'] = 'incomplete'
                else:
                    logging.info('All data found for import {}'.format(metadata['title']))
                    response['response'] = 'complete'

                if response['response'] == 'complete':
                    p = metadata.get('poster_path')
                    r = metadata.get('resolution')
                    metadata = Metadata.convert_to_db(metadata)
                    metadata['poster_path'] = p
                    metadata['resolution'] = r

                metadata['size'] = os.path.getsize(path)
                metadata['human_size'] = Conversions.human_file_size(metadata['size'])
                metadata['finished_file'] = path

                if response['response'] == 'in_library':
                    metadata = {'title': metadata['title']}

                response['movie'] = metadata
                yield json.dumps(response)

            except Exception as e:
                logging.warning('Error gathering metadata.', exc_info=True)
                yield json.dumps({'response': 'incomplete', 'movie': metadata})
                continue

    scan_library_directory._cp_config = {'response.stream': True, 'tools.gzip.on': False}

    @cherrypy.expose
    def import_dir(self, movies, corrected_movies):
        ''' Imports list of movies in data
        movie_data (list): dicts of movie info ready to import
        corrected_movies (list): dicts of user-corrected movie info

        corrected_movies must be [{'/path/to/file': {'known': 'metadata'}}]

        Iterates through corrected_movies and attmpts to get metadata again if required.

        If imported, generates and stores fake search result.

        Creates dict {'success': [], 'failed': []} and
            appends movie data to the appropriate list.

        Yeilds dict ajax-style response
        '''

        logging.info('Adding directory scan movies to library.')

        today = str(datetime.date.today())

        movie_data = json.loads(movies)
        corrected_movies = json.loads(corrected_movies)

        fake_results = []

        success = []

        length = len(movie_data) + len(corrected_movies)
        progress = 1

        if corrected_movies:
            logging.info('{} corrected movies, gathering metadata.'.format(len(corrected_movies)))
            for data in corrected_movies:
                tmdbdata = TheMovieDatabase._search_tmdbid(data['tmdbid'])
                if tmdbdata:
                    tmdbdata = tmdbdata[0]
                    data['year'] = tmdbdata['release_date'][:4]
                    data.update(tmdbdata)
                    movie_data.append(data)
                else:
                    logging.error('Unable to find {} on TMDB.'.format(data['tmdbid']))
                    yield json.dumps({'response': False, 'movie': data, 'progress': [progress, length], 'error': Errors.tmdb_not_found.format(data['tmdbid'])})
                    progress += 1

        logging.info('Adding {} directory scan movies to library.'.format(len(movie_data)))
        for movie in movie_data:
            if movie.get('imdbid'):
                movie['status'] = 'Disabled'
                movie['predb'] = 'found'
                movie['origin'] = 'Directory Import'
                movie['finished_date'] = today
                movie['id'] = movie['tmdbid']
                response = Manage.add_movie(movie, full_metadata=True)
                if response['response'] is True:
                    fake_results.append(searchresults.generate_simulacrum(movie))
                    yield json.dumps({'response': True, 'progress': [progress, length], 'movie': movie})
                    progress += 1
                    success.append(movie)
                    continue
                else:
                    yield json.dumps({'response': False, 'movie': movie, 'progress': [progress, length], 'error': response['error']})
                    progress += 1
                    continue
            else:
                logging.error('Unable to find {} on TMDB.'.format(movie['title']))
                logging.debug(movie)
                yield json.dumps({'response': False, 'movie': movie, 'progress': [progress, length], 'error': Errors.tmdb_not_found.format(data['title'])})
                progress += 1

        fake_results = searchresults.score(fake_results, imported=True)

        for i in success:
            for r in fake_results:
                if r['imdbid'] == i['imdbid']:
                    core.sql.update('MOVIES', 'finished_score', r['score'], 'imdbid', i['imdbid'])
                    break

        core.sql.write_search_results(fake_results)

    import_dir._cp_config = {'response.stream': True, 'tools.gzip.on': False}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def list_files(self, current_dir, move_dir):
        ''' Lists files in directory
        current_dir (str): base path
        move_dir (str): child path to read

        Joins and normalizes paths:
            ('/home/user/movies', '..')
            Becomes /home/user

        Returns dict ajax-style response
        '''

        current_dir = current_dir.strip()
        move_dir = move_dir.strip()

        response = {}

        new_path = os.path.normpath(os.path.join(current_dir, move_dir))
        response['new_path'] = new_path

        try:
            response['list'] = [i for i in os.listdir(new_path) if os.path.isdir(os.path.join(new_path, i)) and not i.startswith('.')]
            response['list'].sort()
        except Exception as e:
            response = {'error': str(e)}
            logging.error('Error listing directory.', exc_info=True)

        return response

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def update_metadata(self, imdbid, tmdbid=None):
        ''' Re-downloads metadata for imdbid
        imdbid (str): imdbid of movie
        tmdbid (str): tmdbid of movie     <optional - default None>

        If tmdbid is None, looks in database for tmdbid using imdbid.
        If that fails, looks on tmdb api for imdbid
        If that fails returns error message


        Returns dict ajax-style response
        '''

        r = Metadata.update(imdbid, tmdbid)

        if r['response'] is True:
            return {'response': True, 'message': _('Metadata updated.')}
        else:
            return r

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def movie_metadata(self, imdbid, tmdbid=None, language=None):
        ''' Re-downloads metadata for imdbid
        imdbid (str): imdbid of movie
        tmdbid (str): tmdbid of movie     <optional - default None>

        If tmdbid is None, looks in database for tmdbid using imdbid.
        If that fails, looks on tmdb api for imdbid
        If that fails returns error message


        Returns dict ajax-style response
        '''

        result = Metadata.tmdb_data(imdbid, tmdbid=tmdbid, language=language)
        if result:
            return {'response': True, 'tmdb_data': result}
        else:
            return {'response': False, 'error': 'Unable to find {} on TMDB.'.format(tmdbid or imdbid)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def single_movie_details(self, key, value):
        ''' Gets single movie's details from database
        key (str): key for sql.get_movie_details
        value (str): value for sql.get_movie_details

        Returns dict
        '''
        return core.sql.get_movie_details(key, value)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def set_movie_details(self, data):
        ''' Updates movie in database
        data (dict): movie fields and values to update

        data *must* include valid tmdbid

        Returns dict
        '''
        data = json.loads(data)
        tmdbid = data.pop('tmdbid')

        if not core.sql.update_multiple_values('MOVIES', data, 'tmdbid', tmdbid):
            return {'response': False, 'error': Errors.database_write}
        else:
            return {'response': True, 'message': 'Database Updated'}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_kodi_movies(self, url):
        ''' Gets list of movies from kodi server
        url (str): url of kodi server

        Calls Kodi import method to gather list.

        Returns dict ajax-style response
        '''

        return library.ImportKodiLibrary.get_movies(url)

    @cherrypy.expose
    def import_kodi_movies(self, movies):
        ''' Imports list of movies in movies from Kodi library
        movie_data (str): json-formatted list of dicts of movies

        Iterates through movies and gathers all required metadata.

        If imported, generates and stores fake search result.

        Creates dict {'success': [], 'failed': []} and
            appends movie data to the appropriate list.

        Yeilds dict ajax-style response
        '''

        movies = json.loads(movies)

        fake_results = []

        success = []

        length = len(movies)
        progress = 1

        logging.info('Adding {} Kodi movies to library.'.format(length))

        for movie in movies:

            if not movie['imdbid']:
                yield json.dumps({'response': False, 'movie': movie, 'progress': [progress, length], 'error': Errors.tmdb_not_found.format("NONE")})
                progress += 1
                continue

            tmdb_data = TheMovieDatabase._search_imdbid(movie['imdbid'])
            if not tmdb_data or not tmdb_data[0].get('id'):
                yield json.dumps({'response': False, 'movie': movie, 'progress': [progress, length], 'error': Errors.tmdb_not_found.format(movie['imdbid'])})
                progress += 1
                continue

            tmdb_data = tmdb_data[0]

            movie['id'] = tmdb_data['id']
            try:
                movie['size'] = os.path.getsize(movie.get('finished_file'))
            except OSError as e:
                movie['size'] = 0
                logging.error('Unable to get the file size', exc_info=True)
            movie['status'] = 'Disabled'
            movie['predb'] = 'found'
            movie['finished_file'] = (movie.get('finished_file') or '').strip()
            movie['origin'] = 'Kodi Import'

            response = Manage.add_movie(movie)
            if response['response'] is True:
                fake_results.append(searchresults.generate_simulacrum(movie))
                yield json.dumps({'response': True, 'progress': [progress, length], 'title': movie['title'], 'imdbid': movie['imdbid']})
                progress += 1
                success.append(movie)
                continue
            else:
                yield json.dumps({'response': False, 'title': movie['title'], 'imdbid': movie['imdbid'], 'progress': [progress, length], 'error': response['error']})
                progress += 1
                continue

        fake_results = searchresults.score(fake_results, imported=True)

        for i in success:
            for r in fake_results:
                if r['imdbid'] == i['imdbid']:
                    core.sql.update('MOVIES', 'finished_score', r['score'], 'imdbid', i['imdbid'])
                    break

        core.sql.write_search_results(fake_results)

    import_kodi_movies._cp_config = {'response.stream': True, 'tools.gzip.on': False}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def upload_plex_csv(self, file_input):
        ''' Recieves upload of csv from browser
        file_input (b'str): csv file fo read

        Reads/parses csv file into a usable dict

        Returns dict ajax-style response
        '''

        try:
            csv_text = file_input.file.read().decode('utf-8')
            file_input.file.close()
        except Exception as e:
            logging.error('Unable to parse Plex CSV', exc_info=True)
            return {'response': False, 'error': str(e)}

        if csv_text:
            return library.ImportPlexLibrary.read_csv(csv_text)
        else:
            return {'response': True, 'complete': [], 'incomplete': []}

    @cherrypy.expose
    def import_plex_csv(self, movies, corrected_movies):
        ''' Imports list of movies genrated by csv import
        movie_data (list): dicts of movie info ready to import
        corrected_movies (list): dicts of user-corrected movie info

        Iterates through corrected_movies and attmpts to get metadata again if required.

        If imported, generates and stores fake search result.

        Creates dict {'success': [], 'failed': []} and
            appends movie data to the appropriate list.

        Yeilds dict ajax-style response
        '''

        movie_data = json.loads(movies)
        corrected_movies = json.loads(corrected_movies)

        fake_results = []

        success = []

        length = len(movie_data) + len(corrected_movies)
        progress = 1

        if corrected_movies:
            logging.info('Adding {} Plex movies to library.'.format(len(corrected_movies)))
            for movie in corrected_movies:
                tmdbdata = TheMovieDatabase._search_imdbid(movie['imdbid'])
                if tmdbdata:
                    tmdbdata = tmdbdata[0]
                    movie['year'] = tmdbdata['release_date'][:4]
                    movie.update(tmdbdata)
                    movie_data.append(movie)
                else:
                    logging.error(Errors.tmdb_not_found.format(movie['imdbid']))
                    yield json.dumps({'response': False, 'movie': movie, 'progress': [progress, length], 'error': Errors.tmdb_not_found.format(movie['imdbid'])})
                    progress += 1

        logging.info('Adding {} Plex movies to library.'.format(length))
        for movie in movie_data:
            logging.info('Importing Plex movie {} {}'.format(movie.get('title', ''), movie.get('year', '')))

            fm = False
            if not movie.get('imdbid') and movie.get('tmdbid'):
                tmdb_data = TheMovieDatabase._search_tmdbid(movie['tmdbid'])
                if tmdb_data:
                    movie.update(tmdb_data[0])
                    fm = True
                else:
                    yield json.dumps({'response': False, 'progress': [progress, length], 'title': movie['title'], 'error': Errors.tmdb_not_found.format(movie['tmdbid'])})
                    progress += 1
                    continue

            if movie.get('imdbid'):
                movie['status'] = 'Disabled'
                movie['predb'] = 'found'
                movie['origin'] = 'Plex Import'

                if not movie.get('id'):
                    tmdb_data = TheMovieDatabase._search_imdbid(movie['imdbid'])
                    if tmdb_data:
                        movie.update(tmdb_data[0])
                    else:
                        yield json.dumps({'response': False, 'progress': [progress, length], 'title': movie['title'], 'error': Errors.tmdb_not_found.format(movie['imdbid'])})
                        progress += 1
                        continue
                response = Manage.add_movie(movie, full_metadata=fm)
                if response['response'] is True:
                    fake_results.append(searchresults.generate_simulacrum(movie))
                    yield json.dumps({'response': True, 'progress': [progress, length], 'title': movie['title'], 'imdbid': movie['imdbid']})
                    progress += 1
                    success.append(movie)
                    continue
                else:
                    yield json.dumps({'response': False, 'progress': [progress, length], 'error': response['error'], 'title': movie['title']})
                    progress += 1
                    continue
            else:
                logging.error(Errors.tmdb_not_found.format(movie['title']))
                yield json.dumps({'response': False, 'progress': [progress, length], 'error': _('Unable to find IMDB ID for {} on TheMovieDB.').format(movie['title']), 'title': movie['title']})
                progress += 1
                continue

        if fake_results:
            fake_results = searchresults.score(fake_results, imported=True)

        for i in success:
            for r in fake_results:
                if r['imdbid'] == i['imdbid']:
                    core.sql.update('MOVIES', 'finished_score', r['score'], 'imdbid', i['imdbid'])
                    break

        if fake_results:
            core.sql.write_search_results(fake_results)

    import_plex_csv._cp_config = {'response.stream': True, 'tools.gzip.on': False}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_cp_movies(self, url, apikey):
        ''' Gets movies from CP server
        url (str): url to cp server
        apikey (str): cp api key

        Reads/parses cp api response

        Returns dict ajax-style response
        '''

        url = '{}/api/{}/movie.list/'.format(url, apikey)

        if not url.startswith('http'):
            url = 'http://{}'.format(url)

        return library.ImportCPLibrary.get_movies(url)

    @cherrypy.expose
    def import_cp_movies(self, wanted, finished):
        ''' Imports movies from CP list to library
        wanted (list): dicts of wanted movies
        finished (list): dicts of finished movies

        Yields dict ajax-style response
        '''
        wanted = json.loads(wanted)
        finished = json.loads(finished)

        fake_results = []

        success = []

        length = len(wanted) + len(finished)
        progress = 1

        logging.info('Adding {} Wanted CouchPotato movies to library.'.format(len(wanted)))
        for movie in wanted:
            response = Manage.add_movie(movie, full_metadata=True)
            if response['response'] is True:
                yield json.dumps({'response': True, 'progress': [progress, length], 'movie': movie})
                progress += 1
                continue
            else:
                yield json.dumps({'response': False, 'movie': movie, 'progress': [progress, length], 'error': response['error']})
                progress += 1
                continue

        logging.info('Adding {} Wanted CouchPotato movies to library.'.format(len(finished)))
        for movie in finished:
            movie['predb'] = 'found'
            movie['status'] = 'Disabled'
            movie['origin'] = 'CouchPotato Import'

            response = Manage.add_movie(movie, full_metadata=True)
            if response['response'] is True:
                fake_results.append(searchresults.generate_simulacrum(movie))
                yield json.dumps({'response': True, 'progress': [progress, length], 'movie': movie})
                progress += 1
                success.append(movie)
                continue
            else:
                yield json.dumps({'response': False, 'movie': movie, 'progress': [progress, length], 'error': response['error']})
                progress += 1
                continue

        fake_results = searchresults.score(fake_results, imported=True)

        for i in success:
            for r in fake_results:
                if r['imdbid'] == i['imdbid']:
                    core.sql.update('MOVIES', 'finished_score', r['score'], 'imdbid', i['imdbid'])
                    break

        core.sql.write_search_results(fake_results)
    import_cp_movies._cp_config = {'response.stream': True, 'tools.gzip.on': False}

    @cherrypy.expose
    def manager_backlog_search(self, movies):
        ''' Bulk manager action for backlog search
        movies (list): dicts of movies, must contain keys imdbid and tmdbid

        Yields dict ajax-style response
        '''

        movies = json.loads(movies)

        logging.info('Performing bulk backlog search for {} movies.'.format(len(movies)))

        ids = [i['imdbid'] for i in movies]

        movies = [i for i in core.sql.get_user_movies() if i['imdbid'] in ids]

        for i, movie in enumerate(movies):
            logging.info('Performing backlog search for {} {}.'.format(movie['title'], movie['year']))

            if not searcher.search(movie):
                response = {'response': False, 'error': Errors.database_write, 'imdbid': movie['imdbid'], 'index': i + 1}
            else:
                response = {'response': True, 'index': i + 1}

            yield json.dumps(response)

    manager_backlog_search._cp_config = {'response.stream': True, 'tools.gzip.on': False}

    @cherrypy.expose
    def manager_update_metadata(self, movies):
        ''' Bulk manager action for metadata update
        movies (list): dicts of movies, must contain keys imdbid and tmdbid

        Yields dict ajax-style response
        '''

        movies = json.loads(movies)

        logging.info('Performing bulk metadata update for {} movies.'.format(len(movies)))

        for i, movie in enumerate(movies):
            r = Metadata.update(movie.get('imdbid'), movie.get('tmdbid'))

            if r['response'] is False:
                response = {'response': False, 'error': r['error'], 'imdbid': movie['imdbid'], 'index': i + 1}
            else:
                response = {'response': True, 'index': i + 1}

            yield json.dumps(response)

    manager_update_metadata._cp_config = {'response.stream': True, 'tools.gzip.on': False}

    @cherrypy.expose
    def manager_change_quality(self, movies, quality):
        ''' Bulk manager action to change movie quality profile
        movies (list): dicts of movies, must contain keys imdbid
        quality (str): quality to set movies to

        Yields dict ajax-style response
        '''

        movies = json.loads(movies)

        logging.info('Setting quality to {} for: {}'.format(quality, ', '.join(i['imdbid'] for i in movies)))

        for i, movie in enumerate(movies):
            if not core.sql.update('MOVIES', 'quality', quality, 'imdbid', movie['imdbid']):
                response = {'response': False, 'error': Errors.database_write, 'imdbid': movie['imdbid'], 'index': i + 1}
            else:
                response = {'response': True, 'index': i + 1}

            yield json.dumps(response)

    manager_change_quality._cp_config = {'response.stream': True, 'tools.gzip.on': False}

    @cherrypy.expose
    def manager_change_category(self, movies, category):
        ''' Bulk manager action to change movie category
        movies (list): dicts of movies, must contain keys imdbid
        category (str): category to set movies to

        Yields dict ajax-style response
        '''

        movies = json.loads(movies)

        logging.info('Setting category to {} for: {}'.format(category, ', '.join(i['imdbid'] for i in movies)))

        for i, movie in enumerate(movies):
            if not core.sql.update('MOVIES', 'category', category, 'imdbid', movie['imdbid']):
                response = {'response': False, 'error': Errors.database_write, 'imdbid': movie['imdbid'], 'index': i + 1}
            else:
                response = {'response': True, 'index': i + 1}

            yield json.dumps(response)

    manager_change_category._cp_config = {'response.stream': True, 'tools.gzip.on': False}

    @cherrypy.expose
    def manager_reset_movies(self, movies):
        ''' Bulk manager action to reset movies
        movies (list): dicts of movies, must contain key imdbid

        Removes all search results

        Updates database row with db_reset dict

        Yields dict ajax-style response
        '''

        movies = json.loads(movies)

        logging.info('Resetting status for {} movies.'.format(len(movies)))

        for i, movie in enumerate(movies):
            logging.debug('Resetting {}'.format(movie['imdbid']))
            imdbid = movie['imdbid']
            if not core.sql.purge_search_results(imdbid):
                yield json.dumps({'response': False, 'error': _('Unable to purge search results.'), 'imdbid': imdbid, 'index': i + 1})
                continue

            db_reset = {'quality': config.default_profile(),
                        'status': 'Waiting',
                        'finished_date': None,
                        'finished_score': None,
                        'backlog': 0,
                        'finished_file': None,
                        'predb': None,
                        'predb_backlog': None
                        }

            if not core.sql.update_multiple_values('MOVIES', db_reset, 'imdbid', imdbid):
                yield json.dumps({'response': False, 'error': Errors.database_write, 'imdbid': imdbid, 'index': i + 1})
                continue

            yield json.dumps({'response': True, 'index': i + 1})

    manager_reset_movies._cp_config = {'response.stream': True, 'tools.gzip.on': False}

    @cherrypy.expose
    def manager_remove_movies(self, movies):
        ''' Bulk action to remove movies
        movies (list): dicts of movies, must contain key imdbid

        Yields dict ajax-style response
        '''

        movies = json.loads(movies)

        logging.info('Removing {} movies from library.'.format(len(movies)))

        for i, movie in enumerate(movies):
            r = self.remove_movie(movie['imdbid'])

            if r['response'] is False:
                response = {'response': False, 'error': r['error'], 'imdbid': movie['imdbid'], 'index': i + 1}
            else:
                response = {'response': True, 'index': i + 1}

            yield(json.dumps(response))

    manager_remove_movies._cp_config = {'response.stream': True, 'tools.gzip.on': False}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def generate_stats(self, category=None):
        ''' Gets library stats for graphing page

        Returns dict of library stats
        '''
        return Manage.get_stats(category)

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def create_backup(self):
        ''' Creates backup zip file ./watcher.zip

        Returns dict ajax-style response
        '''

        logging.info('Creating backup of Watcher as {}'.format(os.path.join(core.PROG_PATH, 'watcher.zip')))

        try:
            backup.backup(require_confirm=False)
        except Exception as e:
            logging.error('Unable to create backup.', exc_info=True)
            return {'response': False, 'error': str(e)}

        return {'response': True, 'message': _('Backup created as {}').format(os.path.join(core.PROG_PATH, 'watcher.zip'))}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def restore_backup(self, fileUpload):
        logging.info('Restoring backup from uploaded zip.')
        n = datetime.datetime.today().microsecond

        tmp_zip = os.path.join(core.PROG_PATH, 'restore_{}.zip'.format(n))

        try:
            with open(tmp_zip, 'wb') as f:
                f.seek(0)
                f.write(fileUpload.file.read())

            logging.info('Restore zip temporarily stored as {}.'.format(tmp_zip))

            backup.restore(require_confirm=False, file=tmp_zip)

            logging.info('Removing temporary zip {}'.format(tmp_zip))
            os.unlink(tmp_zip)

        except Exception as e:
            logging.error('Unable to restore backup.', exc_info=True)
            return {'response': False}

        threading.Timer(3, core.restart).start()
        return {'response': True}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def manual_task_execute(self, name):
        ''' Calls task's now() function to execute task now
        name (str): name of scheduled task to run

        Response includes core.NOTIFICATIONS so the browser can display any
            notifications generated during the task.

        Returns dict ajax-style response
        '''

        try:
            logging.info('Manually executing task {}.'.format(name))
            task = core.scheduler_plugin.task_list[name]
            task.now()

            le = task.last_execution

            return {'response': True, 'message': _('Finished task {}.').format(name), 'last_execution': le, 'notifications': core.NOTIFICATIONS}
        except Exception as e:
            return {'response': False, 'error': str(e)}
