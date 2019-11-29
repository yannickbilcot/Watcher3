# Watcher

<p align="center"><a href="https://hub.docker.com/r/ellnic/watcher3"><img alt="Watcher3" src="https://github.com/ellnic/Watcher3/blob/master/static/images/logo-dark-bg.png"/></a>

Watcher is an automated movie NZB & Torrent searcher and snatcher. You can add a list of wanted movies and Watcher will automatically send the NZB or Torrent to your download client. Watcher also has basic post-processing capabilities such as renaming and moving.

<p align="center"><a href="https://gitter.im/barbequesauce-Watcher3/development"><img alt="Gitter" src="https://img.shields.io/gitter/room/barbequesauce/watcher3.svg"/></a>
<a href="https://kiwiirc.com/client/freenode.net/#watcher3"><img alt="IRC" src="https://img.shields.io/badge/Freenode-Online-Success.svg"/></a>
<a href="https://discord.gg/wrHPyre"><img alt="Discord" src="https://img.shields.io/discord/620536178881331200?color=Green&label=discord&style=flat"/></a>
<p align="center"><img alt="Codacy" src="https://api.codacy.com/project/badge/Grade/3392120a6afe40cc8dcfbb8b7e7b3713"/>
<a href="https://hub.docker.com/r/barbequesauce/watcher3"><img alt="Docker Pull Count" src="https://img.shields.io/docker/pulls/barbequesauce/watcher3.svg"/></a>
<a href="https://hub.docker.com/r/barbequesauce/watcher3"><img alt="Docker Build" src="https://img.shields.io/docker/cloud/automated/barbequesauce/watcher3.svg"/></a>
<a href="https://hub.docker.com/r/barbequesauce/watcher3"><img alt="Docker Build" src="https://img.shields.io/docker/cloud/build/barbequesauce/watcher3.svg"/></a>
    

Watcher is a work in progress and plans to add more features in the future, but we will always prioritize speed and stability over features. 

#### Note that as the owner of the original project seems to be inactive, this repository has been established in an attempt to move the project forward, taking in both pending PRs from the original project and PRs applied to other forks.

Watcher may change frequently, so we strongly suggest that you come by and say hello on Freenode (#watcher3) or via Gitter.

You may also wish to subscribe to the subreddit /r/watcher, but at this time there is little activity there. It was for the original project, and most the current developement talk is happening via IRC and Gitter. We now also have [Discord](https://discord.gg/wrHPyre)

Refer to the wiki for more information about post-processing, start scripts, and other features. https://github.com/barbequesauce/Watcher3/wiki

You may also wish to checkout ellnic's repo, which may (or may not) have certain downstream changes before they are pulled. https://github.com/ellnic/Watcher3 Please do not submit PR's there, submit them to barbequesauce.

## Recent Highlights (docker)

Docker now checks for 'standard' config and db names of /config/config.cfg and /config/watcher.sqlite and renames and organises them to /config/watcher.cfg and /config/db/database.sqlite. Originals are placed in /configs/backups. This is useful if you previously ran using python and have literally dumped your config files from the userdata folder into your docker config folder.

## Recent Highlights (Code) - Needs updating

Recent highlights include some bugfixes and enhancements, a redesigned logo and colour scheme and a revised docker container. You can now select items per page in the library and the vanishing library bug is fixed. The docker container now runs with the newly added --posters flag so that the poster meta is stored in /config and is not lost on container update.
 
## Installation

We have several options to choose from:

If you are not using Docker, Watcher requires Python 3. It is also recommended that you install GIT. This will allow you to update much more easily.

### Installation using GIT

Obtaining the files:

    git clone https://github.com/barbequesauce/Watcher3.git

Start Watcher using:

    python3 /watcher/watcher.py

Open a browser and navigate to localhost:9090

### Installation by downloading the ZIP:

If you do not wish to use Git, follow these steps.

1. Open your browser and go to https://github.com/barbequesauce/Watcher3
2. Click on the green Clone or download button and click Download ZIP
3. Once done downloading, extract the ZIP to the location in which you want Watcher installed
4. Open a terminal and cd to the Watcher directory.
5. Start Watcher using:

```python3 watcher/watcher.py```

6. Open a browser and navigate to localhost:9090


#### Usage arguments (not for docker)

You can add the following arguments to Watcher when running the Python script. Always use the absolute path when supplying a directory or file argument.

Run the server as a daemon (*nix only)

    $ watcher.py --daemon

Run the server as a background process (Windows only)

    $ python watcher.py --daemon

Change address to bind to.

    $ watcher.py --address 0.0.0.0

Change port to host on.

    $ watcher.py --port 9090

Open browser on launch.

    $ watcher.py --browser

Change path to config file. If not present, one will be created.

     watcher.py --conf /path/to/config.cfg

Specify custom posters dir (where watcher saves posters to).

     watcher.py --posters /path/to/posters/dir

Change path of log directory.

    $ watcher.py --log /path/to/logs/

Change path to database. If not present, a new, empty database will be created.

    $ watcher.py --db /path/to/database.sqlite

Change path to plugins directory.

    $ watcher.py --plugins /path/to/plugins/

Create PID file.

    $ watcher.py --pid /path/to/pid/file.pid


#### Backup / Restore (non-docker)

Watcher includes a simple script for backing up and restoring your database and config.

The backup function will create a new watcher.zip in the Watcher folder.

To restore, place watcher.zip in the Watcher folder of your target installation and run the restore command.
Usage

Back up Watcher.

    $ backup.py -b

Restore Watcher.

    $ backup.py -r

## Docker:

We now have an updated Docker container using an alpine 3.8 base, with a few extra things like nano and vim for on the fly edits without stopping the container.

1. Pull the container:

``` docker pull barbequesauce/watcher3```

2. Example run command:

```
    docker run -d \
  --name=watcher3 \
  -v /path/to/config/:/config \
  -v /path/to/downloads/:/downloads \
  -v /path/to/movies/:/movies \
  -e UMASK_SET=022 \
  -e APP_GID=1000 -e APP_UID=1000 \
  -p 9090:9090 \
  barbequesauce/watcher3
``` 


If you wish to exec into the container to have a look around, use:

``` docker exec -it watcher3 /bin/bash```

You may also wish to checkout ellnic's repo: https://github.com/ellnic/Watcher3
