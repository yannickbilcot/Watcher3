import core
from core.movieinfo import TheMovieDatabase
from core.library import Metadata, Manage
from core import searcher
import cherrypy
import threading
import os
import json
import logging

logging = logging.getLogger(__name__)

api_version = 2.6

''' API

All methods output a json object:
{'response': true}

A 'true' response indicates that the request was valid and returns useful data.
A 'false' response indicates that the request was invalid or failed. This will
    always include an 'error' key that describes the reason for the failure.

All successul method calls then append additional key:value pairs to the output json.


# METHODS

mode=liststatus:
    Description:
        Effectively a database dump of the MOVIES table
        Additional params (besides mode and apikey) will be applied as filters to the movie database
            For example, passing &imdbid=tt1234557 will only return movies with the imdbid tt1234567.
            Multiple filters can be applied using the columns described in core.sql

    Example:
        Request:
            ?apikey=123456789&mode=liststatus
        Response:
            {'movies': [{'key': 'value', 'key2', 'value2'}, {'key': 'value', 'key2', 'value2'}]}

        Request:
            ?apikey=123456789&mode=liststatus&origin=Search
        Response:
            {'movies': [{'key': 'value', 'origin', 'Search'}, {'key': 'value', 'origin', 'Search'}]}

mode=addmovie
    Description:
        Adds a movie to the user's library
        Accepts imdb and tmdb id #s
        Imdb id must include 'tt'
        Will add using Default quality profile unless specified otherwise
        Will add using Default category unless specified otherwise

    Example:
        Request:
            ?apikey=123456789&mode=addmovie&imdbid=tt1234567&quality=Default
        Response:
            {'message': 'MOVIE TITLE YEAR added to wanted list.'}

        Request:
            ?apikey=123456789&mode=addmovie&tmdbid=1234567
        Response:
            {'message': 'MOVIE TITLE YEAR added to wanted list.'}

mode=removemovie
    Description:
        Removes movie from user's library
        Does not remove movie files, only removes entry from Watcher

    Example:
        Request:
            ?apikey=123456789&mode=addmovie&imdbid=tt1234567
        Response:
            {'removed': 'tt1234567'}

mode=getconfig
    Description:
        Returns a dump of the user's config

    Example:
        Request:
            ?apikey=123456789&mode=getconfig
        Response:
            {'config': {'Search': {'etc': 'etc'}}}

mode=version
    Description:
        Returns API version and current git hash of Watcher

    Example:
        Request:
            ?apikey=123456789&mode=version
        Response:
            {'version': '4fcdda1df1a4ff327c3219311578d703a288e598', 'api_version': 1.0}

mode=poster
    Description:
        Returns desired poster image as data stream with 'image/jpeg' as Content-Type header
        If an error occurs, returns JSON

    Example:
        Request:
            ?apikey=123456789&mode=poster&imdbid=tt1234567
        Response:
            <image data>

        Request:
            ?apikey=123456789&mode=poster&imdbid=tt0000000
        Response:
            {'response': false, 'error': 'file not found: tt0000000.jpg'}
            
mode=search_movie
    Description:
        Search a movie by title, in defined indexers
        Accept q param

    Example:
        Request:
            ?apikey=123456789&mode=search_movie&q=Movie%20Title
        Response:
            {'response': True, 'results', [{'tmdbid': 'xxxx', 'title': 'Movie Title', 'year': 2019, 'plot': 'Movie plot']}
            
mode=search_results
    Description:
        Return search results for movie
        Accept imdbid param

    Example:
        Request:
            ?apikey=123456789&mode=search_results&imdbid=tt1234567
        Response:
            {'response': True, 'results', [{'status': 'Available', 'title': 'Movie Title', 'guid': 'xxx', 'indexer': 'Indexer Name', ...]}

        Request:
            ?apikey=123456789&mode=search_results&imdbid=tt0000000
        Response:
            {'response': false, 'error': 'no movie for tt0000000'}
            
mode=update_metadata
    Description:
        Update metadata for movie.
        Requires imdbid, tmdbid optional

    Example:
        Request:
            ?apikey=123456789&mode=update_metadata&imdbid=tt1234567
        Response:
            {'response': True, 'message': 'Metadata updated'}

        Request:
            ?apikey=123456789&mode=update_metadata&imdbid=tt0000000
        Response:
            {'response': false, 'error': 'Empty response from TMDB'}
            
mode=update_movie_options
    Description:
        Update options for movie.
        Requires imdbid
        Category, quality, title, language and filters are optional

    Example:
        Request:
            ?apikey=123456789&mode=update_movie_options&imdbid=tt1234567&quality=Default
        Response:
            {'response': True, 'message': 'Movie options updated'}

        Request:
            ?apikey=123456789&mode=update_metadata&imdbid=tt0000000
        Response:
            {'response': false, 'error': 'Error saving movie options'}

mode=server_shutdown
    Description:
        Gracefully terminate Watcher server and child processes.
        Shutdown may be instant or delayed to wait for threaded tasks to finish.
        Returns confirmation that request was received.

    Example:
        ?apikey=123456789&mode=shutdown

mode=server_restart
    Description:
        Gracefully restart Watcher server.
        Shutdown may be instant or delayed to wait for threaded tasks to finish.
        Returns confirmation that request was received.

    Example:
        ?apikey=123456789&mode=restart

mode=task
    Description:
        Starts task manually.

    Example:
        ?apikey=123456789&mode=task&task=PostProcessing%20Scan

mode=update_check
    Description:
        Starts update check task.

    Example:
        ?apikey=123456789&mode=update_check


# API Version
Methods added to the api or minor adjustments to existing methods will increase the version by X.1
Version 1.11 is greater than 1.9
It is safe to assume that these version increases will not break any api interactions

Changes to the output responses will increase the version to the next whole number 2.0
Major version changes can be expected to break api interactions

# VERSION HISTORY
1.0     First commit
1.1     Consistency in responses

2.0     Change to semantically correct json. Responses are now bools instead of str 'true'/'false'
2.1     Adjust addmovie() to pass origin argument. Adjust addmovie() to search tmdb for itself rather than in core.ajax()
2.2     Update documentation for all methods
2.3     Update dispatch method. Allow arbitrary filters in liststatus.
2.4     Allow category argument in addmovie method.
2.5     Add search_movie, task, update_check, update_metadata and update_movie_options methods.
2.6     Add search_results method.
'''


def api_json_out(func):
    ''' Decorator to return json from api request
    Use this rather than cherrypy.tools.json_out. The cherrypy tool changes the
        request handler which only applies to the method being called, in this
        case default(). Using this allows dispatched methods to return json
        while still allowing methods to return other content types (ie poster())
    '''
    def decor(*args, **kwargs):
        cherrypy.response.headers['Content-Type'] = 'application/json'
        return json.dumps(func(*args, **kwargs)).encode('utf-8')
    return decor


class API(object):

    @cherrypy.expose()
    def default(self, **params):
        ''' Get handler for API calls

        params: kwargs must inlcude {'apikey': $, 'mode': $}

        Checks api key matches and other required keys are present based on
            mode. Then dispatches to correct method to handle request.
        '''

        logging.info('API request from {}'.format(cherrypy.request.headers['Remote-Addr']))

        serverkey = core.CONFIG['Server']['apikey']

        if 'apikey' not in params:
            logging.warning('API request failed, no key supplied.')
            return json.dumps({'response': False, 'error': 'no api key supplied'})

        if serverkey != params['apikey']:
            logging.warning('Invalid API key in request: {}'.format(params['apikey']))
            return json.dumps({'response': False, 'error': 'incorrect api key'})
        params.pop('apikey')

        # find what we are going to do
        if 'mode' not in params:
            return json.dumps({'response': False, 'error': 'no api mode specified'})

        mode = params.pop('mode')
        if not hasattr(self, mode):
            return {'response': False, 'error': 'unknown method call: {}'.format(mode)}
        else:
            return getattr(self, mode)(params)

    @api_json_out
    def liststatus(self, filters):
        ''' Returns status of user's movies
        filters (dict): filters to apply to database request

        Returns all movies where col:val pairs match all key:val pairs in filters

        Returns list of movie details from MOVIES table.

        Returns dict
        '''

        logging.info('API request movie list -- filters: {}'.format(filters))
        movies = core.sql.get_user_movies()
        if not movies:
            return {'response': True, 'movies': []}

        for i in filters.keys():
            if i not in core.sql.MOVIES.columns:
                return {'response': False, 'error': 'Invalid filter key: {}'.format(i)}

        return {'response': True, 'movies': [i for i in movies if all(i[k] == v for k, v in filters.items())]}

    @api_json_out
    def addmovie(self, params):
        ''' Add movie with default quality settings
        params (dict): params passed in request url

        params must contain either 'imdbid' or 'tmdbid' key and value

        Returns dict {'status': 'success', 'message': 'X added to wanted list.'}
        '''

        if not (params.get('imdbid') or params.get('tmdbid')):
            return {'response': False, 'error': 'no movie id supplied'}
        elif (params.get('imdbid') and params.get('tmdbid')):
            return {'response': False, 'error': 'multiple movie ids supplied'}

        origin = cherrypy.request.headers.get('User-Agent', 'API')
        origin = 'API' if origin.startswith('Mozilla/') else origin

        quality = params.get('quality') or core.config.default_profile()
        category = params.get('category', 'Default')

        if params.get('imdbid'):
            imdbid = params['imdbid']
            logging.info('API request add movie imdb {}'.format(imdbid))
            movie = TheMovieDatabase._search_imdbid(imdbid)
            if not movie:
                return {'response': False, 'error': 'Cannot find {} on TMDB'.format(imdbid)}
            else:
                movie = movie[0]
                movie['imdbid'] = imdbid
        elif params.get('tmdbid'):
            tmdbid = params['tmdbid']
            logging.info('API request add movie tmdb {}'.format(tmdbid))
            movie = TheMovieDatabase._search_tmdbid(tmdbid)

            if not movie:
                return {'response': False, 'error': 'Cannot find {} on TMDB'.format(tmdbid)}
            else:
                movie = movie[0]

        movie['quality'] = quality
        movie['category'] = category
        movie['status'] = 'Waiting'
        movie['origin'] = origin

        response = Manage.add_movie(movie, full_metadata=True)
        if response['response'] and core.CONFIG['Search']['searchafteradd'] and movie['year'] != 'N/A':
            threading.Thread(target=searcher._t_search_grab, args=(movie,)).start()

        return response

    @api_json_out
    def removemovie(self, params):
        ''' Remove movie from library, if delete_file is true, finished_file will be deleted too
        params (dict): params passed in request url, must include imdbid

        Returns dict
        '''
        imdbid = params.get('imdbid')
        if not imdbid:
            return {'response': False, 'error': 'no imdbid supplied'}

        logging.info('API request remove movie {}'.format(imdbid))

        if params['delete_file']:
            f = core.sql.get_movie_details('imdbid', imdbid).get('finished_file')
            if f:
                try:
                    logging.debug('Finished file for {} is {}'.format(imdbid, f))
                    os.unlink(f)
                    # clear finished_* columns, in case remove_movie fails
                    core.sql.update_multiple_values('MOVIES', {'finished_date': None, 'finished_score': None,
                                                               'finished_file': None}, 'imdbid', imdbid)
                except Exception as e:
                    error = 'Unable to delete file {}'.format(f)
                    logging.error(error, exc_info=True)
                    return {'response': False, 'error': error}

        return Manage.remove_movie(imdbid)

    def poster(self, params):
        ''' Return poster
        params (dict): params passed in request url, must include imdbid

        Returns image as binary datastream with image/jpeg content type header
        '''

        cherrypy.response.headers['Content-Type'] = "image/jpeg"
        err = None
        try:
            with open(os.path.abspath(os.path.join(core.POSTER_DIR, '{}.jpg'.format(params['imdbid']))), 'rb') as f:
                img = f.read()
            return img
        except KeyError as e:
            err = {'response': False, 'error': 'no imdbid supplied'}
        except FileNotFoundError as e:
            err = {'response': False, 'error': 'file not found: {}.jpg'.format(params['imdbid'])}
        except Exception as e:
            err = {'response': False, 'error': str(e)}
        finally:
            if err:
                cherrypy.response.headers['Content-Type'] = 'application/json'
                return json.dumps(err).encode('utf-8')

    @api_json_out
    def update_metadata(self, params):
        ''' Re-downloads metadata for imdbid
        params(dict): params passed in request url, must include imdbid, may include tmdbid

        If tmdbid is None, looks in database for tmdbid using imdbid.
        If that fails, looks on tmdb api for imdbid
        If that fails returns error message

        Returns dict ajax-style response
        '''
        if not params.get('imdbid'):
            return {'response': False, 'error': 'no imdbid supplied'}

        r = Metadata.update(params['imdbid'], params.get('tmdbid'))

        if r['response'] is True:
            return {'response': True, 'message': 'Metadata updated'}
        else:
            return r

    @api_json_out
    def update_movie_options(self, params):
        ''' Re-downloads metadata for imdbid
        params(dict): params passed in request url, must include imdbid, may include these params:

        quality (str): name of new quality
        category (str): name of new category
        status (str): management state ('automatic', 'disabled')
        language (str): name of language to download movie
        title (str): movie title
        filters (str): JSON.stringified dict of filter words

        Returns dict ajax-style response
        '''
        imdbid = params.get('imdbid')
        if not imdbid:
            return {'response': False, 'error': 'no imdbid supplied'}

        movie = core.sql.get_movie_details('imdbid', imdbid)
        if not movie:
            return {'response': False, 'error': 'no movie for {}'.format(imdbid)}

        quality = params.get('quality', movie['quality'])
        category = params.get('category', movie['category'])
        language = params.get('language', movie['download_language'])
        title = params.get('title', movie['title'])
        filters = params.get('filters', movie['filters'])
        if Manage.update_movie_options(imdbid, quality, category, language, title, filters):
            return {'response': True, 'message': 'Movie options updated'}
        else:
            return {'response': False, 'message': 'Unable to write to database'}


    @api_json_out
    def search_results(self, params):
        ''' Gets search results for movie
        params(dict): params passed in request url, must include imdbid

        Returns dict ajax-style response
        '''
        imdbid = params.get('imdbid')
        if not imdbid:
            return {'response': False, 'error': 'no imdbid supplied'}

        movie = core.sql.get_movie_details('imdbid', imdbid)
        if not movie:
            return {'response': False, 'error': 'no movie for {}'.format(imdbid)}

        results = Manage.search_results(imdbid, quality=movie.get('quality'))
        return {'response': True, 'results': results}

    @api_json_out
    def search_movie(self, params):
        ''' Search indexers for specific movie
        params(dict): params passed in request url, must include q

        Returns dict ajax-style response
        '''
        if not params.get('q'):
            return {'response': False, 'error': 'no query supplied'}

        results = TheMovieDatabase.search(params['q'])
        if results:
            Manage.add_status_to_search_movies(results)
        else:
            return {'response': False, 'error': 'No Results found for {}'.format(params['q'])}

        return {'response': True, 'results': results}

    @api_json_out
    def version(self, *args):
        ''' Simple endpoint to return commit hash
        Mostly used to test connectivity without modifying the server.

        Returns dict
        '''
        return {'response': True, 'version': core.CURRENT_HASH, 'api_version': api_version}

    @api_json_out
    def getconfig(self, *args):
        ''' Returns config contents as JSON object
        '''
        return {'response': True, 'config': core.CONFIG}

    @api_json_out
    def task(self, params):
        ''' Returns config contents as JSON object
        '''
        if not params.get('task'):
            return {'response': False, 'error': 'no task supplied'}

        task = core.scheduler_plugin.task_list.get(params['task'])
        if task:
            task.now()
            return {'response': True}
        else:
            return {'response': False, 'error': 'No task "{}"'.format(params['task'])}

    @api_json_out
    def update_check(self, *args):
        ''' Returns config contents as JSON object
        '''
        return core.updater.update_check()

    @api_json_out
    def server_shutdown(self, *args):
        threading.Timer(1, core.shutdown).start()
        return {'response': True}

    @api_json_out
    def server_restart(self, *args):
        threading.Timer(1, core.restart).start()
        return {'response': True}
