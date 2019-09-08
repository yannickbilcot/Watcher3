## Watcher

<p align="center"><a href="https://hub.docker.com/r/ellnic/watcher3"><img alt="Watcher3" src="https://github.com/ellnic/Watcher3/blob/master/static/images/logo-dark-bg.png"/></a>

Watcher is an automated movie NZB & Torrent searcher and snatcher. You can add a list of wanted movies and Watcher will automatically send the NZB or Torrent to your download client. Watcher also has basic post-processing capabilities such as renaming and moving.

Watcher is a work in progress and plans to add more features in the future, but we will always prioritize speed and stability over features. **Note that as the owner of the original project seems to be inactive, barbequesauce/watcher3 has been established in an attempt to move the project forward, taking in both pending PRs from the original project and PRs applied to other forks. **    

Watcher may change frequently, so we strongly suggest you join us on IRC (#watcher3 on Freenode) or Gitter.

<a href="https://gitter.im/barbequesauce-Watcher3/development"><img alt="Gitter" src="https://img.shields.io/gitter/room/barbequesauce/watcher3.svg"/></a>
<a href="https://kiwiirc.com/client/freenode.net/#watcher3"><img alt="IRC" src="https://img.shields.io/badge/Freenode-Online-Success.svg"/></a>
</p>

Refer to the [wiki](https://github.com/barbequesauce/Watcher3/wiki) for more information about post-processing, start scripts, and other features.

## Installation

**Docker:**

<p align="center"><a href="https://hub.docker.com/r/ellnic/watcher3"><img alt="Docker Pull Count" src="https://img.shields.io/docker/pulls/ellnic/watcher3.svg"/></a>
<a href="https://hub.docker.com/r/ellnic/watcher3"><img alt="Docker Build" src="https://img.shields.io/docker/cloud/automated/ellnic/watcher3.svg"/></a>
<a href="https://hub.docker.com/r/ellnic/watcher3"><img alt="Docker Build" src="https://img.shields.io/docker/cloud/build/ellnic/watcher3.svg"/></a>

* docker run -d \ --name=watcher3
*   -v /path/to/config/:/config
*   -v /path/to/downloads/:/downloads
*   -v /path/to/movies/:/movies
*   -e PGID=1000 -e PUID=1000
*   -p 9090:9090
*   ellnic/watcher3


You can also git clone or download a zip and run using python, but please see https://github.com/barbequesauce/Watcher3 for that.

